#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def render(renderer: Path, skeleton: Path, atlas: Path, pose: dict, output: Path, case: dict) -> None:
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
        raise RuntimeError(f"Render failed for {pose['id']}:\n{result.stdout}\n{result.stderr}")


def distance(left: Path, right: Path) -> float:
    a = np.asarray(Image.open(left).convert("RGBA"), dtype=np.int16)
    b = np.asarray(Image.open(right).convert("RGBA"), dtype=np.int16)
    return float(np.abs(a - b).mean() / 255.0)


def score_frames(qualities: list[float]) -> float:
    bottom_count = max(1, math.ceil(len(qualities) * 0.2))
    return 0.8 * float(np.mean(qualities)) + 0.2 * float(np.mean(sorted(qualities)[:bottom_count]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a baseline under V2 trusted-energy neutralization.")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--energy", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    case_root = args.case.resolve()
    candidate_root = args.candidate.resolve()
    energy_root = args.energy.resolve() / "aggregate"
    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"Output exists: {output}; use --force")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
    oracle = json.loads((case_root / "dev_oracle.json").read_text(encoding="utf-8"))
    validation_root = case_root / Path(oracle["validation_manifest"]).parent
    validation = json.loads((case_root / oracle["validation_manifest"]).read_text(encoding="utf-8"))
    target_root = case_root / oracle["target_attachments"]
    source_root = case_root / case["source_attachments"]
    expected = {page["name"]: page for page in case["output_pages"]}
    actual = {path.name for path in candidate_root.glob("*.png")}
    if actual != set(expected):
        raise ValueError(f"Candidate page mismatch: missing={sorted(set(expected) - actual)} extra={sorted(actual - set(expected))}")

    shutil.copyfile(case_root / case["skeleton"], output / "skeleton.json")
    source_atlas = (case_root / case["atlas"]).read_text(encoding="utf-8")
    reports = []
    for threshold_index, threshold in enumerate(args.threshold):
        threshold_root = output / f"threshold_{threshold_index:02d}_{threshold:.0e}"
        candidate_neutral = threshold_root / "candidate_attachments"
        noop_neutral = threshold_root / "noop_attachments"
        candidate_neutral.mkdir(parents=True)
        noop_neutral.mkdir()
        support_texels = 0
        alpha_texels = 0
        for name, page in expected.items():
            shape = (page["height"], page["width"])
            energy = np.fromfile(energy_root / f"{name}.energy.f32", dtype=np.float32)
            if energy.size != shape[0] * shape[1]:
                raise ValueError(f"Energy size mismatch for {name}")
            support = energy.reshape(shape) >= threshold
            source = np.asarray(Image.open(source_root / name).convert("RGBA"), dtype=np.uint8)
            target = np.asarray(Image.open(target_root / name).convert("RGBA"), dtype=np.uint8)
            candidate = np.asarray(Image.open(candidate_root / name).convert("RGBA"), dtype=np.uint8)
            if not np.array_equal(source[:, :, 3], target[:, :, 3]) or not np.array_equal(
                source[:, :, 3], candidate[:, :, 3]
            ):
                raise ValueError(f"Alpha mismatch for {name}")
            alpha_nonzero = source[:, :, 3] > 0
            support &= alpha_nonzero
            support_texels += int(support.sum())
            alpha_texels += int(alpha_nonzero.sum())

            candidate_output = target.copy()
            candidate_output[support, :3] = candidate[support, :3]
            noop_output = target.copy()
            noop_output[support, :3] = source[support, :3]
            Image.fromarray(candidate_output, "RGBA").save(candidate_neutral / name)
            Image.fromarray(noop_output, "RGBA").save(noop_neutral / name)

        candidate_atlas = source_atlas.replace("source_attachments/", "candidate_attachments/")
        noop_atlas = source_atlas.replace("source_attachments/", "noop_attachments/")
        (threshold_root / "candidate.atlas").write_text(candidate_atlas, encoding="utf-8")
        (threshold_root / "noop.atlas").write_text(noop_atlas, encoding="utf-8")
        frames = threshold_root / "frames"
        frames.mkdir()
        qualities = []
        frame_reports = []
        for index, pose in enumerate(validation):
            candidate_frame = frames / f"candidate_{index:03d}.png"
            noop_frame = frames / f"noop_{index:03d}.png"
            render(args.renderer.resolve(), output / "skeleton.json", threshold_root / "candidate.atlas", pose, candidate_frame, case)
            render(args.renderer.resolve(), output / "skeleton.json", threshold_root / "noop.atlas", pose, noop_frame, case)
            reference = validation_root / pose["reference"]
            candidate_distance = distance(candidate_frame, reference)
            noop_distance = distance(noop_frame, reference)
            quality = float(np.clip(1.0 - candidate_distance / (noop_distance + 1e-12), 0.0, 1.0))
            qualities.append(quality)
            frame_reports.append(
                {
                    "id": pose["id"],
                    "candidate_distance": candidate_distance,
                    "noop_distance": noop_distance,
                    "quality": quality,
                }
            )
        report = {
            "threshold": threshold,
            "support_texels": support_texels,
            "alpha_nonzero_texels": alpha_texels,
            "support_fraction": support_texels / max(alpha_texels, 1),
            "score": score_frames(qualities),
            "mean_quality": float(np.mean(qualities)),
            "bottom20_quality": float(np.mean(sorted(qualities)[: max(1, math.ceil(len(qualities) * 0.2))])),
            "frames": frame_reports,
        }
        (threshold_root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        reports.append(report)
        print(json.dumps({key: report[key] for key in ("threshold", "support_fraction", "score")}, indent=2))

    (output / "report.json").write_text(json.dumps({"thresholds": reports}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
