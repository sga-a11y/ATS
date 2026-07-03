cmake_minimum_required(VERSION 3.22.1)
project(tsbot_protocol)

add_library(tsbot_protocol SHARED
    protocol.cpp
    protocol_jni.cpp
)

find_library(log-lib log)
target_link_libraries(tsbot_protocol ${log-lib})
target_compile_features(tsbot_protocol PUBLIC cxx_std_17)
