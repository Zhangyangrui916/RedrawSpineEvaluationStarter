#pragma once

#include "redrawspine/draw_packet.h"
#include "redrawspine/renderer.h"

#include <cstddef>
#include <string>
#include <vector>

namespace redrawspine {

struct ContinuousCheckResult {
    std::size_t fragment_samples = 0;
    std::size_t compared_values = 0;
    double signal_rms_bytes = 0.0;
    double error_mae_bytes = 0.0;
    double error_rms_bytes = 0.0;
    double relative_rms = 0.0;
    double adjoint_left = 0.0;
    double adjoint_right = 0.0;
    double adjoint_relative_error = 0.0;
};

ContinuousCheckResult runContinuousCheck(const std::vector<DrawPacket> &source_packets,
                                         const std::vector<DrawPacket> &target_packets,
                                         const RenderOptions &options, ColorRenderer &renderer,
                                         const std::string &output_directory);

}  // namespace redrawspine
