#!/usr/bin/env python3
"""Replot a video latency curve from a CSV; preserve the exact 8 x 6 inch canvas."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
VIDEO = "5cf7af68d381d7cb80e5567444e894c2.mp4"
REPORT = (HERE.parents[1] / "海洋实验同步包" / "02_文本压缩算法选择" / "video_compression.md")
STYLES = {
    "S0": ("S0 original direct", "#6B7280", "o"),
    "S1": ("S1 H.264 lower bitrate", "#2563EB", "s"),
    "S2": ("S2 H.265/HEVC", "#10B981", "^"),
    "S3": ("S3 AV1", "#F59E0B", "D"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=HERE / "digitized_plot_data.csv")
    parser.add_argument("--video-name", default=VIDEO)
    parser.add_argument("--packet-size", type=int, default=4096)
    parser.add_argument("--output-stem", default="file8_latency_reduction_digitized")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    # The report's size ratios identify the sample; they are not latency values.
    for line in args.report.read_text(encoding="utf-8").splitlines():
        fields = [value.strip() for value in line.strip().strip("|").split("|")]
        if len(fields) == 6 and fields[0] == "8" and fields[1] == VIDEO:
            ratios = dict(zip(STYLES, map(float, fields[2:])))
            break
    else:
        raise ValueError("Cannot find the File 8 compression-ratio row in the report.")
    with (HERE / "file8_report_compression_ratios.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file_id", "video_name", "algorithm", "compression_ratio", "data_origin"])
        writer.writeheader()
        for algorithm, ratio in ratios.items():
            writer.writerow({"file_id": 8, "video_name": VIDEO, "algorithm": algorithm,
                             "compression_ratio": ratio, "data_origin": "report_table"})
    with args.input_csv.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    data = [row for row in source if row["video_name"] == args.video_name
            and int(row["packet_size_bytes"]) == args.packet_size]
    if not data:
        raise ValueError("No rows match the selected video and packet size.")
    for algorithm in STYLES:
        subset = [row for row in data if row["algorithm"] == algorithm]
        bands = [float(row["bandwidth_mbps"]) for row in subset]
        if sorted(bands) != [2.0, 4.0, 10.0]:
            raise ValueError(f"Expected exactly one point at 2, 4, 10 Mbps for {algorithm}.")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "font.size": 16,
        "axes.labelsize": 20,
        "axes.labelweight": "bold",
        "axes.linewidth": 1.7,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.18, right=0.97, bottom=0.16, top=0.97)
    for algorithm, (label, color, marker) in STYLES.items():
        subset = sorted((row for row in data if row["algorithm"] == algorithm),
                        key=lambda row: float(row["bandwidth_mbps"]))
        ax.plot([float(row["bandwidth_mbps"]) for row in subset],
                [float(row["latency_reduction_pct"]) for row in subset],
                label=label, color=color, marker=marker,
                linewidth=3.0, markersize=8, markeredgewidth=1.2, zorder=3)
    ax.axhline(0, color="#374151", linewidth=2, linestyle="--", alpha=0.65, zorder=4)
    ax.set_xlabel("Bandwidth (Mbps)", fontsize=20, fontweight="bold", labelpad=10)
    ax.set_ylabel("Latency reduction (%)", fontsize=20, fontweight="bold", labelpad=8)
    ax.set_xlim(1.6, 10.4)
    ax.set_ylim(-275, 110)
    ax.set_xticks([2, 4, 10])
    ax.set_yticks([-250, -200, -150, -100, -50, 0, 50, 100])
    ax.tick_params(width=1.7, length=6)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontweight("bold")
    legend = ax.legend(loc="lower left", bbox_to_anchor=(0.025, 0.025),
                       ncol=2, frameon=False, fontsize=12,
                       borderaxespad=0.3, labelspacing=0.5, markerscale=0.8,
                       columnspacing=1.0, handlelength=1.8, handletextpad=0.5)
    # Break only the background grid at the legend's footprint.
    fig.canvas.draw()
    box = legend.get_window_extent(fig.canvas.get_renderer()).expanded(1.04, 1.16)
    (legend_left, legend_bottom), (_, legend_top) = ax.transData.inverted().transform(
        [[box.x0, box.y0], [box.x1, box.y1]])
    for y_tick in ax.get_yticks():
        grid_right = legend_left if legend_bottom <= y_tick <= legend_top else 10.4
        ax.hlines(y_tick, 1.6, grid_right, color="#E5E7EB", linewidth=0.9, alpha=0.75, zorder=0)
    for x_tick in [2, 4, 10]:
        grid_top = legend_bottom if x_tick >= legend_left else 110
        ax.vlines(x_tick, -275, grid_top, color="#E5E7EB", linewidth=0.9, alpha=0.75, zorder=0)
    stem = HERE / args.output_stem
    fig.canvas.draw()
    # The canvas must stay exactly 8 x 6 inches; tight cropping changes its size.
    fig.savefig(stem.with_suffix(".png"), dpi=600, facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    print(f"Saved {stem.name}: 8 x 6 inches; {len(data)} source points.")


if __name__ == "__main__":
    main()
