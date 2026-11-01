"""Data loss, delivered volume and peak cache occupancy on one MB axis."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
PREFIX = "buffer_capacity_single_axis_8x6"
PLOT_LAYOUT = dict(left=0.15, right=0.985, bottom=0.16, top=0.94)
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
x = [float(row["Buffer_capacity_MB"]) for row in rows]
loss = [float(row["Data_loss_MB"]) for row in rows]
delivered = [float(row["Delivered_volume_MB"]) for row in rows]
peak = [float(row["Peak_buffer_occupancy_MB"]) for row in rows]
assert len(rows) == 7 and x == [0, 20, 40, 60, 80, 100, 120]
assert all(value >= 0 for value in loss + delivered + peak)
assert all(occupied <= capacity for occupied, capacity in zip(peak, x))

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "font.weight": "bold",
    "axes.labelsize": 20, "axes.labelweight": "bold",
    "axes.linewidth": 1.2, "xtick.labelsize": 16, "ytick.labelsize": 16,
    "legend.fontsize": 15, "legend.frameon": False,
    "pdf.fonttype": 42, "svg.fonttype": "none", "savefig.facecolor": "white",
})
fig, ax = plt.subplots(figsize=(8, 6))
fig.subplots_adjust(**PLOT_LAYOUT)
series = [
    (loss, "#0072B2", "o", "-", 8.5, "Data loss"),
    (delivered, "#D55E00", "s", "--", 8, "Delivered volume"),
    (peak, "#6F4C9B", "^", "-.", 9, "Peak cache occupancy"),
]
for values, color, marker, linestyle, size, label in series:
    ax.plot(x, values, color=color, marker=marker, linestyle=linestyle,
            markersize=size, markeredgewidth=1.5, linewidth=3,
            label=label, zorder=3)
ax.set_xlabel("Cache capacity (MB)", labelpad=9)
ax.set_ylabel("Volume (MB)", labelpad=8)
ax.set_xlim(-5, 125)
ax.set_xticks(x)
ax.set_ylim(-20, 800)
ax.set_yticks(range(0, 801, 100))
ax.tick_params(axis="both", labelsize=16, width=1.2, length=4, pad=5)
for spine in ax.spines.values():
    spine.set_visible(True)
    spine.set_color("#2C2C2C")
    spine.set_linewidth(1.2)
ax.set_axisbelow(True)
ax.grid(axis="y", color="#DEDEDE", linewidth=0.8)
# Position the legend in the gap between delivered volume and the lower curves.
ax.legend(loc="center right", bbox_to_anchor=(0.98, 0.57), ncol=1,
          handlelength=2, handletextpad=0.5, markerscale=1, frameon=True,
          facecolor="white", edgecolor="none", framealpha=1,
          borderpad=0.5, labelspacing=1.1,
          prop={"size": 15, "weight": "bold"})
fig.canvas.draw()
assert tuple(fig.get_size_inches()) == (8, 6) and len(fig.axes) == 1
require_matplotlib_panel_alignment(fig,
    json_out=OUT / f"{PREFIX}.alignment.json", strict=True)
fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
fig.savefig(OUT / f"{PREFIX}.pdf")
fig.savefig(OUT / f"{PREFIX}.svg")
fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
plt.close(fig)
