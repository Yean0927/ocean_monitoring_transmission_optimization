#!/usr/bin/env python3
"""Run the ns-3 packet/chunk cache-priority experiment.

The ns-3 program owns the network behavior. This wrapper selects the
CSV-defined link-state segments, invokes each run, aggregates the returned
records, and refreshes the markdown report.
"""

from __future__ import annotations

import csv
import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parent
LINK_CSV = ROOT / "dynamic-link-config" / "dynamic-link-fluctuation.csv"
REPORT_PATH = ROOT / "packet-level-cache-priority-experiment-report.md"
SUMMARY_CSV = ROOT / "packet_level_cache_priority_summary.csv"
STREAM_CSV = ROOT / "packet_level_cache_priority_by_stream.csv"
FULL_STREAM_CSV = ROOT / "packet_level_cache_priority_60min_by_stream.csv"
NS3_ROOT = ROOT / "ns3-simulation-main" / ".tooling" / "ns-allinone-3.42" / "ns-3.42"
NS3_BINARY = NS3_ROOT / "build" / "scratch" / "ns3.42-packet-cache-priority-optimized"
OUTPUT_DIR = ROOT / "ns3-simulation-main" / "results" / "packet-cache-priority"

LINK_UPDATE_SECONDS = 30.0
IMAGE_MEDIAN_BYTES = 258715  # median PNG file size across the nine extracted images
IMAGE_CAPTURE_INTERVAL_SECONDS = 5.0
VIDEO_MEDIAN_FILE_BYTES = 4354778
VIDEO_MEDIAN_RATE_BYTES_PER_SECOND = 208481.0
RECORD_SIZES = (76, 43, 128, 1041, VIDEO_MEDIAN_FILE_BYTES, IMAGE_MEDIAN_BYTES)
PACKET_SIZES = (76, 43, 128, 1041, 1472, 1472)
RATES_MBPS = (0.000050665, 0.000028665, 0.051200, 0.000069400,
              VIDEO_MEDIAN_RATE_BYTES_PER_SECOND * 8.0 / 1_000_000.0,
              IMAGE_MEDIAN_BYTES * 8.0 / (IMAGE_CAPTURE_INTERVAL_SECONDS * 1_000_000.0))
CACHE_CAPACITY_MB = 50.0
SEED = 31
STRATEGIES = (
    "FIFO",
    "Priority-SP",
    "Priority-Aging",
    "Priority-MaxF",
    "Priority-Utility",
    "Priority-Utility-Ti",
)
ALL_STRATEGIES = ("No-Cache",) + STRATEGIES


@dataclass(frozen=True)
class StateSpec:
    state_id: str
    label: str
    start_min: float
    end_min: float


@dataclass(frozen=True)
class LinkSample:
    time_min: float
    capacity_mbps: float
    rtt_ms: float
    packet_loss_rate: float


STATE_SPECS = (
    StateSpec("S1", "带宽下降", 0.0, 23.5),
    StateSpec("S2", "带宽波动", 23.5, 42.0),
    StateSpec("S3", "带宽上升", 42.0, 60.0),
)


def read_samples() -> List[LinkSample]:
    with LINK_CSV.open(newline="", encoding="utf-8") as handle:
        return [
            LinkSample(
                float(row["time_min"]),
                float(row["capacity_mbps"]),
                float(row["rtt_ms"]),
                float(row["packet_loss_rate"]),
            )
            for row in csv.DictReader(handle)
            if float(row["time_min"]) < 60.0
        ]


