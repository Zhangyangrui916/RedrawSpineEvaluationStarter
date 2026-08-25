#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace redrawspine {

struct Color {
    float r = 1.0f;
    float g = 1.0f;
    float b = 1.0f;
    float a = 1.0f;
};

struct DrawPacket {
    std::string slot_name;
    std::string attachment_name;
    std::vector<float> positions;
    std::vector<float> uvs;
    std::vector<std::uint16_t> indices;
    Color color;
    unsigned int texture_id = 0;
    int page_index = -1;
    int texture_width = 0;
    int texture_height = 0;
    std::string texture_path;
    const std::uint8_t *texture_rgba = nullptr;
};

}  // namespace redrawspine
