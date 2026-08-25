#include "redrawspine/renderer.h"

#include <glad/glad.h>
#include <stb_image_write.h>

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace redrawspine {
namespace {

struct Vertex {
    float x;
    float y;
    float r;
    float g;
    float b;
    float a;
    float u;
    float v;
};

constexpr const char *kVertexShader = R"GLSL(
#version 330 core
layout(location = 0) in vec2 a_position;
layout(location = 1) in vec4 a_color;
layout(location = 2) in vec2 a_uv;

uniform vec4 u_viewport;

out vec4 v_color;
out vec2 v_uv;

void main() {
    vec2 normalized = (a_position - u_viewport.xy) / u_viewport.zw;
    gl_Position = vec4(normalized * 2.0 - 1.0, 0.0, 1.0);
    v_color = a_color;
    v_uv = a_uv;
}
)GLSL";

constexpr const char *kFragmentShader = R"GLSL(
#version 330 core
in vec4 v_color;
in vec2 v_uv;

uniform sampler2D u_texture;

out vec4 frag_color;

void main() {
    frag_color = v_color * texture(u_texture, v_uv);
}
)GLSL";

}  // namespace

ColorRenderer::ColorRenderer() {
    program_ = createProgram();
    glGenVertexArrays(1, &vao_);
    glGenBuffers(1, &vbo_);
    glGenBuffers(1, &ebo_);

    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, sizeof(Vertex), reinterpret_cast<void *>(0));
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, sizeof(Vertex), reinterpret_cast<void *>(2 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, sizeof(Vertex), reinterpret_cast<void *>(6 * sizeof(float)));
    glBindVertexArray(0);

    glGenFramebuffers(1, &framebuffer_);
    glGenTextures(1, &color_texture_);
}

ColorRenderer::~ColorRenderer() {
    if (color_texture_) glDeleteTextures(1, &color_texture_);
    if (framebuffer_) glDeleteFramebuffers(1, &framebuffer_);
    if (ebo_) glDeleteBuffers(1, &ebo_);
    if (vbo_) glDeleteBuffers(1, &vbo_);
    if (vao_) glDeleteVertexArrays(1, &vao_);
    if (program_) glDeleteProgram(program_);
}

unsigned int ColorRenderer::compileShader(unsigned int type, const char *source) {
    const unsigned int shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, nullptr);
    glCompileShader(shader);
    int success = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        std::array<char, 4096> log{};
        glGetShaderInfoLog(shader, static_cast<int>(log.size()), nullptr, log.data());
        glDeleteShader(shader);
        throw std::runtime_error("OpenGL shader compilation failed: " + std::string(log.data()));
    }
    return shader;
}

unsigned int ColorRenderer::createProgram() {
    const unsigned int vertex = compileShader(GL_VERTEX_SHADER, kVertexShader);
    const unsigned int fragment = compileShader(GL_FRAGMENT_SHADER, kFragmentShader);
    const unsigned int program = glCreateProgram();
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glLinkProgram(program);
    glDeleteShader(vertex);
    glDeleteShader(fragment);

    int success = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &success);
    if (!success) {
        std::array<char, 4096> log{};
        glGetProgramInfoLog(program, static_cast<int>(log.size()), nullptr, log.data());
        glDeleteProgram(program);
        throw std::runtime_error("OpenGL program linking failed: " + std::string(log.data()));
    }
    return program;
}

void ColorRenderer::ensureTarget(int width, int height) {
    if (width == target_width_ && height == target_height_) return;
    glBindTexture(GL_TEXTURE_2D, color_texture_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color_texture_, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        throw std::runtime_error("OpenGL framebuffer is incomplete");
    }
    target_width_ = width;
    target_height_ = height;
}

