#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    if args.work.exists():
        shutil.rmtree(args.work)
    args.work.mkdir(parents=True)

    model = root / "assets" / "source_model"
    skeleton = json.loads((model / "skeleton.json").read_text(encoding="utf-8"))
    animation_names = set(skeleton["animations"])
    manifest = json.loads((model / "page_manifest.json").read_text(encoding="utf-8"))
    require(len(manifest) == 20, "Source model must contain 20 independent pages")

    case_ids = set()
    for spec_path in sorted((root / "case_specs").glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        require(spec["schema_version"] == 1, f"Unexpected schema version: {spec_path}")
        require(spec["case_id"] not in case_ids, f"Duplicate case_id: {spec['case_id']}")
        case_ids.add(spec["case_id"])
        require(set(spec["animations"]) <= animation_names, f"Unknown animation in {spec_path}")
        require(spec["observation_budget"] >= 2, f"Observation budget is too small: {spec_path}")
        require(spec["coverage"]["max_best_single_fraction"] <= 1, f"Invalid coverage threshold: {spec_path}")
    require(case_ids == {"static_mesh_seed_a", "static_mesh_seed_b"}, f"Unexpected case specs: {case_ids}")

    output = args.work / "walk.png"
    stats = args.work / "walk.json"
    environment = dict(os.environ)
    if os.name == "nt":
        environment["REDRAWSPINE_GL_BACKEND"] = "native"
    result = subprocess.run(
        [
            str(args.renderer),
            "--skeleton",
            str(model / "skeleton.json"),
            "--atlas",
            str(model / "skeleton.atlas"),
            "--animation",
            "00_Walk",
            "--time",
            "0.4",
            "--output",
            str(output),
            "--stats",
            str(stats),
        ],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(result.returncode == 0, f"trusted-render failed:\n{result.stdout}\n{result.stderr}")
    values = json.loads(stats.read_text(encoding="utf-8"))
    require(values["draw_packets"] >= 6, f"Too few draw packets: {values}")
    require(values["nonzero_alpha_pixels"] > 5000, f"Blank render: {values}")
    require(output.stat().st_size > 1024, "Rendered PNG is unexpectedly small")

    coverage_dir = args.work / "coverage"
    coverage_stats = args.work / "coverage.json"
    result = subprocess.run(
        [
            str(args.renderer),
            "--skeleton",
            str(model / "skeleton.json"),
            "--atlas",
            str(model / "skeleton.atlas"),
            "--animation",
            "00_Walk",
            "--time",
            "0.4",
            "--mode",
            "coverage",
            "--coverage-dir",
            str(coverage_dir),
            "--stats",
            str(coverage_stats),
        ],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(result.returncode == 0, f"coverage pass failed:\n{result.stdout}\n{result.stderr}")
    coverage = json.loads(coverage_stats.read_text(encoding="utf-8"))
    require(coverage["owned_screen_pixels"] > 5000, f"Coverage ownership is empty: {coverage}")
    require(coverage["reliable_screen_pixels"] > 1000, f"Reliable coverage is empty: {coverage}")
    require(len(list(coverage_dir.glob("page_*.png"))) >= 6, "Coverage pass wrote too few page masks")

    print(
        json.dumps(
            {"passed": True, "case_ids": sorted(case_ids), "render": values, "coverage": coverage}, indent=2
        )
    )


if __name__ == "__main__":
    main()
