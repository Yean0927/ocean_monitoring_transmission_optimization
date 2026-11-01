"""Ablation views with fixed-size originals and a compact three-panel variant."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
CONFIGS = ["FULL", "WO_PROTOCOL", "WO_COMPRESSION", "WO_CACHE", "BASELINE",
           "ADD_PROTOCOL", "ADD_COMPRESSION", "ADD_CACHE"]
assert [r["Configuration"] for r in rows] == CONFIGS
LABELS = ["Full", "W/o protocol", "W/o compression", "W/o cache", "Baseline",
          "Add protocol", "Add compression", "Add cache"]
SHORT_LABELS = ["Full", "−Prot.", "−Comp.", "−Cache", "Baseline", "+Prot.",
                "+Comp.", "+Cache"]
success = np.array([float(r["Success_rate_percent"]) for r in rows])
loss = np.array([float(r["Confirmed_loss_percent"]) for r in rows])
time = np.array([float(r["Average_delivery_time_s"]) for r in rows])
assert np.all((success >= 0) & (success <= 100))
assert np.all((loss >= 0) & (loss <= 100)) and np.all(time > 0)
x = np.arange(len(rows))
BLUE, ORANGE, PURPLE = "#0072B2", "#D55E00", "#6F4C9B"
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 13, "axes.labelsize": 20, "axes.labelweight": "bold",
    "axes.linewidth": 1.7, "xtick.labelsize": 12, "ytick.labelsize": 13,
    "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none",
    "savefig.facecolor": "white",
})

def save(fig, prefix, expected_size=(8, 6)):
    fig.canvas.draw()
    assert tuple(fig.get_size_inches()) == expected_size
    # Keep the exact canvas dimensions in every export.
    fig.savefig(OUT / f"{prefix}.png", dpi=300)
    fig.savefig(OUT / f"{prefix}.pdf")
    fig.savefig(OUT / f"{prefix}.svg")
    fig.savefig(OUT / f"{prefix}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)

def style_axis(ax, compact=False, labels=LABELS, tick_angle=90):
    ax.set_xlim(-0.3, 7.3)
    ax.set_xticks(x, labels)
    ax.tick_params(axis="both", width=1.7, length=5, pad=5)
    for label in ax.get_xticklabels():
        label.set_rotation(tick_angle)
        label.set_rotation_mode("anchor")
        label.set_ha("right")
        label.set_va("center" if tick_angle == 90 else "top")
        label.set_fontsize((8 if tick_angle != 90 else 10) if compact else 11.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.8)

# View 1: rates on the left axis; average delivery time on the right.
dual_order = np.array([0, 1, 2, 3, 5, 6, 7, 4])  # move Baseline to the far right
dual_labels = [LABELS[i] for i in dual_order]
fig, left = plt.subplots(figsize=(8, 6))
fig.subplots_adjust(left=0.12, right=0.84, bottom=0.33, top=0.84)
right = left.twinx()
handles = [
    left.plot(x, success[dual_order], color=BLUE, marker="o", linewidth=3, markersize=7.5,
              label="Success Rate", zorder=3)[0],
    left.plot(x, loss[dual_order], color=ORANGE, marker="s", linestyle="--", linewidth=3,
              markersize=7, label="Confirmed Loss", zorder=3)[0],
    right.plot(x, time[dual_order], color=PURPLE, marker="^", linestyle="-.", linewidth=3,
               markersize=8, label="Average delivery time", zorder=3)[0],
]
style_axis(left, labels=dual_labels)
left.set_xlabel("Method", labelpad=13)
left.set_ylabel("Rate (%)", labelpad=10)
left.set_ylim(-4, 105)
left.set_yticks(np.arange(0, 101, 20))
right.set_ylabel("Avg. Latency (s)", color=PURPLE, labelpad=10)
right.set_ylim(-80, 2100)
right.set_yticks(np.arange(0, 2001, 500))
right.tick_params(axis="y", colors=PURPLE, width=1.7, length=5, pad=5)
right.spines["right"].set_color(PURPLE)
right.spines["left"].set_visible(False)
right.spines["top"].set_visible(False)
fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.97),
           ncol=3, columnspacing=1.0, handlelength=2.0,
           handletextpad=0.5, prop={"size": 11.5, "weight": "bold"})
require_matplotlib_panel_alignment(fig, exclude_axes=[right],
    json_out=OUT / "dual_axis_8x6.alignment.json", strict=True)
save(fig, "dual_axis_8x6")

# View 2: horizontally arranged panels with the metric names on the left axes.
metrics = [
    (success, BLUE, "o", "-", "Successful delivery ratio (%)", (-4, 105),
     np.arange(0, 101, 20)),
    (loss, ORANGE, "s", "--", "Confirmed loss (%)", (-4, 105),
     np.arange(0, 101, 20)),
    (time, PURPLE, "^", "-.", "Average delivery time (s)", (-80, 2100),
     np.arange(0, 2001, 500)),
]
def draw_three_panel(size, prefix, bottom, top, title_size, tick_angle=90):
    fig, axes = plt.subplots(1, 3, figsize=size)
    fig.subplots_adjust(left=0.11, right=0.975, bottom=bottom, top=top, wspace=0.75)
    for ax, (values, color, marker, ls, ylabel, limits, ticks) in zip(axes, metrics):
        ax.plot(x, values[dual_order], color=color, marker=marker, linestyle=ls,
                linewidth=3, markersize=6, zorder=3)
        style_axis(ax, compact=True, labels=[SHORT_LABELS[i] for i in dual_order],
                   tick_angle=tick_angle)
        ax.tick_params(axis="y", labelsize=10)
        ax.set_ylim(limits)
        ax.set_yticks(ticks)
        ax.set_xlabel("Method", fontsize=title_size, fontweight="bold", labelpad=10)
        ax.set_ylabel(ylabel, fontsize=title_size, fontweight="bold", labelpad=6)
    require_matplotlib_panel_alignment(fig, json_out=OUT / f"{prefix}.alignment.json",
                                      tolerance_pt=1.5, strict=True)
    save(fig, prefix, expected_size=size)

draw_three_panel((8, 6), "three_panel_8x6", bottom=0.23, top=0.95, title_size=16)
draw_three_panel((8, 3.6), "three_panel_8x3p6", bottom=0.34, top=0.93, title_size=13,
                 tick_angle=40)
