"""Solid-color comparisons, sorted descending within each data type."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
TYPES = ["D1", "D2", "D3", "D4", "V1", "I1"]
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as stream:
    DATA = {row["Configuration"]: np.array([float(row[t]) for t in TYPES])
            for row in csv.DictReader(stream)}
assert len(DATA) == 8 and all(len(v) == 6 for v in DATA.values())
assert all(np.isfinite(v).all() and ((0 <= v) & (v <= 100)).all() for v in DATA.values())

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
    "axes.labelsize": 12, "axes.linewidth": 1.0, "pdf.fonttype": 42,
    "svg.fonttype": "none", "legend.frameon": False,
    "savefig.facecolor": "white",
})

# Full, Baseline, protocol, compression, cache: fixed across the two plots.
COLORS = ["#006877", "#C3CFE5", "#09ADA8", "#33929C", "#51A260"]

def render(prefix, mode, word):
    configs = ["FULL", "BASELINE"] + [mode + c for c in ["PROTOCOL", "COMPRESSION", "CACHE"]]
    labels = ["Full", "Baseline"] + [f"{word} {c}" for c in ["protocol", "compression", "cache"]]
    fig, ax = plt.subplots(figsize=(10.4, 5.2))
    fig.subplots_adjust(left=0.09, right=0.985, bottom=0.145, top=0.86)
    x = np.arange(6)
    values = np.stack([DATA[key] for key in configs])
    # Stable sorting keeps the legend order for ties, with no changes to values
    # or the permanent color-to-configuration mapping.
    order = np.argsort(-values, axis=0, kind="stable")
    ranks = np.argsort(order, axis=0)
    sorted_values = np.take_along_axis(values, order, axis=0)
    assert np.all(np.diff(sorted_values, axis=0) <= 0)
    with (OUT / f"{prefix}.bar_order.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Data_type", "Left_to_right_rank", "Configuration", "Value_percent"])
        for group, data_type in enumerate(TYPES):
            for rank, config_index in enumerate(order[:, group], 1):
                writer.writerow([data_type, rank, configs[config_index],
                                 f"{values[config_index, group]:.2f}"])
    texts = []
    for i, (key, label, color) in enumerate(zip(configs, labels, COLORS)):
        bars = ax.bar(x + (ranks[i] - 2) * 0.16, DATA[key], width=0.153,
                      color=color, edgecolor="#283744", linewidth=0.85,
                      label=label, zorder=3)
        for bar, value in zip(bars, DATA[key]):
            texts.append(ax.annotate(f"{value:.2f}",
                                    (bar.get_x() + bar.get_width() / 2, value),
                                    xytext=(0, 3.5), textcoords="offset points",
                                    ha="center", va="bottom", fontsize=6.6,
                                    color="#263442", annotation_clip=False, zorder=4))
    ax.set_xlim(-0.52, 5.52)
    ax.set_ylim(0, 110)
    ax.set_xticks(x, TYPES, fontsize=10.5)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_xlabel("Data type", labelpad=12)
    ax.set_ylabel("Successful delivery ratio (%)", labelpad=10)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.8)
    ax.tick_params(axis="both", width=1, length=3, pad=4)
    for spine in ax.spines.values():
        spine.set_color("#2C2C2C")
    ax.legend(ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.055),
              fontsize=8.5, columnspacing=1.5, handlelength=1.8, handletextpad=0.6)

    # Raise only labels that cross a horizontal gridline; derive clearance from
    # the actual final text rectangles, without masking the grid.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    grid_y = [ax.transData.transform((0, level))[1] for level in ax.get_yticks()]
    for text in texts:
        bbox = text.get_window_extent(renderer)
        hits = [y for y in grid_y if bbox.y0 - 1 < y < bbox.y1 + 1]
        if hits:
            shift_pt = (max(hits) + 2 - bbox.y0) * 72 / fig.dpi
            text.set_position((0, 3.5 + shift_pt))
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(OUT / f"{prefix}.alignment.json"),
                                      tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f"{prefix}.png", dpi=300)
    fig.savefig(OUT / f"{prefix}.pdf")
    fig.savefig(OUT / f"{prefix}.svg")
    fig.savefig(OUT / f"{prefix}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)

if __name__ == "__main__":
    render("full_baseline_without_solid_sorted", "WO_", "Without")
    render("full_baseline_add_solid_sorted", "ADD_", "Add")
