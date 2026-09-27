import numpy as np
import audio_dsp as dsp


def tone(freq_hz=1000, sr=48000, n=2048):
    """Generates a sine wave tone at a given frequency."""
    t = np.arange(n) / sr

    fixed_tone = np.sin(2 * np.pi * freq_hz * t)
    return fixed_tone.astype(np.float32)


def test(test_freq=1000, test_sr=48000, test_n=2048):

    # Generate a test tone for the given frequency
    test_tone_input = tone(test_freq, test_sr, test_n)
    test_tone_output = np.zeros(3, dtype=np.float32)

    dsp.process_in_place(test_tone_input, test_tone_output)

    return test_tone_output


def noise(n=2048, seed=7):
    """Generates random noise."""
    random_noise = np.random.default_rng(seed)
    test_tone_input = random_noise.normal(0, 1, n).astype(np.float32)
    test_tone_output = np.zeros(3, dtype=np.float32)

    dsp.process_in_place(test_tone_input, test_tone_output)

    return test_tone_output


def main():

    test_freqs = [1000, 100, 5000]  # Frequencies to test
    for freq in test_freqs:
        result = test(freq)
        print(f"For test frequency {freq}Hz, the output is: {result}")

    # Testing with noise
    result = noise()
    print(f"For Noise, the output is: {result}")


if __name__ == "__main__":
    main()
