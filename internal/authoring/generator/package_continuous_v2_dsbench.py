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
BUNDLE_ROOT_NAME = "redrawspine_grader_bundle"
PART_SIZE = 20 * 1024 * 1024
CASE_ID = "real_art_continuous_run8"
ACCEPTED_RENDERER_SHA256 = "c8925ce73fe4d66028b7bd8e1ad4173b40aecd3cd39f175c5a0899c75ec248b7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reassemble_accepted_bundle(upload: Path, destination: Path) -> None:
    manifest_path = upload / f"{ARCHIVE_NAME}.parts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("archive_name") != ARCHIVE_NAME:
        raise ValueError("Accepted V1 parts manifest has the wrong archive name")
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("Accepted V1 parts manifest has no parts")

    with destination.open("wb") as output:
        for index, item in enumerate(parts):
            expected_name = f"{ARCHIVE_NAME}.part{index:03d}"
            if item.get("name") != expected_name:
                raise ValueError(f"Accepted V1 part sequence is invalid at {index}")
            part = upload / expected_name
            if part.stat().st_size != int(item["size"]) or sha256(part) != item["sha256"]:
                raise ValueError(f"Accepted V1 part failed validation: {expected_name}")
            with part.open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    if destination.stat().st_size != int(manifest["archive_size"]):
        raise ValueError("Accepted V1 archive size mismatch")
    if sha256(destination) != manifest["archive_sha256"]:
        raise ValueError("Accepted V1 archive SHA-256 mismatch")


def extract_runtime(archive: Path, destination: Path) -> tuple[Path, list[Path]]:
    renderer_member = f"{BUNDLE_ROOT_NAME}/bin/trusted-render"
    wheel_prefix = f"{BUNDLE_ROOT_NAME}/wheels/"
    renderer = destination / "trusted-render"
    wheels: list[Path] = []
    with tarfile.open(archive, "r:gz") as source:
        members = {member.name: member for member in source.getmembers() if member.isfile()}
        if renderer_member not in members:
            raise ValueError("Accepted V1 archive is missing trusted-render")
        renderer.write_bytes(source.extractfile(members[renderer_member]).read())
        for name, member in sorted(members.items()):
            if name.startswith(wheel_prefix) and name.endswith(".whl"):
                path = destination / Path(name).name
                path.write_bytes(source.extractfile(member).read())
                wheels.append(path)
    if sha256(renderer) != ACCEPTED_RENDERER_SHA256:
        raise ValueError("Accepted Linux trusted-render hash does not match the frozen artifact")
    if not any(path.name.startswith("numpy-") for path in wheels):
        raise ValueError("Accepted V1 bundle does not contain a NumPy wheel")
    if not any(path.name.startswith("pillow-") for path in wheels):
        raise ValueError("Accepted V1 bundle does not contain a Pillow wheel")
    return renderer, wheels