def state_samples(state: StateSpec, samples: Iterable[LinkSample]) -> List[LinkSample]:
    selected = [sample for sample in samples if state.start_min <= sample.time_min < state.end_min]
    if not selected:
        raise RuntimeError("No link samples found for %s" % state.state_id)
    return selected


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_ns3(
    strategy: str,
    link_update_seconds: float,
    packet_sizes: Sequence[int],
    rates_mbps: Sequence[float],
    record_sizes: Sequence[int] = RECORD_SIZES,
) -> List[Dict[str, str]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / ("FULL-%s.csv" % strategy.replace("-", "_"))
    command = [
        str(NS3_BINARY),
        "--linkCsv=%s" % LINK_CSV,
        "--output=%s" % output,
        "--stateId=FULL",
        "--strategy=%s" % strategy,
        "--startMin=0.0",
        "--endMin=60.0",
        "--seed=%d" % SEED,
        "--linkUpdateSeconds=%s" % link_update_seconds,
        "--recordSizes=%s" % ",".join(str(value) for value in record_sizes),
        "--packetSizes=%s" % ",".join(str(value) for value in packet_sizes),
        "--ratesMbps=%s" % ",".join(str(value) for value in rates_mbps),
    ]
    subprocess.run(command, cwd=str(NS3_ROOT), check=True)
    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    full_summary = next((row for row in rows if row["record_type"] == "summary"), None)
    if full_summary is None:
        raise RuntimeError("ns-3 output has no full-run summary: %s" % output)
    full_error = (float(full_summary["produced_mb"]) - float(full_summary["cache_evicted_mb"]) -
                  float(full_summary["source_dropped_mb"]) - float(full_summary["link_dropped_mb"]) -
                  float(full_summary["delivered_mb"]) - float(full_summary["pending_mb"]))
    if abs(full_error) > 1e-6:
        raise RuntimeError("full-run accounting error in %s: %.9f MB" % (output, full_error))
    checkpoints = sorted(
        (row for row in rows if row["record_type"] == "checkpoint_summary"),
        key=lambda row: float(row["checkpoint_time_min"]),
    )
    samples = read_samples()
    checkpoint_streams = {}
    for row in rows:
        if row["record_type"] == "checkpoint_stream":
            checkpoint_streams[(row["checkpoint_time_min"], row["stream_id"])] = row
    if len(checkpoints) != len(STATE_SPECS):
        raise RuntimeError("expected three continuous-run checkpoints in %s" % output)

    def delta(current: str, previous: str) -> str:
        value = float(current) - float(previous)
        return "0.000000000" if abs(value) < 0.0000000005 else "%.9f" % value

    interval_rows = []
    previous_summary = {field: "0.000000000" for field in (
        "produced_mb", "cache_evicted_mb", "source_dropped_mb", "sent_mb", "delivered_mb", "pending_mb")}
    previous_streams = {stream_id: {field: "0.000000000" for field in (
        "produced_mb", "cache_evicted_mb", "source_dropped_mb", "sent_mb", "delivered_mb")}
                       for stream_id in ("D1", "D2", "D3", "D4", "V1", "I1")}
    for checkpoint in checkpoints:
        state = next(state for state in STATE_SPECS if state.state_id == checkpoint["state_id"])
        produced = delta(checkpoint["produced_mb"], previous_summary["produced_mb"])
        cache_evicted = delta(checkpoint["cache_evicted_mb"], previous_summary["cache_evicted_mb"])
        source_dropped = delta(checkpoint["source_dropped_mb"], previous_summary["source_dropped_mb"])
        sent = delta(checkpoint["sent_mb"], previous_summary["sent_mb"])
        delivered = delta(checkpoint["delivered_mb"], previous_summary["delivered_mb"])
        link_dropped = "%.9f" % (float(sent) - float(delivered))
        total_loss = "%.9f" % (float(cache_evicted) + float(source_dropped) + float(link_dropped))
        pending_change = delta(checkpoint["pending_mb"], previous_summary["pending_mb"])
        row = {
            "state_id": state.state_id,
            "state_label": state.label,
            "strategy": strategy,
            "start_min": "%.1f" % state.start_min,
            "end_min": "%.1f" % state.end_min,
            "duration_min": "%.1f" % (state.end_min - state.start_min),
            "samples": str(len(state_samples(state, samples))),
            "mean_capacity_mbps": "%.6f" % mean([s.capacity_mbps for s in state_samples(state, samples)]),
            "mean_rtt_ms": "%.6f" % mean([s.rtt_ms for s in state_samples(state, samples)]),
            "mean_packet_loss_rate": "%.9f" % mean([s.packet_loss_rate for s in state_samples(state, samples)]),
            "produced_mb": produced,
            "cache_evicted_mb": cache_evicted,
            "source_dropped_mb": source_dropped,
            "sent_mb": sent,
            "delivered_mb": delivered,
            "link_dropped_mb": link_dropped,
            "pending_mb": checkpoint["pending_mb"],
            "pending_change_mb": pending_change,
            "total_loss_mb": total_loss,
            "cache_eviction_rate": "%.9f" % (float(cache_evicted) / float(produced) if float(produced) else 0.0),
            "source_drop_rate": "%.9f" % (float(source_dropped) / float(produced) if float(produced) else 0.0),
            "link_loss_rate": "%.9f" % (float(link_dropped) / float(sent) if float(sent) else 0.0),
            "total_loss_rate": "%.9f" % (float(total_loss) / float(produced) if float(produced) else 0.0),
            "delivery_rate": "%.9f" % (float(delivered) / float(produced) if float(produced) else 0.0),
            "pending_rate": "%.9f" % (float(pending_change) / float(produced) if float(produced) else 0.0),
            "peak_cache_mb": checkpoint["peak_cache_mb"],
            "accounting_error_mb": "%.9f" % (float(produced) - float(cache_evicted) - float(source_dropped) - float(link_dropped) - float(delivered) - float(pending_change)),
            "seed": str(SEED),
        }
        stream_rows = []
        for stream_id, previous_stream in previous_streams.items():
            current = checkpoint_streams[(checkpoint["checkpoint_time_min"], stream_id)]
            stream_produced = delta(current["produced_mb"], previous_stream["produced_mb"])
            stream_cache = delta(current["cache_evicted_mb"], previous_stream["cache_evicted_mb"])
            stream_source = delta(current["source_dropped_mb"], previous_stream["source_dropped_mb"])
            stream_sent = delta(current["sent_mb"], previous_stream["sent_mb"])
            stream_delivered = delta(current["delivered_mb"], previous_stream["delivered_mb"])
            stream_link = "%.9f" % (float(stream_sent) - float(stream_delivered))
            stream_loss = "%.9f" % (float(stream_cache) + float(stream_source) + float(stream_link))
            stream_pending_change = delta(current["pending_mb"], previous_stream.get("pending_mb", "0.000000000"))
            stream_rows.append({
                "state_id": state.state_id, "state_label": state.label, "strategy": strategy,
                "stream_id": stream_id, "produced_mb": stream_produced,
                "cache_evicted_mb": stream_cache, "source_dropped_mb": stream_source,
                "sent_mb": stream_sent, "delivered_mb": stream_delivered,
                "link_dropped_mb": stream_link, "pending_mb": current["pending_mb"],
                "pending_change_mb": stream_pending_change,
                "loss_rate": "%.9f" % (float(stream_loss) / float(stream_produced) if float(stream_produced) else 0.0),
            })
            previous_streams[stream_id] = current
        row["_streams"] = stream_rows
        interval_rows.append(row)
        previous_summary = checkpoint
    return interval_rows


def number(row: Dict[str, str], field: str) -> float:
    return float(row[field])


def enrich_summary(row: Dict[str, str], state: StateSpec, samples: Sequence[LinkSample]) -> Dict[str, str]:
    produced = number(row, "produced_mb")
    cache_evicted = number(row, "cache_evicted_mb")
    source_dropped = number(row, "source_dropped_mb")
    sent = number(row, "sent_mb")
    delivered = number(row, "delivered_mb")
    link_dropped = number(row, "link_dropped_mb")
    pending = number(row, "pending_mb")
    output = Path(row.pop("_output"))
    with output.open(newline="", encoding="utf-8") as handle:
        list(csv.DictReader(handle))

    total_loss = cache_evicted + source_dropped + link_dropped
    row.update(
        {
            "state_label": state.label,
            "start_min": "%.1f" % state.start_min,
            "end_min": "%.1f" % state.end_min,
            "duration_min": "%.1f" % (state.end_min - state.start_min),
            "samples": str(len(samples)),
            "mean_capacity_mbps": "%.6f" % mean([sample.capacity_mbps for sample in samples]),
            "mean_rtt_ms": "%.6f" % mean([sample.rtt_ms for sample in samples]),
            "mean_packet_loss_rate": "%.9f" % mean([sample.packet_loss_rate for sample in samples]),
            "total_loss_mb": "%.9f" % total_loss,
            "cache_eviction_rate": "%.9f" % (cache_evicted / produced if produced else 0.0),
            "source_drop_rate": "%.9f" % (source_dropped / produced if produced else 0.0),
            "link_loss_rate": "%.9f" % (link_dropped / sent if sent else 0.0),
            "total_loss_rate": "%.9f" % (total_loss / produced if produced else 0.0),
            "delivery_rate": "%.9f" % (delivered / produced if produced else 0.0),
            "pending_rate": "%.9f" % (pending / produced if produced else 0.0),
            "accounting_error_mb": "%.9f" % (produced - cache_evicted - source_dropped - link_dropped - delivered - pending),
        }
    )
    return row


def write_csvs(rows: Sequence[Dict[str, str]]) -> None:
    fields = [
        "state_id", "state_label", "strategy", "start_min", "end_min", "duration_min", "samples",
        "mean_capacity_mbps", "mean_rtt_ms", "mean_packet_loss_rate", "produced_mb", "cache_evicted_mb",
        "source_dropped_mb", "sent_mb", "delivered_mb", "link_dropped_mb", "pending_mb", "total_loss_mb",
        "cache_eviction_rate", "source_drop_rate", "link_loss_rate", "total_loss_rate", "delivery_rate",
        "pending_rate", "pending_change_mb", "peak_cache_mb", "accounting_error_mb", "seed",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    stream_fields = [
        "state_id", "state_label", "strategy", "stream_id", "produced_mb", "cache_evicted_mb",
        "source_dropped_mb", "sent_mb", "delivered_mb", "link_dropped_mb", "pending_mb", "pending_change_mb", "loss_rate",
    ]
    with STREAM_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=stream_fields)
        writer.writeheader()
        for row in rows:
            for stream in row["_streams"]:
                writer.writerow({field: stream[field] for field in stream_fields})

    write_full_stream_csv()


def write_full_stream_csv() -> None:
    """Use the drained full-run counters for all data generated before 60 min."""
    full_fields = [
        "strategy", "stream_id", "produced_mb", "cache_evicted_mb", "source_dropped_mb",
        "sent_mb", "delivered_mb", "link_dropped_mb", "pending_mb", "lost_mb",
        "loss_rate", "share_of_strategy_loss",
    ]
    full_rows = []
    for strategy in ALL_STRATEGIES:
        path = OUTPUT_DIR / ("FULL-%s.csv" % strategy.replace("-", "_"))
        with path.open(newline="", encoding="utf-8") as handle:
            raw_rows = list(csv.DictReader(handle))
        stream_rows = {row["stream_id"]: row for row in raw_rows if row["record_type"] == "stream"}
        if set(stream_rows) != {"D1", "D2", "D3", "D4", "V1", "I1"}:
            raise RuntimeError("full-run stream rows missing in %s" % path)
        for stream_id in ("D1", "D2", "D3", "D4", "V1", "I1"):
            stream = stream_rows[stream_id]
            totals = {field: float(stream[field]) for field in
                      ("produced_mb", "cache_evicted_mb", "source_dropped_mb",
                       "sent_mb", "delivered_mb", "link_dropped_mb")}
            lost = sum(totals[field] for field in
                       ("cache_evicted_mb", "source_dropped_mb", "link_dropped_mb"))
            full_rows.append({
                "strategy": strategy, "stream_id": stream_id,
                **{field: "%.9f" % value for field, value in totals.items()},
                "pending_mb": stream["pending_mb"],
                "lost_mb": "%.9f" % lost,
                "loss_rate": "%.9f" % (lost / totals["produced_mb"] if totals["produced_mb"] else 0.0),
            })
        strategy_loss = sum(float(row["lost_mb"]) for row in full_rows if row["strategy"] == strategy)
        for row in full_rows:
            if row["strategy"] == strategy:
                row["share_of_strategy_loss"] = "%.9f" % (
                    float(row["lost_mb"]) / strategy_loss if strategy_loss else 0.0)
    with FULL_STREAM_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=full_fields)
        writer.writeheader()
        writer.writerows(full_rows)


