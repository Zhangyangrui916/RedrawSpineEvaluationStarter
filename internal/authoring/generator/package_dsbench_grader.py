#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "redrawspine_grader_bundle.tar.gz"
PART_SIZE = 20 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    validation = args.validation_root.resolve()
    source_test_files = validation / "private" / "test_files"
    renderer = validation / "artifacts" / "trusted-render"
    validation_summary = validation / "artifacts" / "validation_summary.json"
    expected_renderer_hash = "c8925ce73fe4d66028b7bd8e1ad4173b40aecd3cd39f175c5a0899c75ec248b7"
    if not source_test_files.is_dir() or not renderer.is_file() or not validation_summary.is_file():
        raise SystemExit("validation root is missing private test files or accepted Linux artifacts")
    summary = json.loads(validation_summary.read_text(encoding="utf-8"))
    if summary.get("passed") is not True or summary.get("required_backend") != "osmesa":
        raise SystemExit("Linux OSMesa validation summary is not a PASS")
    if sha256(renderer) != expected_renderer_hash:
        raise SystemExit("trusted-render does not match the accepted Linux artifact")

    wheels = sorted(args.wheel_dir.resolve().glob("*.whl"))
    if not any(path.name.startswith("numpy-") for path in wheels):
        raise SystemExit("NumPy wheel is missing")
    if not any(path.name.startswith("pillow-") for path in wheels):
        raise SystemExit("Pillow wheel is missing")

    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"output exists: {output}; use --force")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="redrawspine-package-") as temporary_name:
        bundle = Path(temporary_name) / "redrawspine_grader_bundle"
        shutil.copytree(source_test_files, bundle)
        for case_root in (bundle / "cases").iterdir():
            shutil.rmtree(case_root / "contract" / "observations")
            (case_root / "contract" / "page_manifest.json").unlink()
            (case_root / "hidden" / "hidden_signal_report.json").unlink()
            shutil.rmtree(case_root / "hidden" / "noop_frames")
        for filename in ("grade_case.py", "grade_all.py"):
            shutil.copyfile(ROOT / "grader" / filename, bundle / "grader" / filename)
        shutil.copyfile(ROOT / "grader" / "thresholds.json", bundle / "grader" / "thresholds.json")
        (bundle / "bin").mkdir()
        shutil.copyfile(renderer, bundle / "bin" / "trusted-render")
        (bundle / "wheels").mkdir()
        for wheel in wheels:
            shutil.copyfile(wheel, bundle / "wheels" / wheel.name)

        info = {
            "schema_version": 1,
            "private": True,
            "purpose": "DSBench production Code grader",
            "case_ids": ["static_mesh_seed_a", "static_mesh_seed_b"],
            "backend": "osmesa",
            "overall_threshold": 0.9,
            "validated_date": "2026-08-24",
            "renderer_sha256": sha256(bundle / "bin" / "trusted-render"),
            "validation_scores": summary["scores"],
        }
        (bundle / "BUNDLE_INFO.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

        files = sorted(path for path in bundle.rglob("*") if path.is_file())
        manifest_lines = [f"{sha256(path)}  {path.relative_to(bundle).as_posix()}" for path in files]
        (bundle / "MANIFEST.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

        archive = output / ARCHIVE_NAME
        with tarfile.open(archive, "w:gz", compresslevel=6) as target:
            target.add(bundle, arcname=bundle.name)

    shutil.copyfile(ROOT / "grader" / "test_by_code.py", output / "test_by_code.py")
    archive_hash = sha256(output / ARCHIVE_NAME)
    archive_size = (output / ARCHIVE_NAME).stat().st_size
    parts = []
    with (output / ARCHIVE_NAME).open("rb") as source:
        index = 0
        while chunk := source.read(PART_SIZE):
            part = output / f"{ARCHIVE_NAME}.part{index:03d}"
            part.write_bytes(chunk)
            parts.append({"name": part.name, "size": len(chunk), "sha256": sha256(part)})
            index += 1
    parts_manifest = {
        "schema_version": 1,
        "archive_name": ARCHIVE_NAME,
        "archive_size": archive_size,
        "archive_sha256": archive_hash,
        "parts": parts,
    }
    parts_manifest_name = f"{ARCHIVE_NAME}.parts.json"
    (output / parts_manifest_name).write_text(json.dumps(parts_manifest, indent=2), encoding="utf-8")
    (output / ARCHIVE_NAME).unlink()
    instructions = f"""# DSBench Upload Instructions

1. Under Code grading, select Python and paste the complete contents of `test_by_code.py`.
2. Under grading attachments, use Upload File and select `{parts_manifest_name}` plus every `{ARCHIVE_NAME}.partNNN` file together.
3. Do not place this private archive in the rollout workspace or mention it in the task Prompt.
4. The grading image must provide `libOSMesa.so.8`; NumPy and Pillow are already carried inside the archive.
5. Start Code grading after the rollout has produced `/workspace/results/<case_id>/page_NNN.png`.

Reassembled archive SHA-256: `{archive_hash}`
"""
    (output / "UPLOAD_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "parts": len(parts),
                "largest_part_bytes": max(item["size"] for item in parts),
                "archive_bytes": archive_size,
                "archive_sha256": archive_hash,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
