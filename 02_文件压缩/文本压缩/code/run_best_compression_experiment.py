
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
# Re-run the current best implementation/configuration for the five ocean
# compression schemes:
#
#   gzip           -> whole-file raw bytes + gzip
#   Gorilla        -> optimized typed numeric time series + native codec
#   Chimp          -> optimized typed numeric time series + native codec
#   Parquet+ZSTD   -> optimized typed table + Parquet(ZSTD)
#   Parquet+Snappy -> optimized typed table + Parquet(Snappy)
#
# The best configs default to the current experiment C/D results. If
# sample_results/compression_experiment_CD_optimized_cpu100/
# best_config_by_algorithm_scenario.csv exists, it is used as the source of
# truth so later optimization runs can be replayed without editing this file.

import argparse
import csv
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_PACKAGES = ROOT / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_edge_compression_experiment import (  # noqa: E402
    ALGORITHMS,
    DEFAULT_BANDWIDTHS_MBPS,
    DEFAULT_PACKET_SIZES,
    NATIVE_CODEC_BIN,
    algorithm_input_object,
    build_best_rows,
    build_end_to_end_rows,
    discover_datasets,
    normalized_rows,
    parse_list,
    write_csv,
)
from run_parquet_optimization_experiment import run_candidate as run_parquet_candidate  # noqa: E402
from run_timeseries_optimization_experiment import run_candidate as run_timeseries_candidate  # noqa: E402
from run_whole_file_compression_experiment import (  # noqa: E402
    benchmark_whole_gzip,
    ceil_div,
)


DEFAULT_CONFIG_CSV = (
    OCEAN_ROOT
    / "data"
    / "压缩实验参考结果"
    / "compression_experiment_CD_optimized_cpu100"
    / "best_config_by_algorithm_scenario.csv"
)


FALLBACK_BEST_CONFIGS = {
    ("D1_big_buoy_weather", "gorilla"): {"numeric_mode": "generic", "segment_records": "1024"},
    ("D1_big_buoy_weather", "chimp"): {"numeric_mode": "generic", "segment_records": "8192"},
    ("D1_big_buoy_weather", "parquet_zstd"): {
        "row_group_size": "default",
        "use_dictionary": "True",
        "zstd_level": "6",
    },
    ("D1_big_buoy_weather", "parquet_snappy"): {
        "row_group_size": "default",
        "use_dictionary": "True",
        "zstd_level": "",
    },
    ("D2_weather_utf16", "gorilla"): {"numeric_mode": "generic", "segment_records": "1024"},
    ("D2_weather_utf16", "chimp"): {"numeric_mode": "generic", "segment_records": "whole_file"},
    ("D2_weather_utf16", "parquet_zstd"): {
        "row_group_size": "default",
        "use_dictionary": "False",
        "zstd_level": "6",
    },
    ("D2_weather_utf16", "parquet_snappy"): {
        "row_group_size": "65536",
        "use_dictionary": "True",
        "zstd_level": "",
    },
    ("D3_wave_sensor", "gorilla"): {"numeric_mode": "generic", "segment_records": "1024"},
    ("D3_wave_sensor", "chimp"): {"numeric_mode": "generic", "segment_records": "whole_file"},
    ("D3_wave_sensor", "parquet_zstd"): {
        "row_group_size": "65536",
        "use_dictionary": "True",
        "zstd_level": "6",
    },
    ("D3_wave_sensor", "parquet_snappy"): {
        "row_group_size": "default",
        "use_dictionary": "True",
        "zstd_level": "",
    },
    ("D4_ocean_current_log", "gorilla"): {
        "numeric_mode": "d4_semantic_adcp",
        "segment_records": "8192",
    },
    ("D4_ocean_current_log", "chimp"): {
        "numeric_mode": "d4_semantic_adcp",
        "segment_records": "1024",
    },
    ("D4_ocean_current_log", "parquet_zstd"): {
        "row_group_size": "8192",
        "use_dictionary": "False",
        "zstd_level": "6",
    },
    # D4 Parquet+Snappy has a bandwidth-specific tie in the current results.
    # The config CSV, when present, preserves that scenario-level choice.
    ("D4_ocean_current_log", "parquet_snappy"): {
        "row_group_size": "8192",
        "use_dictionary": "False",
        "zstd_level": "",
    },
}


MEASUREMENT_FIELDS = [
    "dataset",
    "source_files",
    "kind",
    "algorithm",
    "input_object",
    "preprocessing_scope",
    "optimization_source",
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
    "row_group_size",
    "use_dictionary",
    "zstd_level",
    "numeric_mode",
    "segment_records",
    "row_count",
    "column_count",
    "numeric_column_count",
    "numeric_row_count",
]


