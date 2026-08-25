#include "redrawspine/continuous_alpha_operator.h"
#include "redrawspine/gl_context.h"
#include "redrawspine/spine_asset.h"

#include <stb_image.h>
#include <stb_image_write.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

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

struct PoseSpec {
    std::string id;
    std::string animation;
    float time = 0.0f;
    std::filesystem::path before;
    std::filesystem::path after;
};

struct PoseData {
    PoseSpec spec;
    std::vector<redrawspine::DrawPacket> packets;
};

struct PageSource {
    int width = 0;
    int height = 0;
    std::filesystem::path path;
    const std::uint8_t *rgba = nullptr;
};

std::vector<std::string> splitTabs(const std::string &line) {
    std::vector<std::string> fields;
    std::size_t begin = 0;
    while (true) {
        const std::size_t tab = line.find('\t', begin);
        fields.push_back(line.substr(begin, tab == std::string::npos ? tab : tab - begin));
        if (tab == std::string::npos) return fields;
        begin = tab + 1;
    }
}

std::vector<PoseSpec> readPoses(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("Unable to open pose list " + path.u8string());
    std::vector<PoseSpec> poses;
    std::string line;
    int line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        const auto fields = splitTabs(line);
        if (fields.size() != 5) {
            throw std::runtime_error("Pose list line " + std::to_string(line_number) + " must have 5 tab fields");
        }
        PoseSpec pose;
        pose.id = fields[0];
        pose.animation = fields[1];
        pose.time = std::stof(fields[2]);
        pose.before = std::filesystem::u8path(fields[3]);
        pose.after = std::filesystem::u8path(fields[4]);
        poses.push_back(std::move(pose));
    }
    if (poses.empty()) throw std::runtime_error("Pose list is empty");
    return poses;
}

std::vector<redrawspine::ContinuousPageField> createGlobalFields(const std::vector<PoseData> &poses) {
    std::map<int, std::pair<int, int>> dimensions;
    for (const PoseData &pose : poses) {
        for (const redrawspine::DrawPacket &packet : pose.packets) {
            const auto [iterator, inserted] = dimensions.emplace(
                packet.page_index, std::make_pair(packet.texture_width, packet.texture_height));
            if (!inserted && iterator->second != std::make_pair(packet.texture_width, packet.texture_height)) {
                throw std::runtime_error("Inconsistent page dimensions across poses");
            }
        }
    }
    std::vector<redrawspine::ContinuousPageField> result;
    for (const auto &[page_index, dimensions_value] : dimensions) {
        redrawspine::ContinuousPageField page;
        page.page_index = page_index;
        page.width = dimensions_value.first;
        page.height = dimensions_value.second;
        page.rgb.resize(static_cast<std::size_t>(page.width) * page.height * 3, 0.0f);
        result.push_back(std::move(page));
    }
    return result;
}

std::vector<redrawspine::ContinuousPageField> zeroLike(
    const std::vector<redrawspine::ContinuousPageField> &prototype) {
    auto result = prototype;
    for (auto &page : result) std::fill(page.rgb.begin(), page.rgb.end(), 0.0f);
    return result;
}

void fillZero(std::vector<redrawspine::ContinuousPageField> &field) {
    for (auto &page : field) std::fill(page.rgb.begin(), page.rgb.end(), 0.0f);
}

double dot(const std::vector<redrawspine::ContinuousPageField> &left,
           const std::vector<redrawspine::ContinuousPageField> &right) {
    double result = 0.0;
    for (std::size_t page = 0; page < left.size(); ++page) {
        for (std::size_t index = 0; index < left[page].rgb.size(); ++index) {
            result += static_cast<double>(left[page].rgb[index]) * right[page].rgb[index];
        }
    }
    return result;
}

void axpy(std::vector<redrawspine::ContinuousPageField> &output, double scale,
          const std::vector<redrawspine::ContinuousPageField> &input) {
    const float scale_float = static_cast<float>(scale);
    for (std::size_t page = 0; page < output.size(); ++page) {
        for (std::size_t index = 0; index < output[page].rgb.size(); ++index) {
            output[page].rgb[index] += scale_float * input[page].rgb[index];
        }
    }
}

void combine(std::vector<redrawspine::ContinuousPageField> &output,
             const std::vector<redrawspine::ContinuousPageField> &left, double scale,
             const std::vector<redrawspine::ContinuousPageField> &right) {
    const float scale_float = static_cast<float>(scale);
    for (std::size_t page = 0; page < output.size(); ++page) {
        for (std::size_t index = 0; index < output[page].rgb.size(); ++index) {
            output[page].rgb[index] = left[page].rgb[index] + scale_float * right[page].rgb[index];
        }
    }
}

void precondition(std::vector<redrawspine::ContinuousPageField> &output,
                  const std::vector<redrawspine::ContinuousPageField> &residual,
                  const std::vector<redrawspine::ContinuousPageField> &diagonal, float ridge) {
    for (std::size_t page = 0; page < output.size(); ++page) {
        for (std::size_t index = 0; index < output[page].rgb.size(); ++index) {
            output[page].rgb[index] = residual[page].rgb[index] / (diagonal[page].rgb[index] + ridge);
        }
    }
}

