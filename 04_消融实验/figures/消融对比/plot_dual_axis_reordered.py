"""Dual-axis ablation means using the shared descending-success order."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
PREFIX = "dual_axis_8x6_reordered"
ORDER = ["FULL", "WO_CACHE", "WO_PROTOCOL", "ADD_COMPRESSION",
         "WO_COMPRESSION", "ADD_PROTOCOL", "ADD_CACHE", "BASELINE"]
LABELS = ["Full", "−Buffer", "−Prot.", "+Comp.", "−Comp.", "+Prot.",
          "+Buffer", "Baseline"]
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    source_rows = list(csv.DictReader(handle))
by_configuration = {row["Configuration"]: row for row in source_rows}
assert len(by_configuration) == len(source_rows) == len(ORDER) == 8
assert set(ORDER) == set(by_configuration)
rows = [by_configuration[configuration] for configuration in ORDER]
success = np.array([float(row["Success_rate_percent"]) for row in rows])
loss = np.array([float(row["Confirmed_loss_percent"]) for row in rows])
time = np.array([float(row["Average_delivery_time_s"]) for row in rows])
assert np.all((success >= 0) & (success <= 100))
assert np.all((loss >= 0) & (loss <= 100)) and np.all(time > 0)
assert np.all(np.diff(success) <= 0)
x = np.arange(len(rows))
BLUE, ORANGE, PURPLE = "#0072B2", "#D55E00", "#6F4C9B"
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 13, "axes.labelsize": 20, "axes.labelweight": "bold",
    "axes.linewidth": 1.7, "xtick.labelsize": 12, "ytick.labelsize": 13,
    "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none",
    "savefig.facecolor": "white",
})
fig, left = plt.subplots(figsize=(8, 6))
fig.subplots_adjust(left=0.12, right=0.84, bottom=0.21, top=0.84)
right = left.twinx()
handles = [
    left.plot(x, success, color=BLUE, marker="o", linewidth=3, markersize=7.5,
              label="Success Rate", zorder=3)[0],
    left.plot(x, loss, color=ORANGE, marker="s", linestyle="--", linewidth=3,
              markersize=7, label="Confirmed Loss", zorder=3)[0],
    right.plot(x, time, color=PURPLE, marker="^", linestyle="-.", linewidth=3,
               markersize=8, label="Average delivery time", zorder=3)[0],
]
left.set_xlim(-0.3, 7.3)
left.set_xticks(x, LABELS)
left.tick_params(axis="both", width=1.7, length=5, pad=5)
for tick in left.get_xticklabels():
    tick.set_rotation(40)
    tick.set_rotation_mode("anchor")
    tick.set_ha("right")
    tick.set_va("top")
left.set_xlabel("Method", labelpad=12)
left.set_ylabel("Rate (%)", labelpad=10)
left.set_ylim(-4, 105)
left.set_yticks(np.arange(0, 101, 20))
left.spines["top"].set_visible(False)
left.spines["right"].set_visible(False)
left.set_axisbelow(True)
left.grid(axis="y", color="#E0E0E0", linewidth=0.8)
right.set_ylabel("Avg. Latency (s)", color=PURPLE, labelpad=10)
right.set_ylim(-80, 2100)
right.set_yticks(np.arange(0, 2001, 500))
right.tick_params(axis="y", colors=PURPLE, width=1.7, length=5, pad=5)
right.spines["right"].set_color(PURPLE)
right.spines["left"].set_visible(False)
right.spines["top"].set_visible(False)
fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.97),
           ncol=3, columnspacing=1.0, handlelength=2.0, handletextpad=0.5,
           prop={"size": 11.5, "weight": "bold"})
fig.canvas.draw()
assert tuple(fig.get_size_inches()) == (8, 6)
require_matplotlib_panel_alignment(fig, exclude_axes=[right],
    json_out=OUT / f"{PREFIX}.alignment.json", strict=True)
fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
fig.savefig(OUT / f"{PREFIX}.pdf")
fig.savefig(OUT / f"{PREFIX}.svg")
fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
plt.close(fig)
