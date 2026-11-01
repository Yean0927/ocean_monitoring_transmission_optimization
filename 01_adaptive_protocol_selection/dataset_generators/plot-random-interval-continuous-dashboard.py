#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Draw a dashboard-style summary with continuous-style histograms for the
# random-interval protocol label dataset.

import argparse
import csv
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ns3-final-submission-matplotlib")

import matplotlib.pyplot as plt
import numpy as np


PROTOCOLS = ["TCP_CUBIC", "TCP_BBR", "QUIC_BBR"]
PLOT_LABELS = ["TCP_CUBIC", "TCP_BBR", "QUIC_BBR", "NO_DELIVERY"]
THROUGHPUT_COLUMNS = {
    "TCP_CUBIC": "tcp_cubic_mbps",
    "TCP_BBR": "tcp_bbr_mbps",
    "QUIC_BBR": "quic_bbr_mbps",
}
COLORS = {
    "TCP_CUBIC": "#0070b8",
    "TCP_BBR": "#00b3b0",
    "QUIC_BBR": "#2F8F9D",
    "NO_DELIVERY": "#c2d0ea",
}
ORACLE_COLOR = "#5D5B8D"
ACCENT_COLOR = "#7B8794"
MISSING_BAND_COLOR = "#E5E7EB"


def read_rows(path):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"No rows found in {path}")
    return rows


def as_float(row, key):
    return float(row.get(key, 0.0) or 0.0)


def pct(value, total):
    return 100.0 * value / total if total else 0.0


def draw_kpis(fig, rows):
    counts = Counter(row["best_protocol"] for row in rows)
    kpis = [
        ("Complete label rows", f"{len(rows)}"),
        ("QUIC_BBR wins", f"{counts['QUIC_BBR']} ({pct(counts['QUIC_BBR'], len(rows)):.1f}%)"),
        ("TCP_CUBIC wins", f"{counts['TCP_CUBIC']} ({pct(counts['TCP_CUBIC'], len(rows)):.1f}%)"),
        ("TCP_BBR wins", f"{counts['TCP_BBR']} ({pct(counts['TCP_BBR'], len(rows)):.1f}%)"),
    ]
    lefts = [0.06, 0.29, 0.52, 0.75]
    for left, (label, value) in zip(lefts, kpis):
        ax = fig.add_axes([left, 0.835, 0.19, 0.075])
        ax.axis("off")
        ax.add_patch(
            plt.Rectangle(
                (0, 0),
                1,
                1,
                transform=ax.transAxes,
                facecolor="#f8fafc",
                edgecolor="#cbd5e1",
                linewidth=1.2,
            )
        )
        ax.text(0.5, 0.62, value, ha="center", va="center", fontsize=17, fontweight="bold", color="#111827")
        ax.text(0.5, 0.25, label, ha="center", va="center", fontsize=9.5, color="#4b5563")


def draw_overall_winner(ax, rows):
    counts = Counter(row["best_protocol"] for row in rows)
    values = [counts[protocol] for protocol in PLOT_LABELS]
    colors = [COLORS[protocol] for protocol in PLOT_LABELS]
    wedges, _ = ax.pie(
        values,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.44, "edgecolor": "white"},
    )
    ax.text(0, 0.08, f"{len(rows)}", ha="center", va="center", fontsize=24, fontweight="bold")
    ax.text(0, -0.14, "labels", ha="center", va="center", fontsize=10, color="#4b5563")
    ax.set_title("Overall best-protocol share", loc="left", fontweight="bold")
    legend_labels = [
        f"{protocol}: {counts[protocol]} ({pct(counts[protocol], len(rows)):.1f}%)"
        for protocol in PLOT_LABELS
        if counts[protocol] > 0
    ]
    used_wedges = [wedge for wedge, protocol in zip(wedges, PLOT_LABELS) if counts[protocol] > 0]
    ax.legend(used_wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.25), frameon=False, fontsize=10)


