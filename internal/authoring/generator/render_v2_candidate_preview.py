#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw


POSES = (
    ("action_0_10", "action", 0.1),
    ("action_1_00", "action", 1.0),
    ("action_2_00", "action", 2.0),
    ("angry_1_00", "angry", 1.0),
    ("idle_0_80", "idle", 0.8),
    ("surprise_0_50", "surprise", 0.5),
)


def render(renderer: Path, skeleton: Path, atlas: Path, animation: str, time: float, output: Path, case: dict) -> None:
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
        animation,
        "--time",
        str(time),
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
        raise RuntimeError(f"Render failed for {animation}@{time}:\n{result.stdout}\n{result.stderr}")


def composite_on_gray(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (36, 39, 43, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")


def comparison(source_path: Path, candidate_path: Path, reference_path: Path, output: Path, title: str) -> None:
    source = Image.open(source_path).convert("RGBA")
    candidate = Image.open(candidate_path).convert("RGBA")
    reference = Image.open(reference_path).convert("RGBA")
    display_size = (source.width // 2, source.height // 2)
    panels = [
        composite_on_gray(source).resize(display_size, Image.Resampling.LANCZOS),
        composite_on_gray(candidate).resize(display_size, Image.Resampling.LANCZOS),
        composite_on_gray(reference).resize(display_size, Image.Resampling.LANCZOS),
    ]
    difference = np.abs(
        np.asarray(candidate, dtype=np.int16)[:, :, :3] - np.asarray(reference, dtype=np.int16)[:, :, :3]
    )
    amplified = np.clip(difference * 8, 0, 255).astype(np.uint8)
    panels.append(Image.fromarray(amplified, "RGB").resize(display_size, Image.Resampling.LANCZOS))

    label_height = 56
    canvas = Image.new("RGB", (display_size[0] * 4, display_size[1] + label_height), (22, 24, 27))
    draw = ImageDraw.Draw(canvas)
    labels = ("S0 / No-op", "Grok reconstruction", "Private S1 reference", "Absolute error x8")
    for index, (panel, label) in enumerate(zip(panels, labels)):
        left = index * display_size[0]
        canvas.paste(panel, (left, label_height))
        draw.text((left + 14, 11), label, fill=(238, 241, 244))
    draw.text((canvas.width - 220, 11), title, fill=(153, 190, 255))
    canvas.save(output, optimize=True)


def contact_sheet(candidate_paths: list[tuple[str, Path]], output: Path) -> None:
    thumb_size = (464, 572)
    label_height = 34
    canvas = Image.new("RGB", (thumb_size[0] * 3, (thumb_size[1] + label_height) * 2), (22, 24, 27))
    draw = ImageDraw.Draw(canvas)
    for index, (label, path) in enumerate(candidate_paths):
        column = index % 3
        row = index // 3
        left = column * thumb_size[0]
        top = row * (thumb_size[1] + label_height)
        image = composite_on_gray(Image.open(path)).resize(thumb_size, Image.Resampling.LANCZOS)
        canvas.paste(image, (left, top + label_height))
        draw.text((left + 12, top + 8), label, fill=(238, 241, 244))
    canvas.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render raw candidate pages beside S0 and private S1.")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--hidden", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    case_root = args.case.resolve()
    hidden = args.hidden.resolve()
    candidate = args.candidate.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Output already exists: {output}")
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise SystemExit(f"Temporary output already exists: {temporary}")
    temporary.mkdir(parents=True)

    try:
        case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
        expected = {page["name"] for page in case["output_pages"]}
        actual = {path.name for path in candidate.glob("*.png")}
        if actual != expected:
            raise ValueError(f"Candidate page set mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")

        shutil.copyfile(case_root / case["skeleton"], temporary / "skeleton.json")
        shutil.copytree(candidate, temporary / "candidate_pages")
        atlas = (case_root / case["atlas"]).read_text(encoding="utf-8")
        (temporary / "candidate.atlas").write_text(
            atlas.replace("source_attachments/", "candidate_pages/"), encoding="utf-8"
        )
        for directory in ("source", "candidate", "reference", "comparison"):
            (temporary / directory).mkdir()

        candidate_paths = []
        manifest = []
        for stem, animation, time in POSES:
            source_frame = temporary / "source" / f"{stem}.png"
            candidate_frame = temporary / "candidate" / f"{stem}.png"
            reference_frame = temporary / "reference" / f"{stem}.png"
            comparison_frame = temporary / "comparison" / f"{stem}_compare.png"
            render(args.renderer.resolve(), temporary / "skeleton.json", case_root / case["atlas"], animation, time, source_frame, case)
            render(args.renderer.resolve(), temporary / "skeleton.json", temporary / "candidate.atlas", animation, time, candidate_frame, case)
            render(args.renderer.resolve(), temporary / "skeleton.json", hidden / "target.atlas", animation, time, reference_frame, case)
            comparison(source_frame, candidate_frame, reference_frame, comparison_frame, f"{animation} @ {time:.2f}s")
            candidate_paths.append((f"{animation} @ {time:.2f}s", candidate_frame))
            manifest.append(
                {
                    "id": stem,
                    "animation": animation,
                    "time": time,
                    "source": f"source/{stem}.png",
                    "candidate": f"candidate/{stem}.png",
                    "reference": f"reference/{stem}.png",
                    "comparison": f"comparison/{stem}_compare.png",
                }
            )
        contact_sheet(candidate_paths, temporary / "grok_candidate_contact_sheet.png")
        (temporary / "poses.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (temporary / "README.md").write_text(
            """# Grok V2 Render Preview

Each comparison image shows S0, the raw Grok reconstruction, private S1, and RGB absolute error amplified 8x.
These poses are not among the ten public observations. Full-resolution transparent renders are kept in the source,
candidate, and reference directories. The candidate pages are copied only to make the preview atlas self-contained.
""",
            encoding="utf-8",
        )
        temporary.rename(output)
        print(json.dumps({"output": str(output), "poses": len(manifest)}, indent=2))
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


if __name__ == "__main__":
    main()
