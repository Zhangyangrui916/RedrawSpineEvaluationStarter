#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]

BAND_LIMITED_MIN_WAVELENGTH = 48.0
BAND_LIMITED_MAX_WAVELENGTH = 256.0
BAND_LIMITED_AMPLITUDE = 24.0


def periodic_field(width: int, height: int, base: tuple[int, int, int], phases: tuple[float, ...]) -> np.ndarray:
    x = np.arange(width, dtype=np.float32)[None, :]
    y = np.arange(height, dtype=np.float32)[:, None]
    channels = []
    periods = ((96.0, 144.0), (128.0, 88.0), (176.0, 112.0))
    for channel, (period_x, period_y) in enumerate(periods):
        value = (
            float(base[channel])
            + 18.0 * np.sin((2.0 * math.pi * x / period_x) + phases[channel * 2])
            + 14.0 * np.cos((2.0 * math.pi * y / period_y) + phases[channel * 2 + 1])
        )
        channels.append(np.broadcast_to(value, (height, width)))
    return np.clip(np.stack(channels, axis=2), 16, 239).astype(np.uint8)


def band_limited_field(width: int, height: int, base: tuple[int, int, int], seed: int) -> np.ndarray:
    # Generate on a padded canvas, then crop, so FFT periodicity does not create a visible page-edge seam.
    padding = int(BAND_LIMITED_MAX_WAVELENGTH)
    padded_width = width + padding * 2
    padded_height = height + padding * 2
    fx = np.fft.rfftfreq(padded_width)[None, :]
    fy = np.fft.fftfreq(padded_height)[:, None]
    frequency = np.sqrt(fx * fx + fy * fy)

    low_cut = 1.0 / BAND_LIMITED_MAX_WAVELENGTH
    high_cut = 1.0 / BAND_LIMITED_MIN_WAVELENGTH
    low_rolloff = 1.0 - np.exp(-np.power(frequency / low_cut, 8))
    high_rolloff = np.exp(-np.power(frequency / high_cut, 8))
    envelope = low_rolloff * high_rolloff

    rng = np.random.default_rng(seed)
    channels = []
    for channel in range(3):
        noise = rng.standard_normal((padded_height, padded_width))
        spectrum = np.fft.rfft2(noise)
        field = np.fft.irfft2(spectrum * envelope, s=(padded_height, padded_width)).real
        field = field[padding : padding + height, padding : padding + width]
        field -= float(field.mean())
        standard_deviation = float(field.std())
        if standard_deviation <= 1e-8:
            raise RuntimeError("Band-limited target field has zero variance")
        field = np.clip(field / standard_deviation, -2.5, 2.5)
        channels.append(float(base[channel]) + BAND_LIMITED_AMPLITUDE * field)
    return np.clip(np.stack(channels, axis=2), 16, 239).astype(np.uint8)


