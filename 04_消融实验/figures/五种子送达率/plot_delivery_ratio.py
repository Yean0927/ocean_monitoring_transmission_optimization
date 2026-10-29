"""Compute byte-weighted category delivery rates from all five repeated seeds."""
from pathlib import Path
import csv
import json
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
INPUT = OUT.parents[1] / "system-ablation-20260928-table-rates" / "validation" / "repeated-five-seeds-20261015"
SEEDS = tuple(range(31, 36))
VARIANTS = ["FULL", "BASELINE", "WO_PROTOCOL", "WO_COMPRESSION", "WO_CACHE",
            "ADD_PROTOCOL", "ADD_COMPRESSION", "ADD_CACHE"]
LABELS = ["Full", "Baseline", "− protocol", "− compression", "− cache",
          "+ protocol", "+ compression", "+ cache"]
COLORS = ["#006D7C", "#C6D2E5", "#10AFA9", "#34909C", "#52A66B",
          "#74BFE8", "#92AAB8", "#AAB7D3"]
CATEGORIES = {"Text": ("D1", "D2", "D3", "D4"), "Video": ("V1",), "Image": ("I1",)}


def write_csv(filename, rows):
    with (OUT / filename).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


counts = []
source_rows = []
for seed in SEEDS:
    with (INPUT / f"seed-{seed}" / "by-stream.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    lookup = {(row["variant"], row["stream"]): row for row in rows}
    assert len(rows) == len(lookup) == 48
    for variant in VARIANTS:
        for category, streams in CATEGORIES.items():
            generated = sum(int(lookup[variant, stream]["generated_raw_bytes"]) for stream in streams)
            delivered = sum(int(lookup[variant, stream]["delivered_raw_equivalent_bytes"]) for stream in streams)
            assert generated > 0 and 0 <= delivered <= generated
            counts.append(dict(seed=seed, variant=variant, category=category,
                               generated_raw_bytes=generated, delivered_raw_equivalent_bytes=delivered,
                               success_pct=100 * delivered / generated))
        for stream in ("D1", "D2", "D3", "D4", "V1", "I1"):
            row = lookup[variant, stream]
            source_rows.append(dict(seed=seed, variant=variant, stream=stream,
                                   generated_raw_bytes=int(row["generated_raw_bytes"]),
                                   delivered_raw_equivalent_bytes=int(row["delivered_raw_equivalent_bytes"])))
assert len(counts) == 120 and len(source_rows) == 240
write_csv("source_stream_counts.csv", source_rows)
write_csv("category_rates_per_seed.csv", counts)

summary = []
values = np.zeros((8, 3))
for i, variant in enumerate(VARIANTS):
    for j, category in enumerate(CATEGORIES):
        group = [r for r in counts if r["variant"] == variant and r["category"] == category]
        assert len(group) == 5
        assert len({r["generated_raw_bytes"] for r in group}) == 1
        percentages = [r["success_pct"] for r in group]
        generated = sum(r["generated_raw_bytes"] for r in group)
        delivered = sum(r["delivered_raw_equivalent_bytes"] for r in group)
        mean = statistics.mean(percentages)
        pooled = 100 * delivered / generated
        assert abs(mean - pooled) < 1e-10
        values[i, j] = mean
        summary.append(dict(variant=variant, category=category, n_seeds=5,
                            generated_raw_bytes_per_seed=group[0]["generated_raw_bytes"],
                            generated_raw_bytes_five_seeds=generated,
                            delivered_raw_equivalent_bytes_five_seeds=delivered,
                            mean_success_pct=mean, sd_success_pct=statistics.stdev(percentages),
                            pooled_success_pct=pooled))
write_csv("category_delivery_summary.csv", summary)
lookup = {(r["variant"], r["category"]): r for r in summary}
notes = ["# 各类数据成功送达率", "", "结果为种子 31–35 的均值 ± 样本标准差，单位为 %。观察终点为 3600 s。", "",
         "文本先合并 D1–D4 的原始等价成功送达字节数和源端生成字节数，再计算比例；视频和图像分别按 V1、I1 的原始等价字节数计算。", "",
         "$$R_{s,v,c}=100\\%\\times\\frac{\\sum_{k\\in c}D_{s,v,k}}{\\sum_{k\\in c}G_{s,v,k}}$$", "",
         "成功送达表示在截止前完成完整文件接收、校验及解压缩。每类数据在所有组与种子中的生成字节数相同，因此五次比例的算术平均等于合并五次送达字节数后计算的比例。未使用 D1–D4 百分比的简单平均。", "",
         "| Group | Text (%) | Video (%) | Image (%) |", "|:--|--:|--:|--:|"]
for variant, label in zip(VARIANTS, LABELS):
    cells = [f"{lookup[variant, c]['mean_success_pct']:.2f} ± {lookup[variant, c]['sd_success_pct']:.2f}" for c in CATEGORIES]
    notes.append("| " + " | ".join([label] + cells) + " |")
notes.extend(["", "每次实验生成字节数：文本 23,106,262 B；视频 750,530,274 B；图像 186,273,685 B。", "",
              "柱状图每根柱表示五次均值，各数据类型内按送达率降序排列。为匹配提供的密集柱状图样式，图中未叠加误差棒；完整标准差保留在本表及 CSV 中。未进行显著性检验。"])
(OUT / "delivery_rates.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10, "axes.labelsize": 16, "axes.labelweight": "bold",
    "axes.linewidth": 1, "pdf.fonttype": 42, "svg.fonttype": "none",
    "legend.frameon": False, "savefig.facecolor": "white",
})
fig, ax = plt.subplots(figsize=(8, 6))
fig.subplots_adjust(left=0.135, right=0.985, bottom=0.135, top=0.83)
x = np.arange(3)
order = np.argsort(-values, axis=0, kind="stable")
ranks = np.argsort(order, axis=0)
width = 0.102
bar_order = []
for i, (variant, label, color) in enumerate(zip(VARIANTS, LABELS, COLORS)):
    positions = x + (ranks[i] - 3.5) * width
    bars = ax.bar(positions, values[i], width=width, color=color,
                  edgecolor="#35434D", linewidth=0.55, zorder=3)
    for j, (bar, value) in enumerate(zip(bars, values[i])):
        ax.annotate(f"{value:.2f}", (bar.get_x() + bar.get_width()/2, value),
                    xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                    fontsize=6.4, fontweight="bold", color="#22313C", zorder=4)
        bar_order.append(dict(category=list(CATEGORIES)[j], rank=int(ranks[i,j])+1,
                              variant=variant, mean_success_pct=float(value)))
