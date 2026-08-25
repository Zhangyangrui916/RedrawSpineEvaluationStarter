#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = ("static_mesh_seed_a", "static_mesh_seed_b")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "exports")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"Output exists: {output}; use --force")
        shutil.rmtree(output)
    starter_cases = output / "starter_cases"
    test_files = output / "test_files"
    starter_cases.mkdir(parents=True)
    (test_files / "cases").mkdir(parents=True)
    (test_files / "grader").mkdir(parents=True)

    for case_id in CASE_IDS:
        case_root = ROOT / "generated" / case_id
        shutil.copytree(case_root / "starter_export", starter_cases / case_id)
        private_case = test_files / "cases" / case_id
        shutil.copytree(case_root / "starter_export", private_case / "contract")
        shutil.copytree(case_root / "private" / "hidden", private_case / "hidden")
        shutil.copytree(case_root / "union_coverage", private_case / "hidden" / "observable_masks")

    for filename in ("grade_case.py", "grade_all.py"):
        shutil.copyfile(ROOT / "grader" / filename, test_files / "grader" / filename)
    threshold = json.loads((ROOT / "grader" / "thresholds.json").read_text(encoding="utf-8"))
    (test_files / "grader" / "thresholds.json").write_text(json.dumps(threshold, indent=2), encoding="utf-8")

    starter_files = sorted(path for path in starter_cases.rglob("*") if path.is_file())
    forbidden_names = {"s1.atlas", "hidden_poses.json", "hidden_signal_report.json", "coverage_audit.json"}
    forbidden = [str(path.relative_to(starter_cases)) for path in starter_files if path.name in forbidden_names]
    forbidden += [str(path.relative_to(starter_cases)) for path in starter_files if "reference_frames" in path.parts]
    if forbidden:
        raise RuntimeError(f"Private files leaked into starter export: {forbidden}")

    manifest = {
        "schema_version": 1,
        "case_ids": list(CASE_IDS),
        "starter_files": [
            {"path": str(path.relative_to(starter_cases)).replace("\\", "/"), "sha256": sha256(path)}
            for path in starter_files
        ],
        "test_files_count": sum(1 for path in test_files.rglob("*") if path.is_file()),
        "contains_target_pages": False,
    }
    (output / "export_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "starter_files": len(starter_files),
                "test_files": manifest["test_files_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
