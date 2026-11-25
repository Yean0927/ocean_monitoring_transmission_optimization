"""Plot all supplied policy loss percentages on an exact 8 × 6 inch canvas."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from hatch_patterns import hatch_artists, VectorHatchHandler
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
PREFIX = "cache_policy_loss_8x6"
CATEGORIES = ["D1", "D2", "D3", "D4", "V1", "I1"]
LABELS = ["No Cache", "FIFO", "Priority-Aging", "Priority-MaxF", "Priority-Utility"]
COLORS = ["#B6B6B6", "#5086BC", "#8EB9DF", "#AFCEE6", "#FFD27A"]
HATCHES = ["", "////", "\\\\", "..", "xx"]


def main():
    with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["Policy"] for row in rows] == LABELS
    values = np.array([[float(row[category]) for category in CATEGORIES] for row in rows])
    assert values.shape == (5, 6)
    assert np.isfinite(values).all() and np.all((0 <= values) & (values <= 100))
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
        "axes.labelsize": 20, "axes.linewidth": 1.2, "pdf.fonttype": 42,
        "svg.fonttype": "none", "legend.frameon": False,
        "savefig.facecolor": "white", "hatch.linewidth": 0.7,
    })
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.15, right=0.985, bottom=0.16, top=0.94)
    x = np.arange(len(CATEGORIES), dtype=float)
    handles, pattern_bars = [], []
    for i, (label, color, pattern) in enumerate(zip(LABELS, COLORS, HATCHES)):
        bars = ax.bar(x + (i - 2) * 0.15, values[i], width=0.15,
                      color=color, edgecolor="none", linewidth=0, zorder=3)
        handles.append(Patch(facecolor=color, hatch=pattern, label=label))
        pattern_bars.extend((bar, pattern) for bar in bars)
    ax.set_xlim(-0.55, 5.55)
    ax.set_ylim(0, 104)
    ax.set_xticks(x, CATEGORIES)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_xlabel("Data stream", labelpad=9)
    ax.set_ylabel("Data loss rate (%)", labelpad=8)
    ax.tick_params(axis="both", labelsize=16, width=1.2, length=4, pad=5)
    ax.set_axisbelow(True)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_color("#2C2C2C")
    legend = ax.legend(handles=handles, handler_map={Patch: VectorHatchHandler()},
                       ncol=1, loc="upper center", bbox_to_anchor=(4.0, 100),
                       bbox_transform=ax.transData,
                       fontsize=11, handlelength=1.1, handleheight=1.1,
                       handletextpad=0.35, labelspacing=0.36,
                       borderaxespad=0, borderpad=0)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    legend_box = legend.get_window_extent(renderer)
    assert all(not bar.get_window_extent(renderer).overlaps(legend_box)
               for bar, _ in pattern_bars), "Legend intersects a data bar"
    legend_left = ax.transData.inverted().transform((legend_box.x0, legend_box.y0))[0]
    legend_right = ax.transData.inverted().transform((legend_box.x1, legend_box.y1))[0]
    for level in ax.get_yticks():
        display_y = ax.transData.transform((0, level))[1]
        if legend_box.y0 <= display_y <= legend_box.y1:
            ax.hlines([level, level], [-0.55, legend_right + 0.04],
                      [legend_left - 0.04, 5.55], color="#E8E8E8", linewidth=0.8, zorder=0.5)
        else:
            ax.hlines(level, -0.55, 5.55, color="#E8E8E8", linewidth=0.8, zorder=0.5)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for bar, pattern in pattern_bars:
        box = bar.get_window_extent(renderer).transformed(fig.dpi_scale_trans.inverted())
        for artist in hatch_artists(box.bounds, pattern, fig.dpi_scale_trans):
            ax.add_artist(artist)
    fig.canvas.draw()
    assert tuple(fig.get_size_inches()) == (8, 6) and len(fig.axes) == 1
    assert len(pattern_bars) == 30
    require_matplotlib_panel_alignment(
        fig, json_out=str(OUT / f"{PREFIX}.alignment.json"), tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
    fig.savefig(OUT / f"{PREFIX}.pdf")
    fig.savefig(OUT / f"{PREFIX}.svg")
    fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


if __name__ == "__main__":
    main()
