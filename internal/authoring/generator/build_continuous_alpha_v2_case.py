#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from build_real_art_dev import render


def compose_target(source_path: Path, replay_path: Path, written_mask_path: Path | None) -> tuple[Image.Image, dict]:
    source = np.asarray(Image.open(source_path).convert("RGBA"), dtype=np.uint8).copy()
    replay = np.asarray(Image.open(replay_path).convert("RGBA"), dtype=np.uint8)
    if source.shape != replay.shape:
        raise ValueError(f"Replay page shape differs from source: {replay_path}")
    if not np.array_equal(source[:, :, 3], replay[:, :, 3]):
        raise ValueError(f"Replay alpha differs from canonical source: {replay_path}")

    direct = np.zeros(source.shape[:2], dtype=bool)
    if written_mask_path is not None:
        raw_mask = np.fromfile(written_mask_path, dtype=np.uint8)
        if raw_mask.size != source.shape[0] * source.shape[1]:
            raise ValueError(f"Written-mask shape differs from source: {written_mask_path}")
        direct = raw_mask.reshape(source.shape[:2]) == 128
    replay_nonwhite = np.zeros(source.shape[:2], dtype=bool)
    if written_mask_path is not None:
        replay_nonwhite = np.any(replay[:, :, :3] != 255, axis=2)
    alpha_nonzero = source[:, :, 3] > 0
    target_defined = (direct | replay_nonwhite) & alpha_nonzero
    propagated = target_defined & ~direct

    target = source.copy()
    target[target_defined, :3] = replay[target_defined, :3]
    target[target[:, :, 3] == 0, :3] = 0
    return Image.fromarray(target, "RGBA"), {
        "direct_written_mask_texels": int(direct.sum()),
        "direct_written_target_texels": int((direct & alpha_nonzero).sum()),
        "propagated_texels": int(propagated.sum()),
        "target_defined_texels": int(target_defined.sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the continuous-alpha V2 public development case.")
    parser.add_argument("--base-case", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    base = args.base_case.resolve()
    replay = args.replay.resolve()
    output = args.output.resolve()
    temporary = output.with_name(output.name + ".tmp")
    if output.exists():
        if not args.force:
            raise SystemExit(f"Output exists: {output}; use --force")
        shutil.rmtree(output)
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)

    try:
        case = json.loads((base / "case.json").read_text(encoding="utf-8"))
        replay_report = json.loads((replay / "replay_report.json").read_text(encoding="utf-8"))
        if replay_report["archived_page_total_different_pixels"] != 0:
            raise ValueError("Continuous-alpha V2 requires an exact archived-run replay")
        replay_run = int(replay_report["run"])

        shutil.copyfile(base / case["skeleton"], temporary / "skeleton.json")
        shutil.copyfile(base / case["atlas"], temporary / "skeleton.atlas")
        shutil.copyfile(base / "page_manifest.json", temporary / "page_manifest.json")
        shutil.copytree(base / case["source_attachments"], temporary / "source_attachments")
        oracle = temporary / "oracle"
        target_root = oracle / "target_attachments"
        target_root.mkdir(parents=True)

        page_stats = []
        totals = {
            "direct_written_mask_texels": 0,
            "direct_written_target_texels": 0,
            "propagated_texels": 0,
            "target_defined_texels": 0,
        }
        for page in case["output_pages"]:
            name = page["name"]
            replay_page = replay / "full_s1_pages" / name
            if not replay_page.is_file():
                raise ValueError(f"Replay is missing page: {name}")
            written_mask = replay / "final_written_masks" / f"{Path(name).stem}.writtenMask"
            target, stats = compose_target(
                temporary / "source_attachments" / name,
                replay_page,
                written_mask if written_mask.is_file() else None,
            )
            target.save(target_root / name)
            page_stats.append({"name": name, **stats})
            for key in totals:
                totals[key] += stats[key]

        source_atlas = (temporary / "skeleton.atlas").read_text(encoding="utf-8")
        target_atlas = source_atlas.replace("source_attachments/", "target_attachments/")
        (oracle / "target.atlas").write_text(target_atlas, encoding="utf-8")

        observations = []
        for observation in case["observations"]:
            relative = Path("observations") / observation["id"]
            before = temporary / relative / "before.png"
            after = temporary / relative / "after.png"
            render(
                args.renderer.resolve(),
                temporary / "skeleton.json",
                temporary / "skeleton.atlas",
                observation["animation"],
                observation["time"],
                before,
                case["viewport"],
            )
            render(
                args.renderer.resolve(),
                temporary / "skeleton.json",
                oracle / "target.atlas",
                observation["animation"],
                observation["time"],
                after,
                case["viewport"],
            )
            observations.append({**observation, "before": f"{relative.as_posix()}/before.png", "after": f"{relative.as_posix()}/after.png"})

        base_oracle = json.loads((base / "dev_oracle.json").read_text(encoding="utf-8"))
        base_validation_path = base / base_oracle["validation_manifest"]
        validation_poses = json.loads(base_validation_path.read_text(encoding="utf-8"))
        validation_root = oracle / "validation"
        validation_manifest = []
        for index, pose in enumerate(validation_poses):
            frame = f"frame_{index:03d}.png"
            noop = validation_root / "noop_frames" / frame
            reference = validation_root / "reference_frames" / frame
            render(
                args.renderer.resolve(),
                temporary / "skeleton.json",
                temporary / "skeleton.atlas",
                pose["animation"],
                pose["time"],
                noop,
                case["viewport"],
            )
            render(
                args.renderer.resolve(),
                temporary / "skeleton.json",
                oracle / "target.atlas",
                pose["animation"],
                pose["time"],
                reference,
                case["viewport"],
            )
            validation_manifest.append(
                {
                    "id": f"validation_{index:03d}",
                    "animation": pose["animation"],
                    "time": pose["time"],
                    "noop": f"noop_frames/{frame}",
                    "reference": f"reference_frames/{frame}",
                }
            )
        (validation_root / "hidden_poses.json").write_text(
            json.dumps(validation_manifest, indent=2), encoding="utf-8"
        )

        production_reference = oracle / "production_reference" / "raw_sd_pose_frames"
        production_reference.mkdir(parents=True)
        for frame in sorted((replay / "raw_frames").glob("*.png")):
            shutil.copyfile(frame, production_reference / frame.name)

        case_id = args.case_id or f"real_art_continuous_run{replay_run}"
        v2_case = {
            **case,
            "case_id": case_id,
            "skeleton": "skeleton.json",
            "atlas": "skeleton.atlas",
            "observations": observations,
        }
        (temporary / "case.json").write_text(json.dumps(v2_case, indent=2), encoding="utf-8")
        dev_oracle = {
            "schema_version": 2,
            "case_id": v2_case["case_id"],
            "purpose": "public-continuous-alpha-development-oracle",
            "source_run": replay_run,
            "target_attachments": "oracle/target_attachments",
            "target_atlas": "oracle/target.atlas",
            "validation_manifest": "oracle/validation/hidden_poses.json",
            "final_cases_expose_target_attachments": False,
            "target_rule": "Use replay RGB where final mask is Written (128) or replay RGB is not exact white; otherwise retain S0. Preserve S0 alpha.",
        }
        (temporary / "dev_oracle.json").write_text(json.dumps(dev_oracle, indent=2), encoding="utf-8")
        provenance = {
            "schema_version": 2,
            "source_replay_report": str((replay / "replay_report.json").resolve()),
            "replay_run": replay_run,
            "replay_exact_archived_pages": replay_report["archived_page_sha256_matches"],
            **totals,
            "page_stats": page_stats,
        }
        (oracle / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        readme = """# Continuous-Alpha Real-Art V2 Public Development Case

This case uses an archived RedrawSpine result with real semitransparent attachment alpha. Before/after observations and
validation references are freshly rendered from one fixed S0/S1 page pair. Archived raw SD pose images are visual
context only, are not equation truth, and may be omitted from distributable exports.

The public oracle exposes S1 for development diagnosis. The hidden evaluation package does not expose S1, trusted
coefficient-energy support, or validation references. Exact recovery outside stable public-observation support is not
required; completion quality outside that support is a separate aesthetic concern.
"""
        (temporary / "DEV_README.md").write_text(readme, encoding="utf-8")

        temporary.rename(output)
        print(json.dumps({"output": str(output), "case_id": v2_case["case_id"], **totals}, indent=2))
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


if __name__ == "__main__":
    main()
