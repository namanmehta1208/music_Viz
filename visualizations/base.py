"""What every visualization shares: the audio data it gets each frame, color
themes that cross-fade and cycle, and the theme keys.

A visualization only draws. visualizer.py owns the window, the audio and the
analysis, and hands each frame's numbers to whichever visualization is active.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import moderngl
import numpy as np

SHADER_DIR = Path(__file__).parent

# Every pass in every visualization draws one full-screen rectangle.
FULLSCREEN_VERT = SHADER_DIR / "fullscreen.vert"


def load_fragment(path, num_bands=None):
    """Read a fragment shader, paste common.glsl in where it says
    #include "common.glsl", and set its NUM_BANDS (array sizes have to be
    known when the shader compiles)."""
    source = Path(path).read_text()
    source = source.replace(
        '#include "common.glsl"', (SHADER_DIR / "common.glsl").read_text()
    )
    if num_bands is not None:
        source = re.sub(
            r"#define NUM_BANDS \d+", f"#define NUM_BANDS {num_bands}", source
        )
    return source


class FullscreenPass:
    """A fragment shader drawn over the whole target. Set its uniforms
    through .prog, then call render()."""

    def __init__(self, ctx, fragment_shader):
        self.ctx = ctx
        self.prog = ctx.program(
            vertex_shader=FULLSCREEN_VERT.read_text(), fragment_shader=fragment_shader
        )
        # One rectangle: 4 corners of (x, y, u, v), drawn as a triangle strip.
        quad = np.array(
            [-1, -1, 0, 0, 1, -1, 1, 0, -1, 1, 0, 1, 1, 1, 1, 1], dtype="f4"
        )
        self.vbo = ctx.buffer(quad.tobytes())
        # A shader that never reads uv has in_uv optimized away; skip it then.
        if self.prog.get("in_uv", None) is not None:
            layout = (self.vbo, "2f 2f", "in_position", "in_uv")
        else:
            layout = (self.vbo, "2f 8x", "in_position")
        self.vao = ctx.vertex_array(self.prog, [layout])

    def render(self, target, size):
        target.use()
        self.ctx.viewport = (0, 0, *size)
        self.vao.render(moderngl.TRIANGLE_STRIP)


def follow(current, target, speed, frames):
    """Move part of the way toward target. speed is the fraction per frame at
    60 fps; frames (dt * 60) keeps it the same at any frame rate."""
    return current + (target - current) * (1.0 - (1.0 - speed) ** frames)


class SlowAudio:
    """The music, heavily smoothed, for the calm visualizations: nothing in
    here ever jumps, so nothing on screen flashes.

    levels   per band, follows over ~0.5 s
    energy   overall loudness; bass / mid / treble: each third of the bands
    swell    rises over ~0.2 s after a bass hit, settles over ~1.5 s
    flow     a clock that runs faster when the music is louder; use it
             instead of time for motion, so loud music moves things faster
    """

    LEVEL_SPEED = 0.03
    ENERGY_SPEED = 0.015
    SWELL_ATTACK = 0.08
    SWELL_RELEASE = 0.012
    FLOW_MIN = 0.4  # flow speed in silence...
    FLOW_GAIN = 1.2  # ...plus this much at full loudness

    def __init__(self, num_bands):
        self.num_bands = num_bands
        self.levels = np.zeros(num_bands, dtype=np.float32)
        self.energy = self.bass = self.mid = self.treble = 0.0
        self.swell = 0.0
        self.flow = 0.0

    def update(self, frame):
        frames = frame.dt * 60.0
        heights = frame.heights
        third = self.num_bands // 3
        self.levels = follow(self.levels, heights, self.LEVEL_SPEED, frames)
        speed = self.ENERGY_SPEED
        self.energy = follow(self.energy, float(heights.mean()), speed, frames)
        self.bass = follow(self.bass, float(heights[:third].mean()), speed, frames)
        self.mid = follow(
            self.mid, float(heights[third : 2 * third].mean()), speed, frames
        )
        self.treble = follow(
            self.treble, float(heights[2 * third :].mean()), speed, frames
        )
        swell_speed = self.SWELL_ATTACK if frame.kick > self.swell else self.SWELL_RELEASE
        self.swell = follow(self.swell, frame.kick, swell_speed, frames)
        self.flow += frame.dt * (self.FLOW_MIN + self.FLOW_GAIN * self.energy)


@dataclass
class Frame:
    """One frame of analysed audio, the same for every visualization."""

    heights: np.ndarray  # smoothed loudness per band, 0..1 (bass first)
    flashes: np.ndarray  # onset flash per band, 0..1 (0 = off)
    kick: float  # bass hit strength right now, 0..1
    time: float  # seconds since start
    dt: float  # seconds since the last frame (clamped)


class ThemeCycler:
    """Picks a theme, cross-fades to it, and optionally cycles on its own.

    themes: {name: [color, color, ...]}, every theme with the same number of
    0..1 RGB colors. After `seconds` the next strong kick switches to the next
    theme, so the change lands on a beat. If no kick comes within
    `kick_wait_seconds` more, it switches anyway (0 = don't wait for a kick).
    """

    def __init__(self, themes, seconds, fade_seconds, kick_wait_seconds=0.0):
        self.themes = themes
        self.names = list(themes)
        self.seconds = seconds
        self.fade_seconds = fade_seconds
        self.kick_wait_seconds = kick_wait_seconds
        self.auto = True
        self.colors = np.array(themes[self.names[0]], dtype=np.float32)
        self.select(0)

    def select(self, index):
        """Start a cross-fade from the current colors to theme `index`."""
        self.index = index % len(self.names)
        name = self.names[self.index]
        self.fade_from = self.colors.copy()
        self.fade_to = np.array(self.themes[name], dtype=np.float32)
        self.fade_progress = 0.0
        self.age = 0.0  # seconds since this theme was chosen
        print(f"Theme: {name}")

    def toggle_auto(self):
        self.auto = not self.auto
        self.age = 0.0
        print(f"Auto theme cycling: {'on' if self.auto else 'off'}")

    def update(self, dt, kick):
        """Advance the cross-fade and the automatic cycling; returns the colors."""
        self.age += dt
        if self.auto and self.age >= self.seconds:
            waited_long_enough = self.age >= self.seconds + self.kick_wait_seconds
            if kick > 0.5 or waited_long_enough:
                self.select(self.index + 1)

        if self.fade_progress < 1.0:
            self.fade_progress = min(1.0, self.fade_progress + dt / self.fade_seconds)
            # smoothstep: starts and ends gently instead of at constant speed
            p = self.fade_progress
            t = p * p * (3.0 - 2.0 * p)
            self.colors = self.fade_from + (self.fade_to - self.fade_from) * t
        return self.colors


class Visualization:
    """Base class. Subclasses set the class attributes and implement render()."""

    name = ""
    description = ""  # one line, shown in the launcher
    themes = {}
    theme_seconds = 20.0
    fade_seconds = 2.0
    kick_wait_seconds = 0.0

    def __init__(self, ctx, num_bands):
        self.ctx = ctx
        self.num_bands = num_bands
        self.theme = ThemeCycler(
            self.themes, self.theme_seconds, self.fade_seconds, self.kick_wait_seconds
        )

    def resize(self, width, height):
        """Window size in real pixels changed (also called when activated)."""

    def render(self, frame, target):
        """Draw one frame into the framebuffer `target`."""
        raise NotImplementedError

    def on_key(self, key, keys):
        """Theme keys: T next, A auto cycling, 1-9 and 0 pick one directly."""
        if key == keys.T:
            self.theme.select(self.theme.index + 1)
        if key == keys.A:
            self.theme.toggle_auto()
        number_keys = [
            keys.NUMBER_1,
            keys.NUMBER_2,
            keys.NUMBER_3,
            keys.NUMBER_4,
            keys.NUMBER_5,
            keys.NUMBER_6,
            keys.NUMBER_7,
            keys.NUMBER_8,
            keys.NUMBER_9,
            keys.NUMBER_0,
        ]
        if key in number_keys and number_keys.index(key) < len(self.theme.names):
            self.theme.select(number_keys.index(key))