def draw_static_vs_oracle(ax, rows):
    static = {}
    for protocol in PROTOCOLS:
        column = THROUGHPUT_COLUMNS[protocol]
        static[protocol] = sum(as_float(row, column) for row in rows) / len(rows)
    oracle = sum(max(as_float(row, column) for column in THROUGHPUT_COLUMNS.values()) for row in rows) / len(rows)
    labels = PROTOCOLS + ["ORACLE"]
    values = [static[protocol] for protocol in PROTOCOLS] + [oracle]
    colors = [COLORS[protocol] for protocol in PROTOCOLS] + [ORACLE_COLOR]
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("Average throughput if selected statically", loc="left", fontweight="bold")
    ax.set_ylabel("Mbit/s")
    ax.grid(axis="y", alpha=0.18)
    ax.tick_params(axis="x", rotation=16)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.01, f"{value:.3f}", ha="center", va="bottom", fontsize=9)


def draw_win_throughput(ax, rows):
    values_by_protocol = defaultdict(list)
    for row in rows:
        protocol = row["best_protocol"]
        if protocol not in PROTOCOLS:
            continue
        values_by_protocol[protocol].append(as_float(row, THROUGHPUT_COLUMNS[protocol]))
    labels = PROTOCOLS
    means = [
        sum(values_by_protocol[label]) / len(values_by_protocol[label])
        if values_by_protocol[label]
        else 0.0
        for label in labels
    ]
    bars = ax.bar(labels, means, color=[COLORS[label] for label in labels])
    ax.set_title("Mean throughput when each protocol wins", loc="left", fontweight="bold")
    ax.set_ylabel("Mbit/s")
    ax.grid(axis="y", alpha=0.18)
    ax.tick_params(axis="x", rotation=16)
    for bar, value in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.01, f"{value:.3f}", ha="center", va="bottom", fontsize=9)


def draw_continuous_interval_histogram(ax, rows, samples_per_row):
    rng = random.Random(42)
    values_by_protocol = defaultdict(list)
    for row in rows:
        low = as_float(row, "min_send_interval_ms")
        high = as_float(row, "max_send_interval_ms")
        protocol = row["best_protocol"]
        for _ in range(samples_per_row):
            values_by_protocol[protocol].append(rng.uniform(low, high))

    bins = np.arange(0, 205, 10)
    data = [values_by_protocol[protocol] for protocol in PLOT_LABELS]
    ax.hist(
        data,
        bins=bins,
        stacked=True,
        color=[COLORS[protocol] for protocol in PLOT_LABELS],
        label=PLOT_LABELS,
        edgecolor="white",
        linewidth=0.35,
    )
    ax.set_xlim(0, 200)
    ax.set_title("Continuous-style send interval histogram", loc="left", fontweight="bold")
    ax.set_xlabel("Per-packet send interval reconstructed from configured ranges (ms)")
    ax.set_ylabel("Sampled packet-level counts")
    ax.grid(axis="y", alpha=0.18)
    ax.axvline(20, color=ACCENT_COLOR, linewidth=1.2, linestyle="--", alpha=0.85)
    ax.axvline(180, color=ACCENT_COLOR, linewidth=1.2, linestyle="--", alpha=0.85)
    ax.text(20, ax.get_ylim()[1] * 0.94, "20 ms", ha="center", va="top", fontsize=9)
    ax.text(180, ax.get_ylim()[1] * 0.94, "180 ms", ha="center", va="top", fontsize=9)


