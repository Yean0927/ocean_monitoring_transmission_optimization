"""Redraw the nine existing latency reduction values with matched axes."""
from pathlib import Path
import csv
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from hatch_patterns import hatch_artists, VectorHatchHandler
from audit_panel_alignment import require_matplotlib_panel_alignment
from plot_layout import PLOT_LAYOUT

OUT = Path(__file__).resolve().parent
ALGORITHMS = ("S1", "S2", "S3")
LABELS = ("S1 H.264", "S2 H.265/HEVC", "S3 AV1")
COLORS = ("#5086BC", "#8EB9DF", "#AFCEE6")
HATCHES = ("////", "\\\\", "..")
BANDWIDTHS = (2, 4, 10)



def draw(rows):
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
        "axes.labelsize": 20, "axes.linewidth": 1.2,
        "pdf.fonttype": 42, "svg.fonttype": "none",
        "legend.frameon": False, "savefig.facecolor": "white",
    })
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(**PLOT_LAYOUT)
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
    ax.set_xlabel("Bandwidth (Mbps)", labelpad=9)
    ax.set_ylabel("Latency reduction (%)", labelpad=8)
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
    require_matplotlib_panel_alignment(fig,
        json_out=OUT / "fig6_latency_reduction_8x6.alignment.json", strict=True)
    stem = OUT / "fig6_latency_reduction_8x6"
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".svg"))
    fig.savefig(stem.with_suffix(".png"), dpi=300)
    fig.savefig(stem.with_suffix(".tiff"), dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


if __name__ == "__main__":
    with (OUT / "fig6_source_data.csv").open(newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))
    rows = [
        dict(algorithm=row["algorithm"], bandwidth_mbps=int(row["bandwidth_mbps"]),
             latency_reduction_pct=float(row["latency_reduction_pct"]))
        for row in source
    ]
    assert len(rows) == 9 and {(r["algorithm"], r["bandwidth_mbps"]) for r in rows} == {
        (algorithm, bandwidth) for algorithm in ALGORITHMS for bandwidth in BANDWIDTHS
    }
    assert all(math.isfinite(row["latency_reduction_pct"]) for row in rows)
    draw(rows)
