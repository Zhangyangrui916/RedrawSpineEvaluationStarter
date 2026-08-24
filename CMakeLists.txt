cmake_minimum_required(VERSION 3.20)
project(redrawspine-evaluation-starter VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(
    REDRAWSPINE_STARTER_TESTS
    "Enable the candidate-visible pristine starter preflight"
    OFF
)
option(
    REDRAWSPINE_AUTHOR_TESTS
    "Enable the maintainer-only source packaging audit"
    OFF
)

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

add_library(redrawspine_forward STATIC
    src/gl_context.cpp
    src/renderer.cpp
    src/spine_asset.cpp
    src/texture_loader.cpp
)
target_include_directories(redrawspine_forward PUBLIC include)
target_link_libraries(redrawspine_forward PUBLIC spine-cpp PRIVATE glad glfw stb OpenGL::GL)

# getDefaultExtension() is an application integration point. Compile it into
# the final executable instead of a static archive so GNU ld does not miss it
# during its single-pass archive scan.
add_executable(redrawspine-render
    src/render_main.cpp
    src/spine_extension.cpp
)
target_link_libraries(redrawspine-render PRIVATE redrawspine_forward)

add_executable(redrawspine-reconstruct
    src/reconstruct_main.cpp
    src/spine_extension.cpp
)
target_link_libraries(redrawspine-reconstruct PRIVATE redrawspine_forward stb)

# Pristine starter checks are opt-in because a valid candidate may repurpose or
# replace the supplied renderer after running the environment preflight.
if(REDRAWSPINE_STARTER_TESTS OR REDRAWSPINE_AUTHOR_TESTS)
    include(CTest)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
endif()

if(REDRAWSPINE_STARTER_TESTS)
    add_test(
        NAME starter_preflight
        COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/public_smoke.py
            --render $<TARGET_FILE:redrawspine-render>
            --reconstruct $<TARGET_FILE:redrawspine-reconstruct>
            --case ${CMAKE_CURRENT_SOURCE_DIR}/assets/public_static_mesh_smoke
            --work ${CMAKE_CURRENT_BINARY_DIR}/starter-preflight-output
    )
endif()

if(REDRAWSPINE_AUTHOR_TESTS)
    add_test(
        NAME starter_source_only_audit
        COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/source_only_audit.py
            --root ${CMAKE_CURRENT_SOURCE_DIR}
    )
endif()
