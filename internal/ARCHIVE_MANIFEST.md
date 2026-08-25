# V2 Archive Manifest

## Included

- Authoring source, private grader source, trusted renderer, schemas, tests, scripts, and vendored dependencies.
- Historical V1-V4 design documents and framework review notes.
- Curated replay, operator, energy, baseline, score, support, and provenance JSON reports.
- DS Bench `test_by_code.py`, package metadata, validation summary, upload instructions, and parts manifest.

## Excluded

- `C:/code/RedrawSpineEvaluationAuthoring/generated` (about 3.82 GiB of regenerable intermediates).
- `build-local` and all compiler output.
- Duplicate `exports/starter_assets`; the repository root already contains the frozen V2 starter.
- The complete private package and DS Bench `.partNNN` payloads. These contain hidden S1/support data and belong in
  private artifact storage or Git LFS, not ordinary public Git history.

## Frozen External Artifacts

- DS Bench archive SHA-256: `e3bf1dd465ecb201e5df6908a1d664571e3521365ef9eb380cd977e482849f11`
- DS Bench archive size: `38,768,742` bytes
- Accepted Linux OSMesa renderer SHA-256: `c8925ce73fe4d66028b7bd8e1ad4173b40aecd3cd39f175c5a0899c75ec248b7`
- Private package source size at packaging: `100,465,748` bytes
- Local DS Bench payload directory at archive time: `C:/Users/yurayzhang/Downloads/RedrawSpine_V2_DSBench_Grader`

The parts manifest under `artifacts/dsbench/` records every payload part size and SHA-256 without committing the private
payload itself.
