"""Music visualizer: whatever your speakers play -> flashing bars of light.

Run from the music_Viz folder:
    PYTHONPATH=build uv run python visualizer.py

Keys:
    T         next color theme      1-5   pick a theme directly
    A         auto theme cycling on/off (on at start)
    F         fullscreen on/off
    Esc       quit

If the window glitches when it loses focus (seen on Hyprland), try the
native-Wayland backend instead:
    PYTHONPATH=build uv run python visualizer.py --window glfw
"""

import os

# Capture what the speakers/headphones play (the monitor), not the microphone.
# Must be set before sounddevice is imported. setdefault lets you override it
# from the shell if you ever want a different source.
os.environ.setdefault("PULSE_SOURCE", "@DEFAULT_MONITOR@")

import moderngl_window as mglw
import numpy as np
import sounddevice as sd

import audio_dsp as dsp
from audio_capture import AudioCapture
from renderer import StreakRenderer

# --- Audio / analysis -------------------------------------------------------
DEVICE = "pulse"
NFFT = 2048
NUM_BANDS = 32          # each band is drawn twice (mirrored), so 64 bars
F_MIN = 30
F_MAX = 16000

# --- dB -> 0..1 height ------------------------------------------------------
DB_FLOOR = -90.0
DB_CEIL = -30.0
# Music has much less energy in the highs than in the bass, so without help
# the outer bars stay dark. This boosts each band a little more than the one
# before it, up to TILT_DB for the highest band.
TILT_DB = 24.0

# --- Motion ------------------------------------------------------------------
# How quickly a bar follows the music, as a fraction per frame at 60 fps.
ATTACK = 0.6
RELEASE = 0.12

# --- Flashing ----------------------------------------------------------------
# A bar flashes when its band jumps above its own recent average (an onset:
# a drum hit, a new note). Steady sounds don't flash, so bars light up
# separately instead of all glowing at once.
AVERAGE_SPEED = 0.04    # how fast the "recent average" follows (~0.4 s memory)
FLASH_GAIN = 5.0        # 0.2 above average = full flash
FLASH_DECAY = 0.72      # per frame at 60 fps; lower = shorter flashes
# Flashes weaker than this are switched off completely, so a bar is either
# clearly lit or gone (no dim leftovers while it fades).
FLASH_CUTOFF = 0.3

# --- Kick (beat) ---------------------------------------------------------------
# A strong onset in the lowest bands (kick drum, bass hit) makes the whole
# frame punch: brighter, more glow, stronger RGB split, more border flares.
KICK_BANDS = 8          # bands 0..7 = roughly 30-150 Hz
KICK_THRESHOLD = 0.35   # ignore small bass onsets
KICK_DECAY = 0.78       # per frame at 60 fps

# --- Color themes ------------------------------------------------------------
# Each theme: colors for the centre bars (bass), middle bars, outer bars
# (treble), and an accent used for the light leak. Values are 0..1 RGB.
THEMES = {
    "Gold":       [(1.00, 0.55, 0.12), (1.00, 0.74, 0.28), (1.00, 0.90, 0.62), (0.90, 0.60, 0.15)],
    "Rose Gold":  [(1.00, 0.62, 0.20), (1.00, 0.42, 0.42), (1.00, 0.78, 0.55), (0.95, 0.40, 0.35)],
    "Royal":      [(1.00, 0.68, 0.18), (0.62, 0.35, 1.00), (1.00, 0.35, 0.78), (0.55, 0.30, 0.90)],
    "Ember":      [(1.00, 0.25, 0.05), (1.00, 0.48, 0.10), (1.00, 0.80, 0.40), (1.00, 0.35, 0.08)],
    "Ice":        [(0.70, 0.90, 1.00), (0.35, 0.70, 1.00), (0.85, 0.95, 1.00), (0.20, 0.55, 0.65)],
}

# Automatic theme cycling. After THEME_SECONDS the next strong kick switches
# to the next theme, so the change lands on a beat. If no kick comes within
# KICK_WAIT_SECONDS more (quiet passage), it switches anyway.
AUTO_CYCLE = True
THEME_SECONDS = 20.0
KICK_WAIT_SECONDS = 6.0
FADE_SECONDS = 2.0      # cross-fade between themes instead of snapping

# Longest gap between frames we treat as "normal". If the window stalls (for
# example while it's in the background), we pretend only this much time passed
# instead of jumping the animation.
MAX_FRAME_TIME = 0.1


