cmake_minimum_required(VERSION 3.15)

# Set vcpkg toolchain before project() if not passed via command line
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
    set(CMAKE_TOOLCHAIN_FILE "$ENV{USERPROFILE}/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "vcpkg toolchain file")
endif()

project(AudioDSP LANGUAGES CXX C)

# Defining C++ version
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 1. Find the packages downloaded by vcpkg
find_package(pybind11 CONFIG REQUIRED)
find_package(kissfft CONFIG REQUIRED)

# 2. Tell Pybind11 to create a Python module from our C++ file
pybind11_add_module(audio_dsp src_cpp/audio_dsp.cpp)

# 3. Link KissFFT to our new module
target_link_libraries(audio_dsp PRIVATE kissfft::kissfft-float)

# cmake -B build \
#   -DCMAKE_TOOLCHAIN_FILE=$HOME/vcpkg/scripts/buildsystems/vcpkg.cmake \
#   -Dpybind11_DIR=$(uv run python -m pybind11 --cmakedir) \
#   -DCMAKE_BUILD_TYPE=Release