def draw_continuous_loss_histogram(ax, rows):
    grouped = defaultdict(Counter)
    for row in rows:
        grouped[as_float(row, "packet_loss_rate") * 100.0][row["best_protocol"]] += 1

    losses = sorted(grouped)
    width = 1.45
    bottoms = {loss: 0 for loss in losses}
    for protocol in PLOT_LABELS:
        heights = [grouped[loss].get(protocol, 0) for loss in losses]
        ax.bar(
            losses,
            heights,
            width=width,
            bottom=[bottoms[loss] for loss in losses],
            color=COLORS[protocol],
            edgecolor="white",
            linewidth=0.45,
            label=protocol,
            align="center",
        )
        for loss, height in zip(losses, heights):
            bottoms[loss] += height

    ax.set_xlim(0, 21)
    ax.set_title("Packet-loss histogram on sampled grid", loc="left", fontweight="bold")
    ax.set_xlabel("Packet loss rate (%)")
    ax.set_ylabel("Anchor conditions")
    ax.grid(axis="y", alpha=0.18)
    ax.axvspan(12, 16, color=MISSING_BAND_COLOR, alpha=0.75)
    ax.text(14, max(bottoms.values()) * 0.88, "not sampled\n12%-16%", ha="center", va="center", fontsize=9, color="#475569", fontweight="bold")
    ax.set_xticks([0.2, 1, 2, 4, 6, 8, 12, 16, 20])
    ax.set_xticklabels(["0.2", "1", "2", "4", "6", "8", "12", "16", "20"], rotation=35, ha="right", fontsize=9)


def draw_capacity_histogram(ax, rows):
    grouped = defaultdict(Counter)
    for row in rows:
        grouped[as_float(row, "capacity_mbps")][row["best_protocol"]] += 1

    capacities = sorted(grouped)
    bottoms = {capacity: 0 for capacity in capacities}
    for protocol in PLOT_LABELS:
        heights = [grouped[capacity].get(protocol, 0) for capacity in capacities]
        ax.bar(
            capacities,
            heights,
            width=0.16,
            bottom=[bottoms[capacity] for capacity in capacities],
            color=COLORS[protocol],
            edgecolor="white",
            linewidth=0.35,
            label=protocol,
            align="center",
        )
        for capacity, height in zip(capacities, heights):
            bottoms[capacity] += height

    ax.set_title("Capacity histogram on sampled grid", loc="left", fontweight="bold")
    ax.set_xlabel("Capacity (Mbps)")
    ax.set_ylabel("Anchor conditions")
    ax.grid(axis="y", alpha=0.18)
    tick_values = [0.2, 0.5, 1, 2, 3, 4, 5]
    ax.set_xticks(tick_values)
    ax.set_xticklabels([f"{capacity:g}" for capacity in tick_values], rotation=35, ha="right", fontsize=8)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="sample_results/protocol_evaluation/real-anchor-labels-random-interval.csv",
    )
    parser.add_argument(
        "--output",
        default="sample_results/figures/random-interval-continuous-anchor-dashboard.png",
    )
    parser.add_argument("--samples-per-row", type=int, default=8)
    args = parser.parse_args()

    rows = read_rows(ROOT / args.input)
    fig = plt.figure(figsize=(16, 11.5), facecolor="white")
    fig.suptitle("Random-Interval Protocol Label Outcome Summary", fontsize=25, fontweight="bold", y=0.965)
    fig.text(
        0.5,
        0.925,
        "Same traffic model: TCP CUBIC, TCP BBR, and QUIC BBR use random packet size and random send interval",
        ha="center",
        fontsize=12.5,
        color="#4b5563",
    )
    draw_kpis(fig, rows)

    gs = fig.add_gridspec(3, 3, left=0.06, right=0.96, top=0.79, bottom=0.14, hspace=0.95, wspace=0.34)
    draw_overall_winner(fig.add_subplot(gs[0, 0]), rows)
    draw_static_vs_oracle(fig.add_subplot(gs[0, 1]), rows)
    draw_win_throughput(fig.add_subplot(gs[0, 2]), rows)
    draw_continuous_interval_histogram(fig.add_subplot(gs[1, :]), rows, args.samples_per_row)
    draw_continuous_loss_histogram(fig.add_subplot(gs[2, 0:2]), rows)
    draw_capacity_histogram(fig.add_subplot(gs[2, 2]), rows)

    fig.text(
        0.06,
        0.035,
        "Note: send-interval histogram is reconstructed from configured random ranges. Packet-loss and capacity remain sampled grid points.",
        fontsize=9.5,
        color="#4b5563",
    )

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=190)
    plt.close(fig)
    print(f"Figure written to {output}")


if __name__ == "__main__":
    main()
