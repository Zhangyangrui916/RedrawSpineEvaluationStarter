# RedrawSpine Evaluation Starter

Source-only starter for the deterministic RedrawSpine static attachment reconstruction benchmark.

## Included

- Official `spine-cpp` from the `spine-runtimes` 4.2 branch.
- A hidden-window OpenGL 3.3 color forward renderer.
- RegionAttachment and ordinary/weighted/linked MeshAttachment draw-packet extraction.
- Normal blend, straight alpha, fixed viewport, RGBA8 PNG output.
- A mixed public Spine asset with 20 independent atlas pages.
- `redrawspine-reconstruct`, initially implemented as an explicit No-op baseline that copies S0 pages.
- A public smoke test covering clean loading, two distinct poses, invalid input, and the No-op output contract.

The starter deliberately does **not** include an attachment-ID/UV pass, screen-to-texel mapping, observation fusion, coverage logic, S1 generation, or the trusted grader.

## Build

Use a build directory outside the source tree when preparing the distributable starter:

```bash
cmake -S . -B /tmp/redrawspine-starter-build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/redrawspine-starter-build -j2
ctest --test-dir /tmp/redrawspine-starter-build --output-on-failure
```

Linux packages expected in the benchmark image:

```bash
apt-get install -y build-essential cmake ninja-build libgl1-mesa-dev libegl1-mesa-dev libosmesa6
```

The vendored GLFW 3.4 build disables X11 and Wayland on Linux. `REDRAWSPINE_GL_BACKEND=auto` tries null-platform EGL, then OSMesa, then native. Windows uses a hidden native WGL context.

## Render A Pose

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

## Candidate CLI

```bash
./redrawspine-reconstruct --case <case_dir> --output <fresh_output_dir>
```

The checked-in implementation copies `source_attachments/*.png` unchanged and should score as No-op. Candidates must replace that implementation with a deterministic multi-observation reconstruction method while preserving the CLI and output contract.

## Public Case Layout

```text
assets/public_static_mesh_smoke/
  case.json
  skeleton.json
  skeleton.atlas
  page_manifest.json
  source_attachments/*.png
```

Generated benchmark cases will additionally contain `observations/`. Hidden S1 pages, hidden poses, reference frames, coverage data, and grader sources must not be placed in the candidate-visible starter.

## Packaging Gate

Before upload, confirm the source directory has no `build/`, object files, libraries, executables, old outputs, hidden instances, or trusted-grader code. Build and test from a fresh external directory.

## Licensing

The Spine Runtimes have license conditions beyond a permissive open-source license. Read `third_party/spine-runtimes/LICENSE` and verify that benchmark distribution is permitted. The character artwork also requires an explicit redistribution decision before public packaging.
