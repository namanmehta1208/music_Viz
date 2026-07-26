#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <kiss_fft.h>
#include <cmath>
#include <vector>

namespace py = pybind11;

// This function will precess thje audio and write to the output array in-place
void process_in_place(py::array_t<float> input_array, py::array_t<float> output_array)
{
    // Request direct pointers to the Python numpy memory
    auto input_buf = input_array.request();
    auto output_buf = output_array.request();

    float *in_ptr = static_cast<float *>(input_buf.ptr);
    float *out_ptr = static_cast<float *>(output_buf.ptr);

    // This one will be 2048 as our audio buffer is of this size
    int nfft = input_buf.size;

    // Allocating KissFFT configuration and arrays
    kiss_fft_cfg cfg = kiss_fft_alloc(nfft, 0, nullptr, nullptr);
    std::vector<kiss_fft_cpx> cx_in(nfft);
    std::vector<kiss_fft_cpx> cx_out(nfft);

    // preapring input data
    for (int i = 0; i < nfft; ++i)
    {
        cx_in[i].r = in_ptr[i];
        cx_in[i].i = 0.0f;
    }

    // Running the FFT
    kiss_fft(cfg, cx_in.data(), cx_out.data());

    // Group the frequencies
    float bass = 0.0f, mid = 0.0f, treble = 0.0f;

    // The first half of the output seems to have the usable frequency
    for (int i = 1; i < nfft / 2; ++i)
    {
        // Calculate the magnitude (amplitude) of this specific frequency bin
        float magnitude = std::sqrt(cx_out[i].r * cx_out[i].r + cx_out[i].i * cx_out[i].i);

        // rough grouping based on the index i (need to tuen this later) !!!
        if (i < 10)
            bass += magnitude;
        else if (i < 100)
            mid += magnitude;
        else
            treble += magnitude;
    }

    // writing the results to the output
    out_ptr[0] = bass;
    out_ptr[1] = mid;
    out_ptr[2] = treble;

    free(cfg);
}

// Expose the function to Python
PYBIND11_MODULE(audio_dsp, m)
{
    m.doc() = "C++ Audio Processing Plugin using KissFFT";
    m.def("process_in_place", &process_in_place, "Run FFT and group frequencies");
}