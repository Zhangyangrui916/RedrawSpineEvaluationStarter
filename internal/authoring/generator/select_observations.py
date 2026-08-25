#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import itertools
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def load_pose_masks(case_root: Path, pose: dict, erode_texels: int) -> dict[str, set[int]]:
    masks = {}
    mask_dir = case_root / pose["masks"]
    for path in sorted(mask_dir.glob("page_*.png")):
        image = Image.open(path).convert("L")
        for _ in range(erode_texels):
            image = image.filter(ImageFilter.MinFilter(3))
        width, _ = image.size
        values = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
        covered = {index for index, value in enumerate(values) if value >= 128}
        if covered:
            masks[path.name] = covered
    return masks


def count_union(masks: dict[str, set[int]]) -> int:
    return sum(len(values) for values in masks.values())


def merge_into(union: dict[str, set[int]], masks: dict[str, set[int]]) -> int:
    added = 0
    for page, values in masks.items():
        current = union.setdefault(page, set())
        before = len(current)
        current.update(values)
        added += len(current) - before
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    args = parser.parse_args()

    case_root = args.case_root.resolve()
    spec = json.loads((case_root / "authoring_spec.json").read_text(encoding="utf-8"))
    candidates = json.loads((case_root / "pose_candidates.json").read_text(encoding="utf-8"))["poses"]
    erode = int(spec["coverage"]["edge_erode_texels"])
    pose_masks = {pose["id"]: load_pose_masks(case_root, pose, erode) for pose in candidates}

    best_single = max(count_union(masks) for masks in pose_masks.values())
    selected = []
    union: dict[str, set[int]] = {}
    remaining = {pose["id"]: pose for pose in candidates}
    for _ in range(int(spec["observation_budget"])):
        ranked = []
        for pose_id, pose in remaining.items():
            gain = 0
            for page, values in pose_masks[pose_id].items():
                gain += len(values - union.get(page, set()))
            ranked.append((gain, pose_id, pose))
        gain, pose_id, pose = max(ranked, key=lambda item: (item[0], item[1]))
        if gain <= 0:
            break
        merge_into(union, pose_masks[pose_id])
        selected.append({**pose, "new_coverage_texels": gain, "union_coverage_texels": count_union(union)})
        del remaining[pose_id]

    union_count = count_union(union)
    gain_ratio = (union_count - best_single) / max(best_single, 1)
    best_fraction = best_single / max(union_count, 1)
    ownership_changes = []
    for left, right in itertools.combinations(selected, 2):
        left_map = Image.open(case_root / left["masks"] / "ownership.png").convert("L")
        right_map = Image.open(case_root / right["masks"] / "ownership.png").convert("L")
        left_values = np.asarray(left_map, dtype=np.uint8)
        right_values = np.asarray(right_map, dtype=np.uint8)
        changed = (left_values != 0) & (right_values != 0) & (left_values != right_values)
        ownership_changes.append(
            {"left": left["id"], "right": right["id"], "changed_topmost_pixels": int(np.count_nonzero(changed))}
        )

    audit = {
        "best_single_coverage_texels": best_single,
        "union_coverage_texels": union_count,
        "union_gain_over_best_single": gain_ratio,
        "best_single_fraction": best_fraction,
        "selected_observations": len(selected),
        "ownership_pairs_with_changes": sum(item["changed_topmost_pixels"] > 0 for item in ownership_changes),
        "max_changed_topmost_pixels": max((item["changed_topmost_pixels"] for item in ownership_changes), default=0),
        "thresholds": spec["coverage"],
        "passed": gain_ratio >= spec["coverage"]["min_union_gain_over_best_single"]
        and best_fraction <= spec["coverage"]["max_best_single_fraction"],
    }

    union_dir = case_root / "union_coverage"
    union_dir.mkdir(exist_ok=True)
    manifest = json.loads((Path(__file__).resolve().parents[1] / spec["source_model"] / "page_manifest.json").read_text(encoding="utf-8"))
    dimensions = {Path(item["page"]).name: (item["width"], item["height"]) for item in manifest}
    for page, (width, height) in dimensions.items():
        pixels = bytearray(width * height)
        for index in union.get(page, set()):
            pixels[index] = 255
        Image.frombytes("L", (width, height), bytes(pixels)).save(union_dir / page)

    output = {
        "schema_version": 1,
        "case_id": spec["case_id"],
        "observations": selected,
        "remaining_pose_ids": sorted(remaining),
        "audit": audit,
    }
    (case_root / "selected_poses.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    (case_root / "coverage_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (case_root / "ownership_audit.json").write_text(json.dumps(ownership_changes, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    if not audit["passed"]:
        raise SystemExit("Coverage audit did not pass the authoring thresholds")


if __name__ == "__main__":
    main()
