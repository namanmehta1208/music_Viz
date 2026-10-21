"""Tide: a few soft glowing lines along a horizon, moving like slow waves
shaped by the spectrum. Calm."""

from pathlib import Path

import moderngl
import numpy as np

from ..base import FullscreenPass, SlowAudio, Visualization, follow, load_fragment

# Each theme: top line, middle lines, bottom line, background glow.
THEMES = {
    "Moonlit": [
        (0.75, 0.85, 1.00),
        (0.30, 0.75, 1.00),
        (0.55, 0.35, 1.00),
        (0.04, 0.06, 0.14),
    ],
    "Sunset": [
        (1.00, 0.80, 0.35),
        (1.00, 0.45, 0.40),
        (0.85, 0.25, 0.65),
        (0.14, 0.05, 0.10),
    ],
    "Sea Glass": [
        (0.60, 1.00, 0.80),
        (0.20, 0.90, 0.85),
        (0.20, 0.55, 1.00),
        (0.02, 0.09, 0.10),
    ],
    "Rose": [
        (1.00, 0.70, 0.60),
        (1.00, 0.50, 0.75),
        (0.70, 0.50, 1.00),
        (0.12, 0.05, 0.12),
    ],
}

NUM_LINES = 7
# Each line follows the line above it at this speed (fraction per frame at
# 60 fps), so a change in the music takes ~0.3 s more to reach each line.
LINE_LAG = 0.05


class Tide(Visualization):
    name = "Tide"
    description = "Soft glowing lines along a horizon, rolling like slow waves. Calm."
    themes = THEMES
    theme_seconds = 60.0
    fade_seconds = 8.0

    def __init__(self, ctx, num_bands):
        super().__init__(ctx, num_bands)
        self.pass_ = FullscreenPass(
            ctx, load_fragment(Path(__file__).parent / "tide.frag")
        )
        self.audio = SlowAudio(num_bands)
        # Row k: the spectrum line k is showing (row 0 = the newest).
        self.spectra = np.zeros((NUM_LINES, num_bands), dtype=np.float32)
        self.spectra_tex = ctx.texture((num_bands, NUM_LINES), 1, dtype="f4")
        self.spectra_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.spectra_tex.repeat_x = False
        self.spectra_tex.repeat_y = False
        self.size = (1, 1)

    def resize(self, width, height):
        self.size = (width, height)

    def render(self, frame, target):
        audio = self.audio
        audio.update(frame)
        frames = frame.dt * 60.0
        self.spectra[0] = audio.levels
        for k in range(1, NUM_LINES):
            self.spectra[k] = follow(
                self.spectra[k], self.spectra[k - 1], LINE_LAG, frames
            )
        self.spectra_tex.write(self.spectra.tobytes())
        palette = np.asarray(self.theme.update(frame.dt, frame.kick), dtype="f4")

        prog = self.pass_.prog
        self.spectra_tex.use(location=0)
        prog["spectra"].value = 0
        prog["num_lines"].value = NUM_LINES
        prog["palette"].write(palette.tobytes())
        prog["resolution"].value = self.size
        prog["time"].value = frame.time
        prog["flow"].value = audio.flow
        prog["energy"].value = audio.energy
        prog["swell"].value = audio.swell
        prog["treble"].value = audio.treble
        self.pass_.render(target, self.size)
