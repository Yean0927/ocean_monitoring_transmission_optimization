#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Build jittered training samples from real NS-3 anchor labels.

import argparse
import csv
import math
import random
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = ["TCP_CUBIC", "TCP_BBR", "QUIC_BBR"]


def as_float(row, key, default=0.0):
    value = row.get(key, "")
    if value == "" or value is None:
        return default
    return float(value)


def clamp(value, low, high):
    return max(low, min(high, value))


def load_real_anchors(path):
    anchors = []
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        for index, row in enumerate(reader):
            anchor = dict(row)
            anchor["anchor_id"] = index
            anchor["source"] = "real_ns3_anchor"
            for key in [
                "rtt_ms",
                "capacity_mbps",
                "packet_loss_rate",
                "packet_size_min",
                "packet_size_max",
                "packet_size_mean",
                "min_send_interval_ms",
                "max_send_interval_ms",
                "mean_send_interval_ms",
                "offered_load_mbps",
                "file_size_mb",
                "duration_s",
                "tcp_cubic_mbps",
                "tcp_bbr_mbps",
                "quic_bbr_mbps",
            ]:
                anchor[key] = as_float(row, key)
            add_training_feature_aliases(anchor)
            anchors.append(anchor)
    if not anchors:
        raise RuntimeError(f"No anchors found in {path}")
    return anchors


def state_from_loss(loss):
    if loss < 0.02:
        return "normal"
    if loss < 0.08:
        return "degrading"
    if loss < 0.16:
        return "bad-variable"
    return "severe"


def range_std(low, high):
    return abs(high - low) / math.sqrt(12.0)


def add_training_feature_aliases(row):
    packet_min = float(row.get("packet_size_min", 0.0))
    packet_max = float(row.get("packet_size_max", packet_min))
    interval_min = float(row.get("min_send_interval_ms", row.get("interval_min_ms", 0.0)))
    interval_max = float(row.get("max_send_interval_ms", row.get("interval_max_ms", interval_min)))
    interval_mean = float(row.get("mean_send_interval_ms", (interval_min + interval_max) / 2.0))

    row["packet_size_std"] = range_std(packet_min, packet_max)
    row["interval_min_ms"] = interval_min
    row["interval_max_ms"] = interval_max
    row["interval_mean_ms"] = interval_mean
    row["interval_std_ms"] = range_std(interval_min, interval_max)
    row.setdefault("phase_progress", 0.0)
    row.setdefault("loss_trend", 0.0)
    row.setdefault("capacity_trend", 0.0)
    row.setdefault("rtt_trend", 0.0)
    row.setdefault("effective_file_size_mb", row.get("file_size_mb", 0.0))
    row.setdefault("compression_ratio", 1.0)
    row.setdefault("prev_rtt_ms", row.get("rtt_ms", 0.0))
    row.setdefault("prev_capacity_mbps", row.get("capacity_mbps", 0.0))
    row.setdefault("prev_packet_loss_rate", row.get("packet_loss_rate", 0.0))
    row.setdefault("source_scenario", row.get("scenario", "unknown"))
    row.setdefault("interval_mode", "random-range")
    row.setdefault("data_type", "synthetic_text")
    row.setdefault("prev_best_protocol", row.get("best_protocol", "unknown"))


def estimate_jittered_throughputs(anchor, row, rng):
    cap_factor = clamp(row["capacity_mbps"] / max(anchor["capacity_mbps"], 1e-6), 0.75, 1.25)
    offered_factor = clamp(row["offered_load_mbps"] / max(anchor["offered_load_mbps"], 1e-6), 0.7, 1.3)
    rtt_factor = clamp(math.sqrt(max(anchor["rtt_ms"], 1.0) / max(row["rtt_ms"], 1.0)), 0.82, 1.18)
    loss_delta = row["packet_loss_rate"] - anchor["packet_loss_rate"]
    values = {}
    for protocol, sensitivity in [("TCP_CUBIC", 9.5), ("TCP_BBR", 3.0), ("QUIC_BBR", 4.5)]:
        base = anchor[f"{protocol.lower()}_mbps"]
        loss_factor = math.exp(-sensitivity * loss_delta)
        noise = rng.uniform(0.96, 1.04)
        traffic_factor = offered_factor if protocol != "QUIC_BBR" else 1.0
        value = base * cap_factor * traffic_factor * rtt_factor * loss_factor * noise
        value = min(value, row["capacity_mbps"] * 1.05)
        if protocol != "QUIC_BBR":
            value = min(value, row["offered_load_mbps"] * 1.1)
        values[protocol] = max(0.0, value)
    return values


