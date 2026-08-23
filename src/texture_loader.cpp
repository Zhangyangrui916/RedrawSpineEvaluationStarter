#include "redrawspine/texture_loader.h"

#include <glad/glad.h>
#include <spine/Atlas.h>
#include <stb_image.h>

#include <stdexcept>
#include <string>

namespace redrawspine {

void OpenGLTextureLoader::load(spine::AtlasPage &page, const spine::String &path) {
    int width = 0;
    int height = 0;
    int channels = 0;
    stbi_set_flip_vertically_on_load(0);
    unsigned char *pixels = stbi_load(path.buffer(), &width, &height, &channels, STBI_rgb_alpha);
    if (!pixels) {
        throw std::runtime_error("Unable to load atlas page " + std::string(path.buffer()) + ": " +
                                 stbi_failure_reason());
    }

    auto *texture = new Texture();
    texture->width = width;
    texture->height = height;
    texture->pma = page.pma;

    glGenTextures(1, &texture->id);
    glBindTexture(GL_TEXTURE_2D, texture->id);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glBindTexture(GL_TEXTURE_2D, 0);
    stbi_image_free(pixels);

    page.width = width;
    page.height = height;
    page.texture = texture;
}

void OpenGLTextureLoader::unload(void *value) {
    auto *texture = static_cast<Texture *>(value);
    if (!texture) return;
    if (texture->id) glDeleteTextures(1, &texture->id);
    delete texture;
}

}  // namespace redrawspine
