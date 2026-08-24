# Task: Reconstruct Static Spine Attachment Pages

This workspace contains two final reconstruction cases:

```text
assets/cases/static_mesh_seed_a
assets/cases/static_mesh_seed_b
```

Each case contains the same Spine skeleton topology and a different unknown target skin. Its `observations/` directory contains several `(before, after)` renders:

```text
before = the source skin S0 rendered at a pose
after  = one fixed unknown target skin S1 rendered at the same pose
```

Observations have no processing-order semantics. Combine every observation for a case to reconstruct one reusable set of static attachment-page PNGs.

## Public Development Oracle

`assets/dev_cases/synthetic_dev` is a fully public calibration fixture. It exposes S1 pages and validation references under `oracle/` intentionally. Develop from its `case.json`, S0, and observations first; inspect the oracle afterward to diagnose texture-space and render-space errors.

Final cases use different target seeds and do not expose S1, trusted support masks, hidden poses, references, or an iterative score. Copying or hardcoding the development target cannot solve them. Exact target-page equality is not required when observations underdetermine individual texels; validation is render-space behavior.

## Required Results

Build and run your implementation. Leave the final pages at:

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

Replace it with a deterministic multi-observation reconstruction method.

## Output Contract

- Produce exactly the pages listed by each `case.json`.
- Names and dimensions must match `output_pages`.
- Files must be non-interlaced RGBA8 PNGs.
- Every output alpha channel must exactly match the corresponding source page.
- RGB under alpha 0 is ignored and canonicalized to transparent black by the grader.
- Output RGB may and should differ from S0.
- Produce one pose-independent static page set. Per-frame caches are not an alternative output.
- The grader uses the original supplied skeleton, atlas mapping, animations, and meshes. Candidate-side asset edits do not change the grading geometry.

Validate format and alpha without checking RGB:

```bash
python tests/output_contract.py \
  --case assets/cases/static_mesh_seed_a \
  --output results/static_mesh_seed_a
```

## Hidden Evaluation

The grader renders the submitted static pages at undisclosed poses using the original supplied skeleton and atlas mapping.

Scoring is based on render-space similarity to the hidden target skin. RGB in regions that the public observations do not reliably constrain is neutralized before rendering, so candidates are not rewarded or penalized for a particular completion or flood choice there. The submitted files are not modified.

Scores are normalized so that copying S0 is approximately 0 and reproducing the target renders is 1. Both final cases and consistently weak poses contribute to the result. The resolved threshold for this local calibration task is `0.9`.

Final evaluation is run once after completion; there is no queryable final score during development. Candidate-generated masks may be useful diagnostics, but they do not define the grading region.

## Forward Semantics

The supplied renderer source is the authoritative forward convention even if you replace its implementation. Cases use the viewport and render size in `case.json`, pixel-center rasterization, GL_LINEAR texture filtering, clamp-to-edge, straight alpha, normal blending, RGBA8 output, no mipmaps, no sRGB conversion, no MSAA, and no dithering. PNG readback is top-down after the renderer's vertical flip.

## Implementation Freedom

Only the final page behavior and CLI are frozen. You may modify, repurpose, replace, or remove the supplied color renderer; change shaders; modify candidate-side Spine integration; implement an ID/UV pass; use a CPU method; or build different internal tools.

`redrawspine-render` and the opt-in pristine-starter preflight are starting infrastructure, not final grading requirements.

## V1 Data Contract

Cases may contain RegionAttachment and ordinary/weighted/linked MeshAttachment, attachment switching, bone translate/rotate/scale/shear, and draw-order changes. They use a fixed viewport, normal blend, binary texture alpha, and one complete atlas page per output attachment.

They do not contain deform timelines, IK/path/transform/physics constraints, clipping, complex blend modes, internal semitransparent texels, atlas packing, rotation, trim, or padding.

`page_manifest.json` maps Spine region names to complete page files. JSON, atlas, manifests, and documentation use UTF-8 without BOM.

## Local Trial Budget

For this local calibration rollout, target a clean configure/build plus both final reconstructions within 15 minutes and 4 GiB peak memory. Record actual time and memory if available. This provisional budget is deliberately generous and is not yet the frozen DS Bench production limit.

Do not access the network or external APIs. Run the supplied project and public checks locally; do not only describe a solution in the final response.
