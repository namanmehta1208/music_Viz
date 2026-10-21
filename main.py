import os
os.environ["PULSE_SOURCE"] = "@DEFAULT_MONITOR@"   # capture what the speakers play



from audio_capture import AudioCapture, find_loopback_device
import time
import numpy as np
import audio_dsp as dsp

NFFT = 2048
NUM_BANDS = 16
F_MIN = 30
F_MAX = 16000

DB_FLOOR = -90
DB_CEIL = -30

def db_to_height(db):
    """Convert decibels to a normalized height value between 0 and 1."""
    height = (db - DB_FLOOR) / (DB_CEIL - DB_FLOOR)
    return np.clip(height, 0, 1)

np.set_printoptions(suppress=True, linewidth=200)

# checking samplerate
device_info = find_loopback_device()
device_id = device_info["index"]
print(f"Device {device_id} info: {device_info}")
correct_sample_rate = int(device_info["default_samplerate"])

print(f"Device {device_id} requires a sample rate of {correct_sample_rate}Hz")


audioBuf = AudioCapture(
    device=device_id,
    channels=min(2, device_info["max_input_channels"]),
    sample_rate=correct_sample_rate,
)

analyzer = dsp.SpectrumAnalyzer(NFFT, correct_sample_rate, NUM_BANDS, F_MIN, F_MAX)    # once: FFT setup + Hann window
bands = np.zeros(NUM_BANDS, dtype=np.float32)          # once: reused every frame


audioBuf.start()

try:
    while True:
        buffer = audioBuf.get_latest_buffer()  # newest 2048 samples
        analyzer.process(buffer, bands)        # C++ fills bands in place
        heights = db_to_height(bands)            # convert to normalized heights
        print(np.round(heights, 2), end="\r")
        time.sleep(1 / 60)                     # about 60 updates per second
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    audioBuf.stop()
