import sounddevice as sd
import numpy as np


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
