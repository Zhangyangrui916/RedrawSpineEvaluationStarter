#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a generated continuous-alpha V2 asset export to starter.")
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--starter-assets", type=Path, required=True)
    args = parser.parse_args()

    export = args.export.resolve()
    assets = args.starter_assets.resolve()
    if assets.name != "assets" or not (assets.parent / ".git").is_dir():
        raise SystemExit(f"Refusing to replace assets outside a starter Git worktree: {assets}")
    for required in (export / "cases", export / "dev_cases", export / "export_manifest.json"):
        if not required.exists():
            raise SystemExit(f"Incomplete V2 starter export: missing {required}")

    for name in ("cases", "dev_cases", "public_static_mesh_smoke"):
        target = assets / name
        if target.exists():
            shutil.rmtree(target)
    shutil.copytree(export / "cases", assets / "cases")
    shutil.copytree(export / "dev_cases", assets / "dev_cases")
    shutil.copyfile(export / "export_manifest.json", assets / "export_manifest.json")
    print(f"Synced V2 assets to {assets}")


if __name__ == "__main__":
    main()