def source_field(width: int, height: int, page_index: int) -> np.ndarray:
    palette = [
        (86, 112, 142),
        (145, 102, 92),
        (91, 139, 105),
        (151, 128, 78),
        (112, 95, 146),
        (78, 138, 145),
    ]
    base = palette[page_index % len(palette)]
    x = np.arange(width, dtype=np.float32)[None, :]
    y = np.arange(height, dtype=np.float32)[:, None]
    repeated = 7.0 * np.sin(2.0 * math.pi * x / 128.0) + 7.0 * np.cos(2.0 * math.pi * y / 128.0)
    return np.clip(np.asarray(base, dtype=np.float32)[None, None, :] + repeated[:, :, None], 24, 224).astype(
        np.uint8
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    case_root = args.case_root.resolve()
    spec = json.loads((case_root / "authoring_spec.json").read_text(encoding="utf-8"))
    source_model = ROOT / spec["source_model"]
    manifest = json.loads((source_model / "page_manifest.json").read_text(encoding="utf-8"))
    private = case_root / "private"
    if private.exists():
        if not args.force:
            raise SystemExit(f"Private output already exists: {private}; use --force")
        shutil.rmtree(private)
    s0_dir = private / "s0_pages"
    s1_dir = private / "s1_pages"
    s0_dir.mkdir(parents=True)
    s1_dir.mkdir(parents=True)

    report_pages = []
    total_changed = 0
    target_generator = spec.get("target_generator", "legacy_periodic_v1")
    if target_generator not in {"legacy_periodic_v1", "band_limited_v2"}:
        raise ValueError(f"Unknown target_generator: {target_generator}")
    for page_index, item in enumerate(manifest):
        page_name = Path(item["page"]).name
        source = Image.open(source_model / item["page"]).convert("RGBA")
        rgba = np.asarray(source, dtype=np.uint8)
        alpha = rgba[:, :, 3]
        alpha_values = set(int(value) for value in np.unique(alpha))
        if not alpha_values <= {0, 255}:
            raise ValueError(f"Non-binary alpha in {page_name}: {sorted(alpha_values)}")

        width, height = source.size
        s0_rgb = source_field(width, height, page_index)
        rng = random.Random(int(spec["target_seed"]) * 1009 + page_index * 9176)
        if target_generator == "legacy_periodic_v1":
            target_base = tuple(rng.randint(48, 207) for _ in range(3))
            phases = tuple(rng.random() * 2.0 * math.pi for _ in range(6))
            target_rgb = periodic_field(width, height, target_base, phases)
            target_field_seed = None
        else:
            target_base = tuple(rng.randint(72, 183) for _ in range(3))
            target_field_seed = int(spec["target_seed"]) * 1_000_003 + page_index * 97_409
            target_rgb = band_limited_field(width, height, target_base, target_field_seed)

        coverage_path = case_root / "union_coverage" / page_name
        coverage = np.asarray(Image.open(coverage_path).convert("L"), dtype=np.uint8) >= 128
        changed = coverage & (alpha == 255)
        s1_rgb = s0_rgb.copy()
        s1_rgb[changed] = target_rgb[changed]

        transparent = alpha == 0
        s0_rgb[transparent] = 0
        s1_rgb[transparent] = 0
        s0_rgba = np.dstack([s0_rgb, alpha])
        s1_rgba = np.dstack([s1_rgb, alpha])
        Image.fromarray(s0_rgba, "RGBA").save(s0_dir / page_name)
        Image.fromarray(s1_rgba, "RGBA").save(s1_dir / page_name)

        changed_count = int(np.count_nonzero(changed))
        total_changed += changed_count
        report_pages.append(
            {
                "page": page_name,
                "width": width,
                "height": height,
                "opaque_texels": int(np.count_nonzero(alpha == 255)),
                "coverage_texels": int(np.count_nonzero(coverage)),
                "changed_texels": changed_count,
                "target_base": list(target_base),
                "target_field_seed": target_field_seed,
            }
        )

    atlas = (source_model / "skeleton.atlas").read_text(encoding="utf-8")
    (private / "s0.atlas").write_text(atlas.replace("pages/", "s0_pages/"), encoding="utf-8")
    (private / "s1.atlas").write_text(atlas.replace("pages/", "s1_pages/"), encoding="utf-8")
    shutil.copyfile(source_model / "skeleton.json", private / "skeleton.json")

    report = {
        "schema_version": 1,
        "case_id": spec["case_id"],
        "target_seed": spec["target_seed"],
        "target_generator": target_generator,
        "target_generator_parameters": (
            {
                "minimum_wavelength_texels": BAND_LIMITED_MIN_WAVELENGTH,
                "maximum_wavelength_texels": BAND_LIMITED_MAX_WAVELENGTH,
                "amplitude": BAND_LIMITED_AMPLITUDE,
            }
            if target_generator == "band_limited_v2"
            else {"periods": [[96.0, 144.0], [128.0, 88.0], [176.0, 112.0]]}
        ),
        "total_changed_texels": total_changed,
        "pages": report_pages,
    }
    (private / "skin_generation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"case_id": spec["case_id"], "changed_texels": total_changed, "pages": len(report_pages)}, indent=2))


if __name__ == "__main__":
    main()
