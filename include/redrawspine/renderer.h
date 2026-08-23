#pragma once

#include "redrawspine/draw_packet.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace redrawspine {

struct RenderOptions {
    int output_width = 768;
    int output_height = 596;
    float viewport_x = -1300.0f;
    float viewport_y = -650.0f;
    float viewport_width = 2450.0f;
    float viewport_height = 1900.0f;
};

struct RenderStats {
    std::size_t draw_packets = 0;
    std::size_t nonzero_alpha_pixels = 0;
    int bbox_left = -1;
    int bbox_top = -1;
    int bbox_right = -1;
    int bbox_bottom = -1;
};

class ColorRenderer {
public:
    ColorRenderer();
    ~ColorRenderer();

    ColorRenderer(const ColorRenderer &) = delete;
    ColorRenderer &operator=(const ColorRenderer &) = delete;

    std::vector<std::uint8_t> render(const std::vector<DrawPacket> &packets, const RenderOptions &options);
    static RenderStats computeStats(const std::vector<std::uint8_t> &pixels, int width, int height,
                                    std::size_t draw_packets);
    static void writePngAtomic(const std::string &path, const std::vector<std::uint8_t> &pixels, int width,
                               int height);

private:
    unsigned int compileShader(unsigned int type, const char *source);
    unsigned int createProgram();
    void ensureTarget(int width, int height);

    unsigned int program_ = 0;
    unsigned int vao_ = 0;
    unsigned int vbo_ = 0;
    unsigned int ebo_ = 0;
    unsigned int framebuffer_ = 0;
    unsigned int color_texture_ = 0;
    int target_width_ = 0;
    int target_height_ = 0;
};

}  // namespace redrawspine
