#!/usr/bin/env python3
"""Create a PNG summary figure for model training and performance comparison."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

from PIL import Image, ImageDraw, ImageFont


COLORS = {
    "text": "#0F172A",
    "muted": "#64748B",
    "grid": "#E2E8F0",
    "border": "#CBD5E1",
    "XGBoost": "#0070B8",
    "LightGBM": "#00B3B0",
    "RandomForest": "#2F8F9D",
    "CatBoost": "#3F8BA5",
    "TinyMLP": "#005F73",
    "LinearSVM": "#6B7C93",
    "ContextualBandit-Ridge": "#8AA4BC",
    "Static-TCP_BBR": "#8EDBD9",
    "Static-QUIC_BBR": "#7CB8C0",
    "Static-TCP_CUBIC": "#C2D0EA",
    "Oracle": "#1F2937",
}
METRIC_COLORS = {
    "accuracy": "#0070B8",
    "macro_f1": "#00B3B0",
    "macro_auc": "#2F8F9D",
}

LEARNED_MODELS = [
    "XGBoost",
    "LightGBM",
    "RandomForest",
    "CatBoost",
    "TinyMLP",
    "LinearSVM",
    "ContextualBandit-Ridge",
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    return ImageFont.truetype(path, size=size)


FONT = {
    "title": load_font(32, True),
    "subtitle": load_font(16),
    "h": load_font(22, True),
    "body": load_font(15),
    "small": load_font(13),
    "small_bold": load_font(13, True),
    "tiny": load_font(11),
}


def read_metrics(path: Path) -> list[dict[str, float | str]]:
    rows = []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            parsed: dict[str, float | str] = {"model": row["model"]}
            for key, value in row.items():
                if key != "model":
                    parsed[key] = float(value)
            rows.append(parsed)
    return rows


def center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font, fill: str) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = box[0] + (box[2] - box[0] - (bbox[2] - bbox[0])) / 2
    y = box[1] + (box[3] - box[1] - (bbox[3] - bbox[1])) / 2
    draw.text((x, y), text, font=font, fill=fill)


def bar_y(value: float, low: float, high: float, y0: int, y1: int) -> float:
    ratio = (value - low) / (high - low)
    return y1 - ratio * (y1 - y0)


def draw_pipeline(draw: ImageDraw.ImageDraw) -> None:
    cards = [
        ("Measured anchors", "3999 complete scenarios"),
        ("Training dataset", "12000 jittered samples"),
        ("Train / test split", "7200 train, 2400 test"),
        ("Candidate models", "LightGBM, XGBoost, RF, SVM, TinyMLP"),
        ("Decision output", "select best reliable protocol"),
    ]
    x = 70
    y = 125
    w = 265
    h = 82
    gap = 20
    for index, (title, subtitle) in enumerate(cards):
        cx = x + index * (w + gap)
        draw.rounded_rectangle((cx, y, cx + w, y + h), radius=8, fill="#F8FAFC", outline=COLORS["border"], width=1)
        draw.text((cx + 18, y + 20), title, font=FONT["body"], fill=COLORS["text"])
        draw.text((cx + 18, y + 50), subtitle, font=FONT["small"], fill=COLORS["muted"])
        if index < len(cards) - 1:
            ax = cx + w + 5
            ay = y + h // 2
            draw.line((ax, ay, cx + w + gap - 6, ay), fill=COLORS["muted"], width=2)
            draw.polygon([(cx + w + gap - 6, ay), (cx + w + gap - 18, ay - 6), (cx + w + gap - 18, ay + 6)], fill=COLORS["muted"])


def draw_classification_metrics(draw: ImageDraw.ImageDraw, rows: list[dict[str, float | str]]) -> None:
    x0, y0, w, h = 80, 300, 700, 310
    draw.text((x0, y0 - 38), "Classification quality", font=FONT["h"], fill=COLORS["text"])
    learned = [row for row in rows if row["model"] in LEARNED_MODELS]
    learned.sort(key=lambda row: float(row["macro_f1"]), reverse=True)
    metrics = [
        ("accuracy", "Acc", METRIC_COLORS["accuracy"]),
        ("macro_f1", "F1", METRIC_COLORS["macro_f1"]),
        ("macro_auc", "AUC", METRIC_COLORS["macro_auc"]),
    ]
    px0, py0 = x0 + 58, y0 + 20
    px1, py1 = x0 + w, y0 + h - 56
    for tick in [0.4, 0.6, 0.8, 1.0]:
        yy = int(bar_y(tick, 0.35, 1.0, py0, py1))
        draw.line((px0, yy, px1, yy), fill=COLORS["grid"], width=1)
        draw.text((px0 - 38, yy - 8), f"{tick:.1f}", font=FONT["tiny"], fill=COLORS["muted"])
    group_w = (px1 - px0) / len(learned)
    bw = 13
    for i, row in enumerate(learned):
        center = px0 + i * group_w + group_w / 2
        for j, (key, _label, color) in enumerate(metrics):
            value = float(row[key])
            yy = bar_y(value, 0.35, 1.0, py0, py1)
            bx = center - 1.5 * bw + j * bw
            draw.rounded_rectangle((bx, yy, bx + bw - 2, py1), radius=3, fill=color)
        label = str(row["model"]).replace("ContextualBandit-Ridge", "Bandit")
        draw.text((center - 34, py1 + 10), label, font=FONT["tiny"], fill="#334155")
    for j, (_key, label, color) in enumerate(metrics):
        lx = x0 + 420 + j * 86
        draw.rounded_rectangle((lx, y0 - 32, lx + 14, y0 - 18), radius=3, fill=color)
        draw.text((lx + 20, y0 - 33), label, font=FONT["tiny"], fill=COLORS["muted"])


def draw_throughput(draw: ImageDraw.ImageDraw, rows: list[dict[str, float | str]]) -> None:
    x0, y0, w, h = 850, 300, 660, 310
    draw.text((x0, y0 - 38), "Selected throughput", font=FONT["h"], fill=COLORS["text"])
    by_model = {str(row["model"]): row for row in rows}
    oracle = max(float(row["avg_oracle_mbps"]) for row in rows)
    values = [
        ("Oracle", oracle),
        ("LightGBM", float(by_model["LightGBM"]["avg_selected_mbps"])),
        ("XGBoost", float(by_model["XGBoost"]["avg_selected_mbps"])),
        ("RandomForest", float(by_model["RandomForest"]["avg_selected_mbps"])),
        ("TCP BBR", float(by_model["Static-TCP_BBR"]["avg_selected_mbps"])),
        ("QUIC BBR", float(by_model["Static-QUIC_BBR"]["avg_selected_mbps"])),
        ("TCP CUBIC", float(by_model["Static-TCP_CUBIC"]["avg_selected_mbps"])),
    ]
    px0, py0 = x0 + 60, y0 + 20
    px1, py1 = x0 + w, y0 + h - 56
    for tick in [0.0, 0.2, 0.4, 0.5]:
        yy = int(bar_y(tick, 0.0, 0.52, py0, py1))
        draw.line((px0, yy, px1, yy), fill=COLORS["grid"], width=1)
        draw.text((px0 - 38, yy - 8), f"{tick:.1f}", font=FONT["tiny"], fill=COLORS["muted"])
    gap = 14
    bw = (px1 - px0 - gap * (len(values) - 1)) / len(values)
    for i, (name, value) in enumerate(values):
        bx = px0 + i * (bw + gap)
        yy = bar_y(value, 0.0, 0.52, py0, py1)
        color = COLORS.get(name, COLORS.get(f"Static-{name.replace(' ', '_')}", "#94A3B8"))
        draw.rounded_rectangle((bx, yy, bx + bw, py1), radius=6, fill=color)
        center_text(draw, (int(bx), int(yy - 24), int(bx + bw), int(yy - 4)), f"{value:.3f}", FONT["small_bold"], COLORS["text"])
        center_text(draw, (int(bx - 10), py1 + 6, int(bx + bw + 10), py1 + 38), name, FONT["tiny"], "#334155")
    draw.text((x0 + 4, y0 + h - 26), "Mbit/s", font=FONT["small_bold"], fill=COLORS["muted"])


def draw_oracle_gap(draw: ImageDraw.ImageDraw, rows: list[dict[str, float | str]]) -> None:
    x0, y0, w, h = 80, 700, 1430, 185
    draw.text((x0, y0 - 38), "Oracle gap ranking", font=FONT["h"], fill=COLORS["text"])
    learned = [row for row in rows if row["model"] in LEARNED_MODELS]
    learned.sort(key=lambda row: float(row["oracle_gap_mbps"]))
    max_gap = max(float(row["oracle_gap_mbps"]) for row in learned)
    label_w = 170
    px0, px1 = x0 + label_w, x0 + w
    row_h = 23
    for i, row in enumerate(learned):
        model = str(row["model"])
        gap = float(row["oracle_gap_mbps"])
        yy = y0 + i * row_h
        name = model.replace("ContextualBandit-Ridge", "Bandit")
        draw.text((x0, yy + 4), name, font=FONT["small"], fill="#334155")
        bw = (gap / max_gap) * (px1 - px0)
        draw.rounded_rectangle((px0, yy + 5, px0 + bw, yy + 19), radius=3, fill=COLORS.get(model, "#64748B"))
        draw.text((px0 + bw + 8, yy + 2), f"{gap:.3f}", font=FONT["small_bold"], fill=COLORS["text"])
    draw.text((x0, y0 + h - 10), "Lower is better. Oracle gap = oracle throughput - selected throughput.", font=FONT["small"], fill=COLORS["muted"])


def make_png(rows: list[dict[str, float | str]], output: Path) -> None:
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    center_text(draw, (0, 28, 1600, 70), "Model Training and Performance Comparison", FONT["title"], COLORS["text"])
    center_text(
        draw,
        (0, 78, 1600, 108),
        "Adaptive protocol selector trained from random-interval ns-3 evaluation samples",
        FONT["subtitle"],
        COLORS["muted"],
    )
    draw_pipeline(draw)
    draw.line((60, 246, 1540, 246), fill=COLORS["grid"], width=2)
    draw_classification_metrics(draw, rows)
    draw_throughput(draw, rows)
    draw.line((60, 650, 1540, 650), fill=COLORS["grid"], width=2)
    draw_oracle_gap(draw, rows)
    draw.text(
        (80, 950),
        "Key result: XGBoost has the best Macro F1; LightGBM has the best selected throughput and smallest oracle gap.",
        font=FONT["body"],
        fill="#334155",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="sample_results/model_results/model-metrics.csv",
    )
    parser.add_argument(
        "--output",
        default="sample_results/figures/model-training-performance-summary.png",
    )
    args = parser.parse_args()
    input_path = ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input)
    output_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    make_png(read_metrics(input_path), output_path)
    print(output_path)


if __name__ == "__main__":
    main()
