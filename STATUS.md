# Implementation Status

## Completed

- Vendored official `spine-cpp` 4.2 source and Spine Runtimes license.
- Pinned the downloaded 4.2 branch revision in `third_party/SPINE_RUNTIME_REVISION.txt`.
- Added a source-only CMake build with vendored GLFW 3.4, GLAD, and stb.
- Added hidden-context OpenGL initialization with Linux null-platform EGL/OSMesa fallback.
- Added RGBA8 texture loading with linear filtering, clamp-to-edge, straight alpha, and no mipmaps.
- Added RegionAttachment and ordinary/weighted/linked MeshAttachment color draw packets in actual Spine draw order.
- Added fixed-viewport offscreen color rendering and atomic PNG output.
- Added `redrawspine-render` pose/list CLI.
- Added the required `redrawspine-reconstruct --case --output` CLI with an explicit No-op baseline.
- Added a mixed public character asset with 20 independent pages.
- Added public smoke and source-only packaging tests.

## Verified Locally

- Windows Visual Studio 2022 Release build from an external clean build directory.
- CTest public smoke and source-only audit.
- Official 4.2 runtime loads all 15 animations.
- All 15 animations render nonblank at a sampled time without touching the fixed viewport boundary.
- Walk and MagicAttack PNGs were visually inspected.
- Invalid animation input returns nonzero without leaving an output.
- No-op reconstruction preserves all 20 page bytes.
- The source tree contains no build directory, executable, library, object, CMake cache, or old analyzer output.

## Intentionally Not In This Starter Yet

- Candidate-visible before/after observations.
- Private S0/S1 generator.
- Private attachment-ID/UV coverage and ownership pass.
- Hidden seed instances and reference frames.
- Trusted grader and score implementation.

Those belong to the authoring/evaluation side. The private ID/UV and coverage implementation must not be copied into the candidate starter.

## Remaining External Gates

1. **Linux target verification:** local WSL is available, but its Ubuntu instance cannot reach the configured apt mirrors, so the Linux toolchain and Mesa/OSMesa packages could not be installed. Re-run the documented clean build in the DSBench/Linux image.
