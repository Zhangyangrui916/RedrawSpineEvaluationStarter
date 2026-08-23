#include "redrawspine/gl_context.h"

#include <glad/glad.h>
#include <GLFW/glfw3.h>

#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

namespace redrawspine {
namespace {

std::string glfwError() {
    const char *description = nullptr;
    const int code = glfwGetError(&description);
    return "GLFW error " + std::to_string(code) + ": " + (description ? description : "unknown");
}

}  // namespace

GlContext::GlContext() {
    const char *requested = std::getenv("REDRAWSPINE_GL_BACKEND");
    std::vector<std::string> candidates;
    if (requested && std::string(requested) != "auto") {
        candidates.emplace_back(requested);
    } else {
#if defined(__linux__)
        candidates = {"egl", "osmesa", "native"};
#else
        candidates = {"native"};
#endif
    }

    std::string failures;
    for (const std::string &candidate : candidates) {
        if (tryCreate(candidate)) return;
        if (!failures.empty()) failures += "; ";
        failures += candidate + "=" + glfwError();
    }
    throw std::runtime_error("Unable to create an OpenGL context: " + failures);
}

GlContext::~GlContext() {
    if (window_) glfwDestroyWindow(window_);
    glfwTerminate();
}

bool GlContext::tryCreate(const std::string &backend) {
    glfwTerminate();

#if defined(__linux__)
    glfwInitHint(GLFW_PLATFORM, backend == "native" ? GLFW_PLATFORM_ANY : GLFW_PLATFORM_NULL);
#endif
    if (!glfwInit()) return false;

    glfwDefaultWindowHints();
    glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_CLIENT_API, GLFW_OPENGL_API);
    if (backend == "egl") {
        glfwWindowHint(GLFW_CONTEXT_CREATION_API, GLFW_EGL_CONTEXT_API);
    } else if (backend == "osmesa") {
        glfwWindowHint(GLFW_CONTEXT_CREATION_API, GLFW_OSMESA_CONTEXT_API);
    } else if (backend != "native") {
        glfwTerminate();
        return false;
    }

    window_ = glfwCreateWindow(1, 1, "RedrawSpine headless renderer", nullptr, nullptr);
    if (!window_) {
        glfwTerminate();
        return false;
    }
    glfwMakeContextCurrent(window_);
    if (!gladLoadGLLoader(reinterpret_cast<GLADloadproc>(glfwGetProcAddress))) {
        glfwDestroyWindow(window_);
        window_ = nullptr;
        glfwTerminate();
        return false;
    }
    backend_ = backend;
    return true;
}

}  // namespace redrawspine
