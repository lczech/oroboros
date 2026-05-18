cmake_minimum_required(VERSION 3.20)

project(cosmos LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(
    cosmos STATIC
    src/functions.cpp
    src/objects.cpp
)

target_include_directories(
    cosmos
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/inc
)

target_compile_features(cosmos PUBLIC cxx_std_20)

add_executable(
    cosmos_app
    src/main.cpp
)

target_link_libraries(
    cosmos_app
    PRIVATE
        cosmos
)