SUMMARY_FIELDS = [
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


def normalize_float_string(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isnan(number):
        return ""
    if number.is_integer():
        return str(int(number))
    return str(number)


def normalize_bool_string(value):
    return "True" if str(value).strip().lower() in {"1", "true", "yes"} else "False"


def config_signature(config):
    return (
        normalize_float_string(config.get("row_group_size", "")),
        normalize_bool_string(config.get("use_dictionary", "")) if config.get("use_dictionary", "") != "" else "",
        normalize_float_string(config.get("zstd_level", "")),
        str(config.get("numeric_mode", "")).strip(),
        str(config.get("segment_records", "")).strip(),
    )


def parse_segment_records(value):
    text = str(value).strip()
    if text in {"", "whole_file", "default"}:
        return 0
    return int(float(text))


def parse_row_group_size(value):
    text = str(value).strip()
    if text in {"", "default"}:
        return 0
    return int(float(text))


def parse_zstd_level(value):
    text = str(value).strip()
    if text == "":
        return None
    return int(float(text))


def load_config_scenarios(config_csv, datasets, algorithms, packet_sizes, bandwidths):
    requested_datasets = {dataset.dataset_id for dataset in datasets}
    requested_algorithms = set(algorithms)
    requested_packets = {str(packet_size) for packet_size in packet_sizes}
    requested_bandwidths = {normalize_float_string(bandwidth) for bandwidth in bandwidths}
    scenarios = []

    if Path(config_csv).exists():
        try:
            optimization_source = str(Path(config_csv).resolve().relative_to(ROOT))
        except ValueError:
            optimization_source = str(config_csv)
        with Path(config_csv).open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                dataset = row.get("dataset", "")
                algorithm = row.get("algorithm", "")
                packet_size = normalize_float_string(row.get("packet_size", ""))
                bandwidth = normalize_float_string(row.get("bandwidth_mbps", ""))
                if dataset not in requested_datasets:
                    continue
                if algorithm not in requested_algorithms:
                    continue
                if packet_size not in requested_packets:
                    continue
                if bandwidth not in requested_bandwidths:
                    continue
                scenarios.append(
                    {
                        "dataset": dataset,
                        "algorithm": algorithm,
                        "packet_size": int(packet_size),
                        "bandwidth_mbps": float(bandwidth),
                        "config": {
                            "row_group_size": normalize_float_string(row.get("row_group_size", "")),
                            "use_dictionary": row.get("use_dictionary", ""),
                            "zstd_level": normalize_float_string(row.get("zstd_level", "")),
                            "numeric_mode": row.get("numeric_mode", ""),
                            "segment_records": row.get("segment_records", ""),
                        },
                        "optimization_source": optimization_source,
                    }
                )

    if scenarios:
        return scenarios

    for dataset in datasets:
        for algorithm in algorithms:
            config = dict(FALLBACK_BEST_CONFIGS.get((dataset.dataset_id, algorithm), {}))
            for packet_size in packet_sizes:
                for bandwidth in bandwidths:
                    scenarios.append(
                        {
                            "dataset": dataset.dataset_id,
                            "algorithm": algorithm,
                            "packet_size": packet_size,
                            "bandwidth_mbps": bandwidth,
                            "config": config,
                            "optimization_source": "fallback_best_configs_in_script",
                        }
                    )
    return scenarios


def add_transfer_fields(row, packet_size, compression_scope, packet_size_role):
    output = dict(row)
    original_size = int(output["original_size_bytes"])
    compressed_size = int(output["compressed_size_bytes"]) if output["compressed_size_bytes"] != "" else 0
    output.update(
        {
            "packet_size": packet_size,
            "transfer_packet_size": packet_size,
            "packet_count": output.get("compression_unit_count", 1),
            "original_transfer_packet_count": ceil_div(original_size, packet_size),
            "compressed_transfer_packet_count": ceil_div(compressed_size, packet_size),
            "compression_scope": compression_scope,
            "packet_size_role": "transfer_fragment_size_after_best_compression",
        }
    )
    output["packet_size_role"] = packet_size_role
    return output


def base_measurement_row(dataset, algorithm, cpu_limit, repeat, optimization_source):
    return {
        "dataset": dataset.dataset_id,
        "source_files": ";".join(dataset.source_files),
        "kind": dataset.kind,
        "algorithm": algorithm,
        "input_object": algorithm_input_object(algorithm),
        "cpu_limit": cpu_limit,
        "repeat": repeat,
        "optimization_source": optimization_source,
        "row_group_size": "",
        "use_dictionary": "",
        "zstd_level": "",
        "numeric_mode": "",
        "segment_records": "",
        "row_count": "",
        "column_count": "",
        "numeric_column_count": "",
        "numeric_row_count": "",
    }


def run_best_gzip(dataset):
    result = benchmark_whole_gzip(dataset)
    result["compression_unit_count"] = 1
    return result


def run_best_parquet(dataset, algorithm, config):
    row_group_size = parse_row_group_size(config.get("row_group_size", ""))
    use_dictionary = normalize_bool_string(config.get("use_dictionary", "True")) == "True"
    zstd_level = parse_zstd_level(config.get("zstd_level", ""))
    result = run_parquet_candidate(dataset, algorithm, row_group_size, use_dictionary, zstd_level)
    result["compression_unit_count"] = 1
    return result


def run_best_timeseries(dataset, algorithm, config, native_codec_bin):
    numeric_mode = config.get("numeric_mode") or "generic"
    segment_records = parse_segment_records(config.get("segment_records", ""))
    return run_timeseries_candidate(dataset, algorithm, numeric_mode, segment_records, native_codec_bin)


def run_unique_measurement(dataset, algorithm, config, cpu_limit, repeat, optimization_source, native_codec_bin):
    base = base_measurement_row(dataset, algorithm, cpu_limit, repeat, optimization_source)
    config = dict(config)

    if algorithm == "gzip":
        result = run_best_gzip(dataset)
        base["preprocessing_scope"] = "none_raw_bytes"
        compression_scope = "whole_file_best_gzip"
        packet_size_role = "transfer_fragment_size_after_whole_file_gzip"
    elif algorithm.startswith("parquet_"):
        result = run_best_parquet(dataset, algorithm, config)
        base["preprocessing_scope"] = "optimized_columnar_schema_timestamp_dictionary"
        base["row_group_size"] = config.get("row_group_size", "")
        base["use_dictionary"] = config.get("use_dictionary", "")
        base["zstd_level"] = config.get("zstd_level", "")
        compression_scope = "whole_file_optimized_parquet"
        packet_size_role = "transfer_fragment_size_after_whole_file_parquet"
    elif algorithm in {"gorilla", "chimp"}:
        result = run_best_timeseries(dataset, algorithm, config, native_codec_bin)
        base["preprocessing_scope"] = "optimized_timestamp_numeric_series"
        base["numeric_mode"] = config.get("numeric_mode", "")
        base["segment_records"] = config.get("segment_records", "")
        compression_scope = "optimized_time_series_batch"
        packet_size_role = "transfer_fragment_size_after_time_series_compression"
    else:
        raise ValueError(f"unsupported algorithm: {algorithm}")

    base.update(result)
    return base, compression_scope, packet_size_role


def summary_row(dataset, packet_size):
    return {
        "dataset": dataset.dataset_id,
        "source_files": ";".join(dataset.source_files),
        "encoding": dataset.encoding,
        "kind": dataset.kind,
        "compression_scope": "best_current_algorithm_config",
        "original_size_bytes": dataset.raw_size_bytes,
        "original_size_MB": dataset.raw_size_bytes / (1024 * 1024),
        "record_count": len(dataset.records),
        "packet_size": packet_size,
        "packet_size_role": "transfer_fragment_size_after_best_compression",
        "original_transfer_packet_count": ceil_div(dataset.raw_size_bytes, packet_size),
        "compression_unit_count": "algorithm_dependent",
    }


def build_scenario_end_to_end_rows(measurement_rows, scenario_keys):
    all_rows = build_end_to_end_rows(measurement_rows, sorted({key[3] for key in scenario_keys}))
    selected_rows = []
    for row in all_rows:
        key = (
            row["dataset"],
            row["algorithm"],
            int(float(row["packet_size"])),
            float(row["bandwidth_mbps"]),
            int(float(row["repeat"])),
            config_signature(row),
        )
        if key in scenario_keys:
            selected_rows.append(row)
    return selected_rows


def write_selected_config_rows(path, scenarios):
    rows = []
    for scenario in sorted(
        scenarios,
        key=lambda item: (item["dataset"], item["algorithm"], item["packet_size"], item["bandwidth_mbps"]),
    ):
        row = {
            "dataset": scenario["dataset"],
            "algorithm": scenario["algorithm"],
            "packet_size": scenario["packet_size"],
            "bandwidth_mbps": scenario["bandwidth_mbps"],
            "optimization_source": scenario["optimization_source"],
        }
        row.update(scenario["config"])
        rows.append(row)
    fields = [
        "dataset",
        "algorithm",
        "packet_size",
        "bandwidth_mbps",
        "optimization_source",
        "row_group_size",
        "use_dictionary",
        "zstd_level",
        "numeric_mode",
        "segment_records",
    ]
    write_csv(path, normalized_rows(rows), fields)


def main():
    parser = argparse.ArgumentParser(description="Run current best ocean compression configurations.")
    parser.add_argument("--input-dir", default=str(OCEAN_DATA))
    parser.add_argument(
        "--output-dir",
        default=str(OCEAN_ROOT / "runs" / "文本压缩" / "compression_experiment_best_current_cpu100"),
    )
    parser.add_argument("--config-csv", default=str(DEFAULT_CONFIG_CSV))
    parser.add_argument("--datasets", default="")
    parser.add_argument("--algorithms", default=",".join(ALGORITHMS))
    parser.add_argument("--packet-sizes", default=",".join(str(item) for item in DEFAULT_PACKET_SIZES))
    parser.add_argument("--bandwidths-mbps", default=",".join(str(item) for item in DEFAULT_BANDWIDTHS_MBPS))
    parser.add_argument("--cpu-limit-label", default="100")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--native-codec-bin", default=str(NATIVE_CODEC_BIN))
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

    scenarios = load_config_scenarios(Path(args.config_csv), datasets, algorithms, packet_sizes, bandwidths)
    scenarios_by_repeat = []
    for repeat in range(1, args.repeats + 1):
        for scenario in scenarios:
            scenario_copy = dict(scenario)
            scenario_copy["repeat"] = repeat
            scenarios_by_repeat.append(scenario_copy)

    dataset_by_id = {dataset.dataset_id: dataset for dataset in datasets}
    unique_runs = {}
    for scenario in scenarios_by_repeat:
        signature = config_signature(scenario["config"])
        key = (
            scenario["dataset"],
            scenario["algorithm"],
            scenario["repeat"],
            signature,
            scenario["optimization_source"],
        )
        unique_runs.setdefault(key, scenario)

    measurement_rows = []
    measurement_by_key = {}
    for index, (key, scenario) in enumerate(sorted(unique_runs.items()), start=1):
        dataset_id, algorithm, repeat, signature, optimization_source = key
        dataset = dataset_by_id[dataset_id]
        print(
            f"[{index}/{len(unique_runs)}] {dataset_id} {algorithm} "
            f"repeat={repeat} config={signature}"
        )
        base_row, compression_scope, packet_size_role = run_unique_measurement(
            dataset,
            algorithm,
            scenario["config"],
            args.cpu_limit_label,
            repeat,
            optimization_source,
            args.native_codec_bin,
        )
        for packet_size in sorted(
            {item["packet_size"] for item in scenarios_by_repeat if item["dataset"] == dataset_id and item["algorithm"] == algorithm}
        ):
            row = add_transfer_fields(base_row, packet_size, compression_scope, packet_size_role)
            measurement_rows.append(row)
            measurement_by_key[(dataset_id, algorithm, repeat, packet_size, signature)] = row

    scenario_keys = set()
    for scenario in scenarios_by_repeat:
        signature = config_signature(scenario["config"])
        key = (
            scenario["dataset"],
            scenario["algorithm"],
            scenario["packet_size"],
            scenario["bandwidth_mbps"],
            scenario["repeat"],
            signature,
        )
        if (scenario["dataset"], scenario["algorithm"], scenario["repeat"], scenario["packet_size"], signature) in measurement_by_key:
            scenario_keys.add(key)

    end_to_end_rows = build_scenario_end_to_end_rows(measurement_rows, scenario_keys)
    best_rows = build_best_rows(end_to_end_rows)
    summary_rows = [summary_row(dataset, packet_size) for dataset in datasets for packet_size in packet_sizes]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "packet_summary.csv", normalized_rows(summary_rows), SUMMARY_FIELDS)
    write_csv(output_dir / "compression_measurements.csv", normalized_rows(measurement_rows), MEASUREMENT_FIELDS)
    end_to_end_fields = MEASUREMENT_FIELDS + [
        "bandwidth_mbps",
        "T_transfer_ms",
        "T_direct_ms",
        "T_total_ms",
        "latency_reduction_pct",
    ]
    write_csv(output_dir / "end_to_end_results.csv", normalized_rows(end_to_end_rows), end_to_end_fields)
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
    write_csv(output_dir / "best_algorithm_by_scenario.csv", normalized_rows(best_rows), best_fields)
    write_selected_config_rows(output_dir / "selected_best_configs.csv", scenarios)
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
