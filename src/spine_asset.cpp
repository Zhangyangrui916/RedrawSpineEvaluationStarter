#include "redrawspine/spine_asset.h"

#include <spine/Animation.h>
#include <spine/AnimationState.h>
#include <spine/AnimationStateData.h>
#include <spine/Atlas.h>
#include <spine/AtlasAttachmentLoader.h>
#include <spine/BlendMode.h>
#include <spine/MeshAttachment.h>
#include <spine/Physics.h>
#include <spine/RegionAttachment.h>
#include <spine/Skeleton.h>
#include <spine/SkeletonData.h>
#include <spine/SkeletonJson.h>
#include <spine/Slot.h>
#include <spine/SlotData.h>

#include <array>
#include <stdexcept>
#include <string>

namespace redrawspine {
namespace {

Color multiplyColors(const spine::Color &skeleton, const spine::Color &slot, const spine::Color &attachment) {
    return {skeleton.r * slot.r * attachment.r, skeleton.g * slot.g * attachment.g,
            skeleton.b * slot.b * attachment.b, skeleton.a * slot.a * attachment.a};
}

Texture *textureFor(spine::TextureRegion *region, const std::string &attachment_name) {
    if (!region || !region->rendererObject) {
        throw std::runtime_error("Attachment has no loaded texture region: " + attachment_name);
    }
    auto *texture = static_cast<Texture *>(region->rendererObject);
    if (texture->pma) throw std::runtime_error("Premultiplied-alpha atlas pages are outside the V1 contract");
    return texture;
}

}  // namespace

SpineAsset::SpineAsset(const std::string &skeleton_path, const std::string &atlas_path) {
    atlas_ = std::make_unique<spine::Atlas>(atlas_path.c_str(), &texture_loader_);
    spine::AtlasAttachmentLoader attachment_loader(atlas_.get());
    spine::SkeletonJson json(&attachment_loader);
    skeleton_data_.reset(json.readSkeletonDataFile(skeleton_path.c_str()));
    if (!skeleton_data_) {
        throw std::runtime_error("Unable to load skeleton JSON " + skeleton_path + ": " + json.getError().buffer());
    }

    skeleton_ = std::make_unique<spine::Skeleton>(skeleton_data_.get());
    animation_state_data_ = std::make_unique<spine::AnimationStateData>(skeleton_data_.get());
    animation_state_data_->setDefaultMix(0.0f);
    animation_state_ = std::make_unique<spine::AnimationState>(animation_state_data_.get());
    applyPose("", 0.0f);
}

SpineAsset::~SpineAsset() = default;

void SpineAsset::applyPose(const std::string &animation_name, float time_seconds) {
    if (time_seconds < 0.0f) throw std::invalid_argument("Animation time must be non-negative");
    skeleton_->setToSetupPose();
    animation_state_->clearTracks();
    if (!animation_name.empty()) {
        if (!skeleton_data_->findAnimation(animation_name.c_str())) {
            throw std::invalid_argument("Unknown animation: " + animation_name);
        }
        animation_state_->setAnimation(0, animation_name.c_str(), false);
        animation_state_->update(time_seconds);
        animation_state_->apply(*skeleton_);
    }
    skeleton_->updateWorldTransform(spine::Physics_Pose);
}

std::vector<DrawPacket> SpineAsset::buildDrawPackets() const {
    std::vector<DrawPacket> packets;
    const spine::Color &skeleton_color = skeleton_->getColor();

    spine::Vector<spine::Slot *> &draw_order = skeleton_->getDrawOrder();
    for (std::size_t slot_index = 0; slot_index < draw_order.size(); ++slot_index) {
        spine::Slot *slot = draw_order[slot_index];
        spine::Attachment *attachment = slot->getAttachment();
        if (!attachment) continue;
        if (slot->getData().getBlendMode() != spine::BlendMode_Normal) {
            throw std::runtime_error("Only normal slot blend mode is supported in V1");
        }

        DrawPacket packet;
        packet.slot_name = slot->getData().getName().buffer();
        packet.attachment_name = attachment->getName().buffer();

        Texture *texture = nullptr;
        if (attachment->getRTTI().isExactly(spine::RegionAttachment::rtti)) {
            auto *region = static_cast<spine::RegionAttachment *>(attachment);
            packet.positions.resize(8);
            region->computeWorldVertices(*slot, packet.positions.data(), 0, 2);
            packet.uvs.assign(region->getUVs().buffer(), region->getUVs().buffer() + region->getUVs().size());
            packet.indices = {0, 1, 2, 2, 3, 0};
            packet.color = multiplyColors(skeleton_color, slot->getColor(), region->getColor());
            texture = textureFor(region->getRegion(), packet.attachment_name);
        } else if (attachment->getRTTI().isExactly(spine::MeshAttachment::rtti)) {
            auto *mesh = static_cast<spine::MeshAttachment *>(attachment);
            const std::size_t world_vertices = static_cast<std::size_t>(mesh->getWorldVerticesLength());
            packet.positions.resize(world_vertices);
            mesh->computeWorldVertices(*slot, 0, world_vertices, packet.positions.data(), 0, 2);
            packet.uvs.assign(mesh->getUVs().buffer(), mesh->getUVs().buffer() + mesh->getUVs().size());
            packet.indices.assign(mesh->getTriangles().buffer(),
                                  mesh->getTriangles().buffer() + mesh->getTriangles().size());
            packet.color = multiplyColors(skeleton_color, slot->getColor(), mesh->getColor());
            texture = textureFor(mesh->getRegion(), packet.attachment_name);
        } else {
            throw std::runtime_error("Unsupported visible attachment type: " + packet.attachment_name);
        }

        if (packet.positions.size() != packet.uvs.size() || packet.positions.size() % 2 != 0) {
            throw std::runtime_error("Invalid vertex/UV data for attachment: " + packet.attachment_name);
        }
        packet.texture_id = texture->id;
        packet.texture_width = texture->width;
        packet.texture_height = texture->height;
        if (packet.color.a > 0.0f && !packet.indices.empty()) packets.push_back(std::move(packet));
    }
    return packets;
}

std::vector<std::string> SpineAsset::animationNames() const {
    std::vector<std::string> names;
    spine::Vector<spine::Animation *> &animations = skeleton_data_->getAnimations();
    for (std::size_t index = 0; index < animations.size(); ++index) {
        names.emplace_back(animations[index]->getName().buffer());
    }
    return names;
}

}  // namespace redrawspine
