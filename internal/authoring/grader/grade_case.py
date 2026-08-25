#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def fail_result(output: Path, reason: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"resolved": False, "score": 0.0, "reason": reason}), encoding="utf-8")


def sanitize_pages(
    case: dict, case_dir: Path, results: Path, support_masks: Path, destination: Path
) -> None:
    expected = {item["name"]: item for item in case["output_pages"]}
    actual = {path.name: path for path in results.glob("*.png") if path.is_file()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValueError(f"page set mismatch; missing={missing}; extra={extra}")
    destination.mkdir(parents=True)

    actual_masks = {path.name: path for path in support_masks.glob("*.png") if path.is_file()}
    if set(actual_masks) != set(expected):
        missing = sorted(set(expected) - set(actual_masks))
        extra = sorted(set(actual_masks) - set(expected))
        raise ValueError(f"support-mask set mismatch; missing={missing}; extra={extra}")

    source_dir = case_dir / case["source_attachments"]
    for name, item in expected.items():
        candidate_path = actual[name]
        if candidate_path.is_symlink() or candidate_path.resolve().parent != results.resolve():
            raise ValueError(f"unsafe candidate page path: {name}")
        with Image.open(candidate_path) as image:
            image.verify()
        candidate = Image.open(candidate_path)
        if candidate.mode != "RGBA":
            raise ValueError(f"page is not RGBA8: {name} mode={candidate.mode}")
        if candidate.size != (item["width"], item["height"]):
            raise ValueError(f"page size mismatch: {name} size={candidate.size}")
        source = Image.open(source_dir / name).convert("RGBA")
        candidate_rgba = np.asarray(candidate, dtype=np.uint8).copy()
        source_rgba = np.asarray(source, dtype=np.uint8)
        source_alpha = source_rgba[:, :, 3]
        if not np.array_equal(candidate_rgba[:, :, 3], source_alpha):
            raise ValueError(f"alpha mismatch: {name}")
        support = np.asarray(Image.open(actual_masks[name]).convert("L"), dtype=np.uint8)
        if support.shape != source_alpha.shape:
            raise ValueError(f"support-mask size mismatch: {name} size={(support.shape[1], support.shape[0])}")
        candidate_rgba[support < 128, :3] = source_rgba[support < 128, :3]
        candidate_rgba[source_alpha == 0, :3] = 0
        Image.fromarray(candidate_rgba, "RGBA").save(destination / name)


def render_candidate(renderer: Path, skeleton: Path, atlas: Path, pose: dict, output: Path, case: dict) -> None:
    viewport = case["viewport"]
    size = case["render_size"]
    environment = dict(os.environ)
    if os.name == "nt":
        environment["REDRAWSPINE_GL_BACKEND"] = "native"
    command = [
        str(renderer),
        "--skeleton",
        str(skeleton),
        "--atlas",
        str(atlas),
        "--animation",
        pose["animation"],
        "--time",
        str(pose["time"]),
        "--output",
        str(output),
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
        raise RuntimeError(f"trusted renderer failed for {pose['id']}: {result.stderr.strip()}")


def rgba_distance(left: Path, right: Path) -> float:
    a = np.asarray(Image.open(left).convert("RGBA"), dtype=np.int16)
    b = np.asarray(Image.open(right).convert("RGBA"), dtype=np.int16)
    return float(np.abs(a - b).mean() / 255.0)


def score_frames(q_values: list[float]) -> float:
    bottom_count = max(1, math.ceil(len(q_values) * 0.2))
    bottom = sorted(q_values)[:bottom_count]
    return 0.8 * float(np.mean(q_values)) + 0.2 * float(np.mean(bottom))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--visible-case", type=Path, required=True)
    parser.add_argument("--private-case", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        case_dir = args.visible_case.resolve()
        private_dir = args.private_case.resolve()
        results = args.results.resolve()
        if not results.is_dir():
            raise ValueError("candidate results directory does not exist")
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        hidden = json.loads((private_dir / "hidden_poses.json").read_text(encoding="utf-8"))
        threshold_config = json.loads(args.thresholds.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory(prefix="redrawspine-grade-") as temporary_name:
            temporary = Path(temporary_name)
            sanitized = temporary / "sanitized_pages"
            sanitize_pages(case, case_dir, results, private_dir / "observable_masks", sanitized)
            shutil.copyfile(case_dir / case["skeleton"], temporary / "skeleton.json")
            atlas = (case_dir / case["atlas"]).read_text(encoding="utf-8")
            atlas = atlas.replace("source_attachments/", "sanitized_pages/")
            (temporary / "candidate.atlas").write_text(atlas, encoding="utf-8")

            q_values = []
            diagnostics = []
            frames = temporary / "candidate_frames"
            frames.mkdir()
            for index, pose in enumerate(hidden):
                candidate_frame = frames / f"frame_{index:03d}.png"
                noop_frame = frames / f"noop_{index:03d}.png"
                render_candidate(args.renderer, temporary / "skeleton.json", temporary / "candidate.atlas", pose,
                                 candidate_frame, case)
                render_candidate(
                    args.renderer,
                    case_dir / case["skeleton"],
                    case_dir / case["atlas"],
                    pose,
                    noop_frame,
                    case,
                )
                reference = private_dir / pose["reference"]
                candidate_distance = rgba_distance(candidate_frame, reference)
                noop_distance = rgba_distance(noop_frame, reference)
                quality = float(np.clip(1.0 - candidate_distance / (noop_distance + 1e-12), 0.0, 1.0))
                q_values.append(quality)
                diagnostics.append(
                    {
                        "id": pose["id"],
                        "candidate_distance": candidate_distance,
                        "noop_distance": noop_distance,
                        "quality": quality,
                    }
                )

            score = score_frames(q_values)
            resolved = score >= float(threshold_config["overall_threshold"])
            reason = (
                f"case={case['case_id']}; frames={len(q_values)}; mean_q={float(np.mean(q_values)):.4f}; "
                f"bottom20_q={float(np.mean(sorted(q_values)[:max(1, math.ceil(len(q_values) * 0.2))])):.4f}"
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps({"resolved": bool(resolved), "score": float(score), "reason": reason}), encoding="utf-8"
            )
            diagnostics_path = args.output.with_suffix(".diagnostics.json")
            diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
            print(json.dumps({"resolved": resolved, "score": score, "reason": reason}, indent=2))
    except Exception as error:
        fail_result(args.output, str(error))
        print(json.dumps({"resolved": False, "score": 0.0, "reason": str(error)}, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