write_csv("bar_order.csv", bar_order)
ax.set_xlim(-0.52, 2.52)
ax.set_ylim(0, 107)
ax.set_xticks(x, list(CATEGORIES), fontsize=15, fontweight="bold")
ax.set_yticks(np.arange(0, 101, 20))
ax.tick_params(axis="y", labelsize=13)
ax.set_xlabel("Data type", labelpad=9)
ax.set_ylabel("Successful delivery ratio (%)", labelpad=8)
ax.set_axisbelow(True)
ax.grid(False)
ax.spines[["top", "right"]].set_visible(False)
handles = [Patch(facecolor=color, edgecolor="#35434D", linewidth=0.55) for color in COLORS]
fig.legend(handles, LABELS, loc="upper center", bbox_to_anchor=(0.56, 0.985),
           ncol=4, fontsize=10.5, handlelength=1, handleheight=1,
           handletextpad=0.45, columnspacing=1.35, labelspacing=0.65)
fig.text(0.985, 0.85, "Mean of 5 seeds", ha="right", va="bottom", fontsize=8, color="#505050")
fig.canvas.draw()
require_matplotlib_panel_alignment(fig, json_out=str(OUT / "delivery_ratio.alignment.json"),
                                  tolerance_pt=1.5, strict=True)
fig.savefig(OUT / "delivery_ratio.pdf")
fig.savefig(OUT / "delivery_ratio.svg")
fig.savefig(OUT / "delivery_ratio.png", dpi=300)
fig.savefig(OUT / "delivery_ratio.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
plt.close(fig)
(OUT / "figure_contract.json").write_text(json.dumps({
    "question": "How does delivery success vary across data categories and ablation configurations?",
    "claim": "Category delivery rates vary by configuration; all comparisons use actual delivered and generated raw-equivalent bytes.",
    "archetype": "quantitative grid", "backend": "python", "dimensions_inches": [8, 6],
    "statistic": "mean across five seeds; sample SD supplied in companion table",
    "data_integrity": "All 240 stream summaries used; no exclusions; text pools D1-D4 bytes before division.",
    "reuse": "Style-only inheritance from the supplied bar chart; statistics recomputed from current repeated runs.",
    "uncertainty_exemption": "Dense reference-style bars show means; all SDs provided in the adjacent table and CSV.",
    "risk": "Large seed variation makes mean-only bars insufficient for significance claims.",
}, indent=2) + "\n")
print((OUT / "delivery_rates.md").read_text())