std::vector<std::uint8_t> ColorRenderer::render(const std::vector<DrawPacket> &packets,
                                                const RenderOptions &options) {
    if (options.output_width <= 0 || options.output_height <= 0 || options.viewport_width <= 0.0f ||
        options.viewport_height <= 0.0f) {
        throw std::invalid_argument("Output and viewport dimensions must be positive");
    }
    ensureTarget(options.output_width, options.output_height);

    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);
    glViewport(0, 0, options.output_width, options.output_height);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glDisable(GL_DITHER);
    glDisable(GL_MULTISAMPLE);
    glEnable(GL_BLEND);
    glBlendEquation(GL_FUNC_ADD);
    glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
    glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
    glClear(GL_COLOR_BUFFER_BIT);

    glUseProgram(program_);
    glUniform4f(glGetUniformLocation(program_, "u_viewport"), options.viewport_x, options.viewport_y,
                options.viewport_width, options.viewport_height);
    glUniform1i(glGetUniformLocation(program_, "u_texture"), 0);
    glBindVertexArray(vao_);

    for (const DrawPacket &packet : packets) {
        const std::size_t vertex_count = packet.positions.size() / 2;
        std::vector<Vertex> vertices(vertex_count);
        for (std::size_t i = 0; i < vertex_count; ++i) {
            vertices[i] = {packet.positions[i * 2], packet.positions[i * 2 + 1], packet.color.r, packet.color.g,
                           packet.color.b, packet.color.a, packet.uvs[i * 2], packet.uvs[i * 2 + 1]};
        }
        glBindBuffer(GL_ARRAY_BUFFER, vbo_);
        glBufferData(GL_ARRAY_BUFFER, static_cast<long long>(vertices.size() * sizeof(Vertex)), vertices.data(),
                     GL_STREAM_DRAW);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                     static_cast<long long>(packet.indices.size() * sizeof(std::uint16_t)), packet.indices.data(),
                     GL_STREAM_DRAW);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, packet.texture_id);
        glDrawElements(GL_TRIANGLES, static_cast<int>(packet.indices.size()), GL_UNSIGNED_SHORT, nullptr);
    }

    std::vector<std::uint8_t> pixels(static_cast<std::size_t>(options.output_width) * options.output_height * 4);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glReadPixels(0, 0, options.output_width, options.output_height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    const std::size_t row_bytes = static_cast<std::size_t>(options.output_width) * 4;
    std::vector<std::uint8_t> row(row_bytes);
    for (int y = 0; y < options.output_height / 2; ++y) {
        std::uint8_t *top = pixels.data() + static_cast<std::size_t>(y) * row_bytes;
        std::uint8_t *bottom = pixels.data() + static_cast<std::size_t>(options.output_height - 1 - y) * row_bytes;
        std::copy(top, top + row_bytes, row.data());
        std::copy(bottom, bottom + row_bytes, top);
        std::copy(row.data(), row.data() + row_bytes, bottom);
    }
    return pixels;
}

RenderStats ColorRenderer::computeStats(const std::vector<std::uint8_t> &pixels, int width, int height,
                                        std::size_t draw_packets) {
    RenderStats stats;
    stats.draw_packets = draw_packets;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const std::size_t index = (static_cast<std::size_t>(y) * width + x) * 4;
            if (pixels[index + 3] == 0) continue;
            ++stats.nonzero_alpha_pixels;
            if (stats.bbox_left < 0) {
                stats.bbox_left = stats.bbox_right = x;
                stats.bbox_top = stats.bbox_bottom = y;
            } else {
                stats.bbox_left = std::min(stats.bbox_left, x);
                stats.bbox_right = std::max(stats.bbox_right, x);
                stats.bbox_top = std::min(stats.bbox_top, y);
                stats.bbox_bottom = std::max(stats.bbox_bottom, y);
            }
        }
    }
    return stats;
}

void ColorRenderer::writePngAtomic(const std::string &path, const std::vector<std::uint8_t> &pixels, int width,
                                   int height) {
    namespace fs = std::filesystem;
    const fs::path output = fs::u8path(path);
    if (!output.parent_path().empty()) fs::create_directories(output.parent_path());
    fs::path temporary = output;
    temporary += ".tmp.png";
    if (!stbi_write_png(temporary.u8string().c_str(), width, height, 4, pixels.data(), width * 4)) {
        throw std::runtime_error("Unable to write PNG: " + output.u8string());
    }
    std::error_code error;
    fs::remove(output, error);
    error.clear();
    fs::rename(temporary, output, error);
    if (error) {
        fs::remove(temporary);
        throw std::runtime_error("Unable to finalize PNG " + output.u8string() + ": " + error.message());
    }
}

}  // namespace redrawspine
