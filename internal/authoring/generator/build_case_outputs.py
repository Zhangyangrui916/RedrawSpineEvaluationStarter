#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def render_pose(renderer: Path, private: Path, atlas_name: str, pose: dict, output: Path, spec: dict) -> None:
    viewport = spec["viewport"]
    size = spec["render_size"]
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    if os.name == "nt":
        environment["REDRAWSPINE_GL_BACKEND"] = "native"
    command = [
        str(renderer),
        "--skeleton",
        str(private / "skeleton.json"),
        "--atlas",
        str(private / atlas_name),
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
        raise RuntimeError(f"Render failed for {pose['id']} {atlas_name}:\n{result.stdout}\n{result.stderr}")


def render_distance(noop: Path, reference: Path) -> tuple[float, int]:
    left = np.asarray(Image.open(noop).convert("RGBA"), dtype=np.int16)
    right = np.asarray(Image.open(reference).convert("RGBA"), dtype=np.int16)
    difference = np.abs(left - right)
    changed = np.any(difference != 0, axis=2)
    return float(difference.mean() / 255.0), int(np.count_nonzero(changed))


def select_hidden(candidates: list[dict], count: int) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate["animation"]].append(candidate)
    for values in groups.values():
        values.sort(key=lambda item: (-item["noop_distance"], item["time"], item["id"]))

    selected = []
    depth = 0
    animations = sorted(groups)
    while len(selected) < count:
        added = False
        for animation in animations:
            if depth < len(groups[animation]):
                selected.append(groups[animation][depth])
                added = True
                if len(selected) == count:
                    break
        if not added:
            break
        depth += 1
    return sorted(selected, key=lambda item: (item["animation"], item["time"], item["id"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    case_root = args.case_root.resolve()
    spec = json.loads((case_root / "authoring_spec.json").read_text(encoding="utf-8"))
    selection = json.loads((case_root / "selected_poses.json").read_text(encoding="utf-8"))
    candidates = json.loads((case_root / "pose_candidates.json").read_text(encoding="utf-8"))["poses"]
    source_model = ROOT / spec["source_model"]
    private = case_root / "private"
    starter_export = case_root / "starter_export"
    hidden = private / "hidden"
    observations_private = private / "observations"
    for directory in (starter_export, hidden, observations_private):
        if directory.exists():
            if not args.force:
                raise SystemExit(f"Output exists: {directory}; use --force")
            shutil.rmtree(directory)

    observations = []
    for index, pose in enumerate(selection["observations"]):
        observation_id = f"obs_{index:03d}"
        private_dir = observations_private / observation_id
        before = private_dir / "before.png"
        after = private_dir / "after.png"
        render_pose(args.renderer, private, "s0.atlas", pose, before, spec)
        render_pose(args.renderer, private, "s1.atlas", pose, after, spec)
        observations.append(
            {
                "id": observation_id,
                "animation": pose["animation"],
                "time": pose["time"],
                "before": f"observations/{observation_id}/before.png",
                "after": f"observations/{observation_id}/after.png",
                "source_pose_id": pose["id"],
            }
        )

    selected_ids = {pose["id"] for pose in selection["observations"]}
    hidden_candidates = private / "hidden_candidates"
    hidden_candidates.mkdir(parents=True, exist_ok=True)
    scored = []
    for pose in candidates:
        if pose["id"] in selected_ids:
            continue
        noop = hidden_candidates / f"{pose['id']}_noop.png"
        reference = hidden_candidates / f"{pose['id']}_reference.png"
        render_pose(args.renderer, private, "s0.atlas", pose, noop, spec)
        render_pose(args.renderer, private, "s1.atlas", pose, reference, spec)
        distance, changed_pixels = render_distance(noop, reference)
        scored.append({**pose, "noop_distance": distance, "changed_render_pixels": changed_pixels})

    eligible = [pose for pose in scored if pose["noop_distance"] > 1e-4 and pose["changed_render_pixels"] > 100]
    hidden_poses = select_hidden(eligible, int(spec["hidden_pose_count"]))
    if len(hidden_poses) != int(spec["hidden_pose_count"]):
        raise RuntimeError(f"Only {len(hidden_poses)} hidden poses have sufficient signal")

    noop_dir = hidden / "noop_frames"
    reference_dir = hidden / "reference_frames"
    noop_dir.mkdir(parents=True)
    reference_dir.mkdir(parents=True)
    hidden_manifest = []
    for index, pose in enumerate(hidden_poses):
        frame_name = f"frame_{index:03d}.png"
        shutil.copyfile(hidden_candidates / f"{pose['id']}_noop.png", noop_dir / frame_name)
        shutil.copyfile(hidden_candidates / f"{pose['id']}_reference.png", reference_dir / frame_name)
        hidden_manifest.append(
            {
                "id": f"hidden_{index:03d}",
                "animation": pose["animation"],
                "time": pose["time"],
                "noop_distance": pose["noop_distance"],
                "changed_render_pixels": pose["changed_render_pixels"],
                "noop": f"noop_frames/{frame_name}",
                "reference": f"reference_frames/{frame_name}",
                "source_pose_id": pose["id"],
            }
        )
    (hidden / "hidden_poses.json").write_text(json.dumps(hidden_manifest, indent=2), encoding="utf-8")
    (hidden / "hidden_signal_report.json").write_text(json.dumps(scored, indent=2), encoding="utf-8")

    source_pages = starter_export / "source_attachments"
    source_pages.mkdir(parents=True)
    for path in sorted((private / "s0_pages").glob("*.png")):
        shutil.copyfile(path, source_pages / path.name)
    shutil.copyfile(private / "skeleton.json", starter_export / "skeleton.json")
    atlas = (source_model / "skeleton.atlas").read_text(encoding="utf-8").replace("pages/", "source_attachments/")
    (starter_export / "skeleton.atlas").write_text(atlas, encoding="utf-8")

    page_manifest = json.loads((source_model / "page_manifest.json").read_text(encoding="utf-8"))
    visible_page_manifest = []
    output_pages = []
    for item in page_manifest:
        page_name = Path(item["page"]).name
        visible_page_manifest.append({**item, "page": f"source_attachments/{page_name}"})
        output_pages.append({"name": page_name, "width": item["width"], "height": item["height"]})
    (starter_export / "page_manifest.json").write_text(
        json.dumps(visible_page_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for observation in observations:
        target = starter_export / Path(observation["before"]).parent
        target.mkdir(parents=True, exist_ok=True)
        private_dir = observations_private / observation["id"]
        shutil.copyfile(private_dir / "before.png", target / "before.png")
        shutil.copyfile(private_dir / "after.png", target / "after.png")

    public_observations = [{key: value for key, value in observation.items() if key != "source_pose_id"} for observation in observations]
    case_json = {
        "schema_version": 1,
        "case_id": spec["case_id"],
        "skeleton": "skeleton.json",
        "atlas": "skeleton.atlas",
        "page_manifest": "page_manifest.json",
        "source_attachments": "source_attachments",
        "observations": public_observations,
        "viewport": spec["viewport"],
        "render_size": spec["render_size"],
        "output_pages": output_pages,
    }
    (starter_export / "case.json").write_text(json.dumps(case_json, indent=2), encoding="utf-8")

    summary = {
        "case_id": spec["case_id"],
        "observations": len(observations),
        "hidden_poses": len(hidden_manifest),
        "min_hidden_noop_distance": min(pose["noop_distance"] for pose in hidden_manifest),
        "max_hidden_noop_distance": max(pose["noop_distance"] for pose in hidden_manifest),
    }
    (case_root / "case_build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
