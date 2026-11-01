"""Plot each reported outcome in its own fixed 8 x 6 inch figure."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
x = [float(row["Buffer_capacity_MB"]) for row in rows]
loss = [float(row["Data_loss_MB"]) for row in rows]
delivered = [float(row["Delivered_volume_MB"]) for row in rows]
assert len(rows) == 7 and all(a < b for a, b in zip(x, x[1:]))
assert all(value >= 0 for value in loss + delivered)

BLUE = "#0072B2"
ORANGE = "#D55E00"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 14,
    "axes.labelsize": 20,
    "axes.labelweight": "bold",
    "axes.linewidth": 1.8,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.facecolor": "white",
})

series = [
    ("data_loss_8x6", loss, "Data loss (MB)", BLUE, "o", (100, 375), range(100, 351, 50)),
    ("delivered_volume_8x6", delivered, "Delivered volume (MB)", ORANGE, "s",
     (580, 740), range(580, 741, 20)),
]
for prefix, values, ylabel, color, marker, ylim, yticks in series:
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.15, right=0.95, bottom=0.16, top=0.94)
    ax.plot(x, values, color=color, marker=marker, markersize=8.5,
            markeredgewidth=1.5, linewidth=3.0, zorder=3)
    ax.set_xlabel("Buffer capacity (MB)", labelpad=12)
    ax.set_ylabel(ylabel, labelpad=12)
    ax.set_xlim(-5, 125)
    ax.set_xticks(x)
    ax.set_ylim(ylim)
    ax.set_yticks(yticks)
    ax.tick_params(axis="both", width=1.8, length=6, pad=7)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#DEDEDE", linewidth=0.8)
    fig.canvas.draw()
    assert tuple(fig.get_size_inches()) == (8, 6) and len(fig.axes) == 1
    # Preserve exact physical dimensions; keep the full canvas on export.
    fig.savefig(OUT / f"{prefix}.png", dpi=300)
    fig.savefig(OUT / f"{prefix}.pdf")
    fig.savefig(OUT / f"{prefix}.svg")
    fig.savefig(OUT / f"{prefix}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)
