#!/usr/bin/env python3
"""Author-only packaging audit for the pristine source starter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_SUFFIXES = {".exe", ".dll", ".lib", ".obj", ".o", ".a", ".so", ".dylib"}
FORBIDDEN_DIRECTORY_NAMES = {"build", "CMakeFiles", "__pycache__"}
FORBIDDEN_FILENAMES = {"CMakeCache.txt"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check that the distributable starter contains source and public data only."
    )
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    violations = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_dir() and path.name in FORBIDDEN_DIRECTORY_NAMES:
            violations.append(str(relative))
        elif path.is_file() and (path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name in FORBIDDEN_FILENAMES):
            violations.append(str(relative))

    case = root / "assets" / "cases" / "real_art_continuous_run8"
    case_json = json.loads((case / "case.json").read_text(encoding="utf-8"))
    pages = sorted((case / case_json["source_attachments"]).glob("*.png"))
    if len(pages) != 200:
        violations.append(f"Expected 200 final source pages, found {len(pages)}")
    for forbidden in ("oracle", "operator_energy", "support_masks", "hidden_poses.json"):
        if (case / forbidden).exists():
            violations.append(f"Final case leaks private path: {forbidden}")

    if violations:
        raise SystemExit("Source-only audit failed:\n" + "\n".join(f"- {item}" for item in violations))
    print(
        json.dumps(
            {
                "passed": True,
                "scope": "author-packaging-audit",
                "files": sum(1 for path in root.rglob("*") if path.is_file()),
                "pages": len(pages),
            }
        )
    )


if __name__ == "__main__":
    main()
