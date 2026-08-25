#pragma once

#include <spine/TextureLoader.h>

#include <cstdint>
#include <string>
#include <vector>

namespace redrawspine {

struct Texture {
    unsigned int id = 0;
    int width = 0;
    int height = 0;
    bool pma = false;
    int page_index = -1;
    std::string path;
    std::vector<std::uint8_t> rgba;
};

class OpenGLTextureLoader final : public spine::TextureLoader {
public:
    void load(spine::AtlasPage &page, const spine::String &path) override;
    void unload(void *texture) override;
};

}  // namespace redrawspine
