
# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/图片文件'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / '原始实验留档/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Experiment C: optimize Parquet+ZSTD and Parquet+Snappy parameters for
# whole-file ocean observation compression. Inputs still start from the
# provided raw txt/log files and preprocessing time is counted.

import argparse
import csv
import io
import math
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOCAL_PACKAGES = ROOT / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from run_edge_compression_experiment import (  # noqa: E402
    DEFAULT_BANDWIDTHS_MBPS,
    DEFAULT_PACKET_SIZES,
    Packet,
    build_best_rows,
    build_end_to_end_rows,
    clean_cell,
    discover_datasets,
    normalized_rows,
    parse_datetime_ms,
    parse_float,
    parse_level,
    parse_list,
    split_delimited,
    write_csv,
)


PARQUET_ALGORITHMS = ["parquet_zstd", "parquet_snappy"]


def whole_file_packet(dataset):
    return Packet(packet_id=0, records=dataset.records)


def ceil_div(left, right):
    return (left + right - 1) // right if right else 0


def add_column(arrays, fields, name, values, pa_type):
    arrays.append(pa.array(values, type=pa_type))
    fields.append(pa.field(name, pa_type))


def build_columnar_table(dataset):
    """Build a typed Arrow table column-by-column from the raw records."""
    arrays = []
    fields = []

    if dataset.kind == "big_weather_csv":
        names = [
            "air_temperature",
            "atmosphere",
            "wind_speed",
            "wind_direction",
            "maximum_instantaneous_air_speed",
            "wind_direction_at_maximum_instantaneous_wind_speed",
            "relative_humidity",
            "rainfall",
            "heading",
            "pitch",
            "roll",
        ]
        time_ms = []
        values = {name: [] for name in names}
        for record in dataset.records:
            cells = split_delimited(record.text, ",")
            if not cells or clean_cell(cells[0]).lower() == "time":
                continue
            timestamp = parse_datetime_ms(cells[0])
            if timestamp is None:
                continue
            time_ms.append(timestamp)
            for index, name in enumerate(names, start=1):
                values[name].append(None if index >= len(cells) or clean_cell(cells[index]) == "" else parse_float(cells[index]))
        add_column(arrays, fields, "time_ms", time_ms, pa.int64())
        for name in names:
            add_column(arrays, fields, name, values[name], pa.float64())

    elif dataset.kind == "weather_tsv":
        names = ["wind_speed", "wind_direction", "air_temperature", "atmosphere", "relative_humidity"]
        time_ms = []
        values = {name: [] for name in names}
        for record in dataset.records:
            cells = split_delimited(record.text, "\t")
            if not cells or "日期" in cells[0] or cells[0].lower().startswith("date"):
                continue
            timestamp = parse_datetime_ms(cells[0])
            if timestamp is None:
                continue
            time_ms.append(timestamp)
            for index, name in enumerate(names, start=1):
                values[name].append(None if index >= len(cells) or clean_cell(cells[index]) == "" else parse_float(cells[index]))
        add_column(arrays, fields, "time_ms", time_ms, pa.int64())
        for name in names:
            add_column(arrays, fields, name, values[name], pa.float64())

    elif dataset.kind == "wave_sensor_tsv":
        names = ["ax", "ay", "az", "wx", "wy", "wz", "angle_x", "angle_y", "angle_z", "temperature", "hx", "hy", "hz"]
        address = []
        time_s = []
        chip_time_ms = []
        values = {name: [] for name in names}
        for record in dataset.records:
            text = clean_cell(record.text)
            if not text or text.startswith("StartTime") or text.startswith("address"):
                continue
            cells = split_delimited(record.text, "\t")
            if len(cells) < 3:
                continue
            timestamp = parse_datetime_ms(cells[2])
            if timestamp is None:
                continue
            address.append(cells[0])
            time_s.append(None if clean_cell(cells[1]) == "" else parse_float(cells[1]))
            chip_time_ms.append(timestamp)
            for index, name in enumerate(names, start=3):
                values[name].append(None if index >= len(cells) or clean_cell(cells[index]) == "" else parse_float(cells[index]))
        add_column(arrays, fields, "address", address, pa.dictionary(pa.int32(), pa.string()))
        add_column(arrays, fields, "time_s", time_s, pa.float64())
        add_column(arrays, fields, "chip_time_ms", chip_time_ms, pa.int64())
        for name in names:
            add_column(arrays, fields, name, values[name], pa.float64())

    elif dataset.kind == "ocean_current_log":
        timestamp_ms = []
        source_file = []
        line_no = []
        level = []
        event_type = []
        message = []
        message_bytes = []
        for record in dataset.records:
            text = record.text.strip()
            timestamp = parse_datetime_ms(text[:19]) if len(text) >= 19 else None
            if timestamp is None:
                continue
            timestamp_ms.append(timestamp)
            source_file.append(record.source_file)
            line_no.append(record.line_no)
            level.append(parse_level(text))
            if "adcp_raw_data" in text:
                event_type.append("adcp_raw_data")
            elif "adcp_preprocessing_data" in text:
                event_type.append("adcp_preprocessing_data")
            else:
                event_type.append("other")
            message.append(text)
            message_bytes.append(len(record.raw))
        add_column(arrays, fields, "timestamp_ms", timestamp_ms, pa.int64())
        add_column(arrays, fields, "source_file", source_file, pa.dictionary(pa.int32(), pa.string()))
        add_column(arrays, fields, "line_no", line_no, pa.int64())
        add_column(arrays, fields, "level", level, pa.dictionary(pa.int32(), pa.string()))
        add_column(arrays, fields, "event_type", event_type, pa.dictionary(pa.int32(), pa.string()))
        add_column(arrays, fields, "message", message, pa.string())
        add_column(arrays, fields, "message_bytes", message_bytes, pa.int64())

    else:
        raise ValueError(f"Unsupported dataset kind: {dataset.kind}")

    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))



