#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy_clean(source: Path, destination: Path, force: bool) -> None:
    if destination.exists():
        if not force:
            raise SystemExit(f"Output exists: {destination}; use --force")
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package a fully public development oracle case.")
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    case_root = args.case_root.resolve()
    output = args.output.resolve()
    starter = case_root / "starter_export"
    private = case_root / "private"
    required = [starter / "case.json", private / "s1_pages", private / "s1.atlas", private / "hidden"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Case has not completed the authoring pipeline; missing={missing}")

    copy_clean(starter, output, args.force)
    oracle = output / "oracle"
    target_pages = oracle / "target_attachments"
    shutil.copytree(private / "s1_pages", target_pages)
    target_atlas = (private / "s1.atlas").read_text(encoding="utf-8").replace("s1_pages/", "target_attachments/")
    (oracle / "target.atlas").write_text(target_atlas, encoding="utf-8")
    shutil.copytree(private / "hidden", oracle / "validation")

    case = json.loads((starter / "case.json").read_text(encoding="utf-8"))
    validation = json.loads((private / "hidden" / "hidden_poses.json").read_text(encoding="utf-8"))
    metadata = {
        "schema_version": 1,
        "case_id": case["case_id"],
        "candidate_input": "case.json",
        "target_attachments": "oracle/target_attachments",
        "target_atlas": "oracle/target.atlas",
        "validation_manifest": "oracle/validation/hidden_poses.json",
        "validation_poses": len(validation),
        "purpose": "public-development-oracle",
        "final_cases_expose_target_attachments": False,
    }
    (output / "dev_oracle.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    readme = f"""# Public Development Oracle: {case['case_id']}

This directory is a calibration fixture, not a final scored case.

## Intended workflow

1. Develop using `case.json`, `source_attachments/`, and `observations/`.
2. Produce static pages with the same CLI and output contract as a final case.
3. Use `oracle/` only after reconstruction to diagnose page and render-space errors.

Each `observations/*/before.png` was rendered from `source_attachments/` (S0) with the supplied renderer, using the
skeleton, animation pose, viewport, and render size recorded in `case.json`. The paired `after.png` uses the same
settings and the fixed development target skin S1.

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
"""
    (output / "DEV_README.md").write_text(readme, encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output),
                "case_id": case["case_id"],
                "observations": len(case["observations"]),
                "target_pages": len(list(target_pages.glob("*.png"))),
                "validation_poses": len(validation),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
