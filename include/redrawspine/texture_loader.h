#pragma once

#include <spine/TextureLoader.h>

namespace redrawspine {

struct Texture {
    unsigned int id = 0;
    int width = 0;
    int height = 0;
    bool pma = false;
};

class OpenGLTextureLoader final : public spine::TextureLoader {
public:
    void load(spine::AtlasPage &page, const spine::String &path) override;
    void unload(void *texture) override;
};

}  // namespace redrawspine
