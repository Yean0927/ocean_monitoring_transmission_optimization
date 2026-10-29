#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot multi-dimensional protocol decision-boundary maps.

import argparse
import csv
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-ns3")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.colors import ListedColormap


PROTOCOLS = ["TCP_CUBIC", "TCP_BBR", "QUIC_BBR", "NO_DELIVERY"]
SHORT = {
    "TCP_CUBIC": "CUBIC",
    "TCP_BBR": "BBR",
    "QUIC_BBR": "QUIC",
    "NO_DELIVERY": "NONE",
}
COLORS = {
    "TCP_CUBIC": "#0070b8",
    "TCP_BBR": "#00b3b0",
    "QUIC_BBR": "#2F8F9D",
    "NO_DELIVERY": "#c2d0ea",
}


def as_float(row, key):
    return float(row.get(key, 0.0) or 0.0)


def read_rows(path):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"No rows found in {path}")
    return rows


def range_label(row, low_key, high_key, suffix):
    return f"{as_float(row, low_key):g}-{as_float(row, high_key):g} {suffix}"


def cell_text(protocol):
    if protocol == "NO_DELIVERY":
        return "NONE"
    return SHORT[protocol]


def plot_for_rtt(rows, rtt, output_dir):
    rtt_rows = [row for row in rows if as_float(row, "rtt_ms") == rtt]
    if not rtt_rows:
        return None

    capacities = sorted({as_float(row, "capacity_mbps") for row in rtt_rows})
    losses = sorted({as_float(row, "packet_loss_rate") for row in rtt_rows})
    packet_ranges = sorted(
        {
            (
                as_float(row, "packet_size_min"),
                as_float(row, "packet_size_max"),
            )
            for row in rtt_rows
        }
    )
    interval_ranges = sorted(
        {
            (
                as_float(row, "min_send_interval_ms"),
                as_float(row, "max_send_interval_ms"),
            )
            for row in rtt_rows
        }
    )

    lookup = {}
    for row in rtt_rows:
        key = (
            as_float(row, "packet_size_min"),
            as_float(row, "packet_size_max"),
            as_float(row, "min_send_interval_ms"),
            as_float(row, "max_send_interval_ms"),
            as_float(row, "capacity_mbps"),
            as_float(row, "packet_loss_rate"),
        )
        lookup[key] = row["best_protocol"]

    protocol_index = {protocol: index for index, protocol in enumerate(PROTOCOLS)}
    cmap = ListedColormap([COLORS[protocol] for protocol in PROTOCOLS])

    fig, axes = plt.subplots(
        len(packet_ranges),
        len(interval_ranges),
        figsize=(19, 17),
        sharex=True,
        sharey=True,
    )
    fig.suptitle(
        f"Protocol Decision Boundary Map (RTT = {rtt:g} ms)",
        fontsize=24,
        fontweight="bold",
        y=0.982,
    )
    fig.text(
        0.5,
        0.955,
        "Rows: packet size range, columns: random send interval range, cells: best protocol over capacity-loss grid",
        ha="center",
        fontsize=12,
        color="#4B5563",
    )

    for row_index, packet_range in enumerate(packet_ranges):
        for col_index, interval_range in enumerate(interval_ranges):
            ax = axes[row_index, col_index]
            matrix = np.full((len(losses), len(capacities)), protocol_index["NO_DELIVERY"])
            texts = [["" for _ in capacities] for _ in losses]
            for y, loss in enumerate(losses):
                for x, capacity in enumerate(capacities):
                    key = (*packet_range, *interval_range, capacity, loss)
                    protocol = lookup.get(key, "NO_DELIVERY")
                    matrix[y, x] = protocol_index[protocol]
                    texts[y][x] = cell_text(protocol)

            ax.imshow(matrix, cmap=cmap, vmin=0, vmax=len(PROTOCOLS) - 1, aspect="auto")
            ax.set_title(f"{interval_range[0]:g}-{interval_range[1]:g} ms", fontsize=11, fontweight="bold")
            ax.set_xticks(range(len(capacities)))
            ax.set_xticklabels([f"{capacity:g}" for capacity in capacities], fontsize=8)
            ax.set_yticks(range(len(losses)))
            ax.set_yticklabels([f"{loss * 100:g}%" for loss in losses], fontsize=8)

            if col_index == 0:
                ax.set_ylabel(f"{packet_range[0]:g}-{packet_range[1]:g} B\nloss", fontsize=10)
            if row_index == len(packet_ranges) - 1:
                ax.set_xlabel("capacity (Mbps)", fontsize=9)

    handles = [mpatches.Patch(color=COLORS[protocol], label=protocol) for protocol in PROTOCOLS]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=True, fontsize=11, bbox_to_anchor=(0.5, 0.025))
    fig.text(
        0.5,
        0.006,
        "The boundary should be read as a sampled decision surface: exact transitions between adjacent grid points are not directly measured.",
        ha="center",
        fontsize=9.5,
        color="#4B5563",
    )

    fig.tight_layout(rect=(0.025, 0.055, 0.995, 0.935))
    output = output_dir / f"protocol-decision-boundary-rtt-{rtt:g}ms-clean.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="02_protocol_evaluation/sample-results/real-anchor-grid-4000-random-interval/real-anchor-labels-random-interval.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="02_protocol_evaluation/sample-results/real-anchor-grid-4000-random-interval",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_rows(input_path)
    rtts = sorted({as_float(row, "rtt_ms") for row in rows})
    outputs = []
    for rtt in rtts:
        output = plot_for_rtt(rows, rtt, output_dir)
        if output:
            outputs.append(output)
    for output in outputs:
        print(f"Figure written to {output}")


if __name__ == "__main__":
    main()