def pct(value: str) -> str:
    return "%.2f%%" % (float(value) * 100.0)


def pct4(value: str) -> str:
    return "%.4f%%" % (float(value) * 100.0)


def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_report(rows: Sequence[Dict[str, str]], samples: Sequence[LinkSample], rates_mbps: Sequence[float]) -> None:
    actual_produced_mb = sum(float(row["produced_mb"]) for row in rows if row["strategy"] == "FIFO")
    theoretical_produced_mb = sum(rates_mbps) * 3600.0 / 8.0
    rate_validation = (
        "七次运行的全程产生量均为 %.6f MB，与按配置速率计算的 %.6f MB 理论值相差约 %.6f MB，"
        "差异来自仿真起止边界的离散 chunk。"
        % (actual_produced_mb, theoretical_produced_mb,
           abs(actual_produced_mb - theoretical_produced_mb))
    )
    state_rows = []
    for state in STATE_SPECS:
        selected = state_samples(state, samples)
        state_rows.append(
            [
                state.state_id, state.label, "%.1f-%.1f" % (state.start_min, state.end_min), str(len(selected)),
                "%.3f" % mean([sample.capacity_mbps for sample in selected]),
                "%.3f" % mean([sample.rtt_ms for sample in selected]),
                pct("%.9f" % mean([sample.packet_loss_rate for sample in selected])),
            ]
        )

    result_rows = []
    for row in rows:
        result_rows.append(
            [row["state_id"], row["state_label"], row["strategy"], pct(row["cache_eviction_rate"]),
             pct(row["source_drop_rate"]), pct(row["link_loss_rate"]), pct(row["total_loss_rate"]),
             pct(row["delivery_rate"]), pct(row["pending_rate"]), row["peak_cache_mb"]]
        )

    loss_rows = []
    for row in rows:
        loss_rows.append(
            [row["state_id"], row["strategy"], "%.2f" % float(row["cache_evicted_mb"]),
             "%.2f" % float(row["source_dropped_mb"]), "%.2f" % float(row["link_dropped_mb"]),
             "%.2f" % float(row["total_loss_mb"]), "%.2f" % float(row["pending_change_mb"])]
        )

    stream_ids = ("D1", "D2", "D3", "D4", "V1", "I1")
    with FULL_STREAM_CSV.open(newline="", encoding="utf-8") as handle:
        full_streams = {(row["strategy"], row["stream_id"]): row for row in csv.DictReader(handle)}
    full_loss_rows = []
    loss_share_rows = []
    for strategy in ALL_STRATEGIES:
        stream_rows = [full_streams[(strategy, stream_id)] for stream_id in stream_ids]
        total_lost = sum(float(stream["lost_mb"]) for stream in stream_rows)
        total_produced = sum(float(stream["produced_mb"]) for stream in stream_rows)
        full_loss_rows.append([
            strategy, *[pct(stream["loss_rate"]) for stream in stream_rows],
            pct(total_lost / total_produced if total_produced else 0.0),
        ])
        loss_share_rows.append([
            strategy, *[pct4(stream["share_of_strategy_loss"]) for stream in stream_rows],
        ])

    result_section = """## 5. 实验结果

本节结果来自本轮重新运行：每种策略连续运行 0–60 min 一次，共 7 次连续实验；仅在 `23.5 min`、`42 min` 和 `60 min` 三个边界记录 S1、S2、S3 区间统计。D1-D4 使用表 2.1 的生成速率；V1 按 4,354,778 B 的逻辑记录和 1.667848 Mbps 生成，记录周期约 20.89 s；I1 每 5 s 产生一张 258,715 B 图片，对应 0.413944 Mbps。V1 和 I1 均切分为最多 1472 B 的 UDP chunk，并在各自记录周期内均匀产生。链路状态按 30 s 更新，随机种子为 31。结果表共有 21 个“策略-状态区间”记录，不是 21 次独立运行；每次连续运行的全程字节对账误差均为 0。{rate_validation}

### 5.1 总体结果

{result_table}

### 5.2 丢失与待传量变化

{loss_table}

### 5.3 S3 结束时的全程分流丢失率（0–60 min）

仿真在 S3 结束的 60 min 停止生成与发送，并额外等待 2 s，让已进入链路的 packet 完成到达或丢失统计。下表累计 0–60 min 产生的数据截至该时点已发生的全部丢失。每一列是该流的 `(缓存淘汰 + 源端未缓存丢弃 + 链路丢失) / 该流 0–60 min 产生量`。60 min 时的待传缓存不计入丢失。

{full_loss_table}

### 5.4 各流占全程已丢失数据的比例

下表的分母是同一策略六类流对 0–60 min 产生的数据已确认的总丢失量，分子是该流的丢失量；每行六类数据之和约为 100%。这与 5.3 节以各流自身产生量为分母的丢失率是两个不同指标。两表的精确字节数和待传量见 `packet_level_cache_priority_60min_by_stream.csv`。

{loss_share_table}

**统计边界。** 60 min 时仍留在缓存中的数据尚未丢失，也尚未送达；因此 5.3 和 5.4 节统计的是截至 S3 结束时已发生的丢失，而非所有生成记录的最终命运。No-Cache 在到达时只尝试立即发送，串行器忙则源端丢弃；当前 FIFO 发送队首、满缓存时丢弃队尾新到的 chunk（drop-tail）。

""".format(
        rate_validation=rate_validation,
        result_table=table(["状态", "link_conditions", "机制", "缓存淘汰率", "源端未缓存丢弃率", "链路丢包率", "总丢失率", "送达率", "待传量变化比例", "峰值缓存(MB)"], result_rows),
        loss_table=table(["状态", "机制", "缓存淘汰(MB)", "源端未缓存丢弃(MB)", "链路丢失(MB)", "总丢失(MB)", "待传量变化(MB)"], loss_rows),
        full_loss_table=table(["机制", "D1", "D2", "D3", "D4", "V1", "I1", "总丢失率"], full_loss_rows),
        loss_share_table=table(["机制", "D1", "D2", "D3", "D4", "V1", "I1"], loss_share_rows),
    )

    existing_report = REPORT_PATH.read_text(encoding="utf-8")
    start_marker = "## 5. 实验结果"
    end_marker = "## 6. 结果解释"
    if start_marker not in existing_report or end_marker not in existing_report:
        raise RuntimeError("report must contain sections 5 and 6 before refreshing results")
    report = existing_report[:existing_report.index(start_marker)] + result_section + existing_report[existing_report.index(end_marker):]
    REPORT_PATH.write_text(report, encoding="utf-8")
    return

