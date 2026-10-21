"""Fireflies: drifting points of light that slowly gather and brighten with
the music. Calm.

Each firefly belongs to one band. An onset in its band makes it light up and
slowly fade again; on its own it just blinks softly. In quiet passages the
fireflies wander apart; as the music gets louder they gather into a few slow
swirls that drift around the screen.
"""

from pathlib import Path

import moderngl
import numpy as np

from ..base import FullscreenPass, SlowAudio, Visualization, follow, load_fragment

HERE = Path(__file__).parent

# Each theme: bass fireflies, mid fireflies, treble fireflies, night background.
THEMES = {
    "Summer Night": [
        (0.70, 1.00, 0.30),
        (1.00, 0.85, 0.35),
        (1.00, 0.60, 0.20),
        (0.010, 0.025, 0.030),
    ],
    "Lanterns": [
        (1.00, 0.45, 0.15),
        (1.00, 0.25, 0.20),
        (1.00, 0.75, 0.35),
        (0.030, 0.012, 0.015),
    ],
    "Spirits": [
        (0.30, 1.00, 0.95),
        (0.35, 0.60, 1.00),
        (0.75, 0.60, 1.00),
        (0.008, 0.015, 0.040),
    ],
    "Sakura": [
        (1.00, 0.55, 0.75),
        (1.00, 0.80, 0.90),
        (0.75, 0.50, 1.00),
        (0.025, 0.012, 0.030),
    ],
}

COUNT = 220
CLUSTERS = 3  # how many swirls they gather into

# Motion (distances in screen heights, times in seconds).
WANDER = 0.06  # strength of each firefly's own aimless drift
GATHER = 0.15  # pull toward its swirl's centre, at full loudness
SWIRL = 0.12  # sideways push around the centre, so they orbit instead of clumping
WALL = 4.0  # push back in when one drifts past the screen edge
DRAG = 0.97  # velocity kept per frame at 60 fps

# Gathering starts above this loudness and is complete GATHER_RANGE above it.
GATHER_START = 0.15
GATHER_RANGE = 0.5

# Light. GLOW_ATTACK/RELEASE: how fast an onset lights a firefly up / lets it
# fade, as a fraction per frame at 60 fps.
GLOW_ATTACK = 0.25
GLOW_RELEASE = 0.025
TRAIL = 0.8  # light kept per frame at 60 fps; higher = longer trails


def gradient(palette, t):
    """Theme color for each t in 0..1: palette[0] -> [1] -> [2]."""
    t = t[:, None]
    low = palette[0] + (palette[1] - palette[0]) * np.clip(t * 2.0, 0.0, 1.0)
    high = palette[1] + (palette[2] - palette[1]) * np.clip(t * 2.0 - 1.0, 0.0, 1.0)
    return np.where(t < 0.5, low, high)


