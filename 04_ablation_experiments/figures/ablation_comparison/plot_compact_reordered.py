"""Compact ablation comparison with one shared success-rate ranking."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
PREFIX = "three_panel_8x3p6_reordered"
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    source_rows = list(csv.DictReader(handle))

# Apply one explicit descending-success order to every metric, without smoothing.
rows = sorted(source_rows, key=lambda row: float(row["Success_rate_percent"]), reverse=True)
ORDER = [row["Configuration"] for row in rows]
assert len(set(ORDER)) == len(source_rows) == 8
assert ORDER[-1] == "BASELINE"
label_map = {
    "FULL": "Full", "WO_PROTOCOL": "−Prot.", "WO_COMPRESSION": "−Comp.",
    "WO_CACHE": "−Cache", "BASELINE": "Baseline", "ADD_PROTOCOL": "+Prot.",
    "ADD_COMPRESSION": "+Comp.", "ADD_CACHE": "+Cache",
}
labels = [label_map[configuration] for configuration in ORDER]
x = np.arange(len(rows))
success = np.array([float(row["Success_rate_percent"]) for row in rows])
loss = np.array([float(row["Confirmed_loss_percent"]) for row in rows])
time = np.array([float(row["Average_delivery_time_s"]) for row in rows])
assert np.all((success >= 0) & (success <= 100))
assert np.all((loss >= 0) & (loss <= 100)) and np.all(time > 0)
assert np.all(np.diff(success) <= 0)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "axes.labelsize": 13, "axes.labelweight": "bold",
    "axes.linewidth": 1.7, "xtick.labelsize": 8, "ytick.labelsize": 10,
    "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none",
    "savefig.facecolor": "white",
})
metrics = [
    (success, "#0072B2", "o", "-", "Successful delivery ratio (%)", (-4, 105),
     np.arange(0, 101, 20)),
    (loss, "#D55E00", "s", "--", "Confirmed loss (%)", (-4, 105),
     np.arange(0, 101, 20)),
    (time, "#6F4C9B", "^", "-.", "Average delivery time (s)", (-80, 2100),
     np.arange(0, 2001, 500)),
]
fig, axes = plt.subplots(1, 3, figsize=(8, 3.6))
fig.subplots_adjust(left=0.11, right=0.975, bottom=0.34, top=0.93, wspace=0.75)
for ax, (values, color, marker, linestyle, ylabel, limits, ticks) in zip(axes, metrics):
    ax.plot(x, values, color=color, marker=marker, linestyle=linestyle,
            linewidth=3, markersize=6, zorder=3)
    ax.set_xlim(-0.3, 7.3)
    ax.set_xticks(x, labels)
    ax.tick_params(axis="both", width=1.7, length=5, pad=5)
    for tick in ax.get_xticklabels():
        tick.set_rotation(40)
        tick.set_rotation_mode("anchor")
        tick.set_ha("right")
        tick.set_va("top")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.8)
    ax.set_ylim(limits)
    ax.set_yticks(ticks)
    ax.set_xlabel("Method", fontsize=13, fontweight="bold", labelpad=10)
    ax.set_ylabel(ylabel, fontsize=13, fontweight="bold", labelpad=6)

fig.canvas.draw()
assert tuple(fig.get_size_inches()) == (8, 3.6)
require_matplotlib_panel_alignment(fig, json_out=OUT / f"{PREFIX}.alignment.json",
                                  tolerance_pt=1.5, strict=True)
fig.savefig(OUT / f"{PREFIX}.png", dpi=300)
fig.savefig(OUT / f"{PREFIX}.pdf")
fig.savefig(OUT / f"{PREFIX}.svg")
fig.savefig(OUT / f"{PREFIX}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
plt.close(fig)

# Preserve all supplied mean columns in a copy reflecting the display order.
with (OUT / "source_data_reordered.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print("Display order:", " → ".join(ORDER))
