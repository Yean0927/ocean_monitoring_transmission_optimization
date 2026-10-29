#!/usr/bin/env python3
"""Run the integrated three-module ablation on the current ns-3 cache model.

Modules:
1. XGBoost adaptive protocol selection from phase 1.
2. Best whole-file compression at 2 Mbps on the unlimited-CPU host profile.
3. 50 MB Priority-MaxF packet/chunk cache from phase 3.

The packet-cache ns-3 program uses UDP. To keep the existing cache and link
loss model unchanged, protocol selection is injected as an effective service
capacity coefficient. The coefficients are measured phase-1 selected
throughput divided by the phase-1 oracle throughput. Compression is injected
as a long-run output-rate reduction; it does not claim record-level ratios.
"""

from __future__ import annotations

import csv
import subprocess
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter

from PIL import Image


HERE = Path(__file__).resolve().parent
NS3_MAIN = HERE.parent
CACHE_EXAM = NS3_MAIN.parent
WORKSPACE = CACHE_EXAM.parent
NS3_ROOT = NS3_MAIN / ".tooling" / "ns-allinone-3.42" / "ns-3.42"
NS3_BINARY = NS3_ROOT / "build" / "scratch" / "ns3.42-packet-cache-priority-optimized"
SOURCE_LINK = CACHE_EXAM / "dynamic-link-config" / "dynamic-link-fluctuation.csv"
RESULT_DIR = NS3_MAIN / "results" / "integrated-ablation"
MODEL_METRICS = WORKSPACE / "海洋实验同步包" / "01_自适应协议选择" / "sample_results" / "model_results" / "model-metrics.csv"
TEXT_BEST = WORKSPACE / "海洋实验同步包" / "02_文本压缩算法选择" / "sample_results" / "compression_experiment_CD_optimized_cpu100" / "best_algorithm_by_scenario.csv"
TEXT_END_TO_END = WORKSPACE / "海洋实验同步包" / "02_文本压缩算法选择" / "sample_results" / "compression_experiment_CD_optimized_cpu100" / "end_to_end_results.csv"

STREAMS = ("D1", "D2", "D3", "D4", "V1", "I1")
RAW_RATES_MBPS = (0.000050665, 0.000028665, 0.051200, 0.000069400, 1.567000, 2.069720)
RECORD_SIZES = (76, 43, 128, 1041, 195875, 258715)
PACKET_SIZES = (76, 43, 128, 1041, 1472, 1472)
SEED = 31

