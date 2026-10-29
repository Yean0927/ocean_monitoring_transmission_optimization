"""Two separate 8 × 6 inch bar charts with matching method styles."""
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
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
METHODS = [row["Method"] for row in rows]
COLORS = ["#5086BC", "#8EB9DF", "#AFCEE6", "#FFD27A", "#B6B6B6",
          "#E77A6A", "#729FC7"]
HATCHES = ["////", "\\\\", "..", "xx", "", "++", "//"]
TICK_LABELS = ["XGBoost", "LightGBM", "Random\nForest", "CatBoost", "TinyMLP",
               "Linear\nSVM", "Contextual\nBandit"]
assert len(rows) == len(set(METHODS)) == 7

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
    "axes.labelsize": 20, "axes.linewidth": 1.2, "pdf.fonttype": 42,
    "svg.fonttype": "none", "legend.frameon": False, "savefig.facecolor": "white",
})


def draw(metric, ylabel, prefix, ymax, ticks, legend_location):
    values = np.array([float(row[metric]) for row in rows])
    assert np.all(np.isfinite(values)) and np.all(values >= 0)
    if metric == "Macro_F1":
        assert np.all(values <= 1)
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.16, right=0.985, bottom=0.20, top=0.985)
    handles, pattern_bars, value_labels = [], [], []
    for position, (name, value, color, hatch) in enumerate(
            zip(METHODS, values, COLORS, HATCHES)):
        bar = ax.bar(position, value, width=0.74, color=color,
                     edgecolor="none", linewidth=0, zorder=3)[0]
        pattern_bars.append((bar, hatch))
        handles.append(Patch(facecolor=color, hatch=hatch, label=name))
        value_labels.append(ax.annotate(
            f"{value:.3f}", (position, value),
            xytext=(0, 4), textcoords="offset points",
            ha="center", va="bottom", fontsize=12,
            fontweight="bold", color="#283744", zorder=5))
    ax.set_xlim(-0.65, 6.65)
    ax.set_ylim(0, ymax)
    ax.set_yticks(ticks)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f" if metric == "Macro_F1" else "%.2f"))
    ax.set_xticks(np.arange(7), TICK_LABELS, fontsize=12, ha="center")
    ax.set_xlabel("Method", labelpad=10)
    ax.set_ylabel(ylabel, labelpad=9)
    ax.tick_params(axis="y", labelsize=16, width=1.2, length=4, pad=5)
    ax.tick_params(axis="x", width=1.2, length=4, pad=6)
    for spine in ax.spines.values():
        spine.set_color("#2C2C2C")
    legend = ax.legend(handles=handles, handler_map={Patch: VectorHatchHandler()},
                       ncol=1, loc=legend_location, fontsize=12,
                       handlelength=1.1, handleheight=1.1, handletextpad=0.35,
                       labelspacing=0.36, borderaxespad=0.55, borderpad=0)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    text_boxes = [legend.get_window_extent(renderer)]
    text_boxes.extend(label.get_window_extent(renderer) for label in value_labels)
    for level in ticks:
        screen_y = ax.transData.transform((0, level))[1]
        segments = [(-0.65, 6.65)]
        for box in text_boxes:
            if box.y0 <= screen_y <= box.y1:
                left, right = ax.transData.inverted().transform(
                    [(box.x0, screen_y), (box.x1, screen_y)])[:, 0]
                revised = []
                for start, stop in segments:
                    if stop <= left - 0.04 or start >= right + 0.04:
                        revised.append((start, stop))
                    else:
                        if start < left - 0.04:
                            revised.append((start, left - 0.04))
                        if stop > right + 0.04:
                            revised.append((right + 0.04, stop))
                segments = revised
        for start, stop in segments:
            ax.hlines(level, start, stop, color="#E8E8E8", linewidth=0.8, zorder=0.5)
    for bar, pattern in pattern_bars:
        bounds = bar.get_window_extent(renderer).transformed(fig.dpi_scale_trans.inverted())
        for artist in hatch_artists(bounds.bounds, pattern, fig.dpi_scale_trans):
            ax.add_artist(artist)
    fig.canvas.draw()
    assert tuple(fig.get_size_inches()) == (8, 6) and len(ax.patches) >= 7
    require_matplotlib_panel_alignment(
        fig, json_out=str(OUT / f"{prefix}.alignment.json"),
        tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f"{prefix}.pdf")
    fig.savefig(OUT / f"{prefix}.svg")
    fig.savefig(OUT / f"{prefix}.png", dpi=300)
    fig.savefig(OUT / f"{prefix}.tiff", dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


draw("Macro_F1", "Macro F1", "macro_f1_8x6", 1.18,
     np.arange(0, 1.01, 0.2), "upper right")
draw("Oracle_gap_Mbit_per_s", "Oracle gap (Mbps)", "oracle_gap_8x6", 0.045,
     np.arange(0, 0.041, 0.01), "upper left")
