"""Streaks: thin bars of light that flash on every onset, with bloom, RGB
split and lens flares on kicks. Loud and flashy."""

from ..base import Visualization
from .renderer import StreakRenderer

# Each theme: colors for the centre bars (bass), middle bars, outer bars
# (treble), and an accent used for the light leak. Values are 0..1 RGB.
THEMES = {
    "Gold": [
        (1.00, 0.55, 0.12),
        (1.00, 0.74, 0.28),
        (1.00, 0.90, 0.62),
        (0.90, 0.60, 0.15),
    ],
    "Rose Gold": [
        (1.00, 0.62, 0.20),
        (1.00, 0.42, 0.42),
        (1.00, 0.78, 0.55),
        (0.95, 0.40, 0.35),
    ],
    "Royal": [
        (1.00, 0.68, 0.18),
        (0.62, 0.35, 1.00),
        (1.00, 0.35, 0.78),
        (0.55, 0.30, 0.90),
    ],
    "Ember": [
        (1.00, 0.25, 0.05),
        (1.00, 0.48, 0.10),
        (1.00, 0.80, 0.40),
        (1.00, 0.35, 0.08),
    ],
    "Ice": [
        (0.70, 0.90, 1.00),
        (0.35, 0.70, 1.00),
        (0.85, 0.95, 1.00),
        (0.20, 0.55, 0.65),
    ],
    "Toxic": [
        (0.25, 1.00, 0.10),
        (0.75, 1.00, 0.15),
        (0.85, 1.00, 0.70),
        (0.10, 0.80, 0.20),
    ],
    "Synthwave": [
        (1.00, 0.15, 0.60),
        (0.10, 0.90, 1.00),
        (0.85, 0.60, 1.00),
        (0.60, 0.15, 0.85),
    ],
    "Laser": [
        (1.00, 0.05, 0.15),
        (1.00, 0.10, 0.55),
        (1.00, 0.70, 0.75),
        (0.85, 0.00, 0.10),
    ],
    "Ultraviolet": [
        (0.55, 0.10, 1.00),
        (0.25, 0.35, 1.00),
        (0.80, 0.70, 1.00),
        (0.40, 0.05, 0.85),
    ],
    "Aqua": [
        (0.00, 1.00, 0.70),
        (0.00, 0.80, 1.00),
        (0.70, 1.00, 0.95),
        (0.00, 0.65, 0.60),
    ],
}


class Streaks(Visualization):
    name = "Streaks"
    description = "Flashing bars of light with bloom and lens flares. Loud and flashy."
    themes = THEMES
    # After 20 s, switch theme on the next strong kick (or after 6 s more).
    theme_seconds = 20.0
    fade_seconds = 2.0
    kick_wait_seconds = 6.0

    def __init__(self, ctx, num_bands):
        super().__init__(ctx, num_bands)
        self.renderer = StreakRenderer(ctx, num_bands)

    def resize(self, width, height):
        self.renderer.resize(width, height)

    def render(self, frame, target):
        self.renderer.set_theme(*self.theme.update(frame.dt, frame.kick))
        self.renderer.render(frame.heights, frame.flashes, frame.kick, frame.time, target)