# Host-16C, 2 Mbps per-file decisions in the stage-2 video report. Compression
# ratios come from 视频压缩.md. The two Host-16C 2 Mbps per-file latency
# reduction tables use the same S1/S2 choices. Their difference recovers the
# FFmpeg decode-to-null time, to the precision of the rounded report values.
VIDEO_RATIO = {
    "2019-05-30_18.50.28.mkv": 0.142,
    "3f2b041a2f5cf63ddc2e449fa7e3fd80.mp4": 0.313,
    "5fdbdd4dd7b628c0986de9028e8be48a.mp4": 0.314,
    "48290d122823a5cf9af2a146ba3d238b.mp4": 0.208,
    "4a3b00dd39998a85cb1db439bf0bbe93.mp4": 0.139,
    "ba5cd3bd2090f260c1810d600604f038.mp4": 0.278,
    "705ccbb00cfbaab61780706633e3c7ce.mp4": 0.094,
    "5cf7af68d381d7cb80e5567444e894c2.mp4": 0.112,
    "4412e5bfafeaa07161d2082422e349e1.mp4": 0.114,
}
VIDEO_LATENCY_REDUCTION = {
    "2019-05-30_18.50.28.mkv": 0.0880,
    "3f2b041a2f5cf63ddc2e449fa7e3fd80.mp4": 0.4865,
    "5fdbdd4dd7b628c0986de9028e8be48a.mp4": 0.4999,
    "48290d122823a5cf9af2a146ba3d238b.mp4": 0.7223,
    "4a3b00dd39998a85cb1db439bf0bbe93.mp4": 0.8011,
    "ba5cd3bd2090f260c1810d600604f038.mp4": 0.6190,
    "705ccbb00cfbaab61780706633e3c7ce.mp4": 0.8397,
    "5cf7af68d381d7cb80e5567444e894c2.mp4": 0.8194,
    "4412e5bfafeaa07161d2082422e349e1.mp4": 0.8486,
}
VIDEO_LATENCY_REDUCTION_WITH_DECODE = {
    "2019-05-30_18.50.28.mkv": 0.0044,
    "3f2b041a2f5cf63ddc2e449fa7e3fd80.mp4": 0.4683,
    "5fdbdd4dd7b628c0986de9028e8be48a.mp4": 0.4830,
    "48290d122823a5cf9af2a146ba3d238b.mp4": 0.7107,
    "4a3b00dd39998a85cb1db439bf0bbe93.mp4": 0.7901,
    "ba5cd3bd2090f260c1810d600604f038.mp4": 0.6058,
    "705ccbb00cfbaab61780706633e3c7ce.mp4": 0.8246,
    "5cf7af68d381d7cb80e5567444e894c2.mp4": 0.8040,
    "4412e5bfafeaa07161d2082422e349e1.mp4": 0.8326,
}
IMAGE_RATIO = 20644 / 258715  # nine-image median, JPEG Q75 optimize baseline
IMAGE_COMPRESSION_SECONDS_PER_100MB = 0.3017080612  # current-host 9-image median-cycle benchmark


@dataclass(frozen=True)
class Variant:
    variant_id: str
    description: str
    adaptive_protocol: bool
    compression: bool
    cache: bool


