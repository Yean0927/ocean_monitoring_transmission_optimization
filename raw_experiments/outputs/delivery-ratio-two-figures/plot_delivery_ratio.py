"""Two grouped-bar comparisons, using the supplied table without aggregation."""
from pathlib import Path
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.collections import LineCollection
from matplotlib.legend_handler import HandlerPatch
import numpy as np
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
DATA_TYPES = ["D1", "D2", "D3", "D4", "V1", "I1"]
with (OUT / "source_data.csv").open(newline="", encoding="utf-8") as handle:
    DATA = {row["Configuration"]: np.array([float(row[key]) for key in DATA_TYPES])
            for row in csv.DictReader(handle)}
assert len(DATA) == 8
assert all(np.isfinite(v).all() and ((v >= 0) & (v <= 100)).all() for v in DATA.values())

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 11,
    "axes.labelsize": 14,
    "xtick.labelsize": 13,
    "ytick.labelsize": 12,
    "axes.linewidth": 0.9,
    "hatch.linewidth": 0.65,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "legend.frameon": False,
    "savefig.facecolor": "white",
})

# Data types keep their visual identities across both comparisons.
STYLES = [
    ("#4E86BC", "/////"),
    ("#8EB9DE", "\\\\\\"),
    ("#AFCEE7", ".."),
    ("#FFD27B", "xx"),
    ("#B6B6B6", ""),
    ("#E87868", "++"),
]

def bounded_pattern(width, height, pattern):
    """Construct actual bounded vector segments, without PDF tiling patterns."""
    if not pattern or width <= 0 or height <= 0:
        return []
    if "." in pattern:
        return [[(max(px - 0.3, 0) / width, py / height),
                 (min(px + 0.3, width) / width, py / height)]
                for px in np.arange(1.5, width, 3)
                for py in np.arange(1.5, height, 3)]
    if "+" in pattern:
        families, spacing = [(1, 0), (0, 1)], 7.0
    elif "x" in pattern:
        families, spacing = [(1, 1), (1, -1)], 10.0
    elif "/" in pattern:
        families, spacing = [(1, -1)], 3.2
    else:
        families, spacing = [(1, 1)], 7.0
    segments = []
    for a, b in families:
        corners = [0, a * width, b * height, a * width + b * height]
        start, stop = min(corners), max(corners)
        for c in np.arange(np.floor(start / spacing) * spacing, stop + spacing, spacing):
            candidates = []
            if b:
                candidates += [(0, c / b), (width, (c - a * width) / b)]
            if a:
                candidates += [(c / a, 0), ((c - b * height) / a, height)]
            points = []
            for px, py in candidates:
                if -1e-8 <= px <= width + 1e-8 and -1e-8 <= py <= height + 1e-8:
                    point = (min(max(px / width, 0), 1), min(max(py / height, 0), 1))
                    if point not in points:
                        points.append(point)
            if len(points) >= 2:
                segments.append(points[:2])
    return segments

class BoundedHatchHandler(HandlerPatch):
    def create_artists(self, legend, orig_handle, xdescent, ydescent,
                       width, height, fontsize, trans):
        artists = super().create_artists(legend, orig_handle, xdescent, ydescent,
                                        width, height, fontsize, trans)
        patch = artists[0]
        pattern = orig_handle.get_hatch()
        patch.set_hatch(None)
        segments = bounded_pattern(width, height, pattern)
        if segments:
            artists.append(LineCollection(segments, colors="white", linewidths=0.65,
                                          transform=patch.get_transform()))
        return artists

def render(prefix, component_prefix, component_label):
    configs = ["FULL", "BASELINE"] + [component_prefix + name for name in
                                      ["PROTOCOL", "COMPRESSION", "CACHE"]]
    labels = ["Full", "Baseline"] + [component_label + "\n" + name for name in
                                    ["protocol", "compression", "cache"]]
    fig, ax = plt.subplots(figsize=(183 / 25.4, 126 / 25.4))
    fig.subplots_adjust(left=0.135, right=0.985, bottom=0.185, top=0.98)
    x = np.arange(len(configs), dtype=float)
    width = 0.125
    matrix = np.stack([DATA[config] for config in configs])
    handles = []
    bars_to_pattern = []
    for i, (label, (color, hatch)) in enumerate(zip(DATA_TYPES, STYLES)):
        bars = ax.bar(x + (i - 2.5) * width, matrix[:, i], width=width,
                      color=color, edgecolor="white", linewidth=0.6,
                      zorder=3, label=label)
        bars_to_pattern.extend((bar, hatch) for bar in bars)
        handles.append(Patch(facecolor=color, edgecolor="white", linewidth=0.6,
                             hatch=hatch, label=label))
    ax.set_xlim(-0.58, len(configs) - 0.42)
    ax.set_ylim(0, 128)
    ax.set_xticks(x, labels, fontsize=9.5)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_xlabel("Experimental settings", labelpad=9)
    ax.set_ylabel("Successful delivery ratio (%)", labelpad=7)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#ECECEC", linewidth=0.7)
    ax.tick_params(axis="both", length=3.5, width=0.8, pad=4)
    for spine in ax.spines.values():
        spine.set_color("#333333")
    # Matplotlib fills legend columns vertically. Reorder only legend handles
    # so the two rows read D1 / D2 / D3, then D4 / V1 / I1.
    order = [0, 3, 1, 4, 2, 5]
    ax.legend(handles=[handles[i] for i in order], ncol=3, loc="upper left",
              bbox_to_anchor=(0.012, 0.996), borderaxespad=0.2,
              fontsize=12, columnspacing=3.4, handlelength=1.55,
              handleheight=1.05, handletextpad=0.45, labelspacing=0.85,
              handler_map={Patch: BoundedHatchHandler()})
    fig.canvas.draw()
    for bar, pattern in bars_to_pattern:
        bbox = bar.get_window_extent()
        segments = bounded_pattern(bbox.width * 72 / fig.dpi,
                                   bbox.height * 72 / fig.dpi, pattern)
        if segments:
            ax.add_collection(LineCollection(segments, colors="white", linewidths=0.65,
                                            transform=bar.get_transform(), zorder=3.1))
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(OUT / f"{prefix}.alignment.json"),
                                      tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f"{prefix}.png", dpi=300)
    fig.savefig(OUT / f"{prefix}.pdf")
    fig.savefig(OUT / f"{prefix}.svg")
    fig.savefig(OUT / f"{prefix}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)

if __name__ == "__main__":
    render("full_baseline_without_settings", "WO_", "Without")
    render("full_baseline_add_settings", "ADD_", "Add")
