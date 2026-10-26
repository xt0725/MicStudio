cmake_minimum_required(VERSION 3.20)
project(MicStudioRNNoise C)
set(RN_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/rnnoise")
add_library(rnnoise SHARED
  ${RN_ROOT}/src/denoise.c ${RN_ROOT}/src/rnn.c ${RN_ROOT}/src/rnn_data.c
  ${RN_ROOT}/src/pitch.c ${RN_ROOT}/src/celt_lpc.c ${RN_ROOT}/src/kiss_fft.c)
target_include_directories(rnnoise PRIVATE ${RN_ROOT}/src ${RN_ROOT}/include)
target_compile_definitions(rnnoise PRIVATE RNNOISE_BUILD DLL_EXPORT _USE_MATH_DEFINES)
set_target_properties(rnnoise PROPERTIES C_STANDARD 11)
if(MSVC)
  target_compile_options(rnnoise PRIVATE /O2 /wd4244 /wd4305)
else()
  target_link_libraries(rnnoise PRIVATE m)
endif()
