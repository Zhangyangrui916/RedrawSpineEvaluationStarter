#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


AUTHORING_DIRS = (
    "assets",
    "author_tests",
    "case_specs",
    "dev_specs",
    "generator",
    "grader",
    "schemas",
    "scripts",
    "third_party",
    "trusted_renderer",
)

AUTHORING_FILES = (
    ".gitignore",
    "CMakeLists.txt",
    "CONTINUOUS_ALPHA_V2_DESIGN_DRAFT.md",
    "DEV_CASES.md",
    "README_AUTHORING.md",
    "STATUS.md",
)

CALIBRATION_FILES = {
    "replay/run8_replay_report.json": "generated/continuous_alpha_v2/replay_run_8/replay_report.json",
    "replay/run11_replay_report.json": "generated/continuous_alpha_v2/replay_run_11/replay_report.json",
    "replay/run12_replay_report.json": "generated/continuous_alpha_v2/replay_run_12/replay_report.json",
    "operator/action_0_1_forward_adjoint_check.json": "generated/continuous_alpha_v2/operator_check_action_0_1/report.json",
    "operator/run12_energy_report.json": "generated/continuous_alpha_v2/public_dev_run12/operator_energy/energy_report.json",
    "operator/run8_energy_report.json": "generated/continuous_alpha_v2/hidden_pilot_run8/operator_energy/energy_report.json",
    "baseline/run12_correct_pcg.json": "generated/continuous_alpha_v2/public_dev_run12/baseline_pcg_20iter/report.json",
    "baseline/run12_single_observation.json": "generated/continuous_alpha_v2/public_dev_run12/baseline_single_observation/report.json",
    "baseline/run8_correct_pcg.json": "generated/continuous_alpha_v2/hidden_pilot_run8/baseline_pcg_20iter/report.json",
    "baseline/run8_single_observation.json": "generated/continuous_alpha_v2/hidden_pilot_run8/baseline_single_observation/report.json",
    "scores/run12_correct.json": "generated/continuous_alpha_v2/public_dev_run12/baseline_pcg_20iter_grade_exact_energy/report.json",
    "scores/run12_single_observation.json": "generated/continuous_alpha_v2/public_dev_run12/baseline_single_observation_grade_exact_energy/report.json",
    "scores/run12_claude_binary.json": "generated/continuous_alpha_v2/public_dev_run12/claude_binary_grade_exact_energy/report.json",
    "scores/run8_correct.json": "generated/continuous_alpha_v2/hidden_pilot_run8/grade_correct_exact_energy.json",
    "scores/run8_single_observation.json": "generated/continuous_alpha_v2/hidden_pilot_run8/grade_single_exact_energy.json",
    "private/package_manifest.json": "generated/continuous_alpha_v2/exports/private_package/package_manifest.json",
    "private/thresholds.json": "generated/continuous_alpha_v2/exports/private_package/grader/thresholds.json",
    "private/support_report.json": "generated/continuous_alpha_v2/exports/private_package/cases/real_art_continuous_run8/hidden/support_report.json",
    "private/provenance.json": "generated/continuous_alpha_v2/exports/private_package/cases/real_art_continuous_run8/hidden/provenance.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> dict:
    if not source.is_file():
        raise ValueError(f"Archive source file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "path": destination.as_posix(),
        "source": str(source),
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a curated V2 authoring archive inside the starter worktree.")
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    authoring = args.authoring.resolve()
    downloads = args.downloads.resolve()
    destination = args.destination.resolve()
    repository = destination.parent
    if destination.name != "internal" or not (repository / ".git").is_dir():
        raise SystemExit(f"Destination must be <starter-worktree>/internal: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise SystemExit(f"Destination is not empty: {destination}")

    archive_authoring = destination / "authoring"
    for name in AUTHORING_DIRS:
        shutil.copytree(
            authoring / name,
            archive_authoring / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for name in AUTHORING_FILES:
        copy_file(authoring / name, archive_authoring / name)

    index = []
    calibration = destination / "calibration"
    for relative, source_relative in CALIBRATION_FILES.items():
        index.append(copy_file(authoring / source_relative, calibration / relative))

    historical = destination / "docs" / "history"
    for source in sorted(downloads.glob("RedrawSpine*.md")) + sorted(downloads.glob("RedrawSpine*.docx")):
        index.append(copy_file(source, historical / source.name))

    preview = downloads / "Grok_V2_Render_Preview"
    for name in ("README.md", "poses.json", "raw_render_metrics.json"):
        index.append(copy_file(preview / name, calibration / "grok_preview" / name))

    ds_source = downloads / "RedrawSpine_V2_DSBench_Grader"
    ds_destination = destination / "artifacts" / "dsbench"
    for name in (
        "PACKAGE_INFO.json",
        "VALIDATION_SUMMARY.json",
        "redrawspine_grader_bundle.tar.gz.parts.json",
        "test_by_code.py",
        "UPLOAD_INSTRUCTIONS.md",
    ):
        index.append(copy_file(ds_source / name, ds_destination / name))

    (destination / ".gitignore").write_text(
        """authoring/build*/
authoring/generated/
artifacts/dsbench/*.part[0-9][0-9][0-9]
private_package/
__pycache__/
*.tmp
*.log
""",
        encoding="utf-8",
    )
    (calibration / "FILE_INDEX.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (calibration / "README.md").write_text(
        """# V2 Calibration Records

This directory contains small, immutable reports selected from the multi-gigabyte generated authoring workspace.
Rendered frames, texture pages, solver outputs, and per-pose energy arrays are intentionally excluded. `FILE_INDEX.json`
records the original local path, byte size, and SHA-256 of each copied report or historical document.
""",
        encoding="utf-8",
    )
    (destination / "README_PRIVATE.md").write_text(
        """# Private V2 Authoring Archive

This directory is not candidate-visible task material. It contains the V2 generator, trusted renderer, private grader
source, design history, calibration reports, and reproducible packaging scripts. Keep the public `v2` starter branch
free of this directory.

Do not push this archive to a public remote while the benchmark or hidden Run 8 target remains usable. The complete
private target/support package and upload-ready DS Bench parts remain external artifacts referenced by hash in
`ARCHIVE_MANIFEST.md`.

Build the standalone authoring tools with:

```bash
cmake -S internal/authoring -B ../redrawspine-authoring-build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build ../redrawspine-authoring-build -j2
```
""",
        encoding="utf-8",
    )
    (destination / "ARCHIVE_MANIFEST.md").write_text(
        """# V2 Archive Manifest

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
""",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "destination": str(destination),
                "authoring_files": sum(1 for path in archive_authoring.rglob("*") if path.is_file()),
                "indexed_records": len(index),
                "total_bytes": sum(path.stat().st_size for path in destination.rglob("*") if path.is_file()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
