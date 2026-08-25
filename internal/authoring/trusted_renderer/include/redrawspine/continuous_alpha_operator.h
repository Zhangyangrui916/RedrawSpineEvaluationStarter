#pragma once

#include "redrawspine/draw_packet.h"
#include "redrawspine/renderer.h"

#include <cstddef>
#include <vector>

namespace redrawspine {

struct ContinuousPageField {
    int page_index = -1;
    int width = 0;
    int height = 0;
    std::vector<float> rgb;
};

struct ContinuousOperatorStats {
    std::size_t fragment_samples = 0;
};

class ContinuousAlphaOperator {
public:
    static std::vector<ContinuousPageField> createPageFields(const std::vector<DrawPacket> &packets);

    ContinuousOperatorStats forward(const std::vector<DrawPacket> &packets, const RenderOptions &options,
                                    const std::vector<ContinuousPageField> &texture_rgb,
                                    std::vector<float> &screen_rgb) const;

    ContinuousOperatorStats adjoint(const std::vector<DrawPacket> &packets, const RenderOptions &options,
                                    const std::vector<float> &screen_rgb,
                                    std::vector<ContinuousPageField> &texture_rgb,
                                    bool accumulate = false) const;

    ContinuousOperatorStats coefficientEnergy(const std::vector<DrawPacket> &packets,
                                               const RenderOptions &options,
                                               std::vector<ContinuousPageField> &texture_rgb_energy,
                                               bool accumulate = false) const;
};

}  // namespace redrawspine
