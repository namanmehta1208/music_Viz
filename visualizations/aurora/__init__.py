"""Aurora: slow curtains of northern lights over a still mountain lake.
Calm: the music shapes it, but heavily smoothed, so nothing flashes."""

from pathlib import Path

import moderngl
import numpy as np

from ..base import FullscreenPass, SlowAudio, Visualization, load_fragment

HERE = Path(__file__).parent

# Each theme: curtain bottom edge, curtain body, curtain top, night sky.
# The sky color is very dark on purpose; the shader brightens it a little
# near the horizon.
THEMES = {
    "Northern": [
        (0.20, 1.00, 0.55),
        (0.10, 0.80, 0.70),
        (0.55, 0.30, 0.95),
        (0.010, 0.020, 0.050),
    ],
    "Dusk": [
        (1.00, 0.45, 0.55),
        (0.75, 0.35, 0.85),
        (0.35, 0.40, 1.00),
        (0.040, 0.015, 0.050),
    ],
    "Lagoon": [
        (0.10, 1.00, 0.85),
        (0.10, 0.55, 1.00),
        (0.60, 0.80, 1.00),
        (0.005, 0.025, 0.045),
    ],
    "Solar": [
        (1.00, 0.60, 0.20),
        (1.00, 0.30, 0.40),
        (0.60, 0.20, 0.70),
        (0.035, 0.015, 0.030),
    ],
}


class Aurora(Visualization):
    name = "Aurora"
    description = "Slow northern lights over a mountain lake. Calm and relaxing."
    themes = THEMES
    theme_seconds = 60.0
    fade_seconds = 8.0  # long, soft cross-fades; no waiting for a kick

    def __init__(self, ctx, num_bands):
        super().__init__(ctx, num_bands)
        # The slow noise is worked out once per screen column (columns.frag),
        # then the main pass reads it for every pixel in that column.
        self.columns = FullscreenPass(ctx, load_fragment(HERE / "columns.frag"))
        self.pass_ = FullscreenPass(
            ctx, load_fragment(HERE / "aurora.frag", num_bands)
        )
        self.audio = SlowAudio(num_bands)
        self.size = None
        self.columns_tex = self.columns_fbo = None

    def resize(self, width, height):
        if (width, height) == self.size or width == 0 or height == 0:
            return
        self.size = (width, height)
        for obj in (self.columns_tex, self.columns_fbo):
            if obj is not None:
                obj.release()
        # One pixel per screen column, 4 rows; 32-bit floats for exact heights.
        self.columns_tex = self.ctx.texture((width, 4), 4, dtype="f4")
        self.columns_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.columns_tex.repeat_x = False  # the lake's ripples can reach past the edge
        self.columns_tex.repeat_y = False
        self.columns_fbo = self.ctx.framebuffer(color_attachments=[self.columns_tex])

    def render(self, frame, target):
        audio = self.audio
        audio.update(frame)
        palette = np.asarray(self.theme.update(frame.dt, frame.kick), dtype="f4")

        self.columns.prog["resolution"].value = self.size
        self.columns.prog["flow"].value = audio.flow
        self.columns.render(self.columns_fbo, (self.size[0], 4))

        prog = self.pass_.prog
        self.columns_tex.use(location=0)
        prog["columns"].value = 0
        prog["levels"].write(audio.levels.astype("f4").tobytes())
        prog["palette"].write(palette.tobytes())
        prog["resolution"].value = self.size
        prog["time"].value = frame.time
        prog["energy"].value = audio.energy
        prog["swell"].value = audio.swell
        prog["treble"].value = audio.treble
        self.pass_.render(target, self.size)
