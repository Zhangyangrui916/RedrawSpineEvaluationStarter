# Authoring Status

## Continuous-Alpha Real-Art V2

V2 is an independent task branch; it does not add a case to V1.

- Archived Run 12 public dev and Run 8 hidden pilot replay exactly match all 50 stored redraw pages.
- Target assembly uses final Written mask OR replay RGB nonwhite on the 50 redraw pages, with canonical S0 alpha.
- Shared CPU raster traversal implements per-channel matrix-free forward, adjoint, and coefficient energy.
- Adjoint dot-product relative error: `3.05e-8`; real-delta linear prediction MAE: `0.0723/255`.
- Trusted support is frozen at `max_rgb(sum_p(A[p,t]^2)) >= 1e-4` and alpha nonzero.
- Run 8 support: 1,604,189 / 4,685,761 alpha-nonzero texels (`34.2354%`).
- Private grader neutralizes candidate and No-op RGB to S1 outside trusted support.
- Frozen threshold: `0.9`.

| Baseline | Run 12 | Run 8 |
|---|---:|---:|
| Reference | 1.0000 | 1.0000 |
| Correct continuous PCG | 0.97384 | 0.97911 |
| Single observation | 0.82827 | 0.81565 |
| Claude topmost/binary LS | 0.60785 | not reused across target |
| No-op | approximately 0 | approximately 0 |

Generated packages:

- `generated/continuous_alpha_v2/exports/starter_assets`
- `generated/continuous_alpha_v2/exports/private_package`

Starter `v2` has been synchronized with one final Run 8 case and the Run 12 public dev oracle. Windows clean Release
build, 200-page output contract, forward preflight, and source/private-leak audit pass. Remaining deployment gates are
Linux OSMesa acceptance and a fresh cold-agent trial.

## Implemented

- Private schemas plus two final mixed static-mesh case specifications.
- Independent official spine-cpp 4.2 trusted renderer.
- Windows native OpenGL color and page-ID/UV coverage rendering.
- 5x5 stable-owner reliability filtering and 2x2 bilinear texel footprints.
- Greedy multi-pose selection and coverage/ownership audits.
- Low-information S0 plus high-dimensional seeded `band_limited_v2` S1 generation.
- 1:1 (`2450 x 1900`) final observations.
- Candidate-visible final exports and a fully public `synthetic_dev` oracle.
- Optional archived-production `real_art_dev` oracle.
- Hidden pose selection and reference/no-op frame generation.
- Private observable-mask export.
- Artifact-only grader that restores mask-external candidate RGB to S0 before hidden rendering.
- Two-case aggregate render-space grading.

## Final V2 Calibration Data

### static_mesh_seed_a

- Candidate poses: 59
- Observations: 6
- Best-single coverage: 481,308 texels
- Union coverage: 959,819 texels
- Union gain over best single: 0.994
- Best-single fraction: 0.501
- Ownership-changing selected pose pairs: 15
- Maximum changed topmost pixels: 205,002
- Hidden poses: 20
- Hidden No-op distance: 0.00923 to 0.01058

### static_mesh_seed_b

- Candidate poses: 51
- Observations: 7
- Best-single coverage: 487,758 texels
- Union coverage: 899,384 texels
- Union gain over best single: 0.844
- Best-single fraction: 0.542
- Ownership-changing selected pose pairs: 21
- Maximum changed topmost pixels: 220,564
- Hidden poses: 24
- Hidden No-op distance: 0.00892 to 0.01279

### Grader Closure

| Baseline | Aggregate score | Expected result |
|---|---:|---|
| Reference S1 | 1.0000 | Pass |
| Claude LS, lambda=0.08 | 0.9981 | Pass |
| nearest scatter without fill | 0.9815 | Pass at 1:1 |
| Single-observation LS | 0.6807 | Fail |
| No-op S0 | approximately 0 | Fail |

The production threshold is frozen at `0.9`. It was not moved to fit these results.

### Linux OSMesa Acceptance (2026-08-24)

- Debian 13, GCC 14.2, Python 3.12, OSMesa backend confirmed by a nonblank smoke render.
- Reference S1: `0.99598` (pass).
- Cold-agent reconstruction: `0.99515` (pass).
- Single-observation reconstruction: `0.67850` (fail).
- No-op S0: `0.0` (fail).
- Peak grader RSS across the four runs: `198,356 kB`.
- Aggregate grading wall time per result set: 38-43 seconds on the validation container.
- DSBench deployment removes grader-unused observation files and stored No-op frames. No-op normalization frames are
  rendered from S0 at scoring time with the trusted OSMesa renderer. The private archive is uploaded as independently
  checksummed parts of at most 20 MiB, remaining below both the upload request limit and the 64 MiB fallback asset-layer
  limit used when the platform has no `mkfs.erofs`.
- The Code grader discovers the unique final results root at either `/workspace/results` or one direct repository child
  such as `/workspace/starter/results`; DSBench mounts the downloaded starter in the latter layout.

## V1 Starter Readiness

- Regenerated final A/B and `synthetic_dev` are synchronized to the starter worktree.
- Candidate preflight and maintainer source audit are separate CMake options.
- Clean Visual Studio Release build and candidate preflight pass.
- Final and dev case schemas and output contracts pass.
- Private masks, references, and grader code are absent from starter final cases.
- Clean trial workspace: `C:/code/_agent_trial_v2/work`.

## V1 Remaining Non-Blocking Work

- Run one production-platform Code grading smoke test after uploading the final private bundle.
- V1 master remains frozen; continuous-alpha work proceeds only on V2.

No Region/Mesh type-specific cases, mutant suite, or continuous-alpha final V1 gate is used.
