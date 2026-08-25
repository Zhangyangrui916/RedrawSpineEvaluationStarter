#include "redrawspine/coverage_renderer.h"

#include <glad/glad.h>
#include <stb_image_write.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace redrawspine {
namespace {

struct Vertex {
    float x;
    float y;
    float u;
    float v;
};

constexpr const char *kVertexShader = R"GLSL(
#version 330 core
layout(location = 0) in vec2 a_position;
layout(location = 1) in vec2 a_uv;

uniform vec4 u_viewport;

out vec2 v_uv;

void main() {
    vec2 normalized = (a_position - u_viewport.xy) / u_viewport.zw;
    gl_Position = vec4(normalized * 2.0 - 1.0, 0.0, 1.0);
    v_uv = a_uv;
}
)GLSL";

constexpr const char *kFragmentShader = R"GLSL(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform uint u_page_id;

layout(location = 0) out uint out_page_id;
layout(location = 1) out vec2 out_uv;

void main() {
    if (texture(u_texture, v_uv).a < 0.99) discard;
    out_page_id = u_page_id;
    out_uv = v_uv;
}
)GLSL";

void flipRows(std::vector<std::uint32_t> &values, int width, int height) {
    for (int y = 0; y < height / 2; ++y) {
        auto top = values.begin() + static_cast<std::ptrdiff_t>(y) * width;
        auto bottom = values.begin() + static_cast<std::ptrdiff_t>(height - 1 - y) * width;
        std::swap_ranges(top, top + width, bottom);
    }
}

void flipRows(std::vector<float> &values, int width, int height) {
    const int stride = width * 2;
    for (int y = 0; y < height / 2; ++y) {
        auto top = values.begin() + static_cast<std::ptrdiff_t>(y) * stride;
        auto bottom = values.begin() + static_cast<std::ptrdiff_t>(height - 1 - y) * stride;
        std::swap_ranges(top, top + stride, bottom);
    }
}

}  // namespace

CoverageRenderer::CoverageRenderer() {
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
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(Vertex), reinterpret_cast<void *>(2 * sizeof(float)));
    glBindVertexArray(0);
}

CoverageRenderer::~CoverageRenderer() {
    if (ebo_) glDeleteBuffers(1, &ebo_);
    if (vbo_) glDeleteBuffers(1, &vbo_);
    if (vao_) glDeleteVertexArrays(1, &vao_);
    if (program_) glDeleteProgram(program_);
}

unsigned int CoverageRenderer::compileShader(unsigned int type, const char *source) const {
    const unsigned int shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, nullptr);
    glCompileShader(shader);
    int success = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        std::array<char, 4096> log{};
        glGetShaderInfoLog(shader, static_cast<int>(log.size()), nullptr, log.data());
        glDeleteShader(shader);
        throw std::runtime_error("Coverage shader compilation failed: " + std::string(log.data()));
    }
    return shader;
}

unsigned int CoverageRenderer::createProgram() const {
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
        throw std::runtime_error("Coverage program linking failed: " + std::string(log.data()));
    }
    return program;
}