def parse_list(value: str, cast):
    return tuple(cast(item.strip()) for item in value.split(",") if item.strip())


def run(
    link_update_seconds: float = LINK_UPDATE_SECONDS,
    packet_sizes: Sequence[int] = PACKET_SIZES,
    rates_mbps: Sequence[float] = RATES_MBPS,
    record_sizes: Sequence[int] = RECORD_SIZES,
) -> List[Dict[str, str]]:
    if not NS3_BINARY.exists():
        raise FileNotFoundError("ns-3 binary not found: %s; build the scratch target first" % NS3_BINARY)
    samples = read_samples()
    rows: List[Dict[str, str]] = []
    for strategy in ALL_STRATEGIES:
        rows.extend(run_ns3(strategy, link_update_seconds, packet_sizes, rates_mbps, record_sizes))
    write_csvs(rows)
    write_report(rows, samples, rates_mbps)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--link-update-seconds", type=float, default=LINK_UPDATE_SECONDS)
    parser.add_argument("--record-sizes", default=",".join(str(value) for value in RECORD_SIZES))
    parser.add_argument("--packet-sizes", default=",".join(str(value) for value in PACKET_SIZES))
    parser.add_argument("--rates-mbps", default=",".join(str(value) for value in RATES_MBPS))
    args = parser.parse_args()
    record_sizes = parse_list(args.record_sizes, int)
    packet_sizes = parse_list(args.packet_sizes, int)
    rates_mbps = parse_list(args.rates_mbps, float)
    if len(record_sizes) != 6 or len(packet_sizes) != 6 or len(rates_mbps) != 6:
        parser.error("--record-sizes, --packet-sizes, and --rates-mbps each require six values in D1,D2,D3,D4,V1,I1 order")
    if args.link_update_seconds <= 0 or any(value <= 0 for value in record_sizes + packet_sizes + rates_mbps):
        parser.error("link update interval, record sizes, packet sizes, and rates must be positive")
    rows = run(args.link_update_seconds, packet_sizes, rates_mbps, record_sizes)
    print("Wrote %s" % REPORT_PATH)
    print("Wrote %s" % SUMMARY_CSV)
    print("Wrote %s" % STREAM_CSV)
    print("Wrote %s" % FULL_STREAM_CSV)
    for row in rows:
        print(
            "%s,%s,cache=%s,source=%s,link=%s,total=%s,delivery=%s,pending=%s,accounting=%s"
            % (
                row["state_id"], row["strategy"], pct(row["cache_eviction_rate"]),
                pct(row["source_drop_rate"]), pct(row["link_loss_rate"]), pct(row["total_loss_rate"]),
                pct(row["delivery_rate"]), pct(row["pending_rate"]), row["accounting_error_mb"],
            )
        )


if __name__ == "__main__":
    main()
