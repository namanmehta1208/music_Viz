import os

import sounddevice as sd
import numpy as np

# Inputs whose name contains one of these record what the speakers play
# instead of a microphone. Earlier entries win. "pulse"/"pipewire" only count
# because PULSE_SOURCE points them at the monitor (set before importing
# sounddevice in the entry scripts).
LOOPBACK_NAMES = [
    "pulse",  # Linux: PulseAudio / PipeWire
    "pipewire",
    "monitor",
    "stereo mix",  # Windows: Realtek and others
    "what u hear",  # Windows: Creative
    "wave out",
    "loopback",
    "blackhole",  # macOS virtual devices
    "soundflower",
]

# The same device can appear under several host APIs; prefer them in this
# order (unknown APIs and WDM-KS, which is often flaky, come last).
HOSTAPI_PREFERENCE = [
    "Windows WASAPI",
    "Core Audio",
    "ALSA",
    "Windows DirectSound",
    "MME",
]


def find_loopback_device():
    """Pick the input that records what the speakers play.

    Set MUSIC_VIZ_DEVICE to a device index or part of its name to override
    the choice (`python -m sounddevice` lists them). Returns the device's
    info dict from sounddevice (index, name, default_samplerate, ...).
    """
    override = os.environ.get("MUSIC_VIZ_DEVICE")
    if override:
        device = int(override) if override.isdigit() else override
        return sd.query_devices(device, "input")

    def rank(info):
        name = info["name"].lower()
        name_rank = next(
            i for i, keyword in enumerate(LOOPBACK_NAMES) if keyword in name
        )
        api = sd.query_hostapis(info["hostapi"])["name"]
        api_rank = (
            HOSTAPI_PREFERENCE.index(api)
            if api in HOSTAPI_PREFERENCE
            else len(HOSTAPI_PREFERENCE)
        )
        return name_rank, api_rank

    candidates = [
        info
        for info in sd.query_devices()
        if info["max_input_channels"] > 0
        and any(keyword in info["name"].lower() for keyword in LOOPBACK_NAMES)
    ]
    if candidates:
        return min(candidates, key=rank)

    print(
        "Warning: no loopback input found (e.g. 'Stereo Mix' on Windows), "
        "falling back to the default input, which is probably a microphone."
    )
    return sd.query_devices(kind="input")


class AudioCapture:
    # 1. Added 'device=None' to the parameters
    def __init__(
        self,
        device=None,
        sample_rate=44100,
        channels=1,
        chunk_size=512,
        buffer_size=2048,
    ):
        self.device = device  # 2. Store the device ID
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.buffer_size = buffer_size

        # This is our zero-allocation ring buffer. It is always exactly 2048 items long.
        self.audio_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.stream = None

    def _audio_callback(self, indata, frames, time, status):
        """Internal callback used by sounddevice."""
        if status:
            print(f"Audio Status: {status}")

        new_data = indata[:, 0]
        self.audio_buffer = np.roll(self.audio_buffer, -self.chunk_size)
        self.audio_buffer[-self.chunk_size :] = new_data

    def start(self):
        """Starts the background audio listening thread."""
        print(f"Starting audio stream at {self.sample_rate}Hz...")
        self.stream = sd.InputStream(
            device=self.device,  # 3. Pass the device ID to the stream
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.chunk_size,
            callback=self._audio_callback,
        )
        self.stream.start()

    def stop(self):
        """Safely shuts down the audio stream."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            print("Audio stream stopped.")

    def get_latest_buffer(self):
        """
        Returns a copy of the current audio buffer for the visualizer to use.
        Using .copy() is crucial here to prevent thread-collision if the audio
        callback tries to write to the array at the exact same millisecond
        that your C++ module is trying to read it.
        """
        return self.audio_buffer.copy()
