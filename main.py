import sounddevice as sd
from audio_capture import AudioCapture
import time
import numpy as np
import audio_dsp as dsp


# checking samplerate
device_id = 12 # 20
device_info = sd.query_devices(device_id, "input")
print(f"Device {device_id} info: {device_info}")
correct_sample_rate = int(device_info["default_samplerate"])

print(f"Device {device_id} requires a sample rate of {correct_sample_rate}Hz")


audioBuf = AudioCapture(device=device_id, channels=2, sample_rate=correct_sample_rate)

analyzer = dsp.SpectrumAnalyzer(2048)          # once: FFT setup + Hann window
bands = np.zeros(3, dtype=np.float32)          # once: reused every frame

audioBuf.start()

try:
    while True:
        buffer = audioBuf.get_latest_buffer()  # newest 2048 samples
        analyzer.process(buffer, bands)        # C++ fills bands in place
        print(f"bass {bands[0]:8.1f}   mid {bands[1]:8.1f}   treble {bands[2]:8.1f}", end="\r")
        time.sleep(1 / 60)                     # about 60 updates per second
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    audioBuf.stop()
