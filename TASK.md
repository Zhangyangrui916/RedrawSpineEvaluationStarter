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

## Hidden Scoring Contract

For each final case, the authoring renderer computes a trusted texture-space support mask from all public observations. It accepts stable topmost attachment ownership and records the complete 2x2 bilinear texel footprint. Candidate RGB outside this reliable public-observation support is restored to S0 in a temporary grading copy. The submitted files are not modified.

The trusted renderer then renders undisclosed poses with the original skeleton and the temporary candidate pages. For each hidden frame:

```text
candidate_distance = mean absolute RGBA8 distance(candidate, reference) / 255
noop_distance      = mean absolute RGBA8 distance(S0, reference) / 255
quality            = clamp(1 - candidate_distance / noop_distance, 0, 1)
```

A case score is:

```text
0.8 * mean(frame qualities) + 0.2 * mean(bottom 20% frame qualities)
```

The final score is the mean of the two case scores. The resolved threshold for this local calibration task is `0.9`. Final scoring is run once after completion; there is no queryable final score during development.

Candidate-generated masks may be useful diagnostics, but they do not define the final grading support.

## Forward Semantics

The supplied renderer source is the authoritative forward convention even if you replace its implementation. Cases use the viewport and render size in `case.json`, pixel-center rasterization, GL_LINEAR texture filtering, clamp-to-edge, straight alpha, normal blending, RGBA8 output, no mipmaps, no sRGB conversion, no MSAA, and no dithering. PNG readback is top-down after the renderer's vertical flip.

`before.png` is generated from known S0 with these same semantics and can be used to validate projection, UV, draw order, filtering, and readback orientation.

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
