#!/usr/bin/env python3
"""Scan FIFO cache capacities with the packet-level ns-3 experiment.

The capacity values are deliberately generated from one fixed increment. A
capacity is considered sufficient when the continuous 0--60 minute run has
zero application-cache evictions and zero source-side drops. A zero-capacity
cache attempts immediate transmission without buffering. Link loss is reported
separately because it is not a cache-capacity effect in this UDP model.
"""

from __future__ import annotations

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/图片文件'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / '原始实验留档/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()


import argparse
import csv
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LINK_CSV = Path(os.environ.get("OCEAN_LINK_CSV", str(OCEAN_ROOT / "03_缓存机制/链路状态/dynamic-link-fluctuation.csv"))).expanduser().resolve()
NS3_ROOT = OCEAN_NS3
NS3_BINARY = Path(os.environ.get("OCEAN_CACHE_BINARY", str(NS3_ROOT / "build" / "scratch" / "ns3.42-packet-cache-priority-optimized")))
OUTPUT_DIR = OCEAN_ROOT / "runs" / "缓存容量实验"
RESULT_CSV = OUTPUT_DIR / "fifo-cache-capacity-scan.csv"
REPORT_MD = OUTPUT_DIR / "fifo-cache-capacity-scan.md"

IMAGE_MEDIAN_BYTES = 258715
IMAGE_CAPTURE_INTERVAL_SECONDS = 5.0
VIDEO_MEDIAN_FILE_BYTES = 4354778
VIDEO_MEDIAN_RATE_BYTES_PER_SECOND = 208481.0
VIDEO_RECORD_PERIOD_SECONDS = VIDEO_MEDIAN_FILE_BYTES / VIDEO_MEDIAN_RATE_BYTES_PER_SECOND
RECORD_SIZES = (76, 43, 128, 1041, VIDEO_MEDIAN_FILE_BYTES, IMAGE_MEDIAN_BYTES)
PACKET_SIZES = (76, 43, 128, 1041, 1472, 1472)
RATES_MBPS = (0.000050665, 0.000028665, 0.051200, 0.000069400,
              VIDEO_MEDIAN_RATE_BYTES_PER_SECOND * 8.0 / 1_000_000.0,
              IMAGE_MEDIAN_BYTES * 8.0 / (IMAGE_CAPTURE_INTERVAL_SECONDS * 1_000_000.0))
SEED = 31
TOLERANCE_MB = 1e-9


def run_one(capacity_mb: float, output_path: Path) -> dict[str, str]:
    command = [
        str(NS3_BINARY),
        f"--linkCsv={LINK_CSV}",
        f"--output={output_path}",
        "--stateId=FULL",
        "--strategy=FIFO",
        "--startMin=0.0",
        "--endMin=60.0",
        f"--seed={SEED}",
        "--linkUpdateSeconds=30.0",
        f"--cacheCapacityMb={capacity_mb:g}",
        "--recordSizes=" + ",".join(map(str, RECORD_SIZES)),
        "--packetSizes=" + ",".join(map(str, PACKET_SIZES)),
        "--ratesMbps=" + ",".join(map(str, RATES_MBPS)),
    ]
    subprocess.run(command, cwd=NS3_ROOT, check=True)
    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    summary = next(row for row in rows if row["record_type"] == "summary")
    produced = float(summary["produced_mb"])
    cache_evicted = float(summary["cache_evicted_mb"])
    source_dropped = float(summary["source_dropped_mb"])
    link_dropped = float(summary["link_dropped_mb"])
    sent = float(summary["sent_mb"])
    delivered = float(summary["delivered_mb"])
    pending = float(summary["pending_mb"])
    accounting_error = produced - cache_evicted - float(summary["source_dropped_mb"]) \
        - (sent - delivered) - delivered - pending
    summary.update(
        {
            "capacity_mb": f"{capacity_mb:.9f}",
            "cache_evicted_mb": f"{cache_evicted:.9f}",
            "total_loss_mb": f"{cache_evicted + link_dropped:.9f}",
            "sufficient": "1" if cache_evicted + source_dropped <= TOLERANCE_MB else "0",
            "accounting_error_mb": f"{accounting_error:.9f}",
        }
    )
    return summary