std::vector<float> loadFrameDelta(const PoseSpec &pose, int width, int height) {
    int before_width = 0;
    int before_height = 0;
    int before_channels = 0;
    int after_width = 0;
    int after_height = 0;
    int after_channels = 0;
    stbi_set_flip_vertically_on_load(0);
    std::uint8_t *before =
        stbi_load(pose.before.u8string().c_str(), &before_width, &before_height, &before_channels, STBI_rgb_alpha);
    std::uint8_t *after =
        stbi_load(pose.after.u8string().c_str(), &after_width, &after_height, &after_channels, STBI_rgb_alpha);
    if (!before || !after) {
        if (before) stbi_image_free(before);
        if (after) stbi_image_free(after);
        throw std::runtime_error("Unable to load observation pair for " + pose.id);
    }
    if (before_width != width || before_height != height || after_width != width || after_height != height) {
        stbi_image_free(before);
        stbi_image_free(after);
        throw std::runtime_error("Observation dimensions do not match render size for " + pose.id);
    }
    std::vector<float> delta(static_cast<std::size_t>(width) * height * 3);
    for (std::size_t pixel = 0; pixel < delta.size() / 3; ++pixel) {
        for (int channel = 0; channel < 3; ++channel) {
            delta[pixel * 3 + channel] =
                (static_cast<float>(after[pixel * 4 + channel]) - before[pixel * 4 + channel]) / 255.0f;
        }
    }
    stbi_image_free(before);
    stbi_image_free(after);
    return delta;
}

void applyNormal(const redrawspine::ContinuousAlphaOperator &linear_operator,
                 const std::vector<PoseData> &poses, const redrawspine::RenderOptions &options,
                 const std::vector<redrawspine::ContinuousPageField> &input,
                 std::vector<redrawspine::ContinuousPageField> &output, float ridge,
                 std::vector<float> &screen_buffer) {
    fillZero(output);
    for (const PoseData &pose : poses) {
        linear_operator.forward(pose.packets, options, input, screen_buffer);
        linear_operator.adjoint(pose.packets, options, screen_buffer, output, true);
    }
    axpy(output, ridge, input);
}

std::map<int, PageSource> collectPageSources(const std::vector<PoseData> &poses) {
    std::map<int, PageSource> result;
    for (const PoseData &pose : poses) {
        for (const redrawspine::DrawPacket &packet : pose.packets) {
            const PageSource source = {packet.texture_width, packet.texture_height,
                                       std::filesystem::u8path(packet.texture_path), packet.texture_rgba};
            const auto [iterator, inserted] = result.emplace(packet.page_index, source);
            if (!inserted && (iterator->second.width != source.width || iterator->second.height != source.height ||
                              iterator->second.path != source.path)) {
                throw std::runtime_error("Inconsistent page source across poses");
            }
        }
    }
    return result;
}

void writePages(const std::filesystem::path &directory,
                const std::vector<redrawspine::ContinuousPageField> &solution,
                const std::map<int, PageSource> &sources) {
    std::filesystem::create_directories(directory);
    std::map<std::string, int> output_names;
    for (const redrawspine::ContinuousPageField &page : solution) {
        const PageSource &source = sources.at(page.page_index);
        const std::string filename = source.path.filename().u8string();
        if (!output_names.emplace(filename, page.page_index).second) {
            throw std::runtime_error("Duplicate atlas page filename in baseline output: " + filename);
        }
        std::vector<std::uint8_t> rgba(static_cast<std::size_t>(page.width) * page.height * 4);
        for (std::size_t texel = 0; texel < rgba.size() / 4; ++texel) {
            for (int channel = 0; channel < 3; ++channel) {
                const float source_value = source.rgba[texel * 4 + channel] / 255.0f;
                const float value = std::clamp(source_value + page.rgb[texel * 3 + channel], 0.0f, 1.0f);
                rgba[texel * 4 + channel] = static_cast<std::uint8_t>(std::lround(value * 255.0f));
            }
            rgba[texel * 4 + 3] = source.rgba[texel * 4 + 3];
        }
        const std::filesystem::path output = directory / std::filesystem::u8path(filename);
        if (!stbi_write_png(output.u8string().c_str(), page.width, page.height, 4, rgba.data(), page.width * 4)) {
            throw std::runtime_error("Unable to write baseline page " + output.u8string());
        }
    }
}

}  // namespace

