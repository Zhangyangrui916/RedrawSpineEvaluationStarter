# Implementation Status

## Completed

- Vendored official `spine-cpp` 4.2 source and Spine Runtimes license.
- Pinned the downloaded 4.2 branch revision in `third_party/SPINE_RUNTIME_REVISION.txt`.
- Added a source-only CMake build with vendored GLFW 3.4, GLAD, and stb.
- Added hidden-context OpenGL initialization with Linux null-platform EGL/OSMesa fallback.
- Added RGBA8 texture loading with linear filtering, clamp-to-edge, straight alpha, and no mipmaps.
- Added RegionAttachment and ordinary/weighted/linked MeshAttachment color draw packets in actual Spine draw order.
- Added fixed-viewport offscreen color rendering and temporary-file PNG finalization.
- Added `redrawspine-render` pose/list CLI.
- Added the required `redrawspine-reconstruct --case --output` CLI with an explicit No-op baseline.
- Added a mixed public character asset with 20 independent pages.
- Added opt-in pristine-starter preflight and source-only packaging checks.

## Verified on Windows

- Visual Studio 2022 Release build from an external clean build directory.
- Pristine-starter preflight and source-only audit.
- Official 4.2 runtime loads all 15 animations.
- All 15 animations render nonblank at a sampled time without touching the fixed viewport boundary.
- Walk and MagicAttack PNGs were visually inspected.
- Invalid animation input returns nonzero without leaving an output.
- No-op reconstruction preserves all 20 page bytes.
- The source tree contains no build directory, executable, library, object, CMake cache, or old analyzer output.

## Verified in the DSBench Linux Container

- Debian GNU/Linux 13 (trixie), x86_64, no GPU or display server.
- Installed the documented build and Mesa packages through `apt`.
- Completed a clean Ninja Release build from an external directory.
- GLFW null-platform EGL initialization failed as expected in this image; automatic fallback to OSMesa succeeded.
- Verified offscreen render statistics:
  - backend: `osmesa`
  - draw packets: `8`
  - nonzero alpha pixels: `48895`
  - bbox: `[307, 47, 604, 415]`
- The output was a valid nonblank PNG.
- The pristine-starter preflight and source-only audit passed.

Linux portability fixes applied:

1. Use GLFW 3.4's `GLFW_ANY_PLATFORM` constant.
2. Compile `getDefaultExtension()` into the final renderer executable rather than the forward static archive, avoiding GNU ld's single-pass archive-order failure.

## Candidate Freedom

The supplied color renderer is editable starter infrastructure, not a required final interface. A candidate may change, repurpose, replace, or remove it. The opt-in starter checks validate the pristine package only and are not part of candidate grading.

## Intentionally Not Included Yet

- Candidate-visible before/after observations.
- Private deterministic data generator.
- Hidden benchmark instances and reference frames.
- Trusted grader and score implementation.

Those belong to the authoring/evaluation side rather than the candidate-visible starter.

## Remaining External Gates

1. Add at least one complete public observation case and freeze its schema.
2. Resolve and document redistribution permission for the public character artwork before publishing or distributing the starter.
