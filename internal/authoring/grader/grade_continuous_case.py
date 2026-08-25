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


def canonicalize_pages(case: dict, contract: Path, hidden: Path, results: Path, temporary: Path) -> tuple[Path, Path]:
    expected = {item["name"]: item for item in case["output_pages"]}
    actual = {path.name: path for path in results.glob("*.png") if path.is_file()}
    if set(actual) != set(expected):
        raise ValueError(
            f"page set mismatch; missing={sorted(set(expected) - set(actual))}; extra={sorted(set(actual) - set(expected))}"
        )
    support_paths = {path.name: path for path in (hidden / "support_masks").glob("*.png")}
    target_paths = {path.name: path for path in (hidden / "target_attachments").glob("*.png")}
    if set(support_paths) != set(expected) or set(target_paths) != set(expected):
        raise ValueError("private support or target page set does not match the case contract")

    candidate_root = temporary / "candidate_pages"
    noop_root = temporary / "noop_pages"
    candidate_root.mkdir()
    noop_root.mkdir()
    source_root = contract / case["source_attachments"]
    for name, item in expected.items():
        candidate_path = actual[name]
        if candidate_path.is_symlink() or candidate_path.resolve().parent != results.resolve():
            raise ValueError(f"unsafe candidate page path: {name}")
        candidate_image = Image.open(candidate_path)
        if candidate_image.mode != "RGBA" or candidate_image.size != (item["width"], item["height"]):
            raise ValueError(f"candidate page format or size mismatch: {name}")
        candidate = np.asarray(candidate_image, dtype=np.uint8)
        source = np.asarray(Image.open(source_root / name).convert("RGBA"), dtype=np.uint8)
        target = np.asarray(Image.open(target_paths[name]).convert("RGBA"), dtype=np.uint8)
        support = np.asarray(Image.open(support_paths[name]).convert("L"), dtype=np.uint8) >= 128
        if not np.array_equal(candidate[:, :, 3], source[:, :, 3]):
            raise ValueError(f"alpha mismatch: {name}")
        if not np.array_equal(target[:, :, 3], source[:, :, 3]):
            raise ValueError(f"private target alpha mismatch: {name}")

        candidate_eval = target.copy()
        noop_eval = target.copy()
        candidate_eval[support, :3] = candidate[support, :3]
        noop_eval[support, :3] = source[support, :3]
        candidate_eval[source[:, :, 3] == 0, :3] = 0
        noop_eval[source[:, :, 3] == 0, :3] = 0
        Image.fromarray(candidate_eval, "RGBA").save(candidate_root / name)
        Image.fromarray(noop_eval, "RGBA").save(noop_root / name)
    return candidate_root, noop_root


def render(renderer: Path, skeleton: Path, atlas: Path, pose: dict, output: Path, case: dict) -> None:
    viewport = case["viewport"]
    size = case["render_size"]
    environment = dict(os.environ)
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
    if os.name == "nt":
        environment["REDRAWSPINE_GL_BACKEND"] = "native"
    result = subprocess.run(command, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"trusted renderer failed for {pose['id']}: {result.stderr.strip()}")


def rgba_distance(left: Path, right: Path) -> float:
    a = np.asarray(Image.open(left).convert("RGBA"), dtype=np.int16)
    b = np.asarray(Image.open(right).convert("RGBA"), dtype=np.int16)
    return float(np.abs(a - b).mean() / 255.0)


def score_frames(qualities: list[float]) -> float:
    bottom_count = max(1, math.ceil(len(qualities) * 0.2))
    return 0.8 * float(np.mean(qualities)) + 0.2 * float(np.mean(sorted(qualities)[:bottom_count]))


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
        contract = args.visible_case.resolve()
        hidden = args.private_case.resolve()
        results = args.results.resolve()
        if not results.is_dir():
            raise ValueError("candidate results directory does not exist")
        case = json.loads((contract / "case.json").read_text(encoding="utf-8"))
        poses = json.loads((hidden / "hidden_poses.json").read_text(encoding="utf-8"))
        thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory(prefix="redrawspine-continuous-grade-") as temporary_name:
            temporary = Path(temporary_name)
            candidate_pages, noop_pages = canonicalize_pages(case, contract, hidden, results, temporary)
            shutil.copyfile(contract / case["skeleton"], temporary / "skeleton.json")
            atlas_text = (contract / case["atlas"]).read_text(encoding="utf-8")
            (temporary / "candidate.atlas").write_text(
                atlas_text.replace("source_attachments/", f"{candidate_pages.name}/"), encoding="utf-8"
            )
            (temporary / "noop.atlas").write_text(
                atlas_text.replace("source_attachments/", f"{noop_pages.name}/"), encoding="utf-8"
            )

            frames = temporary / "frames"
            frames.mkdir()
            qualities = []
            diagnostics = []
            for index, pose in enumerate(poses):
                candidate_frame = frames / f"candidate_{index:03d}.png"
                noop_frame = frames / f"noop_{index:03d}.png"
                render(args.renderer, temporary / "skeleton.json", temporary / "candidate.atlas", pose, candidate_frame, case)
                render(args.renderer, temporary / "skeleton.json", temporary / "noop.atlas", pose, noop_frame, case)
                reference = hidden / pose["reference"]
                if not reference.is_file():
                    reference = frames / f"reference_{index:03d}.png"
                    render(
                        args.renderer,
                        temporary / "skeleton.json",
                        hidden / "target.atlas",
                        pose,
                        reference,
                        case,
                    )
                candidate_distance = rgba_distance(candidate_frame, reference)
                noop_distance = rgba_distance(noop_frame, reference)
                quality = float(np.clip(1.0 - candidate_distance / (noop_distance + 1e-12), 0.0, 1.0))
                qualities.append(quality)
                diagnostics.append(
                    {
                        "id": pose["id"],
                        "candidate_distance": candidate_distance,
                        "noop_distance": noop_distance,
                        "quality": quality,
                    }
                )

            score = score_frames(qualities)
            resolved = score >= float(thresholds["overall_threshold"])
            bottom_count = max(1, math.ceil(len(qualities) * 0.2))
            reason = (
                f"case={case['case_id']}; frames={len(qualities)}; mean_q={float(np.mean(qualities)):.4f}; "
                f"bottom20_q={float(np.mean(sorted(qualities)[:bottom_count])):.4f}"
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps({"resolved": bool(resolved), "score": float(score), "reason": reason}), encoding="utf-8"
            )
            args.output.with_suffix(".diagnostics.json").write_text(
                json.dumps(diagnostics, indent=2), encoding="utf-8"
            )
            print(json.dumps({"resolved": resolved, "score": score, "reason": reason}, indent=2))
    except Exception as error:
        fail_result(args.output, str(error))
        print(json.dumps({"resolved": False, "score": 0.0, "reason": str(error)}, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