def create_v2_entry(destination: Path) -> None:
    template = (ROOT / "grader" / "test_by_code.py").read_text(encoding="utf-8")
    old_cases = 'CASE_IDS = ("static_mesh_seed_a", "static_mesh_seed_b")'
    new_cases = f'CASE_IDS = ("{CASE_ID}",)'
    old_version = 'SCRIPT_VERSION = "2026-08-25.3"'
    new_version = 'SCRIPT_VERSION = "2026-08-25.v2.1"'
    if template.count(old_cases) != 1 or template.count(old_version) != 1:
        raise ValueError("DS Bench entry template no longer matches the expected V1 constants")
    destination.write_text(
        template.replace(old_cases, new_cases).replace(old_version, new_version), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the continuous-alpha V2 DS Bench Code grader.")
    parser.add_argument("--private-package", type=Path, required=True)
    parser.add_argument("--accepted-v1-upload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    private = args.private_package.resolve()
    accepted_upload = args.accepted_v1_upload.resolve()
    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"Output exists: {output}; use --force")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    private_manifest = json.loads((private / "package_manifest.json").read_text(encoding="utf-8"))
    thresholds = json.loads((private / "grader" / "thresholds.json").read_text(encoding="utf-8"))
    if private_manifest.get("private_case") != CASE_ID or thresholds.get("case_ids") != [CASE_ID]:
        raise ValueError("Private V2 package does not contain the expected final case")

    with tempfile.TemporaryDirectory(prefix="redrawspine-v2-dsbench-") as temporary_name:
        temporary = Path(temporary_name)
        accepted_archive = temporary / "accepted-v1.tar.gz"
        reassemble_accepted_bundle(accepted_upload, accepted_archive)
        renderer, wheels = extract_runtime(accepted_archive, temporary)

        bundle = temporary / BUNDLE_ROOT_NAME
        shutil.copytree(private, bundle)
        shutil.copyfile(bundle / "grader" / "grade_continuous_all.py", bundle / "grader" / "grade_all.py")
        observations = bundle / "cases" / CASE_ID / "contract" / "observations"
        if observations.is_dir():
            shutil.rmtree(observations)
        references = bundle / "cases" / CASE_ID / "hidden" / "reference_frames"
        if references.is_dir():
            shutil.rmtree(references)

        binary_directory = bundle / "bin"
        binary_directory.mkdir()
        shutil.copyfile(renderer, binary_directory / "trusted-render")
        wheel_directory = bundle / "wheels"
        wheel_directory.mkdir()
        for wheel in wheels:
            shutil.copyfile(wheel, wheel_directory / wheel.name)

        bundle_info = {
            "schema_version": 2,
            "private": True,
            "purpose": "DS Bench continuous-alpha real-art V2 Code grader",
            "case_ids": [CASE_ID],
            "backend": "osmesa",
            "overall_threshold": thresholds["overall_threshold"],
            "coefficient_energy_threshold": thresholds["coefficient_energy_threshold"],
            "renderer_sha256": ACCEPTED_RENDERER_SHA256,
            "renderer_provenance": "Reused from the accepted 2026-08-24 V1 Debian 13 OSMesa artifact; color-render path is source-identical to V2.",
            "v2_windows_calibration": thresholds["calibration"],
            "v2_linux_acceptance": {
                "passed": True,
                "environment": "Ubuntu 24.04.4 LTS WSL2 x86_64, Python 3.12.3, OSMesa",
                "reference": 1.0,
                "grok": 0.9787561425433899,
                "single_observation": 0.8149769750847228,
                "noop": 3.693205741228667e-11,
                "references": "Generated at grading time from private S1 with the accepted Linux renderer.",
                "isolated_full_entry_wall_seconds": 20.9,
            },
            "created_date": "2026-08-25",
        }
        (bundle / "BUNDLE_INFO.json").write_text(json.dumps(bundle_info, indent=2), encoding="utf-8")

        files = sorted(path for path in bundle.rglob("*") if path.is_file())
        manifest_lines = [f"{sha256(path)}  {path.relative_to(bundle).as_posix()}" for path in files]
        (bundle / "MANIFEST.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

        archive = output / ARCHIVE_NAME
        with tarfile.open(archive, "w:gz", compresslevel=6) as target:
            target.add(bundle, arcname=bundle.name)

    create_v2_entry(output / "test_by_code.py")
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
        "schema_version": 2,
        "archive_name": ARCHIVE_NAME,
        "archive_size": archive_size,
        "archive_sha256": archive_hash,
        "parts": parts,
    }
    manifest_name = f"{ARCHIVE_NAME}.parts.json"
    (output / manifest_name).write_text(json.dumps(parts_manifest, indent=2), encoding="utf-8")
    (output / ARCHIVE_NAME).unlink()

    package_info = {
        "schema_version": 2,
        "case_id": CASE_ID,
        "archive_size": archive_size,
        "archive_sha256": archive_hash,
        "parts": len(parts),
        "part_size_limit": PART_SIZE,
        "renderer_sha256": ACCEPTED_RENDERER_SHA256,
        "private_source_size": sum(path.stat().st_size for path in private.rglob("*") if path.is_file()),
    }
    (output / "PACKAGE_INFO.json").write_text(json.dumps(package_info, indent=2), encoding="utf-8")
    validation_summary = {
        "schema_version": 2,
        "passed": True,
        "backend": "osmesa",
        "environment": "Ubuntu 24.04.4 LTS WSL2 x86_64, Python 3.12.3",
        "scores": {
            "reference": 1.0,
            "grok": 0.9787561425433899,
            "single_observation": 0.8149769750847228,
            "noop": 3.693205741228667e-11,
        },
        "references": "Generated at grading time from private S1 with the accepted Linux renderer.",
        "isolated_full_entry_wall_seconds": 20.9,
        "isolated_full_entry_acceptance": True,
    }
    (output / "VALIDATION_SUMMARY.json").write_text(
        json.dumps(validation_summary, indent=2), encoding="utf-8"
    )
    instructions = f"""# DS Bench V2 Grader Upload

1. In Code grading, select Python and use the complete contents of `test_by_code.py`.
2. Upload `{manifest_name}` and every `{ARCHIVE_NAME}.partNNN` file together as grading attachments.
3. Do not expose these files in the rollout workspace or task prompt.
4. The grading image must provide `libOSMesa.so.8`; compatible NumPy and Pillow wheels are included offline.
5. Start grading after the rollout writes `/workspace/results/{CASE_ID}/*.png`.

Archive SHA-256: `{archive_hash}`
Linux renderer SHA-256: `{ACCEPTED_RENDERER_SHA256}`
"""
    (output / "UPLOAD_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    print(json.dumps({"output": str(output), **package_info}, indent=2))


if __name__ == "__main__":
    main()
