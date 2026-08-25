#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


CASE_IDS = ("static_mesh_seed_a", "static_mesh_seed_b")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--test-files", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    thresholds = args.test_files / "grader" / "thresholds.json"
    threshold_config = json.loads(thresholds.read_text(encoding="utf-8"))
    grade_case = Path(__file__).with_name("grade_case.py")
    scores = []
    reasons = []
    with tempfile.TemporaryDirectory(prefix="redrawspine-grade-all-") as temporary_name:
        temporary = Path(temporary_name)
        for case_id in CASE_IDS:
            case_root = args.test_files / "cases" / case_id
            case_output = temporary / f"{case_id}.json"
            command = [
                sys.executable,
                str(grade_case),
                "--visible-case",
                str(case_root / "contract"),
                "--private-case",
                str(case_root / "hidden"),
                "--results",
                str(args.results_root / case_id),
                "--renderer",
                str(args.renderer),
                "--thresholds",
                str(thresholds),
                "--output",
                str(case_output),
            ]
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            result = json.loads(case_output.read_text(encoding="utf-8"))
            scores.append(float(result["score"]))
            reasons.append(f"{case_id}={result['score']:.4f}")

    overall = sum(scores) / len(scores)
    resolved = overall >= float(threshold_config["overall_threshold"])
    result = {"resolved": bool(resolved), "score": float(overall), "reason": "; ".join(reasons)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
