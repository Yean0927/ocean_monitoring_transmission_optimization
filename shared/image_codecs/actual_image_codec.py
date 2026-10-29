#!/usr/bin/env python3
"""Encode assembled image bytes for N1; never substitute a reported size ratio.

JPEG Q75 is a configured lossy baseline, not an experimentally proven winner.
The returned payload is the byte string that a sender must fragment and send.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from time import perf_counter

from PIL import Image


def encode_image(raw: bytes, quality: int = 75) -> tuple[bytes, dict]:
    if not 1 <= quality <= 95:
        raise ValueError("JPEG quality must be between 1 and 95")
    start = perf_counter()
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        dimensions = source.size
        converted = source.convert("RGB")
        buffer = io.BytesIO()
        converted.save(buffer, format="JPEG", quality=quality, optimize=True)
        converted.close()
    payload = buffer.getvalue()
    encoded_at = perf_counter()
    with Image.open(io.BytesIO(payload)) as decoded:
        decoded.load()
        if decoded.size != dimensions:
            raise RuntimeError("Decoded image dimensions differ from source")
    decoded_at = perf_counter()
    return payload, {
        "algorithm": f"JPEG-Q{quality}-optimize",
        "raw_bytes": len(raw),
        "encoded_bytes": len(payload),
        "measured_ratio": len(payload) / len(raw),
        "encode_seconds": encoded_at - start,
        "decode_seconds": decoded_at - encoded_at,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "encoded_sha256": hashlib.sha256(payload).hexdigest(),
        "width": dimensions[0],
        "height": dimensions[1],
        "lossless": False,
        "integrity_scope": "decode_and_dimensions_only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quality", type=int, default=75)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("*.png"))
    if not files:
        raise ValueError("No PNG image inputs")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    # Stable ordering selects an actual median-size source, never an invented file.
    representative = sorted(files, key=lambda p: (p.stat().st_size, p.name))[len(files) // 2]
    for source in files:
        payload, result = encode_image(source.read_bytes(), args.quality)
        target = args.output_dir / f"{source.stem}.jpg"
        target.write_bytes(payload)
        result.update(source=str(source.resolve()), output=str(target.resolve()),
                      median_size_representative=(source == representative))
        results.append(result)
    (args.output_dir / "measurements.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"image_count": len(results), "median_size_source": representative.name,
                      "measurements": str(args.output_dir / "measurements.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
