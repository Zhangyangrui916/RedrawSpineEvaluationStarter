#pragma once

#include "redrawspine/draw_packet.h"
#include "redrawspine/renderer.h"

#include <cstddef>
#include <string>
#include <vector>

namespace redrawspine {

struct PageCoefficientEnergy {
    int page_index = -1;
    int width = 0;
    int height = 0;
    std::vector<float> energy_rgb;
    std::vector<float> energy;
    double energy_sum = 0.0;
    float energy_max = 0.0f;
    std::size_t nonzero_texels = 0;
};

struct ContinuousEnergyResult {
    int screen_width = 0;
    int screen_height = 0;
    std::size_t fragment_samples = 0;
    std::vector<PageCoefficientEnergy> pages;
};

class ContinuousAlphaAnalyzer {
public:
    ContinuousEnergyResult coefficientEnergy(const std::vector<DrawPacket> &packets,
                                             const RenderOptions &options) const;
    static void writeEnergy(const std::string &directory, const ContinuousEnergyResult &result);
};

}  // namespace redrawspine
