# RedrawSpine Continuous-Alpha V2 Starter

Source-only starter for a deterministic static Spine texture reconstruction task. Read `TASK.md` first; it defines the
continuous-alpha forward model, required pages, public development oracle, trusted-support policy, and hidden score.

## Included

- Official `spine-cpp` from the `spine-runtimes` 4.2 branch.
- Hidden-window OpenGL 3.3 color renderer for the frozen forward convention.
- Region and ordinary/weighted/linked mesh extraction after runtime animation, deform, IK, and transform constraints.
- One final Run 8 case with S0 and ten before/after observations.
- One fully public Run 12 development oracle with S1, validation renders, and per-texel coefficient energy.
- `redrawspine-reconstruct`, initially a No-op S0 copier.

The final case contains no S1 pages, trusted support masks, hidden poses, reference frames, private generator, or grader.

## Build

With Ninja:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
```

Ninja places executables under `build/`. Multi-config generators place Release executables under `build/Release/`.

On Windows, use an x64 Native Tools Command Prompt or Developer PowerShell for VS 2022. On Linux, install a compiler,
CMake, Ninja, and headless Mesa (`libgl1-mesa-dev`, `libegl1-mesa-dev`, `libosmesa6`). The vendored GLFW build disables
X11 and Wayland. `REDRAWSPINE_GL_BACKEND=auto` tries EGL, OSMesa, then native; graders use headless Mesa.

## Optional Pristine Preflight

Before editing, use an external build directory so author-only source audits are unaffected:

```bash
cmake -S . -B ../redrawspine-v2-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DREDRAWSPINE_STARTER_TESTS=ON
cmake --build ../redrawspine-v2-build -j2
ctest --test-dir ../redrawspine-v2-build --output-on-failure
```

This verifies the forward renderer and No-op starter. It is not a reconstruction-quality test and need not remain valid
after a candidate replaces starter internals.

## Run

```bash
./build/redrawspine-render \
  --skeleton assets/cases/real_art_continuous_run8/skeleton.json \
  --atlas assets/cases/real_art_continuous_run8/skeleton.atlas \
  --animation action --time 0.5 \
  --output preview.png \
  --width 1856 --height 2288 \
  --viewport-x -1099 --viewport-y -3 \
  --viewport-width 1856 --viewport-height 2288

./build/redrawspine-reconstruct \
  --case assets/cases/real_art_continuous_run8 \
  --output results/real_art_continuous_run8

python tests/output_contract.py \
  --case assets/cases/real_art_continuous_run8 \
  --output results/real_art_continuous_run8
```

Keep generated build products and result pages out of source control.
