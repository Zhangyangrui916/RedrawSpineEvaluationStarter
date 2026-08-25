# Continuous-Alpha V2 Status

## Frozen Task

- Independent V2 task; V1 synthetic binary-alpha cases are not part of this branch.
- Public development target: archived RedrawSpine Run 12.
- Final hidden target: independent archived Run 8.
- Ten public observations and 12 hidden validation poses.
- Original `1856 x 2288` viewport/render resolution.
- 200 complete attachment pages with continuous alpha.
- Trusted support: `max_rgb(sum_p(A[p,t]^2)) >= 1e-4` and source alpha nonzero.
- Resolved score threshold: `0.9`.

## Calibration

| Baseline | Run 12 public | Run 8 hidden | Expected |
|---|---:|---:|---|
| Reference S1 | 1.0000 | 1.0000 | Pass |
| Correct 20-iteration continuous PCG | 0.97384 | 0.97911 | Pass |
| Single-observation continuous PCG | 0.82827 | 0.81565 | Fail |
| Claude topmost/binary-alpha LS | 0.60785 | not reused across target | Fail |
| No-op S0 | approximately 0 | approximately 0 | Fail |

The correct baseline uses fixed alpha, matrix-free per-channel forward/adjoint operators, diagonal coefficient-energy
preconditioning, ridge `1e-6`, and 20 PCG iterations. Its Run 8 authoring time was about 133 seconds with roughly
0.75 GiB working memory on Windows native OpenGL.

## Packaging

- Final starter case exposes only S0, observations, skeleton/atlas, and manifests.
- Public Run 12 dev data intentionally exposes S1, validation, and aggregate energy maps.
- Private Run 8 package contains target pages, 200 trusted support masks, 12 references, and the continuous grader.
- Private support covers 1,604,189 of 4,685,761 alpha-nonzero texels (`34.2354%`).
- Grader canonicalization uses private S1 outside support for both candidate and No-op pages.

## Remaining Deployment Work

- Validate the packaged grader with Linux OSMesa and record cross-backend calibration.
- Run at least one fresh cold-agent trial from this V2 starter branch.
- Package the accepted Linux renderer and private files for DS Bench upload.
