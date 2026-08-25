#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def collect_times(value) -> list[float]:
    result: list[float] = []
    if isinstance(value, dict):
        if isinstance(value.get("time"), (int, float)):
            result.append(float(value["time"]))
        for child in value.values():
            result.extend(collect_times(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(collect_times(child))
    return result


def pose_times(duration: float, step: float) -> list[float]:
    if duration <= 0:
        return [0.0]
    count = int(math.floor(duration / step + 1e-6))
    values = [round(index * step, 4) for index in range(count + 1)]
    if duration - values[-1] > step * 0.25:
        values.append(round(duration, 4))
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    source_model = ROOT / spec["source_model"]
    skeleton_data = json.loads((source_model / "skeleton.json").read_text(encoding="utf-8"))
    case_root = args.output_root / spec["case_id"]
    candidates_root = case_root / "coverage_candidates"
    if case_root.exists():
        if not args.force:
            raise SystemExit(f"Output already exists: {case_root}; use --force to regenerate")
        shutil.rmtree(case_root)
    candidates_root.mkdir(parents=True)

    viewport = spec["viewport"]
    size = spec["render_size"]
    environment = dict(os.environ)
    if os.name == "nt":
        environment["REDRAWSPINE_GL_BACKEND"] = "native"

    candidates = []
    pose_index = 0
    for animation in spec["animations"]:
        timeline = skeleton_data["animations"][animation]
        all_times = collect_times(timeline)
        duration = max(all_times) if all_times else 0.0
        for time in pose_times(duration, float(spec.get("candidate_time_step", 0.1))):
            pose_id = f"pose_{pose_index:03d}"
            pose_root = candidates_root / pose_id
            masks = pose_root / "masks"
            stats = pose_root / "stats.json"
            command = [
                str(args.renderer),
                "--skeleton",
                str(source_model / "skeleton.json"),
                "--atlas",
                str(source_model / "skeleton.atlas"),
                "--animation",
                animation,
                "--time",
                str(time),
                "--mode",
                "coverage",
                "--coverage-dir",
                str(masks),
                "--stats",
                str(stats),
                "--boundary-radius",
                "2",
                "--width",
                str(size["width"]),
                "--height",
                str(size["height"]),
                "--viewport-x",
                str(viewport["x"]),
                "--viewport-y",
                str(viewport["y"]),
                "--viewport-width",
                str(viewport["width"]),
                "--viewport-height",
                str(viewport["height"]),
            ]
            result = subprocess.run(command, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(f"Coverage render failed for {animation}@{time}:\n{result.stdout}\n{result.stderr}")
            statistics = json.loads(stats.read_text(encoding="utf-8"))
            candidates.append(
                {
                    "id": pose_id,
                    "animation": animation,
                    "time": time,
                    "duration": duration,
                    "masks": str(masks.relative_to(case_root)).replace("\\", "/"),
                    "stats": str(stats.relative_to(case_root)).replace("\\", "/"),
                    "owned_screen_pixels": statistics["owned_screen_pixels"],
                    "reliable_screen_pixels": statistics["reliable_screen_pixels"],
                }
            )
            pose_index += 1

    manifest = {
        "schema_version": 1,
        "case_id": spec["case_id"],
        "source_spec": str(args.spec.resolve()),
        "renderer": str(args.renderer.resolve()),
        "poses": candidates,
    }
    (case_root / "pose_candidates.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (case_root / "authoring_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(json.dumps({"case_id": spec["case_id"], "candidate_poses": len(candidates)}, indent=2))


if __name__ == "__main__":
    main()