def scalar_equal(left, right):
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, float) and isinstance(right, float) and math.isnan(left) and math.isnan(right):
        return True
    return left == right


def tables_equal(left, right):
    if left.num_rows != right.num_rows or left.column_names != right.column_names:
        return False
    for name in left.column_names:
        left_values = left[name].to_pylist()
        right_values = right[name].to_pylist()
        if len(left_values) != len(right_values):
            return False
        for a, b in zip(left_values, right_values):
            if not scalar_equal(a, b):
                return False
    return True

def run_candidate(dataset, algorithm, row_group_size, use_dictionary, zstd_level):
    codec = "zstd" if algorithm == "parquet_zstd" else "snappy"
    original_size = dataset.raw_size_bytes
    start = time.perf_counter()
    table = build_columnar_table(dataset)
    buffer = io.BytesIO()
    kwargs = {
        "compression": codec,
        "use_dictionary": use_dictionary,
        "row_group_size": None if row_group_size == 0 else row_group_size,
    }
    if codec == "zstd":
        kwargs["compression_level"] = zstd_level
    pq.write_table(table, buffer, **kwargs)
    compressed = buffer.getvalue()
    after_compress = time.perf_counter()
    restored = pq.read_table(io.BytesIO(compressed))
    after_decompress = time.perf_counter()
    ok = tables_equal(table, restored)
    compression_time = after_compress - start
    decompression_time = after_decompress - after_compress
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
        "integrity": "pass" if ok else "fail",
        "integrity_scope": "optimized_columnar_typed_table",
        "valid_packets": 1,
        "row_count": table.num_rows,
        "column_count": table.num_columns,
    }


