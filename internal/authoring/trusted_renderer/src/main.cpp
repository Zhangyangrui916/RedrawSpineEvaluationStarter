#include "redrawspine/gl_context.h"
#include "redrawspine/continuous_alpha_check.h"
#include "redrawspine/continuous_alpha_analyzer.h"
#include "redrawspine/coverage_renderer.h"
#include "redrawspine/renderer.h"
#include "redrawspine/spine_asset.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace {

class Arguments {
public:
    Arguments(int argc, char **argv) {
        for (int index = 1; index < argc; ++index) {
            std::string key = argv[index];
            if (key.rfind("--", 0) != 0 || index + 1 >= argc) {
                throw std::invalid_argument("Expected --key value arguments");
            }
            values_[key] = argv[++index];
        }
    }

    std::string require(const std::string &key) const {
        const auto iterator = values_.find(key);
        if (iterator == values_.end()) throw std::invalid_argument("Missing required argument " + key);
        return iterator->second;
    }

    std::string get(const std::string &key, const std::string &fallback) const {
        const auto iterator = values_.find(key);
        return iterator == values_.end() ? fallback : iterator->second;
    }

private:
    std::unordered_map<std::string, std::string> values_;
};

void writeStats(const std::filesystem::path &path, const redrawspine::RenderStats &stats,
                const std::string &backend) {
    if (path.empty()) return;
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary);
    output << "{\n  \"backend\": \"" << backend << "\",\n"
           << "  \"draw_packets\": " << stats.draw_packets << ",\n"
           << "  \"nonzero_alpha_pixels\": " << stats.nonzero_alpha_pixels << ",\n"
           << "  \"bbox\": [" << stats.bbox_left << ", " << stats.bbox_top << ", " << stats.bbox_right << ", "
           << stats.bbox_bottom << "]\n}\n";
}

void writeCoverageStats(const std::filesystem::path &path, const redrawspine::CoverageResult &coverage,
                        const std::string &backend) {
    if (path.empty()) return;
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary);
    output << "{\n  \"backend\": \"" << backend << "\",\n"
           << "  \"owned_screen_pixels\": " << coverage.owned_screen_pixels << ",\n"
           << "  \"reliable_screen_pixels\": " << coverage.reliable_screen_pixels << ",\n"
           << "  \"pages\": [\n";
    for (std::size_t index = 0; index < coverage.pages.size(); ++index) {
        const auto &page = coverage.pages[index];
        output << "    {\"page_index\": " << page.page_index << ", \"width\": " << page.width
               << ", \"height\": " << page.height << ", \"covered_texels\": " << page.covered_texels << "}";
        output << (index + 1 == coverage.pages.size() ? "\n" : ",\n");
    }
    output << "  ]\n}\n";
}

}  // namespace

int main(int argc, char **argv) {
    try {
        Arguments arguments(argc, argv);
        redrawspine::GlContext context;
        redrawspine::ColorRenderer renderer;
        redrawspine::SpineAsset asset(arguments.require("--skeleton"), arguments.require("--atlas"));

        const std::string animation = arguments.require("--animation");
        const float time = std::stof(arguments.require("--time"));
        redrawspine::RenderOptions options;
        options.output_width = std::stoi(arguments.get("--width", "768"));
        options.output_height = std::stoi(arguments.get("--height", "596"));
        options.viewport_x = std::stof(arguments.get("--viewport-x", "-1300"));
        options.viewport_y = std::stof(arguments.get("--viewport-y", "-650"));
        options.viewport_width = std::stof(arguments.get("--viewport-width", "2450"));
        options.viewport_height = std::stof(arguments.get("--viewport-height", "1900"));

        asset.applyPose(animation, time);
        const auto packets = asset.buildDrawPackets();
        const std::string stats_path = arguments.get("--stats", "");
        const std::string mode = arguments.get("--mode", "color");
        if (mode == "continuous-check") {
            redrawspine::SpineAsset target_asset(arguments.require("--skeleton"),
                                                  arguments.require("--target-atlas"));
            target_asset.applyPose(animation, time);
            const auto target_packets = target_asset.buildDrawPackets();
            const auto check = redrawspine::runContinuousCheck(
                packets, target_packets, options, renderer, arguments.require("--check-dir"));
            std::cout << "backend=" << context.backend() << " fragments=" << check.fragment_samples
                      << " error_mae_bytes=" << check.error_mae_bytes
                      << " relative_rms=" << check.relative_rms
                      << " adjoint_relative_error=" << check.adjoint_relative_error << '\n';
        } else if (mode == "continuous-energy") {
            redrawspine::ContinuousAlphaAnalyzer analyzer;
            const auto energy = analyzer.coefficientEnergy(packets, options);
            analyzer.writeEnergy(arguments.require("--energy-dir"), energy);
            std::cout << "backend=" << context.backend() << " fragments=" << energy.fragment_samples
                      << " pages=" << energy.pages.size() << '\n';
        } else if (mode == "coverage") {
            redrawspine::CoverageRenderer coverage_renderer;
            const int boundary_radius = std::stoi(arguments.get("--boundary-radius", "2"));
            const auto coverage = coverage_renderer.render(packets, options, boundary_radius);
            coverage_renderer.writeMasks(arguments.require("--coverage-dir"), coverage);
            if (!stats_path.empty()) {
                writeCoverageStats(std::filesystem::u8path(stats_path), coverage, context.backend());
            }
            std::cout << "backend=" << context.backend() << " owned_screen=" << coverage.owned_screen_pixels
                      << " reliable_screen=" << coverage.reliable_screen_pixels << '\n';
        } else if (mode == "color") {
            const auto pixels = renderer.render(packets, options);
            const auto stats =
                renderer.computeStats(pixels, options.output_width, options.output_height, packets.size());
            renderer.writePngAtomic(arguments.require("--output"), pixels, options.output_width,
                                    options.output_height);
            if (!stats_path.empty()) writeStats(std::filesystem::u8path(stats_path), stats, context.backend());
            std::cout << "backend=" << context.backend() << " packets=" << stats.draw_packets
                      << " nonzero_alpha=" << stats.nonzero_alpha_pixels << '\n';
        } else {
            throw std::invalid_argument("Unknown render mode: " + mode);
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "trusted-render: " << error.what() << '\n';
        return 1;
    }
}