CoverageResult CoverageRenderer::render(const std::vector<DrawPacket> &packets, const RenderOptions &options,
                                        int screen_boundary_radius) const {
    if (screen_boundary_radius < 0) throw std::invalid_argument("Boundary radius must be non-negative");

    unsigned int framebuffer = 0;
    unsigned int id_texture = 0;
    unsigned int uv_texture = 0;
    glGenFramebuffers(1, &framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);

    glGenTextures(1, &id_texture);
    glBindTexture(GL_TEXTURE_2D, id_texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, options.output_width, options.output_height, 0, GL_RED_INTEGER,
                 GL_UNSIGNED_INT, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, id_texture, 0);

    glGenTextures(1, &uv_texture);
    glBindTexture(GL_TEXTURE_2D, uv_texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RG32F, options.output_width, options.output_height, 0, GL_RG, GL_FLOAT,
                 nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, uv_texture, 0);

    const unsigned int draw_buffers[] = {GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1};
    glDrawBuffers(2, draw_buffers);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        throw std::runtime_error("Coverage framebuffer is incomplete");
    }

    glViewport(0, 0, options.output_width, options.output_height);
    glDisable(GL_BLEND);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glDisable(GL_DITHER);
    const unsigned int zero_id[] = {0, 0, 0, 0};
    const float zero_uv[] = {0, 0, 0, 0};
    glClearBufferuiv(GL_COLOR, 0, zero_id);
    glClearBufferfv(GL_COLOR, 1, zero_uv);

    glUseProgram(program_);
    glUniform4f(glGetUniformLocation(program_, "u_viewport"), options.viewport_x, options.viewport_y,
                options.viewport_width, options.viewport_height);
    glUniform1i(glGetUniformLocation(program_, "u_texture"), 0);
    glBindVertexArray(vao_);

    std::map<int, std::pair<int, int>> page_sizes;
    for (const DrawPacket &packet : packets) {
        if (packet.page_index < 0) throw std::runtime_error("Draw packet has no atlas page index");
        page_sizes[packet.page_index] = {packet.texture_width, packet.texture_height};
        const std::size_t vertex_count = packet.positions.size() / 2;
        std::vector<Vertex> vertices(vertex_count);
        for (std::size_t index = 0; index < vertex_count; ++index) {
            vertices[index] = {packet.positions[index * 2], packet.positions[index * 2 + 1], packet.uvs[index * 2],
                               packet.uvs[index * 2 + 1]};
        }
        glBindBuffer(GL_ARRAY_BUFFER, vbo_);
        glBufferData(GL_ARRAY_BUFFER, static_cast<long long>(vertices.size() * sizeof(Vertex)), vertices.data(),
                     GL_STREAM_DRAW);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                     static_cast<long long>(packet.indices.size() * sizeof(std::uint16_t)), packet.indices.data(),
                     GL_STREAM_DRAW);
        glUniform1ui(glGetUniformLocation(program_, "u_page_id"), static_cast<unsigned int>(packet.page_index + 1));
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, packet.texture_id);
        glDrawElements(GL_TRIANGLES, static_cast<int>(packet.indices.size()), GL_UNSIGNED_SHORT, nullptr);
    }

    const std::size_t pixel_count = static_cast<std::size_t>(options.output_width) * options.output_height;
    std::vector<std::uint32_t> ids(pixel_count);
    std::vector<float> uvs(pixel_count * 2);
    glReadBuffer(GL_COLOR_ATTACHMENT0);
    glReadPixels(0, 0, options.output_width, options.output_height, GL_RED_INTEGER, GL_UNSIGNED_INT, ids.data());
    glReadBuffer(GL_COLOR_ATTACHMENT1);
    glReadPixels(0, 0, options.output_width, options.output_height, GL_RG, GL_FLOAT, uvs.data());
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glDeleteTextures(1, &uv_texture);
    glDeleteTextures(1, &id_texture);
    glDeleteFramebuffers(1, &framebuffer);

    flipRows(ids, options.output_width, options.output_height);
    flipRows(uvs, options.output_width, options.output_height);

    CoverageResult result;
    result.screen_width = options.output_width;
    result.screen_height = options.output_height;
    result.reliable_ownership.resize(pixel_count, 0);
    std::map<int, std::size_t> page_to_result;
    for (const auto &[page_index, size] : page_sizes) {
        PageCoverage page;
        page.page_index = page_index;
        page.width = size.first;
        page.height = size.second;
        page.mask.resize(static_cast<std::size_t>(page.width) * page.height, 0);
        page_to_result[page_index] = result.pages.size();
        result.pages.push_back(std::move(page));
    }

    for (int y = 0; y < options.output_height; ++y) {
        for (int x = 0; x < options.output_width; ++x) {
            const std::size_t pixel = static_cast<std::size_t>(y) * options.output_width + x;
            const std::uint32_t encoded = ids[pixel];
            if (encoded == 0) continue;
            ++result.owned_screen_pixels;

            bool reliable = true;
            for (int dy = -screen_boundary_radius; dy <= screen_boundary_radius && reliable; ++dy) {
                for (int dx = -screen_boundary_radius; dx <= screen_boundary_radius; ++dx) {
                    const int nx = x + dx;
                    const int ny = y + dy;
                    if (nx < 0 || ny < 0 || nx >= options.output_width || ny >= options.output_height ||
                        ids[static_cast<std::size_t>(ny) * options.output_width + nx] != encoded) {
                        reliable = false;
                        break;
                    }
                }
            }
            if (!reliable) continue;
            ++result.reliable_screen_pixels;
            result.reliable_ownership[pixel] = static_cast<std::uint8_t>(encoded);

            const int page_index = static_cast<int>(encoded - 1);
            PageCoverage &page = result.pages[page_to_result.at(page_index)];
            const float u = std::clamp(uvs[pixel * 2], 0.0f, std::nextafter(1.0f, 0.0f));
            const float v = std::clamp(uvs[pixel * 2 + 1], 0.0f, std::nextafter(1.0f, 0.0f));
            const float sample_x = u * page.width - 0.5f;
            const float sample_y = v * page.height - 0.5f;
            const int x0 = static_cast<int>(std::floor(sample_x));
            const int y0 = static_cast<int>(std::floor(sample_y));
            for (int ty : {y0, y0 + 1}) {
                for (int tx : {x0, x0 + 1}) {
                    if (tx >= 0 && ty >= 0 && tx < page.width && ty < page.height) {
                        page.mask[static_cast<std::size_t>(ty) * page.width + tx] = 255;
                    }
                }
            }
        }
    }
    for (PageCoverage &page : result.pages) {
        page.covered_texels = static_cast<std::size_t>(std::count(page.mask.begin(), page.mask.end(), 255));
    }
    return result;
}

void CoverageRenderer::writeMasks(const std::string &directory, const CoverageResult &coverage) {
    namespace fs = std::filesystem;
    const fs::path output = fs::u8path(directory);
    fs::create_directories(output);
    const fs::path ownership_path = output / "ownership.png";
    if (!stbi_write_png(ownership_path.u8string().c_str(), coverage.screen_width, coverage.screen_height, 1,
                        coverage.reliable_ownership.data(), coverage.screen_width)) {
        throw std::runtime_error("Unable to write ownership map: " + ownership_path.u8string());
    }
    for (const PageCoverage &page : coverage.pages) {
        std::ostringstream name;
        name << "page_" << std::setw(3) << std::setfill('0') << page.page_index << ".png";
        const fs::path path = output / name.str();
        if (!stbi_write_png(path.u8string().c_str(), page.width, page.height, 1, page.mask.data(), page.width)) {
            throw std::runtime_error("Unable to write coverage mask: " + path.u8string());
        }
    }
}

}  // namespace redrawspine