class Visualizer(mglw.WindowConfig):
    gl_version = (3, 3)
    title = "Music Visualizer"
    window_size = (1280, 480)
    aspect_ratio = None     # fill the whole window, whatever its shape
    resizable = True
    vsync = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        sample_rate = int(sd.query_devices(DEVICE, "input")["default_samplerate"])
        self.audio = AudioCapture(
            device=DEVICE, channels=2, sample_rate=sample_rate, buffer_size=NFFT
        )
        self.analyzer = dsp.SpectrumAnalyzer(NFFT, sample_rate, NUM_BANDS, F_MIN, F_MAX)

        self.bands_db = np.zeros(NUM_BANDS, dtype=np.float32)    # filled by C++
        self.tilt = np.linspace(0.0, TILT_DB, NUM_BANDS, dtype=np.float32)
        self.reset_state()

        self.renderer = StreakRenderer(self.ctx, NUM_BANDS)
        self.renderer.resize(*self.wnd.buffer_size)

        self.wnd.fullscreen_key = self.wnd.keys.F   # F toggles fullscreen
        self.wnd.cursor = False                      # hide the mouse over the window

        self.theme_names = list(THEMES)
        self.auto_cycle = AUTO_CYCLE
        self.colors = np.array(THEMES[self.theme_names[0]], dtype=np.float32)
        self.set_theme(0)

        self.audio.start()

    def reset_state(self):
        self.heights = np.zeros(NUM_BANDS, dtype=np.float32)     # smoothed level, 0..1
        self.average = np.zeros(NUM_BANDS, dtype=np.float32)     # slow recent average
        self.flashes = np.zeros(NUM_BANDS, dtype=np.float32)     # flash brightness, 0..1
        self.kick = 0.0

    def set_theme(self, index):
        """Start a cross-fade from the current colors to theme `index`."""
        self.theme_index = index % len(self.theme_names)
        name = self.theme_names[self.theme_index]
        self.fade_from = self.colors.copy()
        self.fade_to = np.array(THEMES[name], dtype=np.float32)
        self.fade_progress = 0.0
        self.theme_age = 0.0        # seconds since this theme was chosen
        print(f"Theme: {name}")

    def update_theme(self, dt):
        """Advance the cross-fade and the automatic cycling by dt seconds."""
        self.theme_age += dt
        if self.auto_cycle and self.theme_age >= THEME_SECONDS:
            waited_long_enough = self.theme_age >= THEME_SECONDS + KICK_WAIT_SECONDS
            if self.kick > 0.5 or waited_long_enough:
                self.set_theme(self.theme_index + 1)

        if self.fade_progress < 1.0:
            self.fade_progress = min(1.0, self.fade_progress + dt / FADE_SECONDS)
            # smoothstep: starts and ends gently instead of at constant speed
            t = self.fade_progress * self.fade_progress * (3.0 - 2.0 * self.fade_progress)
            self.colors = self.fade_from + (self.fade_to - self.fade_from) * t
            self.renderer.set_theme(*self.colors)

    def target_heights(self):
        """Newest audio -> one 0..1 height per band."""
        self.analyzer.process(self.audio.get_latest_buffer(), self.bands_db)
        db = self.bands_db + self.tilt
        heights = np.clip((db - DB_FLOOR) / (DB_CEIL - DB_FLOOR), 0.0, 1.0)
        # Never let an invalid number (NaN) in: it would poison the smoothed
        # state and every frame after it would render black.
        return np.nan_to_num(heights, nan=0.0)

    def on_render(self, time, frame_time):
        target = self.target_heights()

        # Move each height part of the way toward its target. Using frame_time
        # keeps the speed the same at 30, 60 or 144 fps.
        dt = min(max(frame_time, 0.0), MAX_FRAME_TIME)
        frames = dt * 60.0
        attack = 1.0 - (1.0 - ATTACK) ** frames
        release = 1.0 - (1.0 - RELEASE) ** frames
        rate = np.where(target > self.heights, attack, release)
        self.heights += (target - self.heights) * rate

        # Flashes: how far above its recent average is each band right now?
        # A new onset restarts the flash at full strength; otherwise it fades.
        self.average += (target - self.average) * (1.0 - (1.0 - AVERAGE_SPEED) ** frames)
        onset = np.clip((target - self.average) * FLASH_GAIN, 0.0, 1.0)
        self.flashes = np.maximum(self.flashes * FLASH_DECAY**frames, onset)

        # Kick: the strongest onset among the bass bands, above a threshold.
        bass_hit = (onset[:KICK_BANDS].max() - KICK_THRESHOLD) / (1.0 - KICK_THRESHOLD)
        self.kick = max(self.kick * KICK_DECAY**frames, float(np.clip(bass_hit, 0.0, 1.0)))

        if not (np.isfinite(self.heights).all() and np.isfinite(self.flashes).all()):
            print("Warning: invalid values in band data, resetting")
            self.reset_state()

        # Hard on/off: rescale so the cutoff becomes 0 and full stays 1.
        visible = np.clip((self.flashes - FLASH_CUTOFF) / (1.0 - FLASH_CUTOFF), 0.0, 1.0)

        self.update_theme(dt)
        self.renderer.render(self.heights, visible, self.kick, time, self.wnd.fbo)

    def on_key_event(self, key, action, modifiers):
        keys = self.wnd.keys
        if action != keys.ACTION_PRESS:
            return
        if key == keys.T:
            self.set_theme(self.theme_index + 1)
        if key == keys.A:
            self.auto_cycle = not self.auto_cycle
            self.theme_age = 0.0
            print(f"Auto theme cycling: {'on' if self.auto_cycle else 'off'}")
        number_keys = [keys.NUMBER_1, keys.NUMBER_2, keys.NUMBER_3, keys.NUMBER_4, keys.NUMBER_5]
        if key in number_keys:
            self.set_theme(number_keys.index(key))

    def on_resize(self, width, height):
        # buffer_size is in real pixels (can differ from width/height on HiDPI)
        self.renderer.resize(*self.wnd.buffer_size)

    def on_close(self):
        self.audio.stop()


if __name__ == "__main__":
    mglw.run_window_config(Visualizer)
