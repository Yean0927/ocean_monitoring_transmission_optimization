"""Byte-weighted Text aggregation, narrow descending bars, two-panel export."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
PREFIX = "combined_text_video_image"
CATEGORIES = ["Text\n(D1–D4)", "Video\n(V1)", "Image\n(I1)"]
GROUPS = [["D1", "D2", "D3", "D4"], ["V1"], ["I1"]]
CONFIGS = ["FULL", "BASELINE", "WO_PROTOCOL", "WO_COMPRESSION", "WO_CACHE",
           "ADD_PROTOCOL", "ADD_COMPRESSION", "ADD_CACHE"]
with (OUT / "source_counts.csv").open(newline="", encoding="utf-8") as handle:
    raw = list(csv.DictReader(handle))
COUNTS = {(row["variant"], row["stream"]):
          (int(row["generated_raw_bytes"]), int(row["delivered_raw_equivalent_bytes"]))
          for row in raw}
assert len(COUNTS) == 48
assert all(0 <= delivered <= generated for generated, delivered in COUNTS.values())
DATA = {}
with (OUT / f"{PREFIX}.source_data.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["Configuration", "Category", "Generated_raw_bytes",
                     "Delivered_raw_equivalent_bytes", "Success_percent"])
    for config in CONFIGS:
        rates = []
        for name, streams in zip(["Text", "Video", "Image"], GROUPS):
            generated = sum(COUNTS[config, stream][0] for stream in streams)
            delivered = sum(COUNTS[config, stream][1] for stream in streams)
            assert generated > 0
            rate = delivered / generated * 100
            rates.append(rate)
            writer.writerow([config, name, generated, delivered, f"{rate:.10f}"])
        DATA[config] = np.array(rates)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
    "axes.labelsize": 11, "axes.linewidth": 1.0, "pdf.fonttype": 42,
    "svg.fonttype": "none", "legend.frameon": False, "savefig.facecolor": "white",
})
COLORS = ["#006877", "#C3CFE5", "#09ADA8", "#33929C", "#51A260"]

fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.1))
fig.subplots_adjust(left=0.066, right=0.99, bottom=0.18, top=0.74, wspace=0.19)
annotations = []
order_rows = []
for ax, panel, mode, word, title in zip(axes, ["a", "b"], ["WO_", "ADD_"],
                                      ["Without", "Add"],
                                      ["Component removal", "Component addition"]):
    configs = ["FULL", "BASELINE"] + [mode + c for c in ["PROTOCOL", "COMPRESSION", "CACHE"]]
    labels = ["Full", "Baseline"] + [f"{word} {c}" for c in ["protocol", "compression", "cache"]]
    values = np.stack([DATA[config] for config in configs])
    order = np.argsort(-values, axis=0, kind="stable")
    ranks = np.argsort(order, axis=0)
    assert np.all(np.diff(np.take_along_axis(values, order, axis=0), axis=0) <= 0)
    x = np.arange(3)
    handles = []
    for i, (config, label, color) in enumerate(zip(configs, labels, COLORS)):
        bars = ax.bar(x + (ranks[i] - 2) * 0.145, DATA[config], width=0.076,
                      color=color, edgecolor="#283744", linewidth=0.8,
                      label=label, zorder=3)
        handles.append(bars)
        for bar, value in zip(bars, DATA[config]):
            text = ax.annotate(f"{value:.2f}",
                               (bar.get_x() + bar.get_width() / 2, value),
                               xytext=(0, 3.5), textcoords="offset points",
                               ha="center", va="bottom", fontsize=6.6,
                               color="#263442", annotation_clip=False, zorder=4)
            annotations.append((ax, text))
    for category, indices in enumerate(order.T):
        for rank, index in enumerate(indices, 1):
            order_rows.append([panel, ["Text", "Video", "Image"][category], rank,
                               configs[index], f"{values[index, category]:.10f}"])
    ax.set_xlim(-0.53, 2.53)
    ax.set_ylim(0, 110)
    ax.set_xticks(x, CATEGORIES, fontsize=10)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_xlabel("Data type", labelpad=9)
    ax.set_ylabel("Successful delivery ratio (%)", labelpad=8)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.8)
    ax.tick_params(axis="both", width=1, length=3, pad=4)
    for spine in ax.spines.values():
        spine.set_color("#2C2C2C")
    # Row-major reading order: Full, Baseline, protocol; compression, cache.
    ax.legend(handles=[handles[i] for i in [0, 3, 1, 4, 2]], ncol=3,
              loc="lower center", bbox_to_anchor=(0.5, 1.045),
              fontsize=8.1, columnspacing=1.2, handlelength=1.5,
              handletextpad=0.5, labelspacing=0.75, borderaxespad=0)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=52)
    ax.annotate(panel, (0, 1), xycoords="axes fraction", xytext=(-11, 54),
                textcoords="offset points", ha="left", va="bottom",
                fontsize=12, fontweight="bold", annotation_clip=False)

fig.canvas.draw()
renderer = fig.canvas.get_renderer()
for ax, text in annotations:
    bbox = text.get_window_extent(renderer)
    grid_y = [ax.transData.transform((0, level))[1] for level in ax.get_yticks()]
    hits = [y for y in grid_y if bbox.y0 - 1 < y < bbox.y1 + 1]
    if hits:
        shift_pt = (max(hits) + 2 - bbox.y0) * 72 / fig.dpi
        text.set_position((0, 3.5 + shift_pt))
fig.canvas.draw()
require_matplotlib_panel_alignment(fig, json_out=str(OUT / f"{PREFIX}.alignment.json"),
                                  tolerance_pt=1.5, gutter_tolerance_pt=1.5,
                                  require_panel_labels=True, strict=True)
fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
fig.savefig(OUT / f"{PREFIX}.pdf")
fig.savefig(OUT / f"{PREFIX}.svg")
fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
with (OUT / f"{PREFIX}.bar_order.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["Panel", "Category", "Left_to_right_rank", "Configuration", "Value_percent"])
    writer.writerows(order_rows)
plt.close(fig)
