#include <cmath>
#include <kiss_fft.h>
#include <kiss_fftr.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <stdexcept>
#include <vector>
#include <numbers>
#include <algorithm>

namespace py = pybind11;

class SpectrumAnalyzer {
public:
  SpectrumAnalyzer(int nfft, float sample_rate, int num_bands, float f_min, float f_max) {
    if(nfft % 2 != 0) {
      throw std::runtime_error("NFFT size must be even.");
    }

    if (f_max > sample_rate / 2) {
      throw std::runtime_error("f_max must be at most half the sample rate.");
    }

    nfft_ = nfft;
    num_bands_ = num_bands;

    cfg_ = kiss_fftr_alloc(nfft_, 0, nullptr, nullptr);

    window_.resize(nfft_);
    windowed_.resize(nfft_);
    cx_out_.resize(nfft_ / 2 + 1);
    band_edges_.resize(num_bands + 1);

    // Create a Hann window
    // w[n] = 0.5 · (1 − cos(2π · n / (N − 1)))
    float window_sum = 0.0f;
    for (int n = 0; n < nfft_; ++n) {
      window_[n] = 0.5f * (1.0f - std::cos(2.0f * std::numbers::pi_v<float> * static_cast<float>(n) / (nfft_ - 1)));
      window_sum += window_[n];
    }

    // Scale so a full-volume sine wave reads ~1.0 (0 dB), whatever nfft is
    scale_ = 2.0f / window_sum;

    // Log-spaced band edges: edge_hz[k] = f_min * (f_max / f_min)^(k / N)
    for (int k = 0; k <= num_bands_; ++k) {
      float fraction = static_cast<float>(k) / num_bands_;            // 0.0 … 1.0
      float edge_hz  = f_min * std::pow(f_max / f_min, fraction);     // 30 Hz … 16000 Hz
      band_edges_[k] = static_cast<int>(std::round(edge_hz * nfft_ / sample_rate));  // Hz → bin

      if (k > 0) {
        band_edges_[k] = std::max(band_edges_[k], band_edges_[k - 1] + 1);  // never an empty band
      }
    }

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
    if (output_buf.size < num_bands_) {
      throw std::runtime_error("Output array must have at least as many elements as there are frequency bands.");
    }

    float *in_ptr = static_cast<float *>(input_buf.ptr);
    float *out_ptr = output_array.mutable_data();

    // Apply the Hann window
    for (int i = 0; i < nfft_; ++i) {
      windowed_[i] = in_ptr[i] * window_[i];
    }

    // Running the FFT
    kiss_fftr(cfg_, windowed_.data(), cx_out_.data());

    // Average the magnitudes inside each band
    for (int b = 0; b < num_bands_; ++b) {
      int start = band_edges_[b];          // first bin of this band
      int end   = band_edges_[b + 1];      // first bin of the NEXT band (not included)

      float sum = 0.0f;
      for (int i = start; i < end; ++i) {
        float magnitude = std::sqrt(cx_out_[i].r * cx_out_[i].r + cx_out_[i].i * cx_out_[i].i);
        sum += magnitude;
      }

      // Average, scale, then convert to decibels: every ×10 in loudness = +20 dB.
      // + 1e-9f keeps silence finite (log10(0) would be -infinity).
      float average = sum / (end - start) * scale_;
      out_ptr[b] = 20.0f * std::log10(average + 1e-9f);

    }

  }

private:
  int nfft_;
  int num_bands_;
  float scale_;
  kiss_fftr_cfg cfg_;
  std::vector<float> window_;
  std::vector<float> windowed_;
  std::vector<kiss_fft_cpx> cx_out_;
  std::vector<int> band_edges_;
};

// Expose the function to Python
PYBIND11_MODULE(audio_dsp, m) {
  py::class_<SpectrumAnalyzer>(m, "SpectrumAnalyzer")
    .def(py::init<int, float, int, float, float>())
    .def("process", &SpectrumAnalyzer::process,
         py::arg("input_array"), py::arg("output_array").noconvert());


  m.doc() = "C++ Audio Processing Plugin using KissFFT";
}