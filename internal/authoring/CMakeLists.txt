cmake_minimum_required(VERSION 3.20)
project(redrawspine-evaluation-authoring VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/utf-8)
    add_compile_definitions(NOMINMAX _CRT_SECURE_NO_WARNINGS)
endif()

set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_INSTALL OFF CACHE BOOL "" FORCE)
if(UNIX AND NOT APPLE)
    set(GLFW_BUILD_X11 OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_WAYLAND OFF CACHE BOOL "" FORCE)
endif()
add_subdirectory(third_party/glfw)

find_package(OpenGL REQUIRED)

add_library(glad STATIC third_party/glad/src/glad.c)
target_include_directories(glad PUBLIC third_party/glad/include)

add_library(stb STATIC third_party/stb/stb_image.cpp)
target_include_directories(stb PUBLIC third_party/stb)

file(GLOB_RECURSE SPINE_CPP_SOURCES CONFIGURE_DEPENDS
    third_party/spine-runtimes/spine-cpp/spine-cpp/src/spine/*.cpp
)
file(GLOB_RECURSE SPINE_CPP_HEADERS CONFIGURE_DEPENDS
    third_party/spine-runtimes/spine-cpp/spine-cpp/include/spine/*.h
)
add_library(spine-cpp STATIC ${SPINE_CPP_SOURCES} ${SPINE_CPP_HEADERS})
target_include_directories(spine-cpp PUBLIC
    third_party/spine-runtimes/spine-cpp/spine-cpp/include
)

add_library(trusted_renderer_core STATIC
    trusted_renderer/src/continuous_alpha_check.cpp
    trusted_renderer/src/continuous_alpha_analyzer.cpp
    trusted_renderer/src/continuous_alpha_operator.cpp
    trusted_renderer/src/coverage_renderer.cpp
    trusted_renderer/src/gl_context.cpp
    trusted_renderer/src/renderer.cpp
    trusted_renderer/src/spine_asset.cpp
    trusted_renderer/src/texture_loader.cpp
)
target_include_directories(trusted_renderer_core PUBLIC trusted_renderer/include)
target_link_libraries(trusted_renderer_core PUBLIC spine-cpp PRIVATE glad glfw stb OpenGL::GL)

add_executable(trusted-render
    trusted_renderer/src/main.cpp
    trusted_renderer/src/spine_extension.cpp
)
target_link_libraries(trusted-render PRIVATE trusted_renderer_core)

add_executable(continuous-baseline
    trusted_renderer/src/continuous_baseline_main.cpp
    trusted_renderer/src/spine_extension.cpp
)
target_include_directories(continuous-baseline PRIVATE third_party/stb)
target_link_libraries(continuous-baseline PRIVATE trusted_renderer_core)

include(CTest)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(
    NAME authoring_contract
    COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/author_tests/test_contract.py
        --root ${CMAKE_CURRENT_SOURCE_DIR}
        --renderer $<TARGET_FILE:trusted-render>
        --work ${CMAKE_CURRENT_BINARY_DIR}/authoring-contract-output
)
