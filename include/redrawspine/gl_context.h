#pragma once

#include <string>

struct GLFWwindow;

namespace redrawspine {

class GlContext {
public:
    GlContext();
    ~GlContext();

    GlContext(const GlContext &) = delete;
    GlContext &operator=(const GlContext &) = delete;

    const std::string &backend() const { return backend_; }

private:
    bool tryCreate(const std::string &backend);

    GLFWwindow *window_ = nullptr;
    std::string backend_;
};

}  // namespace redrawspine
