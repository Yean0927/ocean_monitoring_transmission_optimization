"""All eight configurations in one pyplot axes, exactly 8 by 6 inches."""
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
PREFIX = "delivery_ratio_single_8x6"
PLOT_LAYOUT = dict(left=0.15, right=0.985, bottom=0.16, top=0.94)
CATEGORIES = ["Text", "Video", "Image"]
CONFIGS = ["FULL", "BASELINE", "WO_PROTOCOL", "WO_COMPRESSION", "WO_CACHE",
           "ADD_PROTOCOL", "ADD_COMPRESSION", "ADD_CACHE"]
LABELS = ["Full", "Baseline", "−Prot.", "−Comp.", "−Cache",
          "+Prot.", "+Comp.", "+Cache"]
COLORS = ["#5086BC", "#B6B6B6", "#8EB9DF", "#AFCEE6", "#FFD27A",
          "#E77A6A", "#729FC7", "#EFA99F"]
HATCHES = ["////", "", "\\\\", "..", "xx", "++", "//", "--"]
with (OUT / "delivery_ratio_mean_sd_input.csv").open(newline="", encoding="utf-8") as handle:
    source = list(csv.DictReader(handle))
summary = {(r["Configuration"], r["Category"]):
           (float(r["Mean_percent"]), float(r["Plus_minus_percent"])) for r in source}
assert len(summary) == len(CONFIGS) * len(CATEGORIES) == 24
values = np.array([[summary[cfg, category][0] for category in CATEGORIES]
                   for cfg in CONFIGS])
errors = np.array([[summary[cfg, category][1] for category in CATEGORIES]
                   for cfg in CONFIGS])
assert np.all((0 <= values) & (values <= 100)) and np.all(errors >= 0)
output_rows = [[config, category, f"{values[i, j]:.2f}", f"{errors[i, j]:.2f}"]
               for i, config in enumerate(CONFIGS)
               for j, category in enumerate(CATEGORIES)]
order = np.argsort(-values, axis=0, kind="stable")
ranks = np.argsort(order, axis=0)
assert np.all(np.diff(np.take_along_axis(values, order, axis=0), axis=0) <= 0)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "font.weight": "bold", "axes.labelweight": "bold",
    "axes.labelsize": 20, "axes.linewidth": 1.2, "pdf.fonttype": 42,
    "svg.fonttype": "none", "legend.frameon": False, "savefig.facecolor": "white",
    "hatch.linewidth": 0.7,
})
fig, ax = plt.subplots(figsize=(8, 6))
fig.subplots_adjust(**PLOT_LAYOUT)
handles = []
pattern_bars = []
x = np.arange(3, dtype=float)
for i, (label, color, hatch) in enumerate(zip(LABELS, COLORS, HATCHES)):
    bars = ax.bar(x + (ranks[i] - 3.5) * 0.105, values[i], width=0.105,
                  color=color, edgecolor="none", linewidth=0,
                  label=label, zorder=3)
    handles.append(Patch(facecolor=color, hatch=hatch))
    pattern_bars.extend((bar, hatch) for bar in bars)
# Reserve only the space required by the abbreviated in-plot legend.
ax.set_xlim(-0.55, 2.52)
ax.set_ylim(0, 104)
ax.set_xticks(x, CATEGORIES, fontsize=16)
ax.set_yticks(np.arange(0, 101, 20))
ax.set_xlabel("Data type", labelpad=9)
ax.set_ylabel("Successful delivery ratio (%)", labelpad=8)
ax.set_axisbelow(True)
ax.grid(False)
ax.tick_params(axis="both", labelsize=16, width=1.2, length=4, pad=5)
for spine in ax.spines.values():
    spine.set_color("#2C2C2C")
ax.legend(handles=handles, labels=LABELS, handler_map={Patch: VectorHatchHandler()}, ncol=1,
          loc="upper right", bbox_to_anchor=(0.96, 0.87), fontsize=12,
          handlelength=1.1, handleheight=1.1, handletextpad=0.35,
          labelspacing=0.36, borderaxespad=0, borderpad=0)
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
legend_box = ax.get_legend().get_window_extent(renderer)
legend_left = ax.transData.inverted().transform((legend_box.x0, legend_box.y0))[0]
assert all(not bar.get_window_extent(renderer).overlaps(legend_box)
           for bar, _ in pattern_bars), "Legend intersects a data bar"
for level in ax.get_yticks():
    display_y = ax.transData.transform((0, level))[1]
    line_right = legend_left - 0.025 if legend_box.y0 <= display_y <= legend_box.y1 else ax.get_xlim()[1]
    ax.hlines(level, -0.55, line_right, color="#E8E8E8", linewidth=0.8, zorder=0.5)
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
for bar, pattern in pattern_bars:
    box = bar.get_window_extent(renderer).transformed(fig.dpi_scale_trans.inverted())
    for artist in hatch_artists(box.bounds, pattern, fig.dpi_scale_trans):
        ax.add_artist(artist)
fig.canvas.draw()
assert tuple(fig.get_size_inches()) == (8, 6) and len(fig.axes) == 1
require_matplotlib_panel_alignment(fig, json_out=str(OUT / f"{PREFIX}.alignment.json"),
                                  tolerance_pt=1.5, strict=True)
fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
fig.savefig(OUT / f"{PREFIX}.pdf")
fig.savefig(OUT / f"{PREFIX}.svg")
fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
with (OUT / f"{PREFIX}.source_data.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["Configuration", "Category", "Mean_percent", "Plus_minus_percent"])
    writer.writerows(output_rows)
plt.close(fig)
