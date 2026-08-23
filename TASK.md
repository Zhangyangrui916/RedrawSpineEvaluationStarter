# Task: Reconstruct Static Spine Attachment Pages

This workspace contains two independent reconstruction cases:

```text
assets/cases/static_mesh_seed_a
assets/cases/static_mesh_seed_b
```

Each case contains the same Spine skeleton topology and a different unknown target skin. Its `observations/` directory contains several `(before, after)` renders:

```text
before = the source skin S0 rendered at a pose
after  = one fixed unknown target skin S1 rendered at the same pose
```

Observations have no processing-order semantics. Combine all observations for a case to reconstruct one reusable set of static attachment-page PNGs.

## Required Results

Build and run your implementation during this task. Leave the final pages at:

```text
results/static_mesh_seed_a/page_000.png ... page_019.png
results/static_mesh_seed_b/page_000.png ... page_019.png
```

The initial executable is a No-op baseline:

```bash
./build/redrawspine-reconstruct \
  --case assets/cases/static_mesh_seed_a \
  --output results/static_mesh_seed_a

./build/redrawspine-reconstruct \
  --case assets/cases/static_mesh_seed_b \
  --output results/static_mesh_seed_b
```

Replace the No-op implementation with a deterministic multi-observation reconstruction method.

## Output Contract

- Produce exactly the pages listed by each `case.json`.
- Names and dimensions must match `output_pages`.
- Files must be non-interlaced RGBA8 PNGs.
- Every output alpha channel must exactly match the corresponding source page.
- Output RGB may and should differ from S0.
- Do not replace static pages with per-frame caches or modify the supplied skeleton/animation/mesh as a substitute for reconstruction.

Validate either result without checking its RGB content:

```bash
python tests/output_contract.py \
  --case assets/cases/static_mesh_seed_a \
  --output results/static_mesh_seed_a
```

## Implementation Freedom

Only the final page contract is frozen. You may modify, repurpose, replace, or remove the supplied color renderer; change shaders; modify the candidate-side Spine integration; implement an ID/UV pass; use a CPU method; or build different internal tools.

`redrawspine-render` and the opt-in pristine-starter tests are starting infrastructure, not final grading requirements.

## V1 Data Contract

Cases may contain RegionAttachment and ordinary/weighted/linked MeshAttachment, attachment switching, bone translate/rotate/scale/shear, and draw-order changes. They use a fixed viewport, normal blend, binary texture alpha, and one complete atlas page per output attachment.

They do not contain deform timelines, IK/path/transform/physics constraints, clipping, complex blend modes, internal semitransparent texels, atlas packing, rotation, trim, or padding.

Do not access the network or external APIs. Run the supplied project and public contract checks locally; do not only describe a solution in your final response.
