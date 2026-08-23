#include "redrawspine/gl_context.h"
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
        for (int i = 1; i < argc; ++i) {
            const std::string key = argv[i];
            if (key.rfind("--", 0) != 0) throw std::invalid_argument("Unexpected argument: " + key);
            if (key == "--list-animations") {
                flags_[key] = true;
                continue;
            }
            if (i + 1 >= argc) throw std::invalid_argument("Missing value for " + key);
            values_[key] = argv[++i];
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

    bool flag(const std::string &key) const { return flags_.count(key) != 0; }

private:
    std::unordered_map<std::string, std::string> values_;
    std::unordered_map<std::string, bool> flags_;
};

void writeStats(const std::string &path, const redrawspine::RenderStats &stats, const std::string &backend,
                const std::string &animation, float time) {
    if (path.empty()) return;
    const std::filesystem::path output = std::filesystem::u8path(path);
    if (!output.parent_path().empty()) std::filesystem::create_directories(output.parent_path());
    std::ofstream stream(output, std::ios::binary);
    if (!stream) throw std::runtime_error("Unable to write stats JSON: " + path);
    stream << "{\n"
           << "  \"backend\": \"" << backend << "\",\n"
           << "  \"animation\": \"" << animation << "\",\n"
           << "  \"time\": " << time << ",\n"
           << "  \"draw_packets\": " << stats.draw_packets << ",\n"
           << "  \"nonzero_alpha_pixels\": " << stats.nonzero_alpha_pixels << ",\n"
           << "  \"bbox\": [" << stats.bbox_left << ", " << stats.bbox_top << ", " << stats.bbox_right << ", "
           << stats.bbox_bottom << "]\n"
           << "}\n";
}

}  // namespace

int main(int argc, char **argv) {
    try {
        Arguments arguments(argc, argv);
        const std::string skeleton = arguments.require("--skeleton");
        const std::string atlas = arguments.require("--atlas");

        redrawspine::GlContext context;
        redrawspine::ColorRenderer renderer;
        redrawspine::SpineAsset asset(skeleton, atlas);

        if (arguments.flag("--list-animations")) {
            for (const std::string &name : asset.animationNames()) std::cout << name << '\n';
            return 0;
        }

        const std::string output = arguments.require("--output");
        const std::string animation = arguments.get("--animation", "");
        const float time = std::stof(arguments.get("--time", "0"));
        redrawspine::RenderOptions options;
        options.output_width = std::stoi(arguments.get("--width", "768"));
        options.output_height = std::stoi(arguments.get("--height", "596"));
        options.viewport_x = std::stof(arguments.get("--viewport-x", "-1300"));
        options.viewport_y = std::stof(arguments.get("--viewport-y", "-650"));
        options.viewport_width = std::stof(arguments.get("--viewport-width", "2450"));
        options.viewport_height = std::stof(arguments.get("--viewport-height", "1900"));

        asset.applyPose(animation, time);
        const std::vector<redrawspine::DrawPacket> packets = asset.buildDrawPackets();
        const std::vector<std::uint8_t> pixels = renderer.render(packets, options);
        redrawspine::ColorRenderer::writePngAtomic(output, pixels, options.output_width, options.output_height);
        const redrawspine::RenderStats stats =
            redrawspine::ColorRenderer::computeStats(pixels, options.output_width, options.output_height, packets.size());
        writeStats(arguments.get("--stats", ""), stats, context.backend(), animation, time);
        std::cout << "rendered=" << output << " backend=" << context.backend() << " packets=" << stats.draw_packets
                  << " nonzero_alpha=" << stats.nonzero_alpha_pixels << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "redrawspine-render: " << error.what() << '\n';
        return 1;
    }
}
