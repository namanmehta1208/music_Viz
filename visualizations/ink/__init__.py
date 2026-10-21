"""Ink: colored smoke slowly swirling in water, stirred by the bass. Calm."""

from pathlib import Path

import numpy as np

from ..base import FullscreenPass, SlowAudio, Visualization, load_fragment

# Each theme: bass ink, mid ink, treble ink, water.
THEMES = {
    "Nebula": [
        (1.00, 0.25, 0.65),
        (0.30, 0.40, 1.00),
        (0.20, 0.95, 0.90),
        (0.006, 0.008, 0.025),
    ],
    "Koi": [
        (1.00, 0.40, 0.10),
        (1.00, 0.15, 0.20),
        (1.00, 0.80, 0.35),
        (0.004, 0.018, 0.022),
    ],
    "Indigo": [
        (0.35, 0.25, 1.00),
        (0.70, 0.30, 1.00),
        (0.30, 0.80, 1.00),
        (0.008, 0.006, 0.020),
    ],
    "Moss": [
        (0.30, 0.90, 0.35),
        (0.75, 0.95, 0.25),
        (0.15, 0.80, 0.75),
        (0.005, 0.015, 0.012),
    ],
}

# Drops: a kick at least this strong drops fresh ink somewhere, but no more
# often than every DROP_COOLDOWN seconds. A drop fades out over a few seconds
# and is gone after DROP_LIFETIME.
MAX_DROPS = 4  # must match MAX_DROPS in ink.frag
DROP_KICK = 0.6
DROP_COOLDOWN = 1.5
DROP_LIFETIME = 10.0


class Ink(Visualization):
    name = "Ink"
    description = "Colored smoke slowly swirling in water, stirred by the bass. Calm."
    themes = THEMES
    theme_seconds = 60.0
    fade_seconds = 8.0

    def __init__(self, ctx, num_bands):
        super().__init__(ctx, num_bands)
        self.pass_ = FullscreenPass(
            ctx, load_fragment(Path(__file__).parent / "ink.frag")
        )
        self.audio = SlowAudio(num_bands)
        self.rng = np.random.default_rng()
        # Per drop: x, y, age (< 0 = no drop), which ink color.
        self.drops = np.tile(np.array([0.0, 0.0, -1.0, 0.0], dtype="f4"), (MAX_DROPS, 1))
        self.since_drop = DROP_COOLDOWN
        self.size = (1, 1)

    def resize(self, width, height):
        self.size = (width, height)

    def update_drops(self, frame):
        live = self.drops[:, 2] >= 0.0
        self.drops[live, 2] += frame.dt
        self.drops[self.drops[:, 2] > DROP_LIFETIME, 2] = -1.0

        self.since_drop += frame.dt
        if frame.kick >= DROP_KICK and self.since_drop >= DROP_COOLDOWN:
            self.since_drop = 0.0
            # Reuse a free slot, or the oldest drop if all are in use.
            ages = np.where(self.drops[:, 2] < 0.0, np.inf, self.drops[:, 2])
            slot = int(np.argmax(ages))
            x, y = self.rng.uniform(0.15, 0.85, 2)
            self.drops[slot] = (x, y, 0.0, self.rng.integers(0, 3))

    def render(self, frame, target):
        audio = self.audio
        audio.update(frame)
        self.update_drops(frame)
        palette = np.asarray(self.theme.update(frame.dt, frame.kick), dtype="f4")

        prog = self.pass_.prog
        prog["palette"].write(palette.tobytes())
        prog["drops"].write(self.drops.tobytes())
        prog["resolution"].value = self.size
        prog["time"].value = frame.time
        prog["flow"].value = audio.flow
        prog["energy"].value = audio.energy
        prog["bass"].value = audio.bass
        prog["mid"].value = audio.mid
        prog["treble"].value = audio.treble
        prog["swell"].value = audio.swell
        self.pass_.render(target, self.size)
