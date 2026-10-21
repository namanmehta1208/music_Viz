"""GPU side of the visualizer: turns band heights into a frame.

Each frame runs these passes, every one a full-screen rectangle drawn with a
different fragment shader:

    1. streaks    band heights -> sharp glowing streaks (full resolution)
    2. bloom      shrink + blur the streaks at 1/2, 1/4 and 1/8 size
    3. composite  streaks + blurs -> RGB split, vignette, grain -> the screen

Knows nothing about audio: visualizer.py hands it numbers.
"""

import re
from pathlib import Path

import moderngl
import numpy as np

from ..base import FULLSCREEN_VERT

SHADER_DIR = Path(__file__).parent / "shaders"

# How far each blur reaches, per bloom level. Wider horizontally, because
# the reference look glows sideways more than up and down.
BLOOM_SPREAD = (2.0, 1.0)


def load_shader(name):
    return (SHADER_DIR / name).read_text()


class StreakRenderer:
    def __init__(self, ctx, num_bands, aberration=8.0, exposure=1.6):
        self.ctx = ctx
        self.num_bands = num_bands
        self.aberration = aberration
        self.exposure = exposure

        vert = FULLSCREEN_VERT.read_text()
        # The shader needs the array size at compile time, so patch it in.
        streaks_src = re.sub(
            r"#define NUM_BANDS \d+",
            f"#define NUM_BANDS {num_bands}",
            load_shader("streaks.frag"),
        )
        self.streaks_prog = ctx.program(vertex_shader=vert, fragment_shader=streaks_src)
        self.blur_prog = ctx.program(vertex_shader=vert, fragment_shader=load_shader("blur.frag"))
        self.composite_prog = ctx.program(
            vertex_shader=vert, fragment_shader=load_shader("composite.frag")
        )

        # One rectangle, reused by every pass: 4 corners of (x, y, u, v),
        # drawn as a triangle strip.
        quad = np.array(
            [-1, -1, 0, 0,
              1, -1, 1, 0,
             -1,  1, 0, 1,
              1,  1, 1, 1],
            dtype="f4",
        )
        self.quad_vbo = ctx.buffer(quad.tobytes())
        self.vaos = {
            prog: ctx.vertex_array(prog, [(self.quad_vbo, "2f 2f", "in_position", "in_uv")])
            for prog in (self.streaks_prog, self.blur_prog, self.composite_prog)
        }

        self._targets = []   # every texture/framebuffer we own, for cleanup
        self.size = None
        self.set_theme((1.0, 0.55, 0.12), (1.0, 0.74, 0.28), (1.0, 0.9, 0.62), (0.9, 0.6, 0.15))

    def set_theme(self, low, mid, high, accent):
        """Bar colors from centre (bass) to sides (treble), plus a light-leak accent."""
        self.palette = np.array([low, mid, high], dtype="f4")
        self.accent = tuple(accent)

    # ------------------------------------------------------------------ setup

    def _make_target(self, size):
        """A texture to draw into, plus the framebuffer that points at it."""
        # 'f2' = 16-bit floats, so brightness can go above 1.0 (HDR).
        tex = self.ctx.texture(size, 3, dtype="f2")
        tex.repeat_x = False   # blur near the edges should not wrap around
        tex.repeat_y = False
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        fbo = self.ctx.framebuffer(color_attachments=[tex])
        self._targets += [tex, fbo]
        return tex, fbo

    def resize(self, width, height):
        """(Re)create the offscreen textures for a new window size."""
        if (width, height) == self.size or width == 0 or height == 0:
            return
        for obj in self._targets:
            obj.release()
        self._targets = []
        self.size = (width, height)

        self.scene = self._make_target((width, height))
        # Each bloom level has two textures so we can blur back and forth
        # (horizontal pass A -> B, vertical pass B -> A).
        self.bloom_levels = []
        for divisor in (2, 4, 8):
            level_size = (max(1, width // divisor), max(1, height // divisor))
            self.bloom_levels.append(
                (self._make_target(level_size), self._make_target(level_size), level_size)
            )

    # ----------------------------------------------------------------- render

    def _blur_pass(self, src_tex, dst_fbo, direction):
        dst_fbo.use()
        src_tex.use(location=0)
        self.blur_prog["src"].value = 0
        self.blur_prog["direction"].value = direction
        self.vaos[self.blur_prog].render(moderngl.TRIANGLE_STRIP)

    def render(self, levels, flashes, kick, time, target):
        """Draw one frame into `target`.

        levels:  smoothed loudness per band, 0..1 (num_bands floats)
        flashes: flash brightness per band, 0..1 (num_bands floats)
        kick:    current bass-hit strength, 0..1 (makes the whole frame punch)
        """
        width, height = self.size
        flashes = np.asarray(flashes, dtype="f4")
        self.ctx.disable(moderngl.BLEND | moderngl.DEPTH_TEST)

        # 1. Bars
        scene_tex, scene_fbo = self.scene
        scene_fbo.use()
        self.streaks_prog["levels"].write(np.asarray(levels, dtype="f4").tobytes())
        self.streaks_prog["flashes"].write(flashes.tobytes())
        self.streaks_prog["palette"].write(self.palette.tobytes())
        self.streaks_prog["resolution"].value = (width, height)
        self.vaos[self.streaks_prog].render(moderngl.TRIANGLE_STRIP)

        # 2. Bloom: each level starts from a shrunken copy of the previous one,
        # so the blur gets wider at every level for almost no extra cost.
        source = scene_tex
        for (a_tex, a_fbo), (b_tex, b_fbo), (lw, lh) in self.bloom_levels:
            self._blur_pass(source, a_fbo, (0.0, 0.0))                               # shrink
            self._blur_pass(a_tex, b_fbo, (BLOOM_SPREAD[0] / lw, 0.0))               # blur x
            self._blur_pass(b_tex, a_fbo, (0.0, BLOOM_SPREAD[1] / lh))               # blur y
            source = a_tex

        # 3. Composite onto the real target (the window).
        # Set the drawing area explicitly: the window's framebuffer can keep a
        # stale size from earlier, which would leave parts of the window
        # undrawn (showing leftover garbage pixels).
        target.use()
        self.ctx.viewport = (0, 0, width, height)
        scene_tex.use(location=0)
        for i, ((a_tex, _), _, _) in enumerate(self.bloom_levels, start=1):
            a_tex.use(location=i)
        prog = self.composite_prog
        prog["scene"].value = 0
        prog["bloom1"].value = 1
        prog["bloom2"].value = 2
        prog["bloom3"].value = 3
        prog["time"].value = time
        prog["aberration"].value = self.aberration
        prog["exposure"].value = self.exposure
        prog["energy"].value = float(flashes.mean())
        prog["kick"].value = float(kick)
        prog["accent"].value = self.accent
        self.vaos[prog].render(moderngl.TRIANGLE_STRIP)
