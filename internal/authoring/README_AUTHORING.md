# RedrawSpine Evaluation Authoring

Private, local-only data generation and grading workspace. Do not publish this directory or copy its private passes, target pages, hidden poses, reference frames, or thresholds into the candidate starter.

The implementation is intentionally case-specific and script-oriented. Reproducibility is enforced through explicit specs, seeds, manifests, generated reports, and deterministic output directories rather than a general-purpose framework.

## Backends

- Local iteration: `REDRAWSPINE_GL_BACKEND=native` on Windows.
- Final platform validation: `REDRAWSPINE_GL_BACKEND=osmesa` in the verified Linux image.

Use the same trusted renderer source for both. Windows-generated observations, reference frames, and no-op frames may be retained. The threshold was frozen at `0.9` after the final OSMesa grader produced `0.99598` for Reference S1 and `0.0` for No-op. Pixel-identical cross-backend output is not required.

## Build

```powershell
cmake -S . -B C:/tmp/redrawspine-authoring-build -G "Visual Studio 17 2022" -A x64
cmake --build C:/tmp/redrawspine-authoring-build --config Release -j 2
ctest --test-dir C:/tmp/redrawspine-authoring-build -C Release --output-on-failure
```

## Planned Pipeline

```text
authoring spec
  -> candidate poses
  -> private attachment-ID/UV coverage
  -> greedy observation selection
  -> deterministic S0/S1 pages
  -> before/after observations
  -> hidden poses + reference/no-op frames
  -> candidate-visible starter export
  -> private test_files export
  -> artifact-only render-space grader
```

The V1 case family is mixed static mesh. Region, ordinary/weighted/linked Mesh, attachment switching, occlusion, and draw order all contribute through complete rendered frames; there are no type-specific cases or mutant suite.

Reliable coverage is filtered in screen space: alpha must be nearly opaque and the topmost page ID must remain constant in a 5x5 neighborhood. Each surviving UV sample marks its 2x2 bilinear texel footprint. The sparse texture-space masks are not morphologically eroded.

## Public Development Oracles

See `DEV_CASES.md` for the generated `synthetic_dev` and `real_art_dev` fixtures. These packages intentionally expose
S1 pages and validation references, so development feedback does not require a private scoring service. Final cases
remain separate and never expose an iterative hidden-score oracle.

`synthetic_dev` and the regenerated final Seed A/B cases use the seeded high-dimensional `band_limited_v2` target
generator at 1:1 observation resolution. `legacy_periodic_v1` remains available only for reproducing superseded data.
