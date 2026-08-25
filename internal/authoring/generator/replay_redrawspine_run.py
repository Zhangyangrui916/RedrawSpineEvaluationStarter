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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_pages(source: Path, destination: Path, names: list[str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(source / name, destination / name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay an archived RedrawSpine SD run without invoking SD.")
    parser.add_argument("--redraw-root", type=Path, required=True)
    parser.add_argument("--run", type=int, required=True)
    parser.add_argument("--analyzer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    redraw_root = args.redraw_root.resolve()
    analyzer = args.analyzer.resolve()
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
        white_images = source_images / "white"
        archived_run = redraw_root / "sdout" / str(args.run)
        archived_pages = archived_run / "out"
        uv_root = redraw_root / "PSoutput" / "redraw"
        meta = json.loads((redraw_root / "PSD" / "meta.json").read_text(encoding="utf-8"))

        if not analyzer.is_file():
            raise ValueError(f"Missing analyzer: {analyzer}")
        if len(list(archived_pages.glob("*.png"))) != 50:
            raise ValueError(f"Run {args.run} is not a complete archived 50-page run")

        work_model = temporary / "model"
        work_images = work_model / "images"
        shutil.copytree(source_images, work_images)
        shutil.copyfile(project / "skeleton.json", work_model / "skeleton.json")

        all_page_names = sorted(path.name for path in source_images.glob("*.png"))
        redraw_page_names = sorted(path.name for path in white_images.glob("*.png"))
        if len(redraw_page_names) != 50:
            raise ValueError(f"Expected 50 white/redraw pages, found {len(redraw_page_names)}")
        copy_pages(source_images, temporary / "s0_pages", all_page_names)
        copy_pages(white_images, work_images, redraw_page_names)

        raw_frames = temporary / "raw_frames"
        raw_frames.mkdir()
        for index in range(10):
            source = archived_run / f"{index}.png"
            if not source.is_file():
                raise ValueError(f"Missing archived frame: {source}")
            shutil.copyfile(source, raw_frames / source.name)

        x, y, width, height = meta["viewPort"]
        viewport = f"{x},{y},{width},{height}"
        slots = list(meta["slots"])
        skip = list(meta["skipRedrawSlots"])
        attachment_filter = ",".join(slots) + ",@," + ",".join(skip) + ",@"

        logs = []
        for index in range(10):
            frame = raw_frames / f"{index}.png"
            command = [
                str(analyzer),
                str(work_model / "skeleton.json"),
                str(work_images / "fake.atlas"),
                viewport,
                "rgb",
                str(uv_root),
                "-attachments",
                attachment_filter,
                "-frame",
                str(frame),
            ]
            result = subprocess.run(
                command,
                cwd=temporary,
                env=dict(os.environ),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logs.append(
                {
                    "frame": index,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Analyzer failed on frame {index}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                )

            snapshot = temporary / "snapshots" / f"frame_{index:03d}"
            copy_pages(work_images, snapshot / "pages", redraw_page_names)
            mask_names = [f"{Path(name).stem}.writtenMask" for name in redraw_page_names]
            copy_pages(work_images, snapshot / "masks", mask_names)

        copy_pages(work_images, temporary / "full_s1_pages", all_page_names)
        copy_pages(work_images, temporary / "redrawn_s1_pages", redraw_page_names)
        final_mask_names = [f"{Path(name).stem}.writtenMask" for name in redraw_page_names]
        copy_pages(work_images, temporary / "final_written_masks", final_mask_names)

        comparisons = []
        exact_matches = 0
        total_different_pixels = 0
        for name in redraw_page_names:
            replayed = temporary / "redrawn_s1_pages" / name
            archived = archived_pages / name
            left = np.asarray(Image.open(replayed).convert("RGBA"), dtype=np.int16)
            right = np.asarray(Image.open(archived).convert("RGBA"), dtype=np.int16)
            different_pixels = int(np.count_nonzero(np.any(left != right, axis=2)))
            total_different_pixels += different_pixels
            same_hash = sha256(replayed) == sha256(archived)
            exact_matches += int(same_hash)
            comparisons.append(
                {
                    "page": name,
                    "sha256_match": same_hash,
                    "different_pixels": different_pixels,
                    "mean_absolute_rgba_error": float(np.abs(left - right).mean()),
                }
            )

        state_counts: dict[str, int] = {}
        for path in (temporary / "final_written_masks").glob("*.writtenMask"):
            values = np.fromfile(path, dtype=np.uint8)
            unique, counts = np.unique(values, return_counts=True)
            for value, count in zip(unique, counts):
                state_counts[str(int(value))] = state_counts.get(str(int(value)), 0) + int(count)

        report = {
            "schema_version": 1,
            "run": args.run,
            "source_skeleton_sha256": sha256(project / "skeleton.json"),
            "analyzer_sha256": sha256(analyzer),
            "viewport": {"x": x, "y": y, "width": width, "height": height},
            "frames": 10,
            "redraw_pages": len(redraw_page_names),
            "all_pages": len(all_page_names),
            "archived_page_sha256_matches": exact_matches,
            "archived_page_total_different_pixels": total_different_pixels,
            "final_written_mask_state_counts": state_counts,
            "page_comparisons": comparisons,
        }
        (temporary / "replay_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (temporary / "frame_logs.json").write_text(json.dumps(logs, indent=2), encoding="utf-8")

        temporary.rename(output)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "run": args.run,
                    "pages": len(redraw_page_names),
                    "sha256_matches": exact_matches,
                    "different_pixels": total_different_pixels,
                    "mask_states": state_counts,
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
