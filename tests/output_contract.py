#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def read_rgba8_png(path: Path) -> tuple[int, int, bytes]:
    payload = path.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a PNG: {path.name}")
    offset = len(PNG_SIGNATURE)
    width = height = None
    compressed = bytearray()
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise ValueError(f"truncated PNG chunk: {path.name}")
        length = struct.unpack_from(">I", payload, offset)[0]
        chunk_type = payload[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        if data_end + 4 > len(payload):
            raise ValueError(f"truncated PNG data: {path.name}")
        chunk_data = payload[data_start:data_end]
        expected_crc = struct.unpack_from(">I", payload, data_end)[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(f"PNG CRC mismatch: {path.name}")
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if (bit_depth, color_type, compression, filter_method, interlace) != (8, 6, 0, 0, 0):
                raise ValueError(
                    f"expected non-interlaced RGBA8 PNG: {path.name}; "
                    f"bit_depth={bit_depth} color_type={color_type} interlace={interlace}"
                )
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break
        offset = data_end + 4
    if width is None or height is None:
        raise ValueError(f"PNG has no IHDR: {path.name}")

    raw = zlib.decompress(bytes(compressed))
    stride = width * 4
    if len(raw) != (stride + 1) * height:
        raise ValueError(f"unexpected decompressed PNG size: {path.name}")
    rows = []
    previous = bytearray(stride)
    position = 0
    for _ in range(height):
        filter_type = raw[position]
        position += 1
        encoded = raw[position : position + stride]
        position += stride
        decoded = bytearray(stride)
        for index, value in enumerate(encoded):
            left = decoded[index - 4] if index >= 4 else 0
            up = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = paeth(left, up, upper_left)
            else:
                raise ValueError(f"unsupported PNG filter {filter_type}: {path.name}")
            decoded[index] = (value + predictor) & 0xFF
        rows.append(decoded)
        previous = decoded
    alpha = bytes(channel for row in rows for channel in row[3::4])
    return width, height, alpha


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate candidate attachment pages without checking RGB content.")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    case_root = args.case.resolve()
    output_root = args.output.resolve()
    case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
    expected = {item["name"]: item for item in case["output_pages"]}
    actual = {path.name: path for path in output_root.glob("*.png") if path.is_file()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise SystemExit(f"page set mismatch; missing={missing}; extra={extra}")

    source_root = case_root / case["source_attachments"]
    for name, item in expected.items():
        candidate_path = actual[name]
        if candidate_path.is_symlink() or candidate_path.resolve().parent != output_root:
            raise SystemExit(f"unsafe output page path: {name}")
        width, height, alpha = read_rgba8_png(candidate_path)
        if (width, height) != (item["width"], item["height"]):
            raise SystemExit(f"size mismatch for {name}: {(width, height)}")
        source_width, source_height, source_alpha = read_rgba8_png(source_root / name)
        if (source_width, source_height) != (width, height) or source_alpha != alpha:
            raise SystemExit(f"alpha mismatch for {name}")

    print(json.dumps({"passed": True, "case_id": case["case_id"], "pages": len(expected)}))


if __name__ == "__main__":
    main()
