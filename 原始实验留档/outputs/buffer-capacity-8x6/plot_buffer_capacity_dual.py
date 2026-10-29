"""Data loss, delivered volume and peak occupancy versus buffer capacity."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
PREFIX = "buffer_capacity_8x6"
PLOT_LAYOUT = dict(left=0.15, right=0.82, bottom=0.16, top=0.94)
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
x = [float(row["Buffer_capacity_MB"]) for row in rows]
loss = [float(row["Data_loss_MB"]) for row in rows]
delivered = [float(row["Delivered_volume_MB"]) for row in rows]
peak = [float(row["Peak_buffer_occupancy_MB"]) for row in rows]
assert len(rows) == 7 and x == [0, 20, 40, 60, 80, 100, 120]
assert all(value >= 0 for value in loss + delivered + peak)
assert all(occupied <= capacity for occupied, capacity in zip(peak, x))

BLUE, ORANGE, PURPLE = "#0072B2", "#D55E00", "#6F4C9B"
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 14, "axes.labelsize": 20, "axes.labelweight": "bold",
    "axes.linewidth": 1.8, "xtick.labelsize": 14, "ytick.labelsize": 14,
    "legend.fontsize": 14, "legend.frameon": False,
    "pdf.fonttype": 42, "svg.fonttype": "none", "savefig.facecolor": "white",
})
fig, left = plt.subplots(figsize=(8, 6))
fig.subplots_adjust(**PLOT_LAYOUT)
right = left.twinx()
loss_line, = left.plot(x, loss, color=BLUE, marker="o", markersize=8.5,
                       markeredgewidth=1.5, linewidth=3, label="Data loss", zorder=3)
delivered_line, = right.plot(x, delivered, color=ORANGE, marker="s", linestyle="--",
                             markersize=8, markeredgewidth=1.5, linewidth=3,
                             label="Delivered volume", zorder=3)
peak_line, = left.plot(x, peak, color=PURPLE, marker="^", linestyle="-.",
                       markersize=9, markeredgewidth=1.5, linewidth=3,
                       label="Peak buffer occupancy", zorder=3)
left.set_xlabel("Buffer capacity (MB)", labelpad=12)
left.set_ylabel("Data loss / peak occupancy (MB)", labelpad=12)
right.set_ylabel("Delivered volume (MB)", color=ORANGE, labelpad=12)
left.set_xlim(-5, 125)
left.set_xticks(x)
left.set_ylim(-10, 380)
left.set_yticks(range(0, 351, 50))
right.set_ylim(580, 760)
right.set_yticks(range(580, 761, 20))
left.tick_params(axis="both", width=1.8, length=6, pad=7)
right.tick_params(axis="y", colors=ORANGE, width=1.8, length=6, pad=7)
right.spines["right"].set_color(ORANGE)
left.spines["right"].set_visible(False)
right.spines["left"].set_visible(False)
left.spines["top"].set_visible(False)
right.spines["top"].set_visible(False)
left.set_axisbelow(True)
left.grid(axis="y", color="#DEDEDE", linewidth=0.8)
right.legend(handles=[loss_line, delivered_line, peak_line], loc="upper right",
             ncol=1, handlelength=2, handletextpad=0.5,
             frameon=True, facecolor="white", edgecolor="none", framealpha=1,
             borderpad=0.6, labelspacing=0.5,
             prop={"size": 12.5, "weight": "bold"})
fig.canvas.draw()
assert tuple(fig.get_size_inches()) == (8, 6)
require_matplotlib_panel_alignment(fig, exclude_axes=[right],
    json_out=OUT / f"{PREFIX}.alignment.json", strict=True)
fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
fig.savefig(OUT / f"{PREFIX}.pdf")
fig.savefig(OUT / f"{PREFIX}.svg")
fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
plt.close(fig)
