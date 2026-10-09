#include <cmath>
#include <kiss_fft.h>
#include <kiss_fftr.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <stdexcept>
#include <vector>

namespace py = pybind11;

class SpectrumAnalyzer {
public:
  SpectrumAnalyzer(int nfft) {
    if(nfft % 2 != 0) {
      throw std::runtime_error("NFFT size must be even.");
    }

    nfft_ = nfft;
    cfg_ = kiss_fftr_alloc(nfft_, 0, nullptr, nullptr);
  }

  ~SpectrumAnalyzer() { kiss_fftr_free(cfg_); }

  void process(py::array_t<float> input_array,
               py::array_t<float> output_array) {
    auto input_buf = input_array.request();
    auto output_buf = output_array.request();

    // Perform some basic checks
    if(input_buf.size != nfft_) {
      throw std::runtime_error("Input array size must match the NFFT size.");
    }
    if (input_buf.ndim != 1) {
      throw std::runtime_error("Input array must be 1-dimensional.");
    }
    if (output_buf.size < 3) {
      throw std::runtime_error("Output array must have at least 3 elements for "
                               "bass, mid, and treble.");
    }

    float *in_ptr = static_cast<float *>(input_buf.ptr);
    float *out_ptr = output_array.mutable_data();

    // Allocating KissFFT arrays
    std::vector<kiss_fft_cpx> cx_out(nfft_ / 2 + 1);

    // Running the FFT
    kiss_fftr(cfg_, in_ptr, cx_out.data());

    // Group the frequencies
    float bass = 0.0f, mid = 0.0f, treble = 0.0f;

    // kiss_fftr returns bins 0..nfft/2;
    for (int i = 1; i < nfft_ / 2; ++i) {
      // Calculate the magnitude (amplitude) of this specific frequency bin
      float magnitude =
          std::sqrt(cx_out[i].r * cx_out[i].r + cx_out[i].i * cx_out[i].i);

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
  }

private:
  int nfft_;
  kiss_fftr_cfg cfg_;
};

// Expose the function to Python
PYBIND11_MODULE(audio_dsp, m) {
  py::class_<SpectrumAnalyzer>(m, "SpectrumAnalyzer")
    .def(py::init<int>())
    .def("process", &SpectrumAnalyzer::process,
         py::arg("input_array"), py::arg("output_array").noconvert());


  m.doc() = "C++ Audio Processing Plugin using KissFFT";
}