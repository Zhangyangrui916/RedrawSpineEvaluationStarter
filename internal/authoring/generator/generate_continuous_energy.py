#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate continuous-alpha coefficient energy over public poses.")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-poses", action="store_true")
    args = parser.parse_args()

    case_root = args.case.resolve()
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
        case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
        pages = case["output_pages"]
        aggregate_rgb = [np.zeros((page["height"], page["width"], 3), dtype=np.float64) for page in pages]
        environment = dict(os.environ)
        if os.name == "nt":
            environment["REDRAWSPINE_GL_BACKEND"] = "native"

        pose_reports = []
        for index, observation in enumerate(case["observations"]):
            pose_dir = temporary / "poses" / f"obs_{index:03d}"
            viewport = case["viewport"]
            size = case["render_size"]
            command = [
                str(args.renderer.resolve()),
                "--skeleton",
                str(case_root / case["skeleton"]),
                "--atlas",
                str(case_root / case["atlas"]),
                "--animation",
                observation["animation"],
                "--time",
                str(observation["time"]),
                "--mode",
                "continuous-energy",
                "--energy-dir",
                str(pose_dir),
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
            result = subprocess.run(
                command, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Continuous energy failed for {observation['id']}:\n{result.stdout}\n{result.stderr}"
                )
            manifest = json.loads((pose_dir / "manifest.json").read_text(encoding="utf-8"))
            pose_reports.append(
                {
                    "id": observation["id"],
                    "animation": observation["animation"],
                    "time": observation["time"],
                    "fragment_samples": manifest["fragment_samples"],
                    "pages": len(manifest["pages"]),
                }
            )
            for page in manifest["pages"]:
                page_index = int(page["page_index"])
                raw = np.fromfile(pose_dir / f"page_{page_index:03d}.energy_rgb.f32", dtype=np.float32)
                expected = pages[page_index]["width"] * pages[page_index]["height"] * 3
                if raw.size != expected:
                    raise ValueError(f"Energy size mismatch for page {page_index}: {raw.size} != {expected}")
                aggregate_rgb[page_index] += raw.reshape(
                    (pages[page_index]["height"], pages[page_index]["width"], 3)
                )

        aggregate_dir = temporary / "aggregate"
        aggregate_dir.mkdir()
        source_dir = case_root / case["source_attachments"]
        page_reports = []
        total_nonzero = 0
        total_alpha_nonzero = 0
        for index, (page, channel_energy) in enumerate(zip(pages, aggregate_rgb)):
            name = page["name"]
            energy = np.max(channel_energy, axis=2)
            energy.astype(np.float32).tofile(aggregate_dir / f"{name}.energy.f32")
            maximum = float(energy.max())
            preview = np.zeros(energy.shape, dtype=np.uint8)
            if maximum > 0.0:
                preview = np.rint(np.sqrt(energy / maximum) * 255.0).clip(0, 255).astype(np.uint8)
            Image.fromarray(preview, "L").save(aggregate_dir / f"{name}.png")

            alpha = np.asarray(Image.open(source_dir / name).convert("RGBA"), dtype=np.uint8)[:, :, 3]
            alpha_nonzero = alpha > 0
            values = energy[alpha_nonzero]
            positive = values[values > 0]
            total_nonzero += int(positive.size)
            total_alpha_nonzero += int(values.size)
            quantiles = {}
            if positive.size:
                for quantile in (0.0, 0.01, 0.05, 0.1, 0.5, 0.9, 0.99, 1.0):
                    quantiles[str(quantile)] = float(np.quantile(positive, quantile))
            page_reports.append(
                {
                    "page_index": index,
                    "name": name,
                    "width": page["width"],
                    "height": page["height"],
                    "alpha_nonzero_texels": int(values.size),
                    "energy_nonzero_texels": int(positive.size),
                    "energy_nonzero_fraction": float(positive.size / max(values.size, 1)),
                    "energy_sum": float(energy.sum()),
                    "energy_max": maximum,
                    "positive_energy_quantiles": quantiles,
                }
            )

        report = {
            "schema_version": 1,
            "case_id": case["case_id"],
            "observations": len(case["observations"]),
            "fragment_samples": sum(item["fragment_samples"] for item in pose_reports),
            "pages": len(pages),
            "energy_nonzero_texels": total_nonzero,
            "alpha_nonzero_texels": total_alpha_nonzero,
            "energy_nonzero_fraction": float(total_nonzero / max(total_alpha_nonzero, 1)),
            "pose_reports": pose_reports,
            "page_reports": page_reports,
        }
        (temporary / "energy_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if not args.keep_poses:
            shutil.rmtree(temporary / "poses")
        temporary.rename(output)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "observations": report["observations"],
                    "fragment_samples": report["fragment_samples"],
                    "pages": report["pages"],
                    "energy_nonzero_fraction": report["energy_nonzero_fraction"],
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
