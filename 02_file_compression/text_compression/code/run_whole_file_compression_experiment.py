
# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/images'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / 'raw_experiments/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Run whole-file compression experiments for ocean observation data.
#
# This is experiment B: compression context is the whole dataset/file, while
# packet_size is only used to report transfer fragmentation after compression.

import argparse
import csv
import gzip
import io
import math
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT / "python-packages") not in sys.path and (ROOT / "python-packages").exists():
    sys.path.insert(0, str(ROOT / "python-packages"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_edge_compression_experiment import (  # noqa: E402
    ALGORITHMS,
    DEFAULT_BANDWIDTHS_MBPS,
    DEFAULT_PACKET_SIZES,
    NATIVE_CODEC_BIN,
    Packet,
    algorithm_input_object,
    algorithm_preprocessing_scope,
    build_best_rows,
    build_end_to_end_rows,
    discover_datasets,
    encode_numeric_packet,
    decode_numeric_packet,
    gzip_compress,
    normalized_rows,
    numeric_packet_from_records,
    parse_list,
    parquet_available,
    run_native_numeric_group,
    table_rows_from_records,
    values_equal,
    write_csv,
)


def whole_file_packet(dataset):
    return Packet(packet_id=0, records=dataset.records)


def ceil_div(left, right):
    return (left + right - 1) // right if right else 0


def original_bytes(dataset):
    return b"".join(record.raw for record in dataset.records)


def base_result(original_size, compressed, compression_time, decompression_time, integrity_ok, scope):
    original_mb = original_size / (1024 * 1024)
    return {
        "status": "ok",
        "skip_reason": "",
        "original_size_bytes": original_size,
        "compressed_size_bytes": len(compressed),
        "compression_ratio": len(compressed) / original_size if original_size else "",
        "compression_time_ms": compression_time * 1000.0,
        "decompression_time_ms": decompression_time * 1000.0,
        "compression_throughput_MBps": original_mb / compression_time if compression_time else "",
        "decompression_throughput_MBps": original_mb / decompression_time if decompression_time else "",
        "integrity": "pass" if integrity_ok else "fail",
        "integrity_scope": scope,
        "valid_packets": 1,
    }


def benchmark_whole_gzip(dataset):
    expected = original_bytes(dataset)
    start = time.perf_counter()
    compressed = gzip_compress(expected)
    after_compress = time.perf_counter()
    restored = gzip.decompress(compressed)
    after_decompress = time.perf_counter()
    return base_result(
        len(expected),
        compressed,
        after_compress - start,
        after_decompress - after_compress,
        restored == expected,
        "byte_exact_whole_file",
    )


def benchmark_whole_numeric_python(dataset, codec):
    packet = whole_file_packet(dataset)
    original_size = len(packet.raw)
    start = time.perf_counter()
    expected = numeric_packet_from_records(dataset, packet)
    compressed = encode_numeric_packet(expected, codec)
    after_compress = time.perf_counter()
    restored = decode_numeric_packet(compressed)
    after_decompress = time.perf_counter()
    return base_result(
        original_size,
        compressed,
        after_compress - start,
        after_decompress - after_compress,
        values_equal(expected, restored),
        "parsed_ts_logical_numeric_whole_file",
    )


def benchmark_whole_numeric(dataset, codec, numeric_codec_backend, native_codec_bin):
    if numeric_codec_backend != "python":
        native_path = Path(native_codec_bin)
        if native_path.exists():
            result = run_native_numeric_group(dataset, [whole_file_packet(dataset)], codec, native_path)
            result["integrity_scope"] = "parsed_ts_logical_numeric_native_whole_file"
            return result
        if numeric_codec_backend == "native":
            raise FileNotFoundError(f"Native numeric codec not found: {native_path}")
    return benchmark_whole_numeric_python(dataset, codec)


def benchmark_whole_parquet(dataset, compression):
    import pyarrow as pa
    import pyarrow.parquet as pq

    packet = whole_file_packet(dataset)
    original_size = len(packet.raw)
    start = time.perf_counter()
    expected = table_rows_from_records(dataset, packet)
    table = pa.Table.from_pylist(expected if expected else [{"__empty_file": True}])
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression=compression)
    compressed = buffer.getvalue()
    after_compress = time.perf_counter()
    restored = pq.read_table(io.BytesIO(compressed)).to_pylist()
    after_decompress = time.perf_counter()
    expected_rows = expected if expected else [{"__empty_file": True}]
    return base_result(
        original_size,
        compressed,
        after_compress - start,
        after_decompress - after_compress,
        restored == expected_rows,
        "typed_table_whole_file",
    )


def benchmark_whole_file(dataset, algorithm, numeric_codec_backend, native_codec_bin):
    if algorithm == "gzip":
        return benchmark_whole_gzip(dataset)
    if algorithm == "gorilla":
        return benchmark_whole_numeric(dataset, "gorilla", numeric_codec_backend, native_codec_bin)
    if algorithm == "chimp":
        return benchmark_whole_numeric(dataset, "chimp", numeric_codec_backend, native_codec_bin)
    if algorithm == "parquet_zstd":
        available, reason = parquet_available()
        if not available:
            return skipped_result(dataset, reason)
        return benchmark_whole_parquet(dataset, "zstd")
    if algorithm == "parquet_snappy":
        available, reason = parquet_available()
        if not available:
            return skipped_result(dataset, reason)
        return benchmark_whole_parquet(dataset, "snappy")
    raise ValueError(f"unsupported algorithm: {algorithm}")


def skipped_result(dataset, reason):
    return {
        "status": "skipped",
        "skip_reason": reason,
        "original_size_bytes": dataset.raw_size_bytes,
        "compressed_size_bytes": "",
        "compression_ratio": "",
        "compression_time_ms": "",
        "decompression_time_ms": "",
        "compression_throughput_MBps": "",
        "decompression_throughput_MBps": "",
        "integrity": "skipped",
        "integrity_scope": "",
        "valid_packets": "",
    }


def add_transfer_packet_fields(row, packet_size):
    output = dict(row)
    original_size = int(row["original_size_bytes"])
    compressed_size = int(row["compressed_size_bytes"]) if row["compressed_size_bytes"] != "" else 0
    output.update(
        {
            "packet_size": packet_size,
            "transfer_packet_size": packet_size,
            "packet_count": 1,
            "compression_unit_count": 1,
            "original_transfer_packet_count": ceil_div(original_size, packet_size),
            "compressed_transfer_packet_count": ceil_div(compressed_size, packet_size),
            "compression_scope": "whole_file",
            "packet_size_role": "transfer_fragment_size_after_whole_file_compression",
        }
    )
    return output


def whole_file_summary(dataset, packet_size):
    original_size = dataset.raw_size_bytes
    return {
        "dataset": dataset.dataset_id,
        "source_files": ";".join(dataset.source_files),
        "encoding": dataset.encoding,
        "kind": dataset.kind,
        "compression_scope": "whole_file",
        "original_size_bytes": original_size,
        "original_size_MB": original_size / (1024 * 1024),
        "record_count": len(dataset.records),
        "packet_size": packet_size,
        "packet_size_role": "transfer_fragment_size_after_whole_file_compression",
        "original_transfer_packet_count": ceil_div(original_size, packet_size),
        "compression_unit_count": 1,
    }


def write_csv_rows(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def format_float(value):
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.9f}"
    return value


def main():
    parser = argparse.ArgumentParser(description="Run ocean whole-file compression experiments.")
    parser.add_argument(
        "--input-dir",
        default=str(OCEAN_DATA),
        help="Directory containing the extracted ocean observation data files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OCEAN_ROOT / "runs" / "text_compression" / "compression_experiment_whole_file_cpu100"),
        help="Directory for CSV outputs.",
    )
    parser.add_argument("--datasets", default="", help="Comma-separated dataset ids to run. Empty means all discovered.")
    parser.add_argument("--algorithms", default=",".join(ALGORITHMS), help="Comma-separated algorithms.")
    parser.add_argument("--packet-sizes", default=",".join(str(item) for item in DEFAULT_PACKET_SIZES), help="Transfer packet sizes in bytes.")
    parser.add_argument("--bandwidths-mbps", default=",".join(str(item) for item in DEFAULT_BANDWIDTHS_MBPS), help="Bandwidths in Mbps.")
    parser.add_argument("--cpu-limit-label", default="100", help="Label for externally enforced CPU limit.")
    parser.add_argument("--repeats", type=int, default=1, help="Repeated measurements per dataset/algorithm.")
    parser.add_argument(
        "--numeric-codec-backend",
        choices=["auto", "python", "native"],
        default="auto",
        help="Backend for Gorilla/Chimp numeric codecs. auto uses native binary when present.",
    )
    parser.add_argument(
        "--native-codec-bin",
        default=str(NATIVE_CODEC_BIN),
        help="Path to native Gorilla/Chimp numeric codec executable.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    algorithms = parse_list(args.algorithms, str)
    packet_sizes = parse_list(args.packet_sizes, int)
    bandwidths = parse_list(args.bandwidths_mbps, float)
    selected_datasets = set(parse_list(args.datasets, str)) if args.datasets else None

    unknown = [algorithm for algorithm in algorithms if algorithm not in ALGORITHMS]
    if unknown:
        raise ValueError(f"Unknown algorithms: {unknown}. Supported: {ALGORITHMS}")
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    datasets = discover_datasets(input_dir)
    if selected_datasets:
        datasets = [dataset for dataset in datasets if dataset.dataset_id in selected_datasets]
    if not datasets:
        raise RuntimeError(f"No datasets found in {input_dir}")

    measurement_fields = [
        "dataset",
        "source_files",
        "kind",
        "algorithm",
        "input_object",
        "preprocessing_scope",
        "compression_scope",
        "packet_size_role",
        "packet_size",
        "transfer_packet_size",
        "cpu_limit",
        "repeat",
        "packet_count",
        "compression_unit_count",
        "original_transfer_packet_count",
        "compressed_transfer_packet_count",
        "status",
        "skip_reason",
        "original_size_bytes",
        "compressed_size_bytes",
        "compression_ratio",
        "compression_time_ms",
        "decompression_time_ms",
        "compression_throughput_MBps",
        "decompression_throughput_MBps",
        "integrity",
        "integrity_scope",
        "valid_packets",
    ]
    summary_fields = [
        "dataset",
        "source_files",
        "encoding",
        "kind",
        "compression_scope",
        "original_size_bytes",
        "original_size_MB",
        "record_count",
        "packet_size",
        "packet_size_role",
        "original_transfer_packet_count",
        "compression_unit_count",
    ]

    summary_rows = []
    measurement_rows = []
    for dataset in datasets:
        print(f"Dataset {dataset.dataset_id}: {len(dataset.records)} records, {dataset.raw_size_bytes} bytes")
        for packet_size in packet_sizes:
            summary_rows.append(whole_file_summary(dataset, packet_size))
        for algorithm in algorithms:
            for repeat in range(1, args.repeats + 1):
                print(f"  {algorithm} repeat {repeat}/{args.repeats}")
                try:
                    result = benchmark_whole_file(
                        dataset,
                        algorithm,
                        numeric_codec_backend=args.numeric_codec_backend,
                        native_codec_bin=args.native_codec_bin,
                    )
                except Exception as exc:
                    result = {
                        "status": "error",
                        "skip_reason": repr(exc),
                        "original_size_bytes": dataset.raw_size_bytes,
                        "compressed_size_bytes": "",
                        "compression_ratio": "",
                        "compression_time_ms": "",
                        "decompression_time_ms": "",
                        "compression_throughput_MBps": "",
                        "decompression_throughput_MBps": "",
                        "integrity": "fail",
                        "integrity_scope": "",
                        "valid_packets": "",
                    }

                base_row = {
                    "dataset": dataset.dataset_id,
                    "source_files": ";".join(dataset.source_files),
                    "kind": dataset.kind,
                    "algorithm": algorithm,
                    "input_object": algorithm_input_object(algorithm),
                    "preprocessing_scope": algorithm_preprocessing_scope(algorithm),
                    "cpu_limit": args.cpu_limit_label,
                    "repeat": repeat,
                }
                base_row.update(result)
                for packet_size in packet_sizes:
                    measurement_rows.append(add_transfer_packet_fields(base_row, packet_size))

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(output_dir / "packet_summary.csv", normalized_rows(summary_rows), summary_fields)
    write_csv_rows(output_dir / "compression_measurements.csv", normalized_rows(measurement_rows), measurement_fields)

    end_to_end_rows = build_end_to_end_rows(measurement_rows, bandwidths)
    end_to_end_fields = measurement_fields + [
        "bandwidth_mbps",
        "T_transfer_ms",
        "T_direct_ms",
        "T_total_ms",
        "latency_reduction_pct",
    ]
    write_csv_rows(output_dir / "end_to_end_results.csv", normalized_rows(end_to_end_rows), end_to_end_fields)

    best_rows = build_best_rows(end_to_end_rows)
    best_fields = [
        "dataset",
        "packet_size",
        "bandwidth_mbps",
        "cpu_limit",
        "repeat",
        "best_algorithm",
        "best_T_total_ms",
        "best_latency_reduction_pct",
        "best_compression_ratio",
    ]
    write_csv_rows(output_dir / "best_algorithm_by_scenario.csv", normalized_rows(best_rows), best_fields)
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
