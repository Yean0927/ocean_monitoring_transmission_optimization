"""Two independent 8 × 6 inch grouped-bar comparisons of text codecs."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FormatStrFormatter
from hatch_patterns import hatch_artists, VectorHatchHandler
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
DATASETS = ["D1 buoy weather", "D2 weather UTF-16", "D3 wave sensor", "D4 current log"]
TICK_LABELS = ["D1 buoy\nweather", "D2 weather\nUTF-16", "D3 wave\nsensor", "D4 current\nlog"]
ALGORITHMS = ["LZ4", "ZSTD-3", "Gzip", "Gorilla", "Chimp", "Parquet+ZSTD", "Parquet+Snappy"]
COLORS = ["#5086BC", "#8EB9DF", "#AFCEE6", "#FFD27A", "#B6B6B6", "#E77A6A", "#729FC7"]
HATCHES = ["////", "\\\\", "..", "xx", "", "++", "//"]
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
lookup = {(row["Dataset"], row["Algorithm"]): row for row in rows}
assert len(rows) == len(lookup) == 28
assert set(lookup) == {(dataset, algorithm) for dataset in DATASETS for algorithm in ALGORITHMS}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
    "axes.labelsize": 20, "axes.linewidth": 1.2, "pdf.fonttype": 42,
    "svg.fonttype": "none", "legend.frameon": False, "savefig.facecolor": "white",
})


def draw(metric, ylabel, prefix, limits, ticks, location):
    values = np.array([[float(lookup[dataset, algorithm][metric]) for dataset in DATASETS]
                       for algorithm in ALGORITHMS])
    assert values.shape == (7, 4) and np.all(np.isfinite(values))
    if metric == "Wire_original_ratio":
        assert np.all((values >= 0) & (values <= 1))
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.165, right=0.985, bottom=0.19, top=0.97)
    handles, pattern_bars = [], []
    centers = np.arange(4, dtype=float)
    width = 0.12
    for i, (algorithm, color, pattern) in enumerate(zip(ALGORITHMS, COLORS, HATCHES)):
        bars = ax.bar(centers + (i - 3) * width, values[i], width=width,
                      color=color, edgecolor="none", linewidth=0, zorder=3)
        pattern_bars.extend((bar, pattern) for bar in bars)
        handles.append(Patch(facecolor=color, hatch=pattern, label=algorithm))
    ax.set_xlim(-0.57, 3.57)
    ax.set_ylim(*limits)
    ax.set_yticks(ticks)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f" if metric == "Wire_original_ratio" else "%.0f"))
    ax.set_xticks(centers, TICK_LABELS, fontsize=14)
    ax.set_xlabel("Dataset", labelpad=10)
    ax.set_ylabel(ylabel, labelpad=9)
    ax.tick_params(axis="y", labelsize=16, width=1.2, length=4, pad=5)
    ax.tick_params(axis="x", width=1.2, length=4, pad=6)
    for spine in ax.spines.values():
        spine.set_color("#2C2C2C")
    legend = ax.legend(handles=handles, handler_map={Patch: VectorHatchHandler()},
                       ncol=1, loc=location, fontsize=12,
                       handlelength=1.1, handleheight=1.1, handletextpad=0.35,
                       labelspacing=0.36, borderaxespad=0.55, borderpad=0)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = legend.get_window_extent(renderer)
    legend_left = ax.transData.inverted().transform((box.x0, box.y0))[0]
    for level in ticks:
        if metric == "Latency_reduction_percent" and level == 0:
            continue
        display_y = ax.transData.transform((0, level))[1]
        right = legend_left - 0.025 if box.y0 <= display_y <= box.y1 else 3.57
        ax.hlines(level, -0.57, right, color="#E8E8E8", linewidth=0.8, zorder=0.5)
    if metric == "Latency_reduction_percent":
        ax.axhline(0, color="#6B7280", linewidth=0.9, linestyle="--", zorder=2)
    for bar, pattern in pattern_bars:
        box = bar.get_window_extent(renderer).transformed(fig.dpi_scale_trans.inverted())
        for artist in hatch_artists(box.bounds, pattern, fig.dpi_scale_trans):
            ax.add_artist(artist)
    fig.canvas.draw()
    assert tuple(fig.get_size_inches()) == (8, 6)
    require_matplotlib_panel_alignment(
        fig, json_out=str(OUT / f"{prefix}.alignment.json"),
        tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f"{prefix}.pdf")
    fig.savefig(OUT / f"{prefix}.svg")
    fig.savefig(OUT / f"{prefix}.png", dpi=300)
    fig.savefig(OUT / f"{prefix}.tiff", dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


draw("Latency_reduction_percent", "Latency reduction (%)", "text_latency_reduction_8x6",
     (-100, 100), np.arange(-100, 101, 25), "lower right")
draw("Wire_original_ratio", "Wire/Original", "text_compression_ratio_8x6",
     (0, 0.86), np.arange(0, 0.81, 0.2), "upper right")
