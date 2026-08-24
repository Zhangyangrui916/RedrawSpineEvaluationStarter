# Public Development Oracle: synthetic_dev

This directory is a calibration fixture, not a final scored case.

## Intended workflow

1. Develop using `case.json`, `source_attachments/`, and `observations/`.
2. Produce static pages with the same CLI and output contract as a final case.
3. Use `oracle/` only after reconstruction to diagnose page and render-space errors.

The target pages are intentionally public here. Copying or hardcoding them does not help on final cases,
which use different target seeds and do not expose S1 or validation references.

Exact target-page recovery is not guaranteed by the observations. Bilinear sampling can leave the
texture-space inverse underdetermined. Judge the method primarily by render-space behavior on the
validation poses, not by requiring byte-identical target pages.

Unobserved-texel semantics for this fixture follow its generated target: S1 differs from S0 only within
the reliable union of the public observation footprints. Final task documentation must state the frozen
unobserved-texel policy explicitly rather than requiring candidates to infer it from this oracle.

## Contents

- `case.json`: candidate input and output contract.
- `source_attachments/`: S0 pages.
- `observations/`: public before/after pairs.
- `oracle/target_attachments/`: diagnostic S1 pages.
- `oracle/target.atlas`: atlas for rendering S1 directly.
- `oracle/validation/`: public validation poses plus S0 and S1 reference frames.
