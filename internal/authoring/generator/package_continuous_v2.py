#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


VISIBLE_FILES = ("case.json", "skeleton.json", "skeleton.atlas", "page_manifest.json")


def copy_visible(case_root: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for name in VISIBLE_FILES:
        shutil.copyfile(case_root / name, destination / name)
    shutil.copytree(case_root / "source_attachments", destination / "source_attachments")
    shutil.copytree(case_root / "observations", destination / "observations")


def make_support_masks(case_root: Path, energy_root: Path, destination: Path, threshold: float) -> dict:
    case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
    destination.mkdir(parents=True)
    support_texels = 0
    alpha_texels = 0
    page_reports = []
    for page in case["output_pages"]:
        name = page["name"]
        shape = (page["height"], page["width"])
        energy = np.fromfile(energy_root / "aggregate" / f"{name}.energy.f32", dtype=np.float32)
        if energy.size != shape[0] * shape[1]:
            raise ValueError(f"Energy size mismatch for {name}")
        alpha = np.asarray(
            Image.open(case_root / case["source_attachments"] / name).convert("RGBA"), dtype=np.uint8
        )[:, :, 3]
        support = (energy.reshape(shape) >= threshold) & (alpha > 0)
        Image.fromarray((support * 255).astype(np.uint8), "L").save(destination / name)
        support_count = int(support.sum())
        alpha_count = int(np.count_nonzero(alpha))
        support_texels += support_count
        alpha_texels += alpha_count
        page_reports.append(
            {
                "name": name,
                "support_texels": support_count,
                "alpha_nonzero_texels": alpha_count,
                "support_fraction": support_count / max(alpha_count, 1),
            }
        )
    return {
        "energy_threshold": threshold,
        "support_texels": support_texels,
        "alpha_nonzero_texels": alpha_texels,
        "support_fraction": support_texels / max(alpha_texels, 1),
        "page_reports": page_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the independent continuous-alpha V2 task.")
    parser.add_argument("--public-dev", type=Path, required=True)
    parser.add_argument("--hidden-case", type=Path, required=True)
    parser.add_argument("--public-energy", type=Path, required=True)
    parser.add_argument("--hidden-energy", type=Path, required=True)
    parser.add_argument("--starter-export", type=Path, required=True)
    parser.add_argument("--private-export", type=Path, required=True)
    parser.add_argument("--energy-threshold", type=float, default=1e-4)
    parser.add_argument("--resolved-threshold", type=float, default=0.9)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    public_dev = args.public_dev.resolve()
    hidden_case = args.hidden_case.resolve()
    public_energy = args.public_energy.resolve()
    hidden_energy = args.hidden_energy.resolve()
    starter = args.starter_export.resolve()
    private = args.private_export.resolve()
    for output in (starter, private):
        if output.exists():
            if not args.force:
                raise SystemExit(f"Output exists: {output}; use --force")
            shutil.rmtree(output)

    public_case = json.loads((public_dev / "case.json").read_text(encoding="utf-8"))
    hidden_case_json = json.loads((hidden_case / "case.json").read_text(encoding="utf-8"))
    starter_public = starter / "dev_cases" / public_case["case_id"]
    starter_hidden = starter / "cases" / hidden_case_json["case_id"]
    copy_visible(public_dev, starter_public)
    copy_visible(hidden_case, starter_hidden)

    shutil.copyfile(public_dev / "dev_oracle.json", starter_public / "dev_oracle.json")
    shutil.copyfile(public_dev / "DEV_README.md", starter_public / "DEV_README.md")
    shutil.copytree(public_dev / "oracle" / "target_attachments", starter_public / "oracle" / "target_attachments")
    shutil.copyfile(public_dev / "oracle" / "target.atlas", starter_public / "oracle" / "target.atlas")
    shutil.copyfile(public_dev / "oracle" / "provenance.json", starter_public / "oracle" / "provenance.json")
    shutil.copytree(public_dev / "oracle" / "validation", starter_public / "oracle" / "validation")
    public_operator = starter_public / "operator_energy"
    public_operator.mkdir()
    shutil.copyfile(public_energy / "energy_report.json", public_operator / "energy_report.json")
    shutil.copytree(public_energy / "aggregate", public_operator / "aggregate")
    (starter_public / "PUBLIC_DEV.md").write_text(
        """# Public V2 Development Oracle

This fixture intentionally exposes S1 and validation references. Use it to validate a reconstruction method before
running the same method on the final Run 8 case. The final case does not expose S1, coefficient-energy maps, trusted
support masks, hidden poses, references, or a score oracle.

`operator_energy/aggregate/*.energy.f32` stores little-endian float32 per-texel `max_rgb(sum_p(A[p,t]^2))` values.
The PNG beside each raw map is a visualization only. These maps are diagnostic data, not candidate-submitted masks.
""",
        encoding="utf-8",
    )

    private_case = private / "cases" / hidden_case_json["case_id"]
    copy_visible(hidden_case, private_case / "contract")
    hidden = private_case / "hidden"
    hidden.mkdir(parents=True)
    shutil.copytree(hidden_case / "oracle" / "target_attachments", hidden / "target_attachments")
    shutil.copyfile(hidden_case / "oracle" / "target.atlas", hidden / "target.atlas")
    shutil.copyfile(hidden_case / "oracle" / "provenance.json", hidden / "provenance.json")
    validation = hidden_case / "oracle" / "validation"
    shutil.copyfile(validation / "hidden_poses.json", hidden / "hidden_poses.json")
    shutil.copytree(validation / "reference_frames", hidden / "reference_frames")
    support_report = make_support_masks(
        hidden_case, hidden_energy, hidden / "support_masks", args.energy_threshold
    )
    (hidden / "support_report.json").write_text(json.dumps(support_report, indent=2), encoding="utf-8")

    grader = private / "grader"
    grader.mkdir()
    thresholds = {
        "schema_version": 2,
        "task": "continuous-alpha-real-art-v2",
        "case_ids": [hidden_case_json["case_id"]],
        "coefficient_energy_threshold": args.energy_threshold,
        "overall_threshold": args.resolved_threshold,
        "score_policy": "candidate=S1 outside support; noop=S1 outside support; normalized hidden render-space L1",
        "calibration": {
            "public_run12_correct_pcg": 0.9738354245267979,
            "public_run12_single_observation": 0.8282708321280864,
            "public_run12_claude_binary_topmost": 0.6078536502842778,
            "hidden_run8_correct_pcg": 0.9791118935269605,
            "hidden_run8_single_observation": 0.8156453476391875,
            "reference": 1.0,
            "noop": 0.0,
        },
    }
    (grader / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    authoring_root = Path(__file__).resolve().parent.parent
    shutil.copyfile(authoring_root / "grader" / "grade_continuous_case.py", grader / "grade_continuous_case.py")
    shutil.copyfile(authoring_root / "grader" / "grade_continuous_all.py", grader / "grade_continuous_all.py")
    manifest = {
        "schema_version": 2,
        "starter_public_case": public_case["case_id"],
        "starter_final_case": hidden_case_json["case_id"],
        "private_case": hidden_case_json["case_id"],
        "support": {key: value for key, value in support_report.items() if key != "page_reports"},
        "resolved_threshold": args.resolved_threshold,
    }
    (private / "package_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (starter / "export_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"starter": str(starter), "private": str(private), **manifest}, indent=2))


if __name__ == "__main__":
    main()
