# Task: Reconstruct a Continuous-Alpha Spine Skin

Reconstruct one pose-independent set of static Spine attachment-page PNGs for:

```text
assets/cases/real_art_continuous_run8
```

The case contains ten `(before, after)` observations. Every `before` is the known source skin S0 rendered at a pose;
every `after` is the same unknown target skin S1 rendered at that pose. Observations have no processing-order
semantics. Combine all of them.

This is an inverse-rendering task, not frame recoloring. The final pages must work at poses that are not observations.

## Public Development Oracle

Start with:

```text
assets/dev_cases/real_art_continuous_dev_run12
```

It uses the same model, poses, alpha, and forward convention with a different archived redraw. It intentionally exposes
S1 pages, validation references, and coefficient-energy diagnostics. Use those files to test an algorithm and inspect
failure modes before running it unchanged on the final Run 8 case.

The final case does not expose S1, trusted support masks, hidden poses, references, or an iterative score. A method that
hardcodes or copies the Run 12 target cannot solve Run 8.

## Required Result

Leave exactly 200 output PNGs under:

```text
results/real_art_continuous_run8
```

The starter executable is an explicit No-op baseline:

```bash
./build/redrawspine-reconstruct \
  --case assets/cases/real_art_continuous_run8 \
  --output results/real_art_continuous_run8
```

Replace it with a deterministic multi-observation reconstruction method. The implementation technique is not scored;
matrix-free optimization, inverse mapping, iterative scatter, or another defensible method are all allowed.

## Output Contract

- Produce exactly the pages in `case.json::output_pages`, with matching names and dimensions.
- Files must be non-interlaced RGBA8 PNGs.
- Preserve every source alpha value exactly, including semitransparent values. Only RGB is unknown.
- RGB under alpha 0 is ignored and canonicalized to transparent black by the grader.
- Produce one reusable static page set. Per-frame caches are not an alternative output.
- Grading always uses the original skeleton, atlas mapping, animations, constraints, meshes, and draw order.

Validate structure and alpha without checking RGB:

```bash
python tests/output_contract.py \
  --case assets/cases/real_art_continuous_run8 \
  --output results/real_art_continuous_run8
```

## Why Continuous Alpha Matters

One rendered pixel may contain contributions from several attachment layers. For a pixel `p`, process fragments from
bottom to top. With known texture alpha, tint, geometry, and draw order:

```text
sample_alpha_i = tint_alpha_i * bilinear(texture_alpha_i)
coefficient_i  = sample_alpha_i * product_{j above i}(1 - sample_alpha_j)
frame_rgb_p    = sum_i(coefficient_i * tint_rgb_i * bilinear(texture_rgb_i))
```

The RGB problem remains linear because alpha is fixed. Subtracting each `before` from its `after` removes the known S0
render and gives equations for `delta_texture_rgb = S1.rgb - S0.rgb`.

A V1-style rule that assigns each pixel only to its topmost attachment is not the forward model for this task.

## Hidden Evaluation

The grader renders submitted pages at 12 undisclosed poses and compares them with S1 references. Individual texels that
the ten observations do not stably constrain are neutralized before rendering, so flood/inpainting outside trusted
support is neither rewarded nor penalized.

Trusted texture support is computed privately from the public observation operator:

```text
energy[t, c] = sum_p(A_c[p, t]^2)
support[t]   = alpha[t] > 0 and max_c(energy[t, c]) >= 1e-4
```

Outside support, both candidate and No-op evaluation pages use private S1 RGB. Inside support, the candidate uses its
submitted RGB and No-op uses S0 RGB. Candidate-generated masks do not define grading support.

Scores use hidden render-space RGBA L1 and are normalized so No-op is approximately 0 and Reference S1 is 1. The final
score is 80% mean pose quality plus 20% bottom-20% pose quality. The resolved threshold is `0.9`.

Exact full-page S1 recovery is not guaranteed or required. A candidate can be correct on the resolved task while its
subjective completion outside support differs from the public S1 oracle.

## Forward Convention

The supplied renderer source is the authoritative forward convention even if you replace it. It uses the viewport and
render size in `case.json`, pixel-center rasterization, `GL_LINEAR` texture filtering, clamp-to-edge, straight alpha,
normal blending, RGBA8 output, no mipmaps, no sRGB conversion, no MSAA, and no dithering. PNG readback is top-down after
the framebuffer row flip.

Use `before.png` as a self-calibration signal: rendering the known S0 through a candidate forward model should reproduce
it to RGBA8 quantization tolerance before solving the inverse problem.

## Data Contract

- Spine 4.2 JSON with 308 bones, 209 slots, and 200 complete one-region atlas pages.
- RegionAttachment and ordinary/weighted/linked MeshAttachment.
- Attachment switching, draw-order changes, deform timelines, IK constraints, and transform constraints.
- Normal blend and straight alpha only; no clipping, packed atlas regions, rotation, trim, padding, or PMA.
- Real continuous attachment alpha and multiple simultaneously contributing layers.
- Fixed `1856 x 2288` viewport and render size, approximately one framebuffer pixel per world unit.

`page_manifest.json` maps Spine region names to complete page files. JSON, atlas, manifests, and documentation use UTF-8
without BOM.

## Budget and Restrictions

Target a clean configure/build plus final reconstruction within 15 minutes and 4 GiB peak memory. The calibrated
private PCG baseline takes about 134 seconds and 0.75 GiB on the authoring Windows machine; this is guidance, not a
required algorithm.

Do not access the network or external APIs. Run the supplied project and public checks locally; do not only describe a
solution in the final response.
