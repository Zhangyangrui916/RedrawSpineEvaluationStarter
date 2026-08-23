# RedrawSpine Evaluation Starter

Source-only starter for the deterministic RedrawSpine static attachment reconstruction benchmark.

## Included

- Official `spine-cpp` from the `spine-runtimes` 4.2 branch.
- A hidden-window OpenGL 3.3 color forward renderer.
- RegionAttachment and ordinary/weighted/linked MeshAttachment draw-packet extraction.
- Normal blend, straight alpha, fixed viewport, and RGBA8 PNG output.
- A mixed public Spine asset with 20 independent atlas pages.
- `redrawspine-reconstruct`, initially implemented as an explicit No-op baseline that copies S0 pages.

The starter does **not** contain the reconstruction implementation, private data generator, hidden instances, or trusted grader.

## Build

The benchmark intentionally ships no build products. Configure and compile it from source:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
```

Linux packages expected in the benchmark image:

```bash
apt-get install -y build-essential cmake ninja-build libgl1-mesa-dev libegl1-mesa-dev libosmesa6
```

The vendored GLFW 3.4 build disables X11 and Wayland on Linux. `REDRAWSPINE_GL_BACKEND=auto` tries null-platform EGL, then OSMesa, then native. In the verified DSBench Debian 13 container, EGL initialization failed and the renderer successfully used OSMesa. Windows uses a hidden native WGL context.

## Validate the Pristine Starter Before Editing

The repository contains opt-in checks for validating the **unmodified starter package**:

```bash
cmake -S . -B /tmp/redrawspine-starter-build \
  -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DREDRAWSPINE_AUTHOR_TESTS=ON
cmake --build /tmp/redrawspine-starter-build -j2
REDRAWSPINE_GL_BACKEND=osmesa \
  ctest --test-dir /tmp/redrawspine-starter-build --output-on-failure
```

Run this once before implementation to confirm that source compilation, Spine asset loading, and headless rendering work in the current environment.

These checks validate the supplied starting point only. Passing them does **not** mean the reconstruction task is solved. A valid candidate may modify, repurpose, replace, or remove the supplied color renderer, so these starter checks are not required to pass after implementation and are not part of grading.

## Render a Pose

The supplied renderer is editable example infrastructure:

```bash
./redrawspine-render \
  --skeleton assets/public_static_mesh_smoke/skeleton.json \
  --atlas assets/public_static_mesh_smoke/skeleton.atlas \
  --animation 00_Walk --time 0.4 \
  --viewport-x -1300 --viewport-y -650 \
  --viewport-width 2450 --viewport-height 1900 \
  --width 768 --height 596 \
  --output out/walk.png --stats out/walk.json
```

`redrawspine-render` is not a required final interface. Candidates may change its shaders, change its output format, replace its implementation, or stop using it entirely.

## Candidate CLI and Grading Boundary

The required external interface is:

```bash
./redrawspine-reconstruct --case <case_dir> --output <fresh_output_dir>
```

The checked-in implementation copies `source_attachments/*.png` unchanged and therefore represents the No-op baseline. Candidates must replace it with a deterministic multi-observation reconstruction method while preserving the CLI and output-page contract.

Grading is based on the produced attachment-page PNGs, not on the internal architecture. Candidates may modify the renderer, shaders, Spine integration, vendored runtime, build files, or use a different reconstruction approach.

## Public Case Layout

```text
assets/public_static_mesh_smoke/
  case.json
  skeleton.json
  skeleton.atlas
  page_manifest.json
  source_attachments/*.png
```

Generated benchmark cases will additionally contain `observations/`. Hidden target pages, hidden poses, reference frames, private generation data, and grader sources must not be placed in the candidate-visible starter.

## Packaging Gate

Before publishing or uploading the pristine starter, enable `REDRAWSPINE_AUTHOR_TESTS` and confirm that the source directory has no `build/`, object files, libraries, executables, old outputs, hidden instances, or trusted-grader code. This packaging audit is an authoring check, not a candidate requirement.

## Licensing

The Spine Runtimes have license conditions beyond a permissive open-source license. Read `third_party/spine-runtimes/LICENSE` and verify that benchmark distribution is permitted. The character artwork also requires an explicit redistribution decision before public packaging.
