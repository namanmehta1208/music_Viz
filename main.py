import sounddevice as sd
from audio_capture import AudioCapture
import time

# checking samplerate
device_id = 20
device_info = sd.query_devices(device_id, "input")
correct_sample_rate = int(device_info["default_samplerate"])

print(f"Device {device_id} requires a sample rate of {correct_sample_rate}Hz")


audioBuf = AudioCapture(device=device_id, channels=2, sample_rate=correct_sample_rate)

audioBuf.start()
count = 0

while count != 500:
    print(audioBuf.get_latest_buffer())
    count += 1

audioBuf.stop()
