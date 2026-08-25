#include "redrawspine/continuous_alpha_check.h"

#include "redrawspine/continuous_alpha_operator.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <stdexcept>

namespace redrawspine {
namespace {

std::map<int, const DrawPacket *> uniquePages(const std::vector<DrawPacket> &packets) {
    std::map<int, const DrawPacket *> result;
    for (const DrawPacket &packet : packets) {
        const auto [iterator, inserted] = result.emplace(packet.page_index, &packet);
        if (!inserted && (iterator->second->texture_width != packet.texture_width ||
                          iterator->second->texture_height != packet.texture_height)) {
            throw std::runtime_error("Inconsistent page dimensions in continuous check");
        }
    }
    return result;
}

std::vector<std::uint8_t> reconstructedImage(const std::vector<std::uint8_t> &source,
                                             const std::vector<float> &delta) {
    std::vector<std::uint8_t> result = source;
    for (std::size_t pixel = 0; pixel < delta.size() / 3; ++pixel) {
        for (int channel = 0; channel < 3; ++channel) {
            const float value = source[pixel * 4 + channel] + delta[pixel * 3 + channel] * 255.0f;
            result[pixel * 4 + channel] =
                static_cast<std::uint8_t>(std::lround(std::clamp(value, 0.0f, 255.0f)));
        }
    }
    return result;
}

std::vector<std::uint8_t> errorImage(const std::vector<std::uint8_t> &target,
                                     const std::vector<std::uint8_t> &prediction) {
    std::vector<std::uint8_t> result(target.size(), 255);
    for (std::size_t pixel = 0; pixel < target.size() / 4; ++pixel) {
        for (int channel = 0; channel < 3; ++channel) {
            const int difference = std::abs(static_cast<int>(target[pixel * 4 + channel]) -
                                            static_cast<int>(prediction[pixel * 4 + channel]));
            result[pixel * 4 + channel] = static_cast<std::uint8_t>(std::min(255, difference * 8));
        }
        result[pixel * 4 + 3] = 255;
    }
    return result;
}

}  // namespace

ContinuousCheckResult runContinuousCheck(const std::vector<DrawPacket> &source_packets,
                                         const std::vector<DrawPacket> &target_packets,
                                         const RenderOptions &options, ColorRenderer &renderer,
                                         const std::string &output_directory) {
    const auto source_pages = uniquePages(source_packets);
    const auto target_pages = uniquePages(target_packets);
    ContinuousAlphaOperator linear_operator;
    auto delta_pages = ContinuousAlphaOperator::createPageFields(source_packets);
    for (ContinuousPageField &field : delta_pages) {
        const DrawPacket &source = *source_pages.at(field.page_index);
        const DrawPacket &target = *target_pages.at(field.page_index);
        if (source.texture_width != target.texture_width || source.texture_height != target.texture_height) {
            throw std::runtime_error("Source and target page dimensions differ in continuous check");
        }
        for (std::size_t texel = 0; texel < field.rgb.size() / 3; ++texel) {
            for (int channel = 0; channel < 3; ++channel) {
                field.rgb[texel * 3 + channel] =
                    (static_cast<float>(target.texture_rgba[texel * 4 + channel]) -
                     static_cast<float>(source.texture_rgba[texel * 4 + channel])) /
                    255.0f;
            }
            if (source.texture_rgba[texel * 4 + 3] != target.texture_rgba[texel * 4 + 3]) {
                throw std::runtime_error("Continuous check requires fixed source alpha");
            }
        }
    }

    std::vector<float> predicted_delta;
    const ContinuousOperatorStats stats =
        linear_operator.forward(source_packets, options, delta_pages, predicted_delta);
    const std::vector<std::uint8_t> source_render = renderer.render(source_packets, options);
    const std::vector<std::uint8_t> target_render = renderer.render(target_packets, options);
    const std::vector<std::uint8_t> prediction = reconstructedImage(source_render, predicted_delta);
    const std::vector<std::uint8_t> error = errorImage(target_render, prediction);

    ContinuousCheckResult result;
    result.fragment_samples = stats.fragment_samples;
    result.compared_values = predicted_delta.size();
    double signal_squared = 0.0;
    double error_absolute = 0.0;
    double error_squared = 0.0;
    for (std::size_t pixel = 0; pixel < predicted_delta.size() / 3; ++pixel) {
        for (int channel = 0; channel < 3; ++channel) {
            const double measured = static_cast<double>(target_render[pixel * 4 + channel]) -
                                    source_render[pixel * 4 + channel];
            const double predicted = predicted_delta[pixel * 3 + channel] * 255.0;
            const double difference = predicted - measured;
            signal_squared += measured * measured;
            error_absolute += std::fabs(difference);
            error_squared += difference * difference;
        }
    }
    result.signal_rms_bytes = std::sqrt(signal_squared / std::max<std::size_t>(1, result.compared_values));
    result.error_mae_bytes = error_absolute / std::max<std::size_t>(1, result.compared_values);
    result.error_rms_bytes = std::sqrt(error_squared / std::max<std::size_t>(1, result.compared_values));
    result.relative_rms = result.error_rms_bytes / std::max(1e-12, result.signal_rms_bytes);

    std::uint32_t random_state = 0x8d31a4b7u;
    auto nextRandom = [&]() {
        random_state = random_state * 1664525u + 1013904223u;
        return static_cast<float>((random_state >> 8) * (2.0 / 16777215.0) - 1.0);
    };
    std::vector<float> random_screen(predicted_delta.size());
    for (float &value : random_screen) value = nextRandom();
    auto adjoint_pages = ContinuousAlphaOperator::createPageFields(source_packets);
    linear_operator.adjoint(source_packets, options, random_screen, adjoint_pages);
    for (std::size_t index = 0; index < predicted_delta.size(); ++index) {
        result.adjoint_left += static_cast<double>(predicted_delta[index]) * random_screen[index];
    }
    for (std::size_t page = 0; page < delta_pages.size(); ++page) {
        if (delta_pages[page].page_index != adjoint_pages[page].page_index) {
            throw std::runtime_error("Continuous check page order changed during adjoint");
        }
        for (std::size_t index = 0; index < delta_pages[page].rgb.size(); ++index) {
            result.adjoint_right +=
                static_cast<double>(delta_pages[page].rgb[index]) * adjoint_pages[page].rgb[index];
        }
    }
    result.adjoint_relative_error = std::fabs(result.adjoint_left - result.adjoint_right) /
                                    std::max({1e-12, std::fabs(result.adjoint_left),
                                              std::fabs(result.adjoint_right)});

    namespace fs = std::filesystem;
    const fs::path output = fs::u8path(output_directory);
    fs::create_directories(output);
    ColorRenderer::writePngAtomic((output / "source.png").u8string(), source_render, options.output_width,
                                  options.output_height);
    ColorRenderer::writePngAtomic((output / "target.png").u8string(), target_render, options.output_width,
                                  options.output_height);
    ColorRenderer::writePngAtomic((output / "linear_prediction.png").u8string(), prediction,
                                  options.output_width, options.output_height);
    ColorRenderer::writePngAtomic((output / "absolute_error_x8.png").u8string(), error, options.output_width,
                                  options.output_height);
    std::ofstream report(output / "report.json", std::ios::binary);
    report << std::setprecision(12) << "{\n"
           << "  \"fragment_samples\": " << result.fragment_samples << ",\n"
           << "  \"compared_rgb_values\": " << result.compared_values << ",\n"
           << "  \"signal_rms_bytes\": " << result.signal_rms_bytes << ",\n"
           << "  \"error_mae_bytes\": " << result.error_mae_bytes << ",\n"
           << "  \"error_rms_bytes\": " << result.error_rms_bytes << ",\n"
           << "  \"relative_rms\": " << result.relative_rms << ",\n"
           << "  \"adjoint_left\": " << result.adjoint_left << ",\n"
           << "  \"adjoint_right\": " << result.adjoint_right << ",\n"
           << "  \"adjoint_relative_error\": " << result.adjoint_relative_error << "\n"
           << "}\n";
    return result;
}

}  // namespace redrawspine
