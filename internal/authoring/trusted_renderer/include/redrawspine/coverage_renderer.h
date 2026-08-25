#pragma once

#include "redrawspine/draw_packet.h"
#include "redrawspine/renderer.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace redrawspine {

struct PageCoverage {
    int page_index = -1;
    int width = 0;
    int height = 0;
    std::vector<std::uint8_t> mask;
    std::size_t covered_texels = 0;
};

struct CoverageResult {
    int screen_width = 0;
    int screen_height = 0;
    std::size_t owned_screen_pixels = 0;
    std::size_t reliable_screen_pixels = 0;
    std::vector<std::uint8_t> reliable_ownership;
    std::vector<PageCoverage> pages;
};

class CoverageRenderer {
public:
    CoverageRenderer();
    ~CoverageRenderer();

    CoverageRenderer(const CoverageRenderer &) = delete;
    CoverageRenderer &operator=(const CoverageRenderer &) = delete;

    CoverageResult render(const std::vector<DrawPacket> &packets, const RenderOptions &options,
                          int screen_boundary_radius = 2) const;
    static void writeMasks(const std::string &directory, const CoverageResult &coverage);

private:
    unsigned int compileShader(unsigned int type, const char *source) const;
    unsigned int createProgram() const;

    unsigned int program_ = 0;
    unsigned int vao_ = 0;
    unsigned int vbo_ = 0;
    unsigned int ebo_ = 0;
};

}  // namespace redrawspine