class Fireflies(Visualization):
    name = "Fireflies"
    description = "Drifting points of light that gather and glow with the music. Calm."
    themes = THEMES
    theme_seconds = 60.0
    fade_seconds = 8.0

    def __init__(self, ctx, num_bands):
        super().__init__(ctx, num_bands)
        self.audio = SlowAudio(num_bands)

        self.points_prog = ctx.program(
            vertex_shader=(HERE / "points.vert").read_text(),
            fragment_shader=(HERE / "points.frag").read_text(),
        )
        # Per firefly: x, y, size, r, g, b; rewritten every frame.
        self.points_vbo = ctx.buffer(reserve=COUNT * 6 * 4, dynamic=True)
        self.points_vao = ctx.vertex_array(
            self.points_prog,
            [(self.points_vbo, "2f 1f 3f", "in_position", "in_size", "in_color")],
        )
        self.fade = FullscreenPass(ctx, load_fragment(HERE / "fade.frag"))
        self.composite = FullscreenPass(ctx, load_fragment(HERE / "composite.frag"))

        rng = np.random.default_rng()
        self.band = np.arange(COUNT) % num_bands
        self.cluster = np.arange(COUNT) % CLUSTERS
        # Color position: its band, with a little spread so neighbours differ.
        self.hue = np.clip(
            self.band / (num_bands - 1) + rng.normal(0.0, 0.05, COUNT), 0.0, 1.0
        )
        self.wander_speed = rng.uniform(0.2, 0.7, (COUNT, 2))
        self.wander_phase = rng.uniform(0.0, 2 * np.pi, (COUNT, 2))
        self.blink_speed = rng.uniform(0.4, 1.4, COUNT)
        self.blink_phase = rng.uniform(0.0, 2 * np.pi, COUNT)
        self.base_size = rng.uniform(5.0, 14.0, COUNT)
        self.start = rng.uniform(0.0, 1.0, (COUNT, 2))  # placed on first resize
        self.pos = None
        self.vel = np.zeros((COUNT, 2))
        self.glow = np.zeros(COUNT)

        self.size = None
        self.scene_tex = self.scene_fbo = None

    def resize(self, width, height):
        if (width, height) == self.size or width == 0 or height == 0:
            return
        self.size = (width, height)
        if self.pos is None:
            self.pos = self.start * [width / height, 1.0]
        for obj in (self.scene_tex, self.scene_fbo):
            if obj is not None:
                obj.release()
        # 16-bit floats, so overlapping light can go above 1.0 (HDR).
        self.scene_tex = self.ctx.texture(self.size, 4, dtype="f2")
        self.scene_fbo = self.ctx.framebuffer(color_attachments=[self.scene_tex])
        self.scene_fbo.clear()

    def move(self, dt, time, aspect, gather):
        """One step of the flight: wander, gather and swirl, stay on screen."""
        frames = dt * 60.0
        angle = time * self.wander_speed + self.wander_phase
        force = WANDER * np.stack([np.sin(angle[:, 0]), np.cos(angle[:, 1])], axis=1)

        # Swirl centres wander slowly on their own paths, faster with louder music.
        flow = self.audio.flow
        j = np.arange(CLUSTERS)
        centres = np.stack(
            [
                aspect * (0.5 + 0.3 * np.sin(flow * 0.11 * (j + 1) + j * 2.1)),
                0.5 + 0.22 * np.sin(flow * 0.07 * (j + 2) + j * 1.3),
            ],
            axis=1,
        )
        to_centre = centres[self.cluster] - self.pos
        around = np.stack([-to_centre[:, 1], to_centre[:, 0]], axis=1)
        force += gather * (GATHER * to_centre + SWIRL * around)

        margin = 0.04
        low = np.array([margin, margin])
        high = np.array([aspect - margin, 1.0 - margin])
        force += WALL * (np.maximum(low - self.pos, 0) - np.maximum(self.pos - high, 0))

        self.vel = self.vel * DRAG**frames + force * dt
        self.pos += self.vel * dt

    def render(self, frame, target):
        audio = self.audio
        audio.update(frame)
        width, height = self.size
        aspect = width / height
        frames = frame.dt * 60.0

        gather = np.clip((audio.energy - GATHER_START) / GATHER_RANGE, 0.0, 1.0)
        self.move(frame.dt, frame.time, aspect, gather)

        # An onset in a firefly's band lights it up; then it slowly fades.
        onset = frame.flashes[self.band]
        speed = np.where(onset > self.glow, GLOW_ATTACK, GLOW_RELEASE)
        self.glow = follow(self.glow, onset, speed, frames)
        blink = (0.5 + 0.5 * np.sin(frame.time * self.blink_speed + self.blink_phase)) ** 4
        brightness = blink * (0.15 + 0.5 * audio.levels[self.band]) + 1.6 * self.glow

        palette = np.asarray(self.theme.update(frame.dt, frame.kick), dtype="f4")
        points = np.empty((COUNT, 6), dtype="f4")
        points[:, 0] = self.pos[:, 0] / aspect
        points[:, 1] = self.pos[:, 1]
        points[:, 2] = self.base_size * (1.0 + 0.8 * self.glow) * height / 480.0
        points[:, 3:] = gradient(palette[:3], self.hue) * brightness[:, None]
        self.points_vbo.write(points.tobytes())

        ctx = self.ctx
        ctx.enable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
        # 1. Dim last frame's light (dst * keep), leaving short trails.
        ctx.blend_func = (moderngl.ZERO, moderngl.SRC_ALPHA)
        self.fade.prog["keep"].value = TRAIL**frames
        self.fade.render(self.scene_fbo, self.size)
        # 2. Add the fireflies on top.
        ctx.blend_func = (moderngl.ONE, moderngl.ONE)
        self.points_vao.render(moderngl.POINTS)
        ctx.blend_func = moderngl.DEFAULT_BLENDING
        ctx.disable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)

        # 3. Background + fireflies onto the window.
        prog = self.composite.prog
        self.scene_tex.use(location=0)
        prog["scene"].value = 0
        prog["background"].value = tuple(palette[3])
        prog["energy"].value = audio.energy
        prog["time"].value = frame.time
        self.composite.render(target, self.size)
