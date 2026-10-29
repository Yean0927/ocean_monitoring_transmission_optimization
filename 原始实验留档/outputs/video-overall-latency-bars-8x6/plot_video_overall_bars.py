"""Plot report-derived pooled video latency reduction; no S0 bars."""
from pathlib import Path
import csv
import hashlib
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from hatch_patterns import hatch_artists, VectorHatchHandler

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
REPORT = ROOT / "实验报告" / "视频压缩 (1).md"
VIDEOS = ROOT / "实验数据" / "视频样本"
ALGORITHMS = ("S1", "S2", "S3")
LABELS = ("S1 H.264", "S2 H.265/HEVC", "S3 AV1")
COLORS = ("#5086BC", "#8EB9DF", "#AFCEE6")
HATCHES = ("////", "\\\\", "..")
BANDWIDTHS = (2, 4, 10)


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def calculate():
    text = REPORT.read_text()
    ratios, times = {}, {}
    for line in text.splitlines():
        fields = [value.strip() for value in line.strip().strip("|").split("|")]
        if len(fields) == 6 and fields[0].isdigit():
            if fields[1].endswith((".mp4", ".mkv")):
                ratios[fields[1]] = tuple(map(float, fields[3:6]))
        if len(fields) == 6 and fields[0][:2] in ALGORITHMS:
            times[fields[0][:2]] = (float(fields[3].split()[0]),
                                    float(fields[4].split()[0]))
    assert len(ratios) == 9 and set(times) == set(ALGORITHMS)
    inputs = []
    for name, values in ratios.items():
        path = VIDEOS / name
        size = path.stat().st_size
        inputs.append(dict(video_name=name, original_size_bytes=size,
            S1_report_ratio=values[0], S2_report_ratio=values[1],
            S3_report_ratio=values[2], sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    original = sum(row["original_size_bytes"] for row in inputs)
    rows = []
    for index, algorithm in enumerate(ALGORITHMS):
        compressed = sum(row["original_size_bytes"] * ratios[row["video_name"]][index]
                         for row in inputs)
        encode, decode = times[algorithm]
        processing = 9 * (encode + decode)
        for bandwidth in BANDWIDTHS:
            direct = 8 * original / (1e6 * bandwidth)
            transfer = 8 * compressed / (1e6 * bandwidth)
            total = processing + transfer
            reduction = 100 * (direct - total) / direct
            affine = 100 * (1 - compressed / original) - 100 * processing * 1e6 / (8 * original) * bandwidth
            assert math.isclose(reduction, affine, abs_tol=1e-10)
            rows.append(dict(algorithm=algorithm, bandwidth_mbps=bandwidth,
                n_videos=9, original_total_bytes=original,
                estimated_compressed_total_bytes=compressed,
                report_mean_encode_s=encode, report_mean_decode_s=decode,
                estimated_total_processing_s=processing, T_direct_total_s=direct,
                T_transfer_total_s=transfer, T_video_total_s=total,
                latency_reduction_pct=reduction,
                aggregation="ratio_of_summed_latencies",
                data_origin="approximate_recalculation_from_rounded_report"))
    assert len(rows) == 9
    write_csv("per_video_inputs.csv", inputs)
    write_csv("source_data.csv", rows)
    (OUT / "calculation_manifest.json").write_text(json.dumps(dict(
        report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        metric="pooled end-to-end latency reduction relative to direct transfer",
        n_videos=9, original_total_bytes=original,
        mean_processing_time_assumption="Report means are arithmetic means across the 9 videos",
        rounding="Report compression ratios and processing means are already rounded",
        exclusion="S0 bars omitted at user request; no source videos omitted",
        uncertainty="No uncertainty intervals inferred from unavailable replicate data",
        shape=[3, 3]), indent=2))
    return rows


def draw(rows):
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
        "axes.labelsize": 20, "axes.linewidth": 1.2,
        "pdf.fonttype": 42, "svg.fonttype": "none",
        "legend.frameon": False, "savefig.facecolor": "white",
    })
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.18, right=0.985, bottom=0.16, top=0.97)
    handles, texture_bars = [], []
    width = 0.21
    for index, (algorithm, label, color, pattern) in enumerate(zip(
            ALGORITHMS, LABELS, COLORS, HATCHES)):
        values = [next(r["latency_reduction_pct"] for r in rows
                       if r["algorithm"] == algorithm and r["bandwidth_mbps"] == b)
                  for b in BANDWIDTHS]
        bars = ax.bar([x + (index - 1) * width for x in range(3)], values,
                      width=width, color=color, edgecolor="none", linewidth=0, zorder=3)
        texture_bars.extend((bar, pattern) for bar in bars)
        handles.append(Patch(facecolor=color, hatch=pattern, label=label))
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylim(-650, 100)
    ticks = list(range(-600, 101, 100))
    ax.set_yticks(ticks)
    ax.set_xticks([0, 1, 2], ["2", "4", "10"], fontsize=16)
    ax.set_xlabel("Bandwidth (Mbps)", labelpad=10)
    ax.set_ylabel("Latency reduction (%)", labelpad=9)
    ax.tick_params(axis="both", labelsize=16, width=1.2, length=4, pad=5)
    for spine in ax.spines.values():
        spine.set_color("#2C2C2C")
    legend = ax.legend(handles=handles, handler_map={Patch: VectorHatchHandler()},
        ncol=1, loc="lower left", bbox_to_anchor=(0.025, 0.025), fontsize=14,
        handlelength=1.1, handleheight=1.1, handletextpad=0.35,
        labelspacing=0.36, borderaxespad=0.55, borderpad=0)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = legend.get_window_extent(renderer)
    x0, x1 = [ax.transData.inverted().transform((x, box.y0))[0]
              for x in [box.x0, box.x1]]
    for level in ticks:
        if level == 0:
            continue
        y = ax.transData.transform((0, level))[1]
        if box.y0 - 3 <= y <= box.y1 + 3:
            ax.hlines(level, -0.6, x0 - 0.025, color="#E8E8E8", linewidth=0.8, zorder=0.5)
            ax.hlines(level, x1 + 0.025, 2.6, color="#E8E8E8", linewidth=0.8, zorder=0.5)
        else:
            ax.hlines(level, -0.6, 2.6, color="#E8E8E8", linewidth=0.8, zorder=0.5)
    ax.axhline(0, color="#6B7280", linewidth=0.9, linestyle="--", zorder=2)
    for bar, pattern in texture_bars:
        bar_box = bar.get_window_extent(renderer).transformed(fig.dpi_scale_trans.inverted())
        for artist in hatch_artists(bar_box.bounds, pattern, fig.dpi_scale_trans):
            ax.add_artist(artist)
    fig.canvas.draw()
    assert tuple(fig.get_size_inches()) == (8, 6)
    (OUT / "video_overall_latency_8x6.alignment.json").write_text(json.dumps({
        "verdict": "NOT APPLICABLE", "reason": "Single quantitative panel"}))
    stem = OUT / "video_overall_latency_8x6"
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".svg"))
    fig.savefig(stem.with_suffix(".png"), dpi=600)
    fig.savefig(stem.with_suffix(".tiff"), dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


if __name__ == "__main__":
    draw(calculate())