def jitter_anchor(sample_id, anchor, rng):
    packet_min = max(64, int(anchor["packet_size_min"] * rng.uniform(0.9, 1.1)))
    packet_max = max(packet_min, int(anchor["packet_size_max"] * rng.uniform(0.9, 1.1)))
    interval_min = max(0.5, anchor["min_send_interval_ms"] * rng.uniform(0.9, 1.1))
    interval_max = max(interval_min, anchor["max_send_interval_ms"] * rng.uniform(0.9, 1.1))
    packet_mean = (packet_min + packet_max) / 2.0
    interval_mean = (interval_min + interval_max) / 2.0
    row = {
        "sample_id": sample_id,
        "anchor_id": anchor["anchor_id"],
        "source": "jittered_from_real_ns3_anchor",
        "scenario": anchor["scenario"],
        "state_name": state_from_loss(anchor["packet_loss_rate"]),
        "rtt_ms": clamp(anchor["rtt_ms"] * rng.uniform(0.94, 1.06), 5.0, 500.0),
        "capacity_mbps": clamp(anchor["capacity_mbps"] * rng.uniform(0.9, 1.1), 0.05, 8.0),
        "packet_loss_rate": clamp(anchor["packet_loss_rate"] + rng.uniform(-0.01, 0.01), 0.0, 0.25),
        "traffic_mode": anchor["traffic_mode"],
        "packet_size_min": packet_min,
        "packet_size_max": packet_max,
        "packet_size_mean": packet_mean,
        "min_send_interval_ms": interval_min,
        "max_send_interval_ms": interval_max,
        "mean_send_interval_ms": interval_mean,
        "offered_load_mbps": packet_mean * 8.0 / (interval_mean / 1000.0) / 1_000_000.0,
        "file_size_mb": anchor["file_size_mb"],
        "duration_s": anchor["duration_s"],
        "base_best_protocol": anchor["best_protocol"],
        "base_tcp_cubic_mbps": anchor["tcp_cubic_mbps"],
        "base_tcp_bbr_mbps": anchor["tcp_bbr_mbps"],
        "base_quic_bbr_mbps": anchor["quic_bbr_mbps"],
    }
    add_training_feature_aliases(row)
    throughputs = estimate_jittered_throughputs(anchor, row, rng)
    row["tcp_cubic_mbps"] = throughputs["TCP_CUBIC"]
    row["tcp_bbr_mbps"] = throughputs["TCP_BBR"]
    row["quic_bbr_mbps"] = throughputs["QUIC_BBR"]
    if not any(value > 0 for value in throughputs.values()):
        row["best_protocol"] = "NO_DELIVERY"
    else:
        row["best_protocol"] = max(throughputs, key=throughputs.get)
    return row


def format_row(row):
    output = {}
    for key, value in row.items():
        output[key] = f"{value:.6f}" if isinstance(value, float) else value
    return output


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(format_row(row) for row in rows)


def write_summary(path, anchors, samples):
    anchor_labels = Counter(row["best_protocol"] for row in anchors)
    sample_labels = Counter(row["best_protocol"] for row in samples)
    scenarios = Counter(row["scenario"] for row in anchors)
    with path.open("w") as stream:
        stream.write("# Real Anchor Jitter Dataset Summary\n\n")
        stream.write(f"Real NS-3 anchors: {len(anchors)}\n\n")
        stream.write(f"Jittered samples: {len(samples)}\n\n")
        stream.write("## Important Note\n\n")
        stream.write(
            "The anchor table contains real protocol measurements. TCP CUBIC, TCP BBR, and "
            "QUIC BBR are measured with the same random packet size and random send interval "
            "traffic model. The jittered samples are generated from these real anchors and "
            "are not independent NS-3 runs.\n\n"
        )
        stream.write(
            "The real anchors keep their measured label distribution. By default, the jittered "
            "training samples also preserve the anchor-driven label tendency. Use "
            "`--balance-labels` only for a separate class-balance ablation experiment.\n\n"
        )
        stream.write("## Real Anchor Label Distribution\n\n")
        for label, count in sorted(anchor_labels.items()):
            stream.write(f"- {label}: {count}\n")
        stream.write("\n## Jittered Sample Label Distribution\n\n")
        for label, count in sorted(sample_labels.items()):
            stream.write(f"- {label}: {count}\n")
        stream.write("\n## Scenario Distribution\n\n")
        for label, count in sorted(scenarios.items()):
            stream.write(f"- {label}: {count}\n")


def target_counts(total, labels):
    base = total // len(labels)
    remainder = total % len(labels)
    counts = {label: base for label in labels}
    for label in labels[:remainder]:
        counts[label] += 1
    return counts


def build_balanced_samples(anchors, total_samples, rng):
    anchors_by_label = {
        label: [anchor for anchor in anchors if anchor["best_protocol"] == label]
        for label in PROTOCOLS
    }
    missing = [label for label, rows in anchors_by_label.items() if not rows]
    if missing:
        raise RuntimeError(f"Cannot balance labels with no anchors for: {', '.join(missing)}")

    samples = []
    counts = target_counts(total_samples, PROTOCOLS)
    sample_id = 0
    for label in PROTOCOLS:
        attempts = 0
        while sum(1 for row in samples if row["best_protocol"] == label) < counts[label]:
            anchor = anchors_by_label[label][attempts % len(anchors_by_label[label])]
            row = jitter_anchor(sample_id, anchor, rng)
            attempts += 1
            if row["best_protocol"] != label:
                if attempts > counts[label] * 20:
                    raise RuntimeError(f"Cannot build enough balanced samples for {label}")
                continue
            samples.append(row)
            sample_id += 1
    rng.shuffle(samples)
    for index, row in enumerate(samples):
        row["sample_id"] = index
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--anchor-input",
        default="sample_results/protocol_evaluation/real-anchor-labels-random-interval.csv",
    )
    parser.add_argument("--output-dir", default="sample_results/training_data")
    parser.add_argument("--samples", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--balance-labels", action="store_true")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    anchors = load_real_anchors(ROOT / args.anchor_input)
    if args.balance_labels:
        samples = build_balanced_samples(anchors, args.samples, rng)
    else:
        samples = [
            jitter_anchor(index, anchors[index % len(anchors)], rng)
            for index in range(args.samples)
        ]
        rng.shuffle(samples)

    output_dir = ROOT / args.output_dir
    write_csv(output_dir / "real-anchors-4000.csv", anchors)
    write_csv(output_dir / "jittered-training-samples-12000.csv", samples)
    write_summary(output_dir / "dataset-summary.md", anchors, samples)
    print(f"Real NS-3 anchors: {len(anchors)}")
    print(f"Jittered samples: {len(samples)}")
    print(f"Results written to {output_dir}")


if __name__ == "__main__":
    main()
