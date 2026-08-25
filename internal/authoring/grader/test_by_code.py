#!/usr/bin/env python3
"""DSBench Code grader entry point.

Paste this file into the Python Code grading editor. The script uses only the
standard library until the trusted dependency wheels have been unpacked.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import traceback
import zipfile
from pathlib import Path


ARCHIVE_NAME = "redrawspine_grader_bundle.tar.gz"
PARTS_MANIFEST_NAME = f"{ARCHIVE_NAME}.parts.json"
RESULT_PATH = Path("/eval/code_result.json")
CASE_IDS = ("static_mesh_seed_a", "static_mesh_seed_b")
SCRIPT_VERSION = "2026-08-25.3"


def log(message: str) -> None:
    print(f"[redrawspine-grader] {message}", flush=True)


def write_result(resolved: bool, score: float, reason: str) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"resolved": bool(resolved), "score": float(score), "reason": str(reason)[:2000]}
    RESULT_PATH.write_text(json.dumps(payload), encoding="utf-8")
    log(f"code_result={json.dumps(payload, ensure_ascii=True)}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_archive(destination: Path) -> Path:
    test_files = Path("/test_files")
    archives = sorted(path for path in test_files.rglob(ARCHIVE_NAME) if path.is_file())
    manifests = sorted(path for path in test_files.rglob(PARTS_MANIFEST_NAME) if path.is_file())
    if len(archives) == 1 and not manifests:
        log(f"using single archive: {archives[0]}")
        return archives[0]
    if archives or len(manifests) != 1:
        raise RuntimeError(
            f"expected one {ARCHIVE_NAME} or one {PARTS_MANIFEST_NAME}; "
            f"found archives={len(archives)}, manifests={len(manifests)}"
        )

    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    parts = manifest.get("parts")
    if manifest.get("archive_name") != ARCHIVE_NAME or not isinstance(parts, list) or not parts:
        raise RuntimeError("grader archive parts manifest is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    log(f"reassembling {len(parts)} checked archive parts")
    total_size = 0
    with destination.open("wb") as output:
        for index, item in enumerate(parts):
            expected_name = f"{ARCHIVE_NAME}.part{index:03d}"
            if item.get("name") != expected_name:
                raise RuntimeError(f"grader archive part sequence is invalid at index {index}")
            part = manifests[0].parent / expected_name
            if not part.is_file():
                raise RuntimeError(f"grader archive part is missing: {expected_name}")
            expected_size = int(item.get("size", -1))
            if part.stat().st_size != expected_size or sha256(part) != item.get("sha256"):
                raise RuntimeError(f"grader archive part failed validation: {expected_name}")
            total_size += expected_size
            with part.open("rb") as stream:
                shutil.copyfileobj(stream, output, length=1024 * 1024)
    if total_size != int(manifest.get("archive_size", -1)):
        raise RuntimeError("reassembled grader archive has the wrong size")
    if sha256(destination) != manifest.get("archive_sha256"):
        raise RuntimeError("reassembled grader archive failed SHA-256 validation")
    log(f"archive reassembled and verified: {total_size} bytes")
    return destination


def extract_bundle(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk():
                raise RuntimeError(f"archive links are not allowed: {member.name}")
        bundle.extractall(destination, filter="data")
    bundle_root = destination / "redrawspine_grader_bundle"
    if not (bundle_root / "BUNDLE_INFO.json").is_file():
        raise RuntimeError("grader bundle marker is missing")
    verify_manifest(bundle_root)
    log("internal grader bundle manifest verified")
    return bundle_root


def verify_manifest(bundle_root: Path) -> None:
    manifest_path = bundle_root / "MANIFEST.sha256"
    expected = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64:
            raise RuntimeError("grader bundle manifest is malformed")
        expected[relative] = digest
    actual = {
        path.relative_to(bundle_root).as_posix(): path
        for path in bundle_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(actual) != set(expected):
        raise RuntimeError("grader bundle file set does not match its manifest")
    for relative, path in actual.items():
        if sha256(path) != expected[relative]:
            raise RuntimeError(f"grader bundle checksum mismatch: {relative}")


def unpack_python_wheels(bundle_root: Path, destination: Path) -> None:
    wheels = sorted((bundle_root / "wheels").glob("*.whl"))
    if not wheels:
        raise RuntimeError("trusted Python dependency wheels are missing")
    destination.mkdir(parents=True, exist_ok=True)
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as package:
            package.extractall(destination)


def select_python(dependencies: Path) -> Path:
    candidates = [Path(sys.executable), Path("/usr/local/bin/python3"), Path("/usr/bin/python3")]
    probe = (
        "import sys; "
        f"sys.path.insert(0, {str(dependencies)!r}); "
        "import numpy, PIL; "
        "print(sys.version.split()[0], numpy.__version__, PIL.__version__)"
    )
    seen: set[Path] = set()
    failures = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        result = subprocess.run(
            [str(resolved), "-I", "-c", probe],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log(f"selected Python: {resolved} ({result.stdout.strip()})")
            return resolved
        failures.append(f"{resolved}: {result.stderr.strip()[-300:]}")
    raise RuntimeError("no compatible Python for trusted wheels; " + "; ".join(failures))


def find_results_root() -> Path:
    workspace = Path("/workspace")
    repository_roots = [workspace]
    repository_roots.extend(path for path in workspace.iterdir() if path.is_dir() and not path.is_symlink())
    valid = []
    for repository in repository_roots:
        markers_present = (
            (repository / "TASK.md").is_file()
            and (repository / "CMakeLists.txt").is_file()
            and (repository / "assets" / "cases").is_dir()
        )
        if not markers_present:
            continue
        candidate = repository / "results"
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        if all((candidate / case_id).is_dir() for case_id in CASE_IDS):
            resolved = candidate.resolve()
            if resolved not in valid:
                valid.append(resolved)
    if len(valid) != 1:
        rendered = ", ".join(str(path) for path in valid) or "none"
        raise RuntimeError(f"expected one marked task repository with final results; found {len(valid)}: {rendered}")
    log(f"selected results root: {valid[0]}")
    return valid[0]


def run_grader(bundle_root: Path, dependencies: Path, python: Path, results_root: Path) -> dict:
    renderer_source = bundle_root / "bin" / "trusted-render"
    renderer = Path("/eval/bin/trusted-render")
    renderer.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(renderer_source, renderer)
    renderer.chmod(0o755)

    grade_all = bundle_root / "grader" / "grade_all.py"
    bootstrap = (
        "import runpy,sys; "
        f"sys.path.insert(0, {str(dependencies)!r}); "
        "script=sys.argv[1]; sys.argv=sys.argv[1:]; "
        "runpy.run_path(script, run_name='__main__')"
    )
    command = [
        str(python),
        "-I",
        "-c",
        bootstrap,
        str(grade_all),
        "--results-root",
        str(results_root),
        "--test-files",
        str(bundle_root),
        "--renderer",
        str(renderer),
        "--output",
        str(RESULT_PATH),
    ]
    environment = dict(os.environ)
    environment.pop("LD_PRELOAD", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    environment["PYTHONPATH"] = str(dependencies)
    environment["REDRAWSPINE_GL_BACKEND"] = "osmesa"
    log(f"starting private grader with renderer={renderer}")
    completed = subprocess.run(
        command,
        cwd="/eval",
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    if completed.stdout.strip():
        log("private grader stdout follows")
        print(completed.stdout.rstrip(), flush=True)
    if completed.stderr.strip():
        print("[redrawspine-grader] private grader stderr follows", file=sys.stderr, flush=True)
        print(completed.stderr.rstrip(), file=sys.stderr, flush=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-1200:]
        raise RuntimeError(f"private grader failed with exit {completed.returncode}: {detail}")
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if not isinstance(result.get("resolved"), bool):
        raise RuntimeError("private grader returned an invalid resolved value")
    score = float(result.get("score"))
    if not 0.0 <= score <= 1.0:
        raise RuntimeError("private grader returned a score outside [0, 1]")
    return {"resolved": result["resolved"], "score": score, "reason": str(result.get("reason", ""))}


def main() -> None:
    log(f"entry version={SCRIPT_VERSION}")
    try:
        with tempfile.TemporaryDirectory(prefix="redrawspine-dsbench-", dir="/eval") as temporary_name:
            temporary = Path(temporary_name)
            archive = materialize_archive(temporary / ARCHIVE_NAME)
            bundle_root = extract_bundle(archive, temporary / "bundle")
            dependencies = temporary / "python_deps"
            unpack_python_wheels(bundle_root, dependencies)
            python = select_python(dependencies)
            results_root = find_results_root()
            result = run_grader(bundle_root, dependencies, python, results_root)
        write_result(result["resolved"], result["score"], result["reason"])
    except Exception as error:
        print(f"[redrawspine-grader] infrastructure failure: {error}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        write_result(False, 0.0, f"grader infrastructure error: {error}")


if __name__ == "__main__":
    main()
