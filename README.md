# RedrawSpine Evaluation Starter

Source-only starter for the deterministic RedrawSpine static attachment reconstruction benchmark.

Read `TASK.md` first. It defines required outputs, public development data, trusted-support canonicalization, and the hidden render-space score.

## Included

- Official `spine-cpp` from the `spine-runtimes` 4.2 branch.
- A hidden-window OpenGL 3.3 reference color renderer.
- RegionAttachment and ordinary/weighted/linked MeshAttachment draw-packet extraction.
- Normal blend, straight alpha, fixed viewport, and RGBA8 PNG output.
- Two final 1:1 observation cases with 20 independent pages each.
- A fully public `synthetic_dev` oracle with S1 pages and validation references.
- `redrawspine-reconstruct`, initially an explicit No-op baseline that copies S0.

The starter does not contain final S1 pages, final trusted support masks, final hidden poses, final reference frames, the private generator, or the trusted grader.

## Build

The benchmark ships no build products. With Ninja:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
```

Ninja places executables under `build/`. Multi-config generators such as Visual Studio place Release executables under `build/Release/`.

### Windows

Run the build from an **x64 Native Tools Command Prompt for VS 2022** or a Visual Studio Developer PowerShell. Confirm that `cmake`, `ninja`, and `cl` resolve before configuring. The developer environment supplies the MSVC compiler and SDK paths that are not available in a plain shell on every Windows installation.

### Linux

No special developer prompt is required. Install the compiler, build tools, and headless Mesa dependencies in a normal shell:

```bash
apt-get install -y build-essential cmake ninja-build libgl1-mesa-dev libegl1-mesa-dev libosmesa6
```

Confirm that `cmake`, `ninja`, and `c++` resolve, then use the same Ninja commands above. The vendored GLFW 3.4 build disables X11 and Wayland. `REDRAWSPINE_GL_BACKEND=auto` tries null-platform EGL, then OSMesa, then native; set `REDRAWSPINE_GL_BACKEND=osmesa` when a headless run should require that backend. Windows uses a hidden native WGL context.

## Optional Pristine Preflight

Before editing, use a separate build directory to confirm source compilation, Spine loading, headless rendering, and the checked-in No-op baseline:

```bash
cmake -S . -B /tmp/redrawspine-starter-preflight \
  -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DREDRAWSPINE_STARTER_TESTS=ON
cmake --build /tmp/redrawspine-starter-preflight -j2
REDRAWSPINE_GL_BACKEND=osmesa \
  ctest --test-dir /tmp/redrawspine-starter-preflight --output-on-failure
```

This preflight validates the unmodified starting point only and is not part of final grading. Maintainer packaging audits use the separate `REDRAWSPINE_AUTHOR_TESTS` option and are not candidate instructions.

## Render a Pose

The supplied renderer is editable reference infrastructure:

```bash
./build/redrawspine-render \
  --skeleton assets/public_static_mesh_smoke/skeleton.json \
  --atlas assets/public_static_mesh_smoke/skeleton.atlas \
  --animation 00_Walk --time 0.4 \
  --viewport-x -1300 --viewport-y -650 \
  --viewport-width 2450 --viewport-height 1900 \
  --width 768 --height 596 \
  --output out/walk.png --stats out/walk.json
```

Candidates may change or replace this executable, but replacements must reproduce the forward semantics relevant to their reconstruction.

## Candidate CLI

The required interface is:

```bash
./build/redrawspine-reconstruct --case <case_dir> --output <fresh_output_dir>
```

The checked-in implementation copies `source_attachments/*.png` unchanged. Replace it with a deterministic multi-observation method while preserving the CLI and output-page contract.

Grading consumes produced attachment-page PNGs, not candidate architecture. Build files, shaders, candidate Spine integration, and internal tools may be changed.

## Public Data

Final task inputs:

```text
assets/cases/static_mesh_seed_a/
assets/cases/static_mesh_seed_b/
  case.json
  skeleton.json
  skeleton.atlas
  page_manifest.json
  source_attachments/*.png
  observations/obs_000/{before,after}.png
```

Development oracle:

```text
assets/dev_cases/synthetic_dev/
  case.json
  source_attachments/
  observations/
  oracle/target_attachments/
  oracle/validation/
```

The development target is public by design and never used as a final case. See its `DEV_README.md` for the intended workflow.

After generating final results, run `tests/output_contract.py`. It validates names, dimensions, non-interlaced RGBA8 encoding, and alpha without comparing RGB.

## Licensing

Required third-party licenses and attributions are included under `third_party/` and summarized in `THIRD_PARTY_NOTICES.md`.
