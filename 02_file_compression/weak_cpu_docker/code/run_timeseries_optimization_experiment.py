
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
# Experiment D: optimize Gorilla and Chimp preprocessing/windowing for
# whole-file or batched numeric time-series compression.

import argparse
import csv
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT / "python-packages") not in sys.path and (ROOT / "python-packages").exists():
    sys.path.insert(0, str(ROOT / "python-packages"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_edge_compression_experiment import (  # noqa: E402
    DEFAULT_BANDWIDTHS_MBPS,
    DEFAULT_PACKET_SIZES,
    NATIVE_CODEC_BIN,
    NumericPacket,
    Packet,
    build_best_rows,
    build_end_to_end_rows,
    discover_datasets,
    float_to_bits,
    normalized_rows,
    numeric_packet_from_records,
    pack_u32,
    parse_datetime_ms,
    parse_float,
    parse_list,
    write_native_numeric_batch,
)


TS_ALGORITHMS = ["gorilla", "chimp"]


def ceil_div(left, right):
    return (left + right - 1) // right if right else 0


def whole_file_packet(dataset):
    return Packet(packet_id=0, records=dataset.records)


def split_records(records, segment_records):
    if segment_records <= 0:
        return [records]
    return [records[index : index + segment_records] for index in range(0, len(records), segment_records)]


def split_numeric_packet(packet, segment_rows):
    if segment_rows <= 0 or len(packet.timestamps) <= segment_rows:
        return [packet]
    packets = []
    for start in range(0, len(packet.timestamps), segment_rows):
        end = min(start + segment_rows, len(packet.timestamps))
        values = {column: packet.values[column][start:end] for column in packet.columns}
        packets.append(NumericPacket(timestamps=packet.timestamps[start:end], columns=packet.columns, values=values))
    return packets


def parse_d4_semantic_numeric(dataset):
    rows = []
    keys = set()
    timestamps = []
    for record in dataset.records:
        text = record.text
        if "adcp_preprocessing_data" not in text:
            continue
        log_timestamp = parse_datetime_ms(text[:19]) if len(text) >= 19 else None
        payload = text.split("adcp_preprocessing_data", 1)[-1]
        payload = payload.split(":", 1)[-1].strip()
        try:
            item = json.loads(payload)
        except json.JSONDecodeError:
            continue
        timestamp = parse_datetime_ms(str(item.get("time", ""))) or log_timestamp
        if timestamp is None:
            continue
        row = {}
        for name in ["beam_Angle", "distance_1st_Cell", "ed", "heading", "pitch", "roll", "wN", "wS"]:
            if name in item:
                row[name] = parse_float(str(item[name]))
        beams = item.get("beams", [])
        for cell_index, cell in enumerate(beams):
            if not isinstance(cell, list):
                continue
            for beam_index, beam in enumerate(cell):
                if not isinstance(beam, dict):
                    continue
                for metric in ["corrleation_Magnitude", "echo_Intensity", "good_Percent", "velocity"]:
                    key = f"cell_{cell_index:03d}_beam_{beam_index}_{metric}"
                    row[key] = parse_float(str(beam.get(metric, "")))
        keys.update(row.keys())
        rows.append(row)
        timestamps.append(timestamp)
    columns = sorted(keys)
    values = {column: [] for column in columns}
    for row in rows:
        for column in columns:
            values[column].append(row.get(column, math.nan))
    return NumericPacket(timestamps=timestamps, columns=columns, values=values)


def numeric_packets_for_candidate(dataset, numeric_mode, segment_records):
    if numeric_mode == "generic":
        packets = []
        for records in split_records(dataset.records, segment_records):
            packets.append(numeric_packet_from_records(dataset, Packet(packet_id=len(packets), records=records)))
        return packets
    if numeric_mode == "d4_semantic_adcp":
        if dataset.kind != "ocean_current_log":
            return []
        full = parse_d4_semantic_numeric(dataset)
        return split_numeric_packet(full, segment_records)
    raise ValueError(f"unknown numeric mode: {numeric_mode}")


def run_native_numeric_packets(numeric_packets, algorithm, native_codec_bin):
    native_codec_bin = Path(native_codec_bin)
    if not native_codec_bin.exists():
        raise FileNotFoundError(f"Native numeric codec not found: {native_codec_bin}")
    with tempfile.TemporaryDirectory(prefix="ocean_ts_opt_") as temp_dir:
        batch_path = Path(temp_dir) / "numeric_batch.bin"
        write_native_numeric_batch(batch_path, numeric_packets)
        completed = subprocess.run(
            [str(native_codec_bin), "--codec", algorithm, "--input", str(batch_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    return json.loads(completed.stdout)


def run_candidate(dataset, algorithm, numeric_mode, segment_records, native_codec_bin):
    original_size = dataset.raw_size_bytes
    start = time.perf_counter()
    numeric_packets = numeric_packets_for_candidate(dataset, numeric_mode, segment_records)
    if not numeric_packets:
        raise ValueError(f"numeric mode {numeric_mode} produced no packets for {dataset.dataset_id}")
    after_preprocess = time.perf_counter()
    metrics = run_native_numeric_packets(numeric_packets, algorithm, native_codec_bin)
    preprocess_time = after_preprocess - start
    compression_time = preprocess_time + float(metrics["compression_time_ms"]) / 1000.0
    decompression_time = float(metrics["decompression_time_ms"]) / 1000.0
    compressed_size = int(metrics["compressed_size_bytes"])
    original_mb = original_size / (1024 * 1024)
    return {
        "status": "ok",
        "skip_reason": "",
        "original_size_bytes": original_size,
        "compressed_size_bytes": compressed_size,
        "compression_ratio": compressed_size / original_size if original_size else "",
        "compression_time_ms": compression_time * 1000.0,
        "decompression_time_ms": decompression_time * 1000.0,
        "compression_throughput_MBps": original_mb / compression_time if compression_time else "",
        "decompression_throughput_MBps": original_mb / decompression_time if decompression_time else "",
        "integrity": metrics.get("integrity", "fail"),
        "integrity_scope": f"{numeric_mode}_logical_numeric_native",
        "valid_packets": int(metrics.get("valid_packets", len(numeric_packets))),
        "numeric_column_count": len(numeric_packets[0].columns) if numeric_packets else 0,
        "numeric_row_count": sum(len(packet.timestamps) for packet in numeric_packets),
    }


def add_transfer_fields(row, packet_size):
    output = dict(row)
    original_size = int(output["original_size_bytes"])
    compressed_size = int(output["compressed_size_bytes"])
    output.update(
        {
            "packet_size": packet_size,
            "transfer_packet_size": packet_size,
            "packet_count": output["compression_unit_count"],
            "original_transfer_packet_count": ceil_div(original_size, packet_size),
            "compressed_transfer_packet_count": ceil_div(compressed_size, packet_size),
            "compression_scope": "optimized_time_series",
            "packet_size_role": "transfer_fragment_size_after_time_series_compression",
        }
    )
    return output


def select_best_config_rows(end_to_end_rows):
    groups = {}
    for row in end_to_end_rows:
        key = (
            row["dataset"],
            row["kind"],
            row["algorithm"],
            row["packet_size"],
            row["bandwidth_mbps"],
            row["cpu_limit"],
            row["repeat"],
        )
        groups.setdefault(key, []).append(row)
    return [min(rows, key=lambda row: float(row["T_total_ms"])) for rows in groups.values()]


def write_rows(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Experiment D: optimize Gorilla/Chimp time-series preprocessing.")
    parser.add_argument("--input-dir", default=str(OCEAN_DATA))
    parser.add_argument("--output-dir", default=str(OCEAN_ROOT / "runs" / "weak_cpu_docker" / "compression_experiment_D_timeseries_optimized_cpu100"))
    parser.add_argument("--datasets", default="")
    parser.add_argument("--algorithms", default="gorilla,chimp")
    parser.add_argument("--packet-sizes", default=",".join(str(item) for item in DEFAULT_PACKET_SIZES))
    parser.add_argument("--bandwidths-mbps", default=",".join(str(item) for item in DEFAULT_BANDWIDTHS_MBPS))
    parser.add_argument("--cpu-limit-label", default="100")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--segment-records", default="0,1024,8192", help="0 means one whole-file time-series batch.")
    parser.add_argument("--numeric-modes", default="generic,d4_semantic_adcp")
    parser.add_argument("--native-codec-bin", default=str(NATIVE_CODEC_BIN))
    args = parser.parse_args()

    datasets = discover_datasets(Path(args.input_dir))
    selected = set(parse_list(args.datasets, str)) if args.datasets else None
    if selected:
        datasets = [dataset for dataset in datasets if dataset.dataset_id in selected]
    algorithms = parse_list(args.algorithms, str)
    packet_sizes = parse_list(args.packet_sizes, int)
    bandwidths = parse_list(args.bandwidths_mbps, float)
    segment_records_options = parse_list(args.segment_records, int)
    numeric_modes = parse_list(args.numeric_modes, str)

    candidate_rows = []
    for dataset in datasets:
        print(f"Dataset {dataset.dataset_id}: {dataset.raw_size_bytes} bytes")
        for numeric_mode in numeric_modes:
            if numeric_mode == "d4_semantic_adcp" and dataset.kind != "ocean_current_log":
                continue
            for algorithm in algorithms:
                if algorithm not in TS_ALGORITHMS:
                    raise ValueError(f"Unsupported time-series algorithm: {algorithm}")
                for segment_records in segment_records_options:
                    for repeat in range(1, args.repeats + 1):
                        print(f"  {algorithm} mode={numeric_mode} segment={segment_records} repeat {repeat}/{args.repeats}")
                        result = run_candidate(dataset, algorithm, numeric_mode, segment_records, args.native_codec_bin)
                        base = {
                            "dataset": dataset.dataset_id,
                            "source_files": ";".join(dataset.source_files),
                            "kind": dataset.kind,
                            "algorithm": algorithm,
                            "input_object": "parsed_time_series",
                            "preprocessing_scope": "optimized_timestamp_numeric_series",
                            "optimization_experiment": "D_time_series",
                            "numeric_mode": numeric_mode,
                            "segment_records": "whole_file" if segment_records == 0 else segment_records,
                            "cpu_limit": args.cpu_limit_label,
                            "repeat": repeat,
                            "compression_unit_count": result["valid_packets"],
                        }
                        base.update(result)
                        for packet_size in packet_sizes:
                            candidate_rows.append(add_transfer_fields(base, packet_size))

    fields = [
        "dataset", "source_files", "kind", "algorithm", "input_object", "preprocessing_scope",
        "optimization_experiment", "numeric_mode", "segment_records",
        "compression_scope", "packet_size_role", "packet_size", "transfer_packet_size",
        "cpu_limit", "repeat", "packet_count", "compression_unit_count",
        "original_transfer_packet_count", "compressed_transfer_packet_count",
        "status", "skip_reason", "original_size_bytes", "compressed_size_bytes",
        "compression_ratio", "compression_time_ms", "decompression_time_ms",
        "compression_throughput_MBps", "decompression_throughput_MBps",
        "integrity", "integrity_scope", "valid_packets", "numeric_column_count", "numeric_row_count",
    ]
    output_dir = Path(args.output_dir)
    write_rows(output_dir / "candidate_measurements.csv", normalized_rows(candidate_rows), fields)
    candidate_e2e = build_end_to_end_rows(candidate_rows, bandwidths)
    e2e_fields = fields + ["bandwidth_mbps", "T_transfer_ms", "T_direct_ms", "T_total_ms", "latency_reduction_pct"]
    write_rows(output_dir / "candidate_end_to_end_results.csv", normalized_rows(candidate_e2e), e2e_fields)
    optimized_e2e = select_best_config_rows(candidate_e2e)
    write_rows(output_dir / "end_to_end_results.csv", normalized_rows(optimized_e2e), e2e_fields)
    best_rows = build_best_rows(optimized_e2e)
    best_fields = ["dataset", "packet_size", "bandwidth_mbps", "cpu_limit", "repeat", "best_algorithm", "best_T_total_ms", "best_latency_reduction_pct", "best_compression_ratio"]
    write_rows(output_dir / "best_algorithm_by_scenario.csv", normalized_rows(best_rows), best_fields)
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