int main(int argc, char **argv) {
    try {
        const Arguments arguments(argc, argv);
        redrawspine::GlContext context;
        redrawspine::SpineAsset asset(arguments.require("--skeleton"), arguments.require("--atlas"));
        redrawspine::RenderOptions options;
        options.output_width = std::stoi(arguments.require("--width"));
        options.output_height = std::stoi(arguments.require("--height"));
        options.viewport_x = std::stof(arguments.require("--viewport-x"));
        options.viewport_y = std::stof(arguments.require("--viewport-y"));
        options.viewport_width = std::stof(arguments.require("--viewport-width"));
        options.viewport_height = std::stof(arguments.require("--viewport-height"));
        const int maximum_iterations = std::stoi(arguments.get("--iterations", "20"));
        const float ridge = std::stof(arguments.get("--ridge", "1e-6"));
        const double tolerance = std::stod(arguments.get("--tolerance", "1e-5"));
        if (maximum_iterations < 1 || ridge <= 0.0f || tolerance <= 0.0) {
            throw std::invalid_argument("Iterations, ridge, and tolerance must be positive");
        }

        const auto start = std::chrono::steady_clock::now();
        const auto pose_specs = readPoses(std::filesystem::u8path(arguments.require("--poses")));
        std::vector<PoseData> poses;
        for (const PoseSpec &pose_spec : pose_specs) {
            asset.applyPose(pose_spec.animation, pose_spec.time);
            poses.push_back({pose_spec, asset.buildDrawPackets()});
        }
        const auto sources = collectPageSources(poses);
        redrawspine::ContinuousAlphaOperator linear_operator;
        auto diagonal = createGlobalFields(poses);
        std::size_t energy_fragments = 0;
        for (const PoseData &pose : poses) {
            energy_fragments += linear_operator.coefficientEnergy(pose.packets, options, diagonal, true).fragment_samples;
        }

        auto residual = zeroLike(diagonal);
        std::size_t rhs_fragments = 0;
        for (const PoseData &pose : poses) {
            const std::vector<float> frame_delta =
                loadFrameDelta(pose.spec, options.output_width, options.output_height);
            rhs_fragments +=
                linear_operator.adjoint(pose.packets, options, frame_delta, residual, true).fragment_samples;
        }
        const double rhs_squared = dot(residual, residual);
        if (!(rhs_squared > 0.0)) throw std::runtime_error("Observation right-hand side is zero");

        std::size_t energy_positive = 0;
        std::size_t energy_above_1e4 = 0;
        for (const auto &page : diagonal) {
            for (float value : page.rgb) {
                if (value > 0.0f) ++energy_positive;
                if (value >= 1e-4f) ++energy_above_1e4;
            }
        }

        auto solution = zeroLike(diagonal);
        auto preconditioned = zeroLike(diagonal);
        auto direction = zeroLike(diagonal);
        auto normal_direction = zeroLike(diagonal);
        precondition(preconditioned, residual, diagonal, ridge);
        direction = preconditioned;
        double rho = dot(residual, preconditioned);
        std::vector<float> screen_buffer;
        std::vector<double> relative_residuals;
        int completed_iterations = 0;
        for (int iteration = 0; iteration < maximum_iterations; ++iteration) {
            applyNormal(linear_operator, poses, options, direction, normal_direction, ridge, screen_buffer);
            const double denominator = dot(direction, normal_direction);
            if (!(denominator > 0.0) || !std::isfinite(denominator)) {
                throw std::runtime_error("PCG encountered a non-positive normal-equation denominator");
            }
            const double alpha = rho / denominator;
            axpy(solution, alpha, direction);
            axpy(residual, -alpha, normal_direction);
            const double relative_residual = std::sqrt(dot(residual, residual) / rhs_squared);
            relative_residuals.push_back(relative_residual);
            completed_iterations = iteration + 1;
            std::cout << "iteration=" << completed_iterations << " relative_normal_residual="
                      << std::setprecision(8) << relative_residual << '\n';
            if (relative_residual <= tolerance) break;
            precondition(preconditioned, residual, diagonal, ridge);
            const double next_rho = dot(residual, preconditioned);
            const double beta = next_rho / rho;
            combine(direction, preconditioned, beta, direction);
            rho = next_rho;
        }

        const std::filesystem::path output = std::filesystem::u8path(arguments.require("--output-dir"));
        if (std::filesystem::exists(output)) {
            throw std::runtime_error("Baseline output directory already exists: " + output.u8string());
        }
        std::filesystem::create_directories(output);
        writePages(output / "attachments", solution, sources);
        const double elapsed_seconds =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        std::ofstream report(output / "report.json", std::ios::binary);
        report << std::setprecision(12) << "{\n"
               << "  \"backend\": \"" << context.backend() << "\",\n"
               << "  \"poses\": " << poses.size() << ",\n"
               << "  \"pages\": " << diagonal.size() << ",\n"
               << "  \"energy_fragments\": " << energy_fragments << ",\n"
               << "  \"rhs_fragments\": " << rhs_fragments << ",\n"
               << "  \"ridge\": " << ridge << ",\n"
               << "  \"iterations\": " << completed_iterations << ",\n"
               << "  \"energy_positive_rgb_values\": " << energy_positive << ",\n"
               << "  \"energy_at_least_1e-4_rgb_values\": " << energy_above_1e4 << ",\n"
               << "  \"elapsed_seconds\": " << elapsed_seconds << ",\n"
               << "  \"relative_normal_residuals\": [";
        for (std::size_t index = 0; index < relative_residuals.size(); ++index) {
            if (index) report << ", ";
            report << relative_residuals[index];
        }
        report << "]\n}\n";
        std::cout << "output=" << output.u8string() << " elapsed_seconds=" << elapsed_seconds << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "continuous-baseline: " << error.what() << '\n';
        return 1;
    }
}
