#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the private continuous-alpha PCG authoring baseline.")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--solver", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--ridge", type=float, default=1e-6)
    parser.add_argument("--tolerance", type=float, default=1e-5)
    parser.add_argument("--observation-limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    case_root = args.case.resolve()
    solver = args.solver.resolve()
    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"Output exists: {output}; use --force")
        shutil.rmtree(output)

    case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
    viewport = case["viewport"]
    size = case["render_size"]
    environment = dict(os.environ)
    if os.name == "nt":
        environment["REDRAWSPINE_GL_BACKEND"] = "native"

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="continuous-baseline-", dir=output.parent) as temporary_value:
        pose_list = Path(temporary_value) / "poses.tsv"
        lines = ["# id\tanimation\ttime\tbefore\tafter"]
        observations = case["observations"]
        if args.observation_limit is not None:
            if args.observation_limit < 1:
                raise ValueError("--observation-limit must be positive")
            observations = observations[: args.observation_limit]
        for observation in observations:
            before = (case_root / observation["before"]).resolve()
            after = (case_root / observation["after"]).resolve()
            values = [
                observation["id"],
                observation["animation"],
                str(observation["time"]),
                str(before),
                str(after),
            ]
            if any("\t" in value or "\n" in value or "\r" in value for value in values):
                raise ValueError("Pose-list fields may not contain tabs or newlines")
            lines.append("\t".join(values))
        pose_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

        command = [
            str(solver),
            "--skeleton",
            str((case_root / case["skeleton"]).resolve()),
            "--atlas",
            str((case_root / case["atlas"]).resolve()),
            "--poses",
            str(pose_list),
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
            "--iterations",
            str(args.iterations),
            "--ridge",
            str(args.ridge),
            "--tolerance",
            str(args.tolerance),
            "--output-dir",
            str(output),
        ]
        result = subprocess.run(command, env=environment)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    attachments = output / "attachments"
    source_attachments = case_root / case["source_attachments"]
    expected = {page["name"] for page in case["output_pages"]}
    actual = {path.name for path in attachments.glob("*.png")}
    extra = sorted(actual - expected)
    if extra:
        raise ValueError(f"Solver wrote unexpected pages: {extra}")
    for name in sorted(expected - actual):
        shutil.copyfile(source_attachments / name, attachments / name)

    final = {path.name for path in attachments.glob("*.png")}
    if final != expected:
        raise ValueError("Baseline page completion did not produce the exact expected page set")


if __name__ == "__main__":
    main()
