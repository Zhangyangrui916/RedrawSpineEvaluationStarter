#include "redrawspine/continuous_alpha_analyzer.h"
#include "redrawspine/continuous_alpha_operator.h"

#include <stb_image_write.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace redrawspine {
ContinuousEnergyResult ContinuousAlphaAnalyzer::coefficientEnergy(const std::vector<DrawPacket> &packets,
                                                                  const RenderOptions &options) const {
    ContinuousAlphaOperator linear_operator;
    auto fields = ContinuousAlphaOperator::createPageFields(packets);
    const ContinuousOperatorStats operator_stats = linear_operator.coefficientEnergy(packets, options, fields);
    ContinuousEnergyResult result;
    result.screen_width = options.output_width;
    result.screen_height = options.output_height;
    result.fragment_samples = operator_stats.fragment_samples;
    for (const ContinuousPageField &field : fields) {
        PageCoefficientEnergy page;
        page.page_index = field.page_index;
        page.width = field.width;
        page.height = field.height;
        page.energy_rgb = field.rgb;
        page.energy.resize(static_cast<std::size_t>(page.width) * page.height);
        for (std::size_t texel = 0; texel < page.energy.size(); ++texel) {
            const float value = std::max({field.rgb[texel * 3], field.rgb[texel * 3 + 1],
                                          field.rgb[texel * 3 + 2]});
            page.energy[texel] = value;
            page.energy_sum += value;
            page.energy_max = std::max(page.energy_max, value);
            if (value > 0.0f) ++page.nonzero_texels;
        }
        result.pages.push_back(std::move(page));
    }
    return result;
}

void ContinuousAlphaAnalyzer::writeEnergy(const std::string &directory, const ContinuousEnergyResult &result) {
    namespace fs = std::filesystem;
    const fs::path output = fs::u8path(directory);
    fs::create_directories(output);

    std::ofstream manifest(output / "manifest.json", std::ios::binary);
    manifest << "{\n  \"screen_width\": " << result.screen_width << ",\n"
             << "  \"screen_height\": " << result.screen_height << ",\n"
             << "  \"fragment_samples\": " << result.fragment_samples << ",\n"
             << "  \"pages\": [\n";
    for (std::size_t index = 0; index < result.pages.size(); ++index) {
        const PageCoefficientEnergy &page = result.pages[index];
        std::ostringstream stem;
        stem << "page_" << std::setw(3) << std::setfill('0') << page.page_index;
        const fs::path raw_path = output / (stem.str() + ".energy.f32");
        std::ofstream raw(raw_path, std::ios::binary);
        raw.write(reinterpret_cast<const char *>(page.energy.data()),
                  static_cast<std::streamsize>(page.energy.size() * sizeof(float)));
        const fs::path rgb_raw_path = output / (stem.str() + ".energy_rgb.f32");
        std::ofstream rgb_raw(rgb_raw_path, std::ios::binary);
        rgb_raw.write(reinterpret_cast<const char *>(page.energy_rgb.data()),
                      static_cast<std::streamsize>(page.energy_rgb.size() * sizeof(float)));

        std::vector<std::uint8_t> preview(page.energy.size(), 0);
        if (page.energy_max > 0.0f) {
            for (std::size_t texel = 0; texel < page.energy.size(); ++texel) {
                const float normalized = std::sqrt(page.energy[texel] / page.energy_max);
                preview[texel] = static_cast<std::uint8_t>(std::lround(std::clamp(normalized, 0.0f, 1.0f) * 255.0f));
            }
        }
        const fs::path preview_path = output / (stem.str() + ".png");
        if (!stbi_write_png(preview_path.u8string().c_str(), page.width, page.height, 1, preview.data(), page.width)) {
            throw std::runtime_error("Unable to write continuous energy preview " + preview_path.u8string());
        }

        manifest << "    {\"page_index\": " << page.page_index << ", \"width\": " << page.width
                 << ", \"height\": " << page.height << ", \"energy_sum\": " << page.energy_sum
                 << ", \"energy_max\": " << page.energy_max << ", \"nonzero_texels\": "
                 << page.nonzero_texels << "}";
        manifest << (index + 1 == result.pages.size() ? "\n" : ",\n");
    }
    manifest << "  ]\n}\n";
}

}  // namespace redrawspine