VARIANTS = (
    Variant("FULL", "自适应协议 + 最优压缩 + Priority-MaxF", True, True, True),
    Variant("WO_PROTOCOL", "静态 TCP CUBIC + 最优压缩 + Priority-MaxF", False, True, True),
    Variant("WO_COMPRESSION", "自适应协议 + 不压缩 + Priority-MaxF", True, False, True),
    Variant("WO_CACHE", "自适应协议 + 最优压缩 + No-Cache", True, True, False),
    Variant("BASELINE", "静态 TCP CUBIC + 不压缩 + No-Cache", False, False, False),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def protocol_factors() -> tuple[float, float, dict[str, float]]:
    rows = {row["model"]: row for row in read_csv(MODEL_METRICS)}
    adaptive = rows["XGBoost"]
    static = rows["Static-TCP_CUBIC"]
    oracle = float(adaptive["avg_oracle_mbps"])
    adaptive_factor = float(adaptive["avg_selected_mbps"]) / oracle
    static_factor = float(static["avg_selected_mbps"]) / oracle
    details = {
        "xgboost_selected_mbps": float(adaptive["avg_selected_mbps"]),
        "tcp_cubic_selected_mbps": float(static["avg_selected_mbps"]),
        "oracle_mbps": oracle,
        "adaptive_factor": adaptive_factor,
        "static_factor": static_factor,
    }
    return adaptive_factor, static_factor, details


def image_decode_seconds_per_100mb() -> float:
    """Measure JPEG Q75 decode-to-pixels on the same nine source images."""
    image_dir = WORKSPACE / "实验数据" / "图片文件"
    times_per_100mb = []
    benchmark_rows = []
    for path in sorted(image_dir.glob("*.png")):
        with Image.open(path) as source:
            encoded = BytesIO()
            source.convert("RGB").save(encoded, format="JPEG", quality=75, optimize=True)
        payload = encoded.getvalue()
        samples = []
        for _ in range(30):
            start = perf_counter()
            with Image.open(BytesIO(payload)) as decoded:
                decoded.load()
            samples.append(perf_counter() - start)
        raw_size = path.stat().st_size
        seconds_per_100mb = median(samples) * 100_000_000.0 / raw_size
        times_per_100mb.append(seconds_per_100mb)
        benchmark_rows.append({
            "file": path.name,
            "raw_bytes": raw_size,
            "jpeg_q75_bytes": len(payload),
            "repeat_count": len(samples),
            "median_decode_seconds": median(samples),
            "decode_seconds_per_100mb": seconds_per_100mb,
        })
    if len(times_per_100mb) != 9:
        raise ValueError(f"expected 9 image samples, found {len(times_per_100mb)}")
    write_csv(RESULT_DIR / "image-decode-benchmark.csv", benchmark_rows)
    return median(times_per_100mb)


def compression_specs() -> tuple[tuple[float, ...], tuple[str, ...], tuple[float, ...], tuple[float, ...]]:
    text_rows = []
    for row in read_csv(TEXT_BEST):
        if float(row["bandwidth_mbps"]) == 2.0 and int(row["packet_size"]) == 4096 and int(row["cpu_limit"]) == 100:
            text_rows.append(row)
    by_dataset = {row["dataset"]: row for row in text_rows}
    dataset_order = ("D1_big_buoy_weather", "D2_weather_utf16", "D3_wave_sensor", "D4_ocean_current_log")
    text_ratios = tuple(float(by_dataset[name]["best_compression_ratio"]) for name in dataset_order)
    text_algorithms = tuple(by_dataset[name]["best_algorithm"] for name in dataset_order)

    end_rows = read_csv(TEXT_END_TO_END)
    text_seconds_per_100mb = []
    text_decode_seconds_per_100mb = []
    for dataset, algorithm in zip(dataset_order, text_algorithms):
        row = next(
            row for row in end_rows
            if row["dataset"] == dataset
            and row["algorithm"] == algorithm
            and float(row["bandwidth_mbps"]) == 2.0
            and int(row["packet_size"]) == 4096
            and int(row["cpu_limit"]) == 100
        )
        raw_mb = float(row["original_size_bytes"]) / 1_000_000.0
        text_seconds_per_100mb.append(float(row["compression_time_ms"]) / 1000.0 / raw_mb * 100.0)
        text_decode_seconds_per_100mb.append(float(row["decompression_time_ms"]) / 1000.0 / raw_mb * 100.0)

    video_dir = WORKSPACE / "实验数据" / "视频样本"
    raw_total = 0
    compressed_total = 0.0
    video_encode_seconds = 0.0
    video_decode_seconds = 0.0
    video_processing_rows = []
    for name, ratio in VIDEO_RATIO.items():
        size = (video_dir / name).stat().st_size
        raw_total += size
        compressed_total += size * ratio
        direct_seconds = size * 8.0 / 2_000_000.0
        total_seconds = direct_seconds * (1.0 - VIDEO_LATENCY_REDUCTION[name])
        transfer_seconds = direct_seconds * ratio
        video_encode_seconds += max(0.0, total_seconds - transfer_seconds)
        decode_seconds = direct_seconds * (VIDEO_LATENCY_REDUCTION[name] - VIDEO_LATENCY_REDUCTION_WITH_DECODE[name])
        if decode_seconds < 0:
            raise ValueError(f"decode-inclusive latency is shorter for {name}")
        video_decode_seconds += decode_seconds
        video_processing_rows.append({
            "file": name,
            "raw_bytes": size,
            "compression_ratio": ratio,
            "latency_reduction_without_decode": VIDEO_LATENCY_REDUCTION[name],
            "latency_reduction_with_decode": VIDEO_LATENCY_REDUCTION_WITH_DECODE[name],
            "encode_seconds_estimated": max(0.0, total_seconds - transfer_seconds),
            "decode_seconds_estimated": decode_seconds,
        })
    write_csv(RESULT_DIR / "video-processing-times.csv", video_processing_rows)
    video_ratio = compressed_total / raw_total
    video_seconds_per_100mb = video_encode_seconds / (raw_total / 1_000_000.0) * 100.0
    video_decode_seconds_per_100mb = video_decode_seconds / (raw_total / 1_000_000.0) * 100.0
    ratios = text_ratios + (video_ratio, IMAGE_RATIO)
    algorithms = text_algorithms + ("S1/S2按文件加权", "JPEG-Q75")
    compression_seconds = tuple(text_seconds_per_100mb) + (video_seconds_per_100mb, IMAGE_COMPRESSION_SECONDS_PER_100MB)
    decompression_seconds = tuple(text_decode_seconds_per_100mb) + (video_decode_seconds_per_100mb, image_decode_seconds_per_100mb())
    return ratios, algorithms, compression_seconds, decompression_seconds


def write_effective_link(path: Path, factor: float) -> None:
    rows = read_csv(SOURCE_LINK)
    fields = list(rows[0])
    for row in rows:
        row["capacity_mbps"] = f"{float(row['capacity_mbps']) * factor:.9f}"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_variant(variant: Variant, ratios: tuple[float, ...], adaptive_factor: float, static_factor: float) -> Path:
    factor = adaptive_factor if variant.adaptive_protocol else static_factor
    link_path = RESULT_DIR / ("link-adaptive-xgboost.csv" if variant.adaptive_protocol else "link-static-tcp-cubic.csv")
    if not link_path.exists():
        write_effective_link(link_path, factor)
    rates = tuple(rate * ratio for rate, ratio in zip(RAW_RATES_MBPS, ratios)) if variant.compression else RAW_RATES_MBPS
    output = RESULT_DIR / f"{variant.variant_id}.csv"
    strategy = "Priority-MaxF" if variant.cache else "No-Cache"
    command = [
        str(NS3_BINARY),
        f"--linkCsv={link_path}",
        f"--output={output}",
        f"--stateId={variant.variant_id}",
        f"--strategy={strategy}",
        "--startMin=0.0",
        "--endMin=60.0",
        f"--seed={SEED}",
        "--linkUpdateSeconds=30",
        "--recordSizes=" + ",".join(str(value) for value in RECORD_SIZES),
        "--packetSizes=" + ",".join(str(value) for value in PACKET_SIZES),
        "--ratesMbps=" + ",".join(f"{value:.12f}" for value in rates),
    ]
    subprocess.run(command, cwd=NS3_ROOT, check=True)
    return output


def summarize_variant(variant: Variant, output: Path, ratios: tuple[float, ...], compression_seconds_per_100mb: tuple[float, ...], decompression_seconds_per_100mb: tuple[float, ...], protocol_factor: float):
    rows = read_csv(output)
    stream_rows = {row["stream_id"]: row for row in rows if row["record_type"] == "stream"}
    converted = []
    for index, stream in enumerate(STREAMS):
        row = stream_rows[stream]
        ratio = ratios[index] if variant.compression else 1.0
        values = {field: float(row[field]) / ratio for field in (
            "produced_mb", "cache_evicted_mb", "source_dropped_mb", "sent_mb", "delivered_mb", "link_dropped_mb", "pending_mb"
        )}
        total_loss = values["cache_evicted_mb"] + values["source_dropped_mb"] + values["link_dropped_mb"]
        stream_goodput = values["delivered_mb"] * 8.0 / 3600.0
        network_time_per_100mb = 800.0 / stream_goodput if stream_goodput else float("inf")
        compression_time_per_100mb = compression_seconds_per_100mb[index] if variant.compression else 0.0
        decompression_time_per_100mb = decompression_seconds_per_100mb[index] if variant.compression else 0.0
        converted.append({
            "variant": variant.variant_id,
            "description": variant.description,
            "stream": stream,
            "compression_algorithm": "none" if not variant.compression else COMPRESSION_ALGORITHMS[index],
            "compression_ratio": ratio,
            **values,
            "total_loss_mb": total_loss,
            "loss_rate_pct": 100.0 * total_loss / values["produced_mb"] if values["produced_mb"] else 0.0,
            "delivery_rate_pct": 100.0 * values["delivered_mb"] / values["produced_mb"] if values["produced_mb"] else 0.0,
            "network_time_per_100mb_s": network_time_per_100mb,
            "compression_time_per_100mb_s": compression_time_per_100mb,
            "decompression_time_per_100mb_s": decompression_time_per_100mb,
            "end_to_end_time_per_100mb_s": network_time_per_100mb + compression_time_per_100mb + decompression_time_per_100mb,
        })
    totals = {field: sum(row[field] for row in converted) for field in (
        "produced_mb", "cache_evicted_mb", "source_dropped_mb", "sent_mb", "delivered_mb", "link_dropped_mb", "pending_mb", "total_loss_mb"
    )}
    raw_goodput = totals["delivered_mb"] * 8.0 / 3600.0
    weighted_compression_time = 0.0
    weighted_decompression_time = 0.0
    if variant.compression:
        weighted_compression_time = sum(rate * seconds for rate, seconds in zip(RAW_RATES_MBPS, compression_seconds_per_100mb)) / sum(RAW_RATES_MBPS)
        weighted_decompression_time = sum(rate * seconds for rate, seconds in zip(RAW_RATES_MBPS, decompression_seconds_per_100mb)) / sum(RAW_RATES_MBPS)
    network_time_per_100mb = 800.0 / raw_goodput if raw_goodput else float("inf")
    summary = {
        "variant": variant.variant_id,
        "description": variant.description,
        "adaptive_protocol": int(variant.adaptive_protocol),
        "compression": int(variant.compression),
        "cache": int(variant.cache),
        "cache_strategy": "Priority-MaxF" if variant.cache else "No-Cache",
        "protocol_capacity_factor": protocol_factor,
        "compressed_offered_load_mbps": sum(rate * ratio for rate, ratio in zip(RAW_RATES_MBPS, ratios)) if variant.compression else sum(RAW_RATES_MBPS),
        **totals,
        "total_loss_rate_pct": 100.0 * totals["total_loss_mb"] / totals["produced_mb"],
        "delivery_rate_pct": 100.0 * totals["delivered_mb"] / totals["produced_mb"],
        "pending_rate_pct": 100.0 * totals["pending_mb"] / totals["produced_mb"],
        "raw_equivalent_goodput_mbps": raw_goodput,
        "network_time_per_100mb_s": network_time_per_100mb,
        "compression_time_per_100mb_s": weighted_compression_time,
        "decompression_time_per_100mb_s": weighted_decompression_time,
        "end_to_end_time_per_100mb_s": network_time_per_100mb + weighted_compression_time + weighted_decompression_time,
        "estimated_end_to_end_time_for_generated_data_s": (network_time_per_100mb + weighted_compression_time + weighted_decompression_time) * totals["produced_mb"] / 100.0,
    }
    balance = totals["produced_mb"] - totals["cache_evicted_mb"] - totals["source_dropped_mb"] - totals["link_dropped_mb"] - totals["delivered_mb"] - totals["pending_mb"]
    if abs(balance) > 1e-4:
        raise RuntimeError(f"raw-equivalent accounting error for {variant.variant_id}: {balance}")
    return summary, converted


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(summaries, streams, ratios, algorithms, compression_seconds_per_100mb, decompression_seconds_per_100mb, protocol_details):
    full = next(row for row in summaries if row["variant"] == "FULL")
    by_variant = {row["variant"]: row for row in summaries}
    lines = [
        "# 自适应协议、压缩算法与 Priority-MaxF 缓存联合消融实验",
        "",
        "## 消融组",
        "",
        "| 组别 | 自适应协议 | 压缩 | 缓存 |",
        "|---|---:|---:|---|",
    ]
    for row in summaries:
        lines.append(f"| {row['variant']} | {'XGBoost' if row['adaptive_protocol'] else '静态 TCP CUBIC'} | {'开启' if row['compression'] else '关闭'} | {row['cache_strategy']} |")
    lines += [
        "",
        "## 固定参数",
        "",
        f"- 链路：阶段三当前 60 min 动态链路 CSV，物理带宽基准 2 Mbps，30 s 更新一次，随机种子 {SEED}。",
        "- 缓存：50 MB；启用缓存时只使用 Priority-MaxF。",
        f"- 协议系数：XGBoost={protocol_details['adaptive_factor']:.6f}，静态 TCP CUBIC={protocol_details['static_factor']:.6f}。系数定义为阶段一 `selected throughput / oracle throughput`。XGBoost 按阶段一最高 Macro F1 选定。",
        "- 压缩：D1-D4 使用 Host-16C、2 Mbps、CPU=100 的最优算法；V1 使用九个视频在 2 Mbps 下的 S1/S2 按原始字节加权比例；I1 使用九张图片中位数的 JPEG Q75 基线。",
        "- 公平比较使用原始数据等价值：ns-3 输出的压缩字节按各流压缩比换回原始 MB，再计算送达率、丢失率与成功送达 100 MB 原始数据的等效网络时间。",
        "- 端到端时间估算取 `T_compress + T_transfer + T_decompress`。视频的 `T_decompress` 是 FFmpeg decode-to-null 完整解码校验；文本使用阶段二 CSV 实测解压时间；图片使用当前主机 JPEG-Q75 解码到像素的九图中位耗时。三项按串行相加，结果是每 100 MB 原始数据等价值的估算时间，并非单个文件的实测完成时延。",
        "- 视频编码与解码时间由 Host-16C 2 Mbps 的逐文件时延缩短率还原：未计解码数据见 `edge-text-compression-experiment-report.md`，计入解码数据见 `edge-text-compression-experiment-report-with-decode.md`。两表百分数保留两位小数，故还原的处理时间为近似值；两表的最优 S1/S2 选择在 2 Mbps 下相同。",
        "- 逐文件还原值保存在 `results/integrated-ablation/video-processing-times.csv`；图片解码补测值保存在 `results/integrated-ablation/image-decode-benchmark.csv`，每张图片重复 30 次并取其中位耗时。",
        "- 无压缩组沿用阶段二 S0 直传口径，压缩和解压时间均为 0；图片与视频的解码计时平台不同，视频来自 Host-16C 测量、图片来自当前主机补测。",
        "- 等效网络时间按 `800 Mbit / 原始数据等价 goodput` 计算，包含本轮链路丢失和缓存调度对有效送达速率的影响；它不是单个 packet 的传播时延。",
        "",
        "## 压缩配置",
        "",
        "| 流 | 算法 | 压缩比 | 原始生成速率 Mbps | 压缩后速率 Mbps | 压缩时间 s/100MB | 解压/解码 s/100MB |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for stream, algorithm, ratio, rate, compression_seconds, decompression_seconds in zip(STREAMS, algorithms, ratios, RAW_RATES_MBPS, compression_seconds_per_100mb, decompression_seconds_per_100mb):
        lines.append(f"| {stream} | {algorithm} | {ratio:.6f} | {rate:.6f} | {rate * ratio:.6f} | {compression_seconds:.2f} | {decompression_seconds:.2f} |")
    lines += [
        "",
        "## 总体结果",
        "",
        "| 组别 | 送达率 | 总丢失率 | goodput Mbps | 成功送达网络时间 s/100MB | 压缩 s/100MB | 解压/解码 s/100MB | 端到端 s/100MB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(f"| {row['variant']} | {row['delivery_rate_pct']:.2f}% | {row['total_loss_rate_pct']:.2f}% | {row['raw_equivalent_goodput_mbps']:.3f} | {row['network_time_per_100mb_s']:.2f} | {row['compression_time_per_100mb_s']:.2f} | {row['decompression_time_per_100mb_s']:.2f} | {row['end_to_end_time_per_100mb_s']:.2f} |")
    lines += [
        "",
        "## 模块贡献（从 FULL 去除一个模块）",
        "",
        f"- 去掉自适应协议：送达率变化 {by_variant['WO_PROTOCOL']['delivery_rate_pct'] - full['delivery_rate_pct']:+.2f} 个百分点。",
        f"- 去掉压缩：送达率变化 {by_variant['WO_COMPRESSION']['delivery_rate_pct'] - full['delivery_rate_pct']:+.2f} 个百分点。",
        f"- 去掉 Priority-MaxF：送达率变化 {by_variant['WO_CACHE']['delivery_rate_pct'] - full['delivery_rate_pct']:+.2f} 个百分点。",
        f"- 完整方案端到端时间为 {full['end_to_end_time_per_100mb_s']:.2f} s/100MB；全关闭基线为 {by_variant['BASELINE']['end_to_end_time_per_100mb_s']:.2f} s/100MB。",
        "",
        "## 各数据流丢失率",
        "",
        "| 组别 | D1 | D2 | D3 | D4 | V1 | I1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    stream_map = {(row["variant"], row["stream"]): row for row in streams}
    for variant in VARIANTS:
        values = [stream_map[(variant.variant_id, stream)]["loss_rate_pct"] for stream in STREAMS]
        lines.append("| {} | {} |".format(variant.variant_id, " | ".join(f"{value:.2f}%" for value in values)))
    lines += [
        "",
        "## 边界说明",
        "",
        "协议选择模块没有被改写成 UDP 协议。现有 packet-cache ns-3 程序继续负责 packet/chunk 缓存、动态链路和链路丢包；阶段一实测的协议选择效率只用于缩放可用服务带宽。这个联合消融属于模块输出级集成，避免把 UDP 结果写成真实 TCP/QUIC 栈结果。",
        "",
    ]
    (HERE / "integrated-ablation-report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    global COMPRESSION_ALGORITHMS
    if not NS3_BINARY.exists():
        raise FileNotFoundError(f"ns-3 binary not found: {NS3_BINARY}")
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    adaptive_factor, static_factor, protocol_details = protocol_factors()
    ratios, COMPRESSION_ALGORITHMS, compression_seconds_per_100mb, decompression_seconds_per_100mb = compression_specs()
    write_effective_link(RESULT_DIR / "link-adaptive-xgboost.csv", adaptive_factor)
    write_effective_link(RESULT_DIR / "link-static-tcp-cubic.csv", static_factor)
    summaries = []
    all_streams = []
    for variant in VARIANTS:
        print(f"Running {variant.variant_id}...")
        output = run_variant(variant, ratios, adaptive_factor, static_factor)
        factor = adaptive_factor if variant.adaptive_protocol else static_factor
        summary, streams = summarize_variant(variant, output, ratios, compression_seconds_per_100mb, decompression_seconds_per_100mb, factor)
        summaries.append(summary)
        all_streams.extend(streams)
    write_csv(RESULT_DIR / "ablation-summary.csv", summaries)
    write_csv(RESULT_DIR / "ablation-by-stream.csv", all_streams)
    write_report(summaries, all_streams, ratios, COMPRESSION_ALGORITHMS, compression_seconds_per_100mb, decompression_seconds_per_100mb, protocol_details)
    print(f"Wrote {HERE / 'integrated-ablation-report.md'}")
    print(f"Wrote {RESULT_DIR / 'ablation-summary.csv'}")
    print(f"Wrote {RESULT_DIR / 'ablation-by-stream.csv'}")


if __name__ == "__main__":
    main()
