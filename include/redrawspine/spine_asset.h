#pragma once

#include "redrawspine/draw_packet.h"
#include "redrawspine/texture_loader.h"

#include <memory>
#include <string>
#include <vector>

namespace spine {
class AnimationState;
class AnimationStateData;
class Atlas;
class Skeleton;
class SkeletonData;
}

namespace redrawspine {

class SpineAsset {
public:
    SpineAsset(const std::string &skeleton_path, const std::string &atlas_path);
    ~SpineAsset();

    SpineAsset(const SpineAsset &) = delete;
    SpineAsset &operator=(const SpineAsset &) = delete;

    void applyPose(const std::string &animation_name, float time_seconds);
    std::vector<DrawPacket> buildDrawPackets() const;
    std::vector<std::string> animationNames() const;

private:
    OpenGLTextureLoader texture_loader_;
    std::unique_ptr<spine::Atlas> atlas_;
    std::unique_ptr<spine::SkeletonData> skeleton_data_;
    std::unique_ptr<spine::Skeleton> skeleton_;
    std::unique_ptr<spine::AnimationStateData> animation_state_data_;
    std::unique_ptr<spine::AnimationState> animation_state_;
};

}  // namespace redrawspine
