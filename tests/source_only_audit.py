#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_SUFFIXES = {".exe", ".dll", ".lib", ".obj", ".o", ".a", ".so", ".dylib"}
FORBIDDEN_DIRECTORY_NAMES = {"build", "CMakeFiles", "__pycache__"}
FORBIDDEN_FILENAMES = {"CMakeCache.txt"}
LEAK_MARKERS = {"writtenMask", "decodeUVToSlot", "screenToTexel", "attachmentName2Index"}


def main() -> None:
    parser = argparse.ArgumentParser()
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

    for folder in (root / "src", root / "include"):
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in LEAK_MARKERS:
                if marker in text:
                    violations.append(f"{path.relative_to(root)} contains {marker}")

    case = root / "assets" / "public_static_mesh_smoke"
    case_json = json.loads((case / "case.json").read_text(encoding="utf-8"))
    pages = sorted((case / case_json["source_attachments"]).glob("*.png"))
    if len(pages) != 20:
        violations.append(f"Expected 20 public source pages, found {len(pages)}")

    if violations:
        raise SystemExit("Source-only audit failed:\n" + "\n".join(f"- {item}" for item in violations))
    print(json.dumps({"passed": True, "files": sum(1 for path in root.rglob("*") if path.is_file()), "pages": len(pages)}))


if __name__ == "__main__":
    main()
