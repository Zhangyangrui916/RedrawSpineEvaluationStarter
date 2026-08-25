#!/usr/bin/env python3
"""Validate the pristine starter before candidate implementation begins.

This script intentionally verifies the checked-in No-op baseline as well as the
forward renderer. It is an authoring/environment preflight, not a correctness
test for candidate solutions. A valid reconstruction may change or replace the
renderer and will no longer preserve the source-page hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def run(command: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if expect_success and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly succeeded: {' '.join(command)}")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_pose(
    render: Path, case: Path, case_config: dict, work: Path, animation: str, time: float, label: str
) -> dict:
    output = work / f"{label}.png"
    stats = work / f"{label}.json"
    run(
        [
            str(render),
            "--skeleton",
            str(case / "skeleton.json"),
            "--atlas",
            str(case / "skeleton.atlas"),
            "--animation",
            animation,
            "--time",
            str(time),
            "--output",
            str(output),
            "--stats",
            str(stats),
            "--width",
            str(case_config["render_size"]["width"]),
            "--height",
            str(case_config["render_size"]["height"]),
            "--viewport-x",
            str(case_config["viewport"]["x"]),
            "--viewport-y",
            str(case_config["viewport"]["y"]),
            "--viewport-width",
            str(case_config["viewport"]["width"]),
            "--viewport-height",
            str(case_config["viewport"]["height"]),
        ]
    )
    if not output.is_file() or output.stat().st_size < 1024:
        raise AssertionError(f"Renderer did not create a plausible PNG: {output}")
    values = json.loads(stats.read_text(encoding="utf-8"))
    if values["draw_packets"] < 100:
        raise AssertionError(f"Too few draw packets: {values}")
    if values["nonzero_alpha_pixels"] < 100000:
        raise AssertionError(f"Rendered frame is nearly blank: {values}")
    left, top, right, bottom = values["bbox"]
    width = case_config["render_size"]["width"]
    height = case_config["render_size"]["height"]
    if left <= 0 or top <= 0 or right >= width - 1 or bottom >= height - 1:
        raise AssertionError(f"Rendered character touches the viewport boundary: {values}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the unmodified RedrawSpine starter package before implementation."
    )
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--reconstruct", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()

    if args.work.exists():
        shutil.rmtree(args.work)
    args.work.mkdir(parents=True)

    case_config = json.loads((args.case / "case.json").read_text(encoding="utf-8"))
    animations = run(
        [
            str(args.render),
            "--skeleton",
            str(args.case / "skeleton.json"),
            "--atlas",
            str(args.case / "skeleton.atlas"),
            "--list-animations",
        ]
    ).stdout.splitlines()
    for required in ("action", "idle"):
        if required not in animations:
            raise AssertionError(f"Missing expected animation {required}: {animations}")

    action = render_pose(args.render, args.case, case_config, args.work, "action", 0.5, "action")
    idle = render_pose(args.render, args.case, case_config, args.work, "idle", 0.4, "idle")
    if action["nonzero_alpha_pixels"] == idle["nonzero_alpha_pixels"] and action["bbox"] == idle["bbox"]:
        raise AssertionError("Distinct poses produced indistinguishable render statistics")

    invalid_output = args.work / "invalid.png"
    run(
        [
            str(args.render),
            "--skeleton",
            str(args.case / "skeleton.json"),
            "--atlas",
            str(args.case / "skeleton.atlas"),
            "--animation",
            "does_not_exist",
            "--output",
            str(invalid_output),
        ],
        expect_success=False,
    )
    if invalid_output.exists():
        raise AssertionError("Renderer left an output for an invalid animation")

    reconstructed = args.work / "reconstructed"
    run([str(args.reconstruct), "--case", str(args.case), "--output", str(reconstructed)])
    source_pages = sorted((args.case / "source_attachments").glob("*.png"))
    output_pages = sorted(reconstructed.glob("*.png"))
    if [page.name for page in source_pages] != [page.name for page in output_pages]:
        raise AssertionError("No-op reconstruction did not preserve the page set")
    for source, output in zip(source_pages, output_pages):
        if sha256(source) != sha256(output):
            raise AssertionError(f"Pristine No-op baseline changed {source.name}")

    print(
        json.dumps(
            {
                "passed": True,
                "scope": "pristine-starter-preflight",
                "animations": len(animations),
                "source_pages": len(source_pages),
                "action": action,
                "idle": idle,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
