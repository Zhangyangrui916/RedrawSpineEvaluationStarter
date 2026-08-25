#include "redrawspine/continuous_alpha_operator.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <utility>

namespace redrawspine {
namespace {

struct Footprint {
    std::array<std::size_t, 4> texels{};
    std::array<float, 4> weights{};
    int count = 0;
};

void validateOptions(const RenderOptions &options) {
    if (options.output_width <= 0 || options.output_height <= 0 || options.viewport_width <= 0.0f ||
        options.viewport_height <= 0.0f) {
        throw std::invalid_argument("Output and viewport dimensions must be positive");
    }
}

std::vector<std::size_t> pageLookup(const std::vector<ContinuousPageField> &pages) {
    int maximum_page = -1;
    for (const ContinuousPageField &page : pages) maximum_page = std::max(maximum_page, page.page_index);
    const std::size_t missing = static_cast<std::size_t>(-1);
    std::vector<std::size_t> lookup(static_cast<std::size_t>(maximum_page + 1), missing);
    for (std::size_t index = 0; index < pages.size(); ++index) {
        const ContinuousPageField &page = pages[index];
        if (page.page_index < 0 || page.width <= 0 || page.height <= 0 ||
            page.rgb.size() != static_cast<std::size_t>(page.width) * page.height * 3) {
            throw std::invalid_argument("Invalid continuous-alpha page field");
        }
        if (lookup[page.page_index] != missing) {
            throw std::invalid_argument("Duplicate continuous-alpha page index");
        }
        lookup[page.page_index] = index;
    }
    return lookup;
}

float textureAlpha(const DrawPacket &packet, int x, int y) {
    x = std::clamp(x, 0, packet.texture_width - 1);
    y = std::clamp(y, 0, packet.texture_height - 1);
    const std::size_t offset = (static_cast<std::size_t>(y) * packet.texture_width + x) * 4 + 3;
    return packet.texture_rgba[offset] / 255.0f;
}

Footprint makeFootprint(int width, int height, int x0, int y0, float fx, float fy) {
    const std::array<int, 4> xs = {x0, x0 + 1, x0, x0 + 1};
    const std::array<int, 4> ys = {y0, y0, y0 + 1, y0 + 1};
    const std::array<float, 4> raw_weights = {
        (1.0f - fx) * (1.0f - fy), fx * (1.0f - fy), (1.0f - fx) * fy, fx * fy};

    Footprint result;
    for (int sample = 0; sample < 4; ++sample) {
        if (raw_weights[sample] == 0.0f) continue;
        const int x = std::clamp(xs[sample], 0, width - 1);
        const int y = std::clamp(ys[sample], 0, height - 1);
        const std::size_t texel = static_cast<std::size_t>(y) * width + x;
        int existing = -1;
        for (int index = 0; index < result.count; ++index) {
            if (result.texels[index] == texel) {
                existing = index;
                break;
            }
        }
        if (existing >= 0) {
            result.weights[existing] += raw_weights[sample];
        } else {
            result.texels[result.count] = texel;
            result.weights[result.count] = raw_weights[sample];
            ++result.count;
        }
    }
    return result;
}

float sampledAlpha(const DrawPacket &packet, const Footprint &footprint) {
    float alpha = 0.0f;
    for (int sample = 0; sample < footprint.count; ++sample) {
        const std::size_t texel = footprint.texels[sample];
        const std::size_t offset = texel * 4 + 3;
        alpha += packet.texture_rgba[offset] / 255.0f * footprint.weights[sample];
    }
    return std::clamp(alpha * packet.color.a, 0.0f, 1.0f);
}

bool inclusiveEdge(float dx, float dy) {
    return dy > 0.0f || (dy == 0.0f && dx < 0.0f);
}

bool insideEdge(float value, float dx, float dy) {
    return value > 0.0f || (value == 0.0f && inclusiveEdge(dx, dy));
}

template <typename Visitor>
ContinuousOperatorStats visitSamples(const std::vector<DrawPacket> &packets, const RenderOptions &options,
                                     Visitor &&visitor) {
    validateOptions(options);
    const int screen_width = options.output_width;
    const int screen_height = options.output_height;
    std::vector<float> transmittance(static_cast<std::size_t>(screen_width) * screen_height, 1.0f);
    ContinuousOperatorStats stats;

    for (auto packet_iterator = packets.rbegin(); packet_iterator != packets.rend(); ++packet_iterator) {
        const DrawPacket &packet = *packet_iterator;
        if (packet.page_index < 0 || !packet.texture_rgba || packet.texture_width <= 0 ||
            packet.texture_height <= 0) {
            throw std::runtime_error("Continuous-alpha packet is missing page or CPU texture data");
        }
        const std::size_t vertex_count = packet.positions.size() / 2;
        std::vector<float> screen_x(vertex_count), screen_y(vertex_count);
        for (std::size_t vertex = 0; vertex < vertex_count; ++vertex) {
            screen_x[vertex] =
                (packet.positions[vertex * 2] - options.viewport_x) / options.viewport_width * screen_width;
            screen_y[vertex] =
                (packet.positions[vertex * 2 + 1] - options.viewport_y) / options.viewport_height * screen_height;
        }

        for (std::size_t triangle = 0; triangle + 2 < packet.indices.size(); triangle += 3) {
            int a = packet.indices[triangle];
            int b = packet.indices[triangle + 1];
            int c = packet.indices[triangle + 2];
            float area = (screen_x[b] - screen_x[a]) * (screen_y[c] - screen_y[a]) -
                         (screen_y[b] - screen_y[a]) * (screen_x[c] - screen_x[a]);
            if (std::fabs(area) < 1e-9f) continue;
            if (area < 0.0f) {
                std::swap(b, c);
                area = -area;
            }

            const float min_x = std::min({screen_x[a], screen_x[b], screen_x[c]});
            const float max_x = std::max({screen_x[a], screen_x[b], screen_x[c]});
            const float min_y = std::min({screen_y[a], screen_y[b], screen_y[c]});
            const float max_y = std::max({screen_y[a], screen_y[b], screen_y[c]});
            const int x_begin = std::max(0, static_cast<int>(std::ceil(min_x - 0.5f)));
            const int x_end = std::min(screen_width - 1, static_cast<int>(std::floor(max_x - 0.5f)));
            const int y_begin = std::max(0, static_cast<int>(std::ceil(min_y - 0.5f)));
            const int y_end = std::min(screen_height - 1, static_cast<int>(std::floor(max_y - 0.5f)));

            const float e0_dx = screen_x[c] - screen_x[b];
            const float e0_dy = screen_y[c] - screen_y[b];
            const float e1_dx = screen_x[a] - screen_x[c];
            const float e1_dy = screen_y[a] - screen_y[c];
            const float e2_dx = screen_x[b] - screen_x[a];
            const float e2_dy = screen_y[b] - screen_y[a];
            for (int y = y_begin; y <= y_end; ++y) {
                for (int x = x_begin; x <= x_end; ++x) {
                    const float pixel_x = x + 0.5f;
                    const float pixel_y = y + 0.5f;
                    const float e0 = e0_dx * (pixel_y - screen_y[b]) - e0_dy * (pixel_x - screen_x[b]);
                    const float e1 = e1_dx * (pixel_y - screen_y[c]) - e1_dy * (pixel_x - screen_x[c]);
                    const float e2 = e2_dx * (pixel_y - screen_y[a]) - e2_dy * (pixel_x - screen_x[a]);
                    if (!insideEdge(e0, e0_dx, e0_dy) || !insideEdge(e1, e1_dx, e1_dy) ||
                        !insideEdge(e2, e2_dx, e2_dy)) {
                        continue;
                    }

                    const float l0 = e0 / area;
                    const float l1 = e1 / area;
                    const float l2 = e2 / area;
                    const float u = l0 * packet.uvs[a * 2] + l1 * packet.uvs[b * 2] +
                                    l2 * packet.uvs[c * 2];
                    const float v = l0 * packet.uvs[a * 2 + 1] + l1 * packet.uvs[b * 2 + 1] +
                                    l2 * packet.uvs[c * 2 + 1];
                    const float texture_x = u * packet.texture_width - 0.5f;
                    const float texture_y = v * packet.texture_height - 0.5f;
                    const int x0 = static_cast<int>(std::floor(texture_x));
                    const int y0 = static_cast<int>(std::floor(texture_y));
                    const Footprint footprint = makeFootprint(packet.texture_width, packet.texture_height, x0, y0,
                                                              texture_x - x0, texture_y - y0);
                    const float alpha = sampledAlpha(packet, footprint);
                    if (alpha <= 0.0f) continue;

                    const std::size_t screen_pixel =
                        static_cast<std::size_t>(screen_height - 1 - y) * screen_width + x;
                    const float coefficient = transmittance[screen_pixel] * alpha;
                    if (coefficient > 0.0f) {
                        const std::array<float, 3> coefficients = {
                            coefficient * packet.color.r, coefficient * packet.color.g,
                            coefficient * packet.color.b};
                        visitor(packet.page_index, screen_pixel, footprint, coefficients);
                        ++stats.fragment_samples;
                    }
                    transmittance[screen_pixel] *= 1.0f - alpha;
                }
            }
        }
    }
    return stats;
}

}  // namespace

std::vector<ContinuousPageField> ContinuousAlphaOperator::createPageFields(
    const std::vector<DrawPacket> &packets) {
    std::map<int, std::pair<int, int>> dimensions;
    for (const DrawPacket &packet : packets) {
        const auto [iterator, inserted] =
            dimensions.emplace(packet.page_index, std::make_pair(packet.texture_width, packet.texture_height));
        if (!inserted && iterator->second != std::make_pair(packet.texture_width, packet.texture_height)) {
            throw std::runtime_error("Inconsistent dimensions for continuous-alpha page");
        }
    }
    std::vector<ContinuousPageField> fields;
    for (const auto &[page_index, size] : dimensions) {
        ContinuousPageField field;
        field.page_index = page_index;
        field.width = size.first;
        field.height = size.second;
        field.rgb.resize(static_cast<std::size_t>(field.width) * field.height * 3, 0.0f);
        fields.push_back(std::move(field));
    }
    return fields;
}

ContinuousOperatorStats ContinuousAlphaOperator::forward(
    const std::vector<DrawPacket> &packets, const RenderOptions &options,
    const std::vector<ContinuousPageField> &texture_rgb, std::vector<float> &screen_rgb) const {
    const auto lookup = pageLookup(texture_rgb);
    screen_rgb.assign(static_cast<std::size_t>(options.output_width) * options.output_height * 3, 0.0f);
    return visitSamples(packets, options,
                        [&](int page_index, std::size_t screen_pixel, const Footprint &footprint,
                            const std::array<float, 3> &coefficients) {
                            const ContinuousPageField &page = texture_rgb.at(lookup.at(page_index));
                            for (int channel = 0; channel < 3; ++channel) {
                                float sample = 0.0f;
                                for (int index = 0; index < footprint.count; ++index) {
                                    sample += page.rgb[footprint.texels[index] * 3 + channel] *
                                              footprint.weights[index];
                                }
                                screen_rgb[screen_pixel * 3 + channel] += coefficients[channel] * sample;
                            }
                        });
}

ContinuousOperatorStats ContinuousAlphaOperator::adjoint(
    const std::vector<DrawPacket> &packets, const RenderOptions &options, const std::vector<float> &screen_rgb,
    std::vector<ContinuousPageField> &texture_rgb, bool accumulate) const {
    if (screen_rgb.size() != static_cast<std::size_t>(options.output_width) * options.output_height * 3) {
        throw std::invalid_argument("Continuous-alpha screen field has the wrong size");
    }
    const auto lookup = pageLookup(texture_rgb);
    if (!accumulate) {
        for (ContinuousPageField &page : texture_rgb) std::fill(page.rgb.begin(), page.rgb.end(), 0.0f);
    }
    return visitSamples(packets, options,
                        [&](int page_index, std::size_t screen_pixel, const Footprint &footprint,
                            const std::array<float, 3> &coefficients) {
                            ContinuousPageField &page = texture_rgb.at(lookup.at(page_index));
                            for (int channel = 0; channel < 3; ++channel) {
                                const float value = screen_rgb[screen_pixel * 3 + channel] * coefficients[channel];
                                for (int index = 0; index < footprint.count; ++index) {
                                    page.rgb[footprint.texels[index] * 3 + channel] +=
                                        value * footprint.weights[index];
                                }
                            }
                        });
}

ContinuousOperatorStats ContinuousAlphaOperator::coefficientEnergy(
    const std::vector<DrawPacket> &packets, const RenderOptions &options,
    std::vector<ContinuousPageField> &texture_rgb_energy, bool accumulate) const {
    const auto lookup = pageLookup(texture_rgb_energy);
    if (!accumulate) {
        for (ContinuousPageField &page : texture_rgb_energy) std::fill(page.rgb.begin(), page.rgb.end(), 0.0f);
    }
    return visitSamples(packets, options,
                        [&](int page_index, std::size_t, const Footprint &footprint,
                            const std::array<float, 3> &coefficients) {
                            ContinuousPageField &page = texture_rgb_energy.at(lookup.at(page_index));
                            for (int channel = 0; channel < 3; ++channel) {
                                for (int index = 0; index < footprint.count; ++index) {
                                    const float value = coefficients[channel] * footprint.weights[index];
                                    page.rgb[footprint.texels[index] * 3 + channel] += value * value;
                                }
                            }
                        });
}

}  // namespace redrawspine