def write_report(rows: list[dict[str, str]], step_mb: float) -> None:
    sufficient = next(row for row in rows if row["sufficient"] == "1")
    previous = rows[rows.index(sufficient) - 1] if rows.index(sufficient) else None
    zero_capacity = next(row for row in rows if float(row["capacity_mb"]) == 0.0)
    total_rate_mbps = sum(RATES_MBPS)
    theoretical_produced_mb = total_rate_mbps * 3600.0 / 8.0
    twenty_mb_rows = [
        row for row in rows
        if abs(float(row["capacity_mb"]) / 20.0 - round(float(row["capacity_mb"]) / 20.0)) < 1e-9
    ]
    lines = [
        "# FIFO 缓存容量统一粒度扫描",
        "",
        "本实验复用 packet-level 缓存报告中的连续 0–60 min ns-3 模型、30 s 链路状态更新、随机种子 31、六条数据流生成速率和 1472 B transport chunk 设置，仅将策略固定为 FIFO，并把缓存容量按统一粒度递增。",
        "",
        "## 数据生成参数",
        "",
        "本次 FIFO 缓存容量扫描使用六条数据流参数，数据流顺序统一为 `D1、D2、D3、D4、V1、I1`。其中 D1–D4 使用 packet-level 实验报告中提高 5 倍后的生成速率。V1 的生成速率取九个实际视频分别计算的‘文件大小÷时长’中位数，逻辑记录大小取九个完整视频文件大小的中位数；I1 沿用 packet-level 实验报告中的 5 s 图片生成周期。V1 和 I1 均在传输层切分为 1472 B chunk。表中的生成速率均指 payload 字节速率，不包含 UDP/IP 或链路协议首部。",
        "",
        "| 数据流 | 逻辑记录大小(B) | transport payload(B) | 记录/transport chunk 生成频率 | 数据生成速率(Mbps) |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| D1 大浮标气象数据 | 76 | 76 | 0.083333 Hz（12 s/次） | 0.000050665 |",
        "| D2 普通气象数据 | 43 | 43 | 0.083333 Hz（12 s/次） | 0.000028665 |",
        "| D3 波浪传感器数据 | 128 | 128 | 50 Hz（0.02 s/次） | 0.051200 |",
        "| D4 ADCP 海流数据 | 1041 | 1041 | 0.008333 Hz（120 s/次） | 0.000069400 |",
        f"| V1 海洋视频数据 | {VIDEO_MEDIAN_FILE_BYTES} | 1472 | 中位记录周期约 {VIDEO_RECORD_PERIOD_SECONDS:.2f} s；约 {VIDEO_MEDIAN_RATE_BYTES_PER_SECOND / 1472:.2f} Hz（chunk） | {RATES_MBPS[4]:.6f} |",
        f"| I1 图片数据 | {IMAGE_MEDIAN_BYTES} | 1472 | 0.2 Hz（记录）；约 35.2 Hz（chunk） | {RATES_MBPS[-1]:.6f} |",
        "",
        f"六条数据流的总 payload 生成速率为 **{total_rate_mbps:.9f} Mbps**，对应 60 min 理论产生量约为 **{theoretical_produced_mb:.9f} MB**；仿真输出的 `produced_mb = {float(sufficient['produced_mb']):.9f} MB`。V1 和 I1 的 chunks 在各自逻辑记录生成周期内均匀产生，最后一个 chunk 可小于 1472 B，但不改变对应数据流的总字节生成速率。",
        "",
        f"- 扫描粒度：{step_mb:g} MB（十进制，1 MB = 1,000,000 B）",
        f"- 判定条件：全程 `cache_evicted_mb = 0` 且 `source_dropped_mb = 0`；链路丢包单独统计",
        f"- 按该实验粒度得到的最小充足缓存：**{float(sufficient['capacity_mb']):g} MB**",
        f"- 该容量下：峰值缓存 {float(sufficient['peak_cache_mb']):.6f} MB，缓存淘汰 {float(sufficient['cache_evicted_mb']):.9f} MB",
        "",
        "## 临界区间",
        "",
    ]
    if previous:
        lines.append(f"前一个粒度点 {float(previous['capacity_mb']):g} MB 仍淘汰 {float(previous['cache_evicted_mb']):.6f} MB，因此实测临界容量位于 ({float(previous['capacity_mb']):g}, {float(sufficient['capacity_mb']):g}] MB；本报告不把临界点插值为实测值。")
    else:
        lines.append("扫描起点已满足无缓存淘汰。")
    lines += [
        "",
        "## 扫描结果",
        "",
        "下表列出缓存容量为 20 MB 整数倍的实测点；其他容量点仍保留在完整扫描 CSV 中。",
        "",
        "| 缓存容量(MB) | 总丢失量(MB) | 送达(MB) | 峰值缓存(MB) |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in twenty_mb_rows:
        lines.append(
            f"| {float(row['capacity_mb']):g} | {float(row['total_loss_mb']):.6f} | "
            f"{float(row['delivered_mb']):.6f} | {float(row['peak_cache_mb']):.6f} |"
        )
    lines += [
        "",
        f"说明：总丢失量 = 缓存淘汰量 + 链路丢失量。0 MB 时不暂存数据，生成后立即尝试发送；未能立即发送的数据记为缓存淘汰，该档缓存淘汰 {float(zero_capacity['cache_evicted_mb']):.6f} MB。判定缓存容量足够的条件为全程无缓存淘汰且无源端丢弃。",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    global OUTPUT_DIR, RESULT_CSV, REPORT_MD, LINK_CSV
    parser = argparse.ArgumentParser()
    parser.add_argument("--step-mb", type=float, default=10.0, help="Uniform capacity increment in decimal MB")
    parser.add_argument("--max-mb", type=float, default=400.0, help="Maximum capacity to scan")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Write new measurements here; formal reports are preserved")
    parser.add_argument("--link-csv", type=Path, default=LINK_CSV)
    args = parser.parse_args()
    OUTPUT_DIR = args.output_dir.expanduser().resolve()
    RESULT_CSV = OUTPUT_DIR / "fifo-cache-capacity-scan.csv"
    REPORT_MD = OUTPUT_DIR / "fifo-cache-capacity-scan.md"
    LINK_CSV = args.link_csv.expanduser().resolve()
    if args.step_mb <= 0 or args.max_mb < 0 or args.max_mb < args.step_mb:
        raise ValueError("require 0 < --step-mb <= --max-mb")
    if not NS3_BINARY.exists():
        raise FileNotFoundError(f"ns-3 binary not found: {NS3_BINARY}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUTPUT_DIR / f"raw-v1-{VIDEO_MEDIAN_FILE_BYTES}B-{VIDEO_MEDIAN_RATE_BYTES_PER_SECOND:.0f}Bps-i1-{IMAGE_MEDIAN_BYTES}B-{IMAGE_CAPTURE_INTERVAL_SECONDS:g}s"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    capacity = 0.0
    while capacity <= args.max_mb + TOLERANCE_MB:
        output_path = raw_dir / f"fifo-{capacity:g}MB.csv"
        row = run_one(capacity, output_path)
        rows.append(row)
        print(
            f"capacity={capacity:g} MB, peak={float(row['peak_cache_mb']):.6f} MB, "
            f"evicted={float(row['cache_evicted_mb']):.6f} MB, "
            f"pending={float(row['pending_mb']):.6f} MB"
        )
        if row["sufficient"] == "1":
            break
        capacity += args.step_mb

    if rows[-1]["sufficient"] != "1":
        raise RuntimeError(f"no sufficient cache found through {args.max_mb:g} MB")

    fields = [
        "capacity_mb", "produced_mb", "cache_evicted_mb", "total_loss_mb", "source_dropped_mb", "sent_mb",
        "delivered_mb", "link_dropped_mb", "pending_mb", "peak_cache_mb", "sufficient",
        "accounting_error_mb", "seed",
    ]
    with RESULT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    write_report(rows, args.step_mb)
    print(f"\nWrote {RESULT_CSV}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