def add_transfer_fields(row, packet_size):
    output = dict(row)
    original_size = int(output["original_size_bytes"])
    compressed_size = int(output["compressed_size_bytes"])
    output.update(
        {
            "packet_size": packet_size,
            "transfer_packet_size": packet_size,
            "packet_count": 1,
            "compression_unit_count": 1,
            "original_transfer_packet_count": ceil_div(original_size, packet_size),
            "compressed_transfer_packet_count": ceil_div(compressed_size, packet_size),
            "compression_scope": "whole_file_optimized_parquet",
            "packet_size_role": "transfer_fragment_size_after_whole_file_compression",
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
    parser = argparse.ArgumentParser(description="Experiment C: optimize Parquet codecs.")
    parser.add_argument("--input-dir", default=str(OCEAN_DATA))
    parser.add_argument("--output-dir", default=str(OCEAN_ROOT / "runs" / "文本压缩" / "compression_experiment_C_parquet_optimized_cpu100"))
    parser.add_argument("--datasets", default="")
    parser.add_argument("--algorithms", default="parquet_zstd,parquet_snappy")
    parser.add_argument("--packet-sizes", default=",".join(str(item) for item in DEFAULT_PACKET_SIZES))
    parser.add_argument("--bandwidths-mbps", default=",".join(str(item) for item in DEFAULT_BANDWIDTHS_MBPS))
    parser.add_argument("--cpu-limit-label", default="100")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--row-group-sizes", default="0,8192,65536", help="0 means pyarrow default.")
    parser.add_argument("--dictionary-options", default="true,false")
    parser.add_argument("--zstd-levels", default="1,3,6")
    args = parser.parse_args()

    datasets = discover_datasets(Path(args.input_dir))
    selected = set(parse_list(args.datasets, str)) if args.datasets else None
    if selected:
        datasets = [dataset for dataset in datasets if dataset.dataset_id in selected]
    algorithms = parse_list(args.algorithms, str)
    packet_sizes = parse_list(args.packet_sizes, int)
    bandwidths = parse_list(args.bandwidths_mbps, float)
    row_group_sizes = parse_list(args.row_group_sizes, int)
    dictionary_options = [item.lower() == "true" for item in parse_list(args.dictionary_options, str)]
    zstd_levels = parse_list(args.zstd_levels, int)

    candidate_rows = []
    for dataset in datasets:
        print(f"Dataset {dataset.dataset_id}: {dataset.raw_size_bytes} bytes")
        for algorithm in algorithms:
            if algorithm not in PARQUET_ALGORITHMS:
                raise ValueError(f"Unsupported Parquet algorithm: {algorithm}")
            levels = zstd_levels if algorithm == "parquet_zstd" else [""]
            for row_group_size in row_group_sizes:
                for use_dictionary in dictionary_options:
                    for zstd_level in levels:
                        for repeat in range(1, args.repeats + 1):
                            print(f"  {algorithm} rg={row_group_size} dict={use_dictionary} level={zstd_level or '-'} repeat {repeat}/{args.repeats}")
                            result = run_candidate(dataset, algorithm, row_group_size, use_dictionary, zstd_level or None)
                            base = {
                                "dataset": dataset.dataset_id,
                                "source_files": ";".join(dataset.source_files),
                                "kind": dataset.kind,
                                "algorithm": algorithm,
                                "input_object": "typed_table",
                                "preprocessing_scope": "optimized_columnar_schema_timestamp_dictionary",
                                "optimization_experiment": "C_parquet",
                                "row_group_size": "default" if row_group_size == 0 else row_group_size,
                                "use_dictionary": use_dictionary,
                                "zstd_level": zstd_level,
                                "cpu_limit": args.cpu_limit_label,
                                "repeat": repeat,
                            }
                            base.update(result)
                            for packet_size in packet_sizes:
                                candidate_rows.append(add_transfer_fields(base, packet_size))

    measurement_fields = [
        "dataset", "source_files", "kind", "algorithm", "input_object", "preprocessing_scope",
        "optimization_experiment", "row_group_size", "use_dictionary", "zstd_level",
        "compression_scope", "packet_size_role", "packet_size", "transfer_packet_size",
        "cpu_limit", "repeat", "packet_count", "compression_unit_count",
        "original_transfer_packet_count", "compressed_transfer_packet_count",
        "status", "skip_reason", "original_size_bytes", "compressed_size_bytes",
        "compression_ratio", "compression_time_ms", "decompression_time_ms",
        "compression_throughput_MBps", "decompression_throughput_MBps",
        "integrity", "integrity_scope", "valid_packets", "row_count", "column_count",
    ]
    output_dir = Path(args.output_dir)
    write_rows(output_dir / "candidate_measurements.csv", normalized_rows(candidate_rows), measurement_fields)

    candidate_e2e = build_end_to_end_rows(candidate_rows, bandwidths)
    e2e_fields = measurement_fields + ["bandwidth_mbps", "T_transfer_ms", "T_direct_ms", "T_total_ms", "latency_reduction_pct"]
    write_rows(output_dir / "candidate_end_to_end_results.csv", normalized_rows(candidate_e2e), e2e_fields)

    optimized_e2e = select_best_config_rows(candidate_e2e)
    write_rows(output_dir / "end_to_end_results.csv", normalized_rows(optimized_e2e), e2e_fields)
    best_rows = build_best_rows(optimized_e2e)
    best_fields = ["dataset", "packet_size", "bandwidth_mbps", "cpu_limit", "repeat", "best_algorithm", "best_T_total_ms", "best_latency_reduction_pct", "best_compression_ratio"]
    write_rows(output_dir / "best_algorithm_by_scenario.csv", normalized_rows(best_rows), best_fields)
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()


