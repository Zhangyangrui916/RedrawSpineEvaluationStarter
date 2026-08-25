#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


POINT_TYPES = {"point"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_skeleton(source: Path) -> tuple[dict, list[str], dict[str, str]]:
    skeleton = json.loads(source.read_text(encoding="utf-8"))
    skin = skeleton["skins"][0]["attachments"]
    point_slots = set()
    region_by_attachment: dict[str, str] = {}
    for slot_name, attachments in list(skin.items()):
        for attachment_name, attachment in list(attachments.items()):
            attachment_type = attachment.get("type", "region")
            if attachment_type in POINT_TYPES:
                point_slots.add(slot_name)
                del attachments[attachment_name]
                continue
            if attachment_type not in {"region", "mesh", "linkedmesh"}:
                raise ValueError(f"Unsupported real-art attachment type: {attachment_type} ({attachment_name})")
            region_by_attachment[attachment_name] = attachment.get("path", attachment_name)
        if not attachments:
            del skin[slot_name]

    for slot in skeleton["slots"]:
        if slot["name"] in point_slots:
            slot.pop("attachment", None)
    for animation in skeleton["animations"].values():
        slot_timelines = animation.get("slots", {})
        for slot_name in point_slots:
            slot_timelines.pop(slot_name, None)

    return skeleton, sorted(point_slots), region_by_attachment


def build_atlas(page_dir: str, pages: list[dict]) -> str:
    blocks = []
    for page in pages:
        blocks.append(
            "\n".join(
                [
                    f"{page_dir}/{page['name']}",
                    f"size:{page['width']},{page['height']}",
                    "filter:Linear,Linear",
                    "pma:false",
                    page["region"],
                    f"bounds:0,0,{page['width']},{page['height']}",
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def compose_target(source: Image.Image, redraw: Path | None) -> tuple[Image.Image, int]:
    source_rgba = np.asarray(source.convert("RGBA"), dtype=np.uint8).copy()
    if redraw is None:
        return Image.fromarray(source_rgba, "RGBA"), 0
    redraw_rgba = np.asarray(Image.open(redraw).convert("RGBA"), dtype=np.uint8)
    if redraw_rgba.shape != source_rgba.shape:
        raise ValueError(f"S0/S1 page size mismatch: {redraw}")
    if not np.array_equal(redraw_rgba[:, :, 3], source_rgba[:, :, 3]):
        raise ValueError(f"S0/S1 alpha mismatch: {redraw}")

    written = (source_rgba[:, :, 3] > 0) & np.any(redraw_rgba[:, :, :3] != 255, axis=2)
    source_rgba[written, :3] = redraw_rgba[written, :3]
    source_rgba[source_rgba[:, :, 3] == 0, :3] = 0
    return Image.fromarray(source_rgba, "RGBA"), int(np.count_nonzero(written))


def render(
    renderer: Path,
    skeleton: Path,
    atlas: Path,
    animation: str,
    time: float,
    output: Path,
    viewport: dict,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
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
        animation,
        "--time",
        str(time),
        "--output",
        str(output),
        "--width",
        str(viewport["width"]),
        "--height",
        str(viewport["height"]),
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
        raise RuntimeError(
            f"Render failed for {animation}@{time}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def sequence_poses(path: Path) -> list[dict]:
    poses = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stem = Path(line.strip()).stem
        if not stem:
            continue
        if stem == "restPose":
            poses.append({"animation": "", "time": 0.0, "source": stem})
            continue
        animation, value = stem.rsplit("_", 1)
        poses.append({"animation": animation, "time": float(value), "source": stem})
    return poses


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a public dev case from the archived RedrawSpine SD run.")
    parser.add_argument("--redraw-root", type=Path, required=True)
    parser.add_argument("--run", type=int, default=12)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    redraw_root = args.redraw_root.resolve()
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
        project = redraw_root / "SpineProject"
        source_images = project / "images"
        redraw_pages = redraw_root / "sdout" / str(args.run) / "out"
        if len(list(redraw_pages.glob("*.png"))) != 50:
            raise ValueError(f"Expected a complete 50-page SD run: {redraw_pages}")

        skeleton, removed_points, region_by_attachment = normalized_skeleton(project / "skeleton.json")
        regions = sorted(set(region_by_attachment.values()))
        if len(regions) != 200:
            raise ValueError(f"Expected 200 unique renderable page regions, found {len(regions)}")

        source_dir = temporary / "source_attachments"
        target_dir = temporary / "oracle" / "target_attachments"
        source_dir.mkdir(parents=True)
        target_dir.mkdir(parents=True)
        pages = []
        total_written = 0
        redrawn_pages = 0
        for region in regions:
            name = f"{region}.png"
            source_path = source_images / name
            if not source_path.is_file():
                raise ValueError(f"Missing source attachment page: {source_path}")
            source = Image.open(source_path).convert("RGBA")
            source_rgba = np.asarray(source, dtype=np.uint8).copy()
            source_rgba[source_rgba[:, :, 3] == 0, :3] = 0
            clean_source = Image.fromarray(source_rgba, "RGBA")
            clean_source.save(source_dir / name)

            redraw = redraw_pages / name
            target, written = compose_target(clean_source, redraw if redraw.is_file() else None)
            target.save(target_dir / name)
            total_written += written
            redrawn_pages += int(redraw.is_file())
            pages.append(
                {
                    "region": region,
                    "page": f"source_attachments/{name}",
                    "name": name,
                    "width": source.width,
                    "height": source.height,
                    "alpha_nonzero_pixels": int(np.count_nonzero(source_rgba[:, :, 3] > 0)),
                    "redrawn": redraw.is_file(),
                    "written_pixels": written,
                }
            )

        if redrawn_pages != 50:
            raise ValueError(f"Only {redrawn_pages} archived redraw pages map to the normalized skeleton")

        skeleton_path = temporary / "skeleton.json"
        skeleton_path.write_text(json.dumps(skeleton, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (temporary / "skeleton.atlas").write_text(build_atlas("source_attachments", pages), encoding="utf-8")
        oracle = temporary / "oracle"
        (oracle / "target.atlas").write_text(build_atlas("target_attachments", pages), encoding="utf-8")
        (temporary / "page_manifest.json").write_text(
            json.dumps([{key: value for key, value in page.items() if key not in {"name"}} for page in pages], indent=2),
            encoding="utf-8",
        )

        meta = json.loads((redraw_root / "PSD" / "meta.json").read_text(encoding="utf-8"))
        x, y, width, height = meta["viewPort"]
        viewport = {"x": x, "y": y, "width": width, "height": height}
        observations = []
        poses = sequence_poses(redraw_root / "PSoutput" / "redraw" / "sequence.txt")
        for index, pose in enumerate(poses):
            observation_id = f"obs_{index:03d}"
            relative = Path("observations") / observation_id
            render(
                args.renderer,
                skeleton_path,
                temporary / "skeleton.atlas",
                pose["animation"],
                pose["time"],
                temporary / relative / "before.png",
                viewport,
            )
            render(
                args.renderer,
                skeleton_path,
                oracle / "target.atlas",
                pose["animation"],
                pose["time"],
                temporary / relative / "after.png",
                viewport,
            )
            observations.append(
                {
                    "id": observation_id,
                    "animation": pose["animation"],
                    "time": pose["time"],
                    "before": f"{relative.as_posix()}/before.png",
                    "after": f"{relative.as_posix()}/after.png",
                }
            )

        production_reference = oracle / "production_reference"
        raw_pose_dir = production_reference / "raw_sd_pose_frames"
        raw_pose_dir.mkdir(parents=True)
        raw_pose_manifest = []
        for index, pose in enumerate(poses):
            source_frame = redraw_root / "sdout" / str(args.run) / f"{index}.png"
            if not source_frame.is_file():
                raise ValueError(f"Missing archived raw SD pose frame: {source_frame}")
            destination = raw_pose_dir / source_frame.name
            shutil.copyfile(source_frame, destination)
            raw_pose_manifest.append(
                {
                    "id": f"raw_sd_{index:03d}",
                    "animation": pose["animation"],
                    "time": pose["time"],
                    "frame": f"raw_sd_pose_frames/{source_frame.name}",
                    "equation_truth": False,
                }
            )
        (production_reference / "raw_sd_poses.json").write_text(
            json.dumps(raw_pose_manifest, indent=2), encoding="utf-8"
        )

        validation_poses = [
            ("action", 0.1),
            ("action", 1.0),
            ("action", 2.0),
            ("action", 3.5),
            ("action", 4.5),
            ("angry", 0.4),
            ("angry", 1.0),
            ("idle", 0.4),
            ("idle", 0.8),
            ("delight", 0.5),
            ("shy", 0.5),
            ("surprise", 0.5),
        ]
        validation = oracle / "validation"
        manifest = []
        for index, (animation, time) in enumerate(validation_poses):
            frame = f"frame_{index:03d}.png"
            noop = validation / "noop_frames" / frame
            reference = validation / "reference_frames" / frame
            render(args.renderer, skeleton_path, temporary / "skeleton.atlas", animation, time, noop, viewport)
            render(args.renderer, skeleton_path, oracle / "target.atlas", animation, time, reference, viewport)
            manifest.append(
                {
                    "id": f"validation_{index:03d}",
                    "animation": animation,
                    "time": time,
                    "noop": f"noop_frames/{frame}",
                    "reference": f"reference_frames/{frame}",
                }
            )
        (validation / "hidden_poses.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        case = {
            "schema_version": 1,
            "case_id": "real_art_dev",
            "skeleton": "skeleton.json",
            "atlas": "skeleton.atlas",
            "page_manifest": "page_manifest.json",
            "source_attachments": "source_attachments",
            "observations": observations,
            "viewport": viewport,
            "render_size": {"width": width, "height": height},
            "output_pages": [
                {"name": page["name"], "width": page["width"], "height": page["height"]} for page in pages
            ],
        }
        (temporary / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
        dev_oracle = {
            "schema_version": 1,
            "case_id": "real_art_dev",
            "purpose": "public-real-art-development-oracle",
            "source_run": args.run,
            "target_attachments": "oracle/target_attachments",
            "target_atlas": "oracle/target.atlas",
            "validation_manifest": "oracle/validation/hidden_poses.json",
            "final_cases_expose_target_attachments": False,
        }
        (temporary / "dev_oracle.json").write_text(json.dumps(dev_oracle, indent=2), encoding="utf-8")

        provenance = {
            "schema_version": 1,
            "source_skeleton": "SpineProject/skeleton.json",
            "source_skeleton_sha256": sha256(project / "skeleton.json"),
            "source_sd_run": f"sdout/{args.run}/out",
            "source_sd_run_pages": redrawn_pages,
            "normalized_unique_pages": len(pages),
            "redrawn_pages": redrawn_pages,
            "unchanged_pages": len(pages) - redrawn_pages,
            "removed_nonrendering_point_slots": removed_points,
            "target_written_pixels": total_written,
            "target_composite_rule": "Use archived RGB where it is not exact white; otherwise retain S0. Preserve S0 alpha.",
        }
        (oracle / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

        readme = f"""# Public Real-Art Development Oracle

This optional development fixture is built from the archived RedrawSpine production pipeline and SD run {args.run}.
It is intentionally more complex than the final V1 cases.

## Scope

- 308 bones, 209 slots, weighted meshes, deform timelines, IK constraints, and transform constraints.
- 200 unique static attachment pages with real semitransparent alpha.
- 50 pages contain archived SD redraw pixels; the other {len(pages) - redrawn_pages} pages have S1 equal to S0.
- Three non-rendering PointAttachments are removed during normalization.

The official Spine runtime evaluates constraints and deform before world vertices are extracted. A candidate that uses
the supplied runtime receives final posed triangles in the same way as the original RedrawSpine implementation.
Final V1 benchmark cases still follow the smaller capability contract documented in TASK.md; this fixture is not a
required final gate.

## Target construction

The archived redraw pages were initialized to exact white before screen colors were written back. The fixed S1 oracle
uses archived RGB wherever it differs from exact white and retains S0 elsewhere. S0 alpha is preserved exactly.

All `after.png` and validation references are freshly rendered from this one fixed S1 page set. Raw per-pose SD images
under `oracle/production_reference/` are provided for visual context only. They are not used as equation truth because
they do not necessarily describe one pose-independent static skin.

The original pipeline floods colors beyond directly written texels. Exact full-frame comparison therefore includes
subjective values that public observations may not identify. Interpret reconstruction quality only after masking or
neutralizing texels outside public-observation support; inspect flood completion separately as an aesthetic result.

## Intended workflow

Develop from `case.json`, `source_attachments/`, and `observations/`. Use `oracle/target_attachments/` and
`oracle/validation/` afterward for diagnosis. Target pages are public only in development fixtures and are absent from
final cases.
"""
        (temporary / "DEV_README.md").write_text(readme, encoding="utf-8")

        temporary.rename(output)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "pages": len(pages),
                    "redrawn_pages": redrawn_pages,
                    "observations": len(observations),
                    "validation_poses": len(manifest),
                    "written_pixels": total_written,
                },
                indent=2,
            )
        )
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


if __name__ == "__main__":
    main()
