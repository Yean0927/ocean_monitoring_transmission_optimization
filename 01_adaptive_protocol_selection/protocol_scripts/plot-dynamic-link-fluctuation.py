#!/usr/bin/env python3
"""Plot the simulated dynamic submarine-cable link fluctuation profile."""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


PHASES = [
    ("normal start", 0.0, 3.0, "#EEF5FB"),
    ("gradual degradation", 3.0, 24.0, "#DDF2F3"),
    ("bad variable link", 24.0, 42.0, "#C2D0EA"),
    ("gradual recovery", 42.0, 57.0, "#D6EEF1"),
    ("normal end", 57.0, 60.0, "#EEF5FB"),
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smoothstep(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def severity_at(time_min: float) -> tuple[float, str]:
    if time_min < 3.0:
        return 0.05, "normal start"
    if time_min < 24.0:
        return smoothstep((time_min - 3.0) / 21.0), "gradual degradation"
    if time_min < 42.0:
        return 0.78 + 0.18 * math.sin(time_min * 1.7), "bad variable link"
    if time_min < 57.0:
        return 1.0 - smoothstep((time_min - 42.0) / 15.0), "gradual recovery"
    return 0.05, "normal end"


def build_series(seed: int, step_min: float) -> list[dict[str, float | str]]:
    rng = random.Random(seed)
    rows: list[dict[str, float | str]] = []
    count = int(60 / step_min) + 1

    for index in range(count):
        time_min = round(index * step_min, 6)
        severity, phase = severity_at(time_min)
        severity = clamp(severity + rng.uniform(-0.035, 0.035), 0.0, 1.0)

        # Capacity is kept almost fixed in this test-link profile. The main
        # dynamic link symptoms are delay inflation and packet-loss variation.
        capacity_mbps = 2.0
        rtt_ms = clamp(80.0 + severity * 120.0 + rng.uniform(-4.0, 4.0), 75.0, 210.0)
        loss_rate = clamp(0.002 + severity * 0.155 + rng.uniform(-0.008, 0.008), 0.001, 0.18)

        rows.append(
            {
                "time_min": time_min,
                "phase": phase,
                "capacity_mbps": round(capacity_mbps, 3),
                "rtt_ms": round(rtt_ms, 3),
                "packet_loss_rate": round(loss_rate, 6),
                "severity": round(severity, 4),
            }
        )

    return rows


def write_csv(rows: list[dict[str, float | str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time_min",
                "phase",
                "capacity_mbps",
                "rtt_ms",
                "packet_loss_rate",
                "severity",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def scale(value: float, source_min: float, source_max: float, target_min: float, target_max: float) -> float:
    if source_max == source_min:
        return target_min
    ratio = (value - source_min) / (source_max - source_min)
    return target_min + ratio * (target_max - target_min)


def polyline(points: list[tuple[float, float]], color: str, width: float = 3.0) -> str:
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polyline points="{point_text}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" />'
    )


def area(points: list[tuple[float, float]], baseline_y: float, color: str) -> str:
    if not points:
        return ""
    polygon = [(points[0][0], baseline_y), *points, (points[-1][0], baseline_y)]
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in polygon)
    return f'<polygon points="{point_text}" fill="{color}" opacity="0.14" />'


def plot(rows: list[dict[str, float | str]], output: Path) -> None:
    times = [float(row["time_min"]) for row in rows]
    capacities = [float(row["capacity_mbps"]) for row in rows]
    rtts = [float(row["rtt_ms"]) for row in rows]
    losses = [float(row["packet_loss_rate"]) * 100.0 for row in rows]
    severities = [float(row["severity"]) for row in rows]
    width = 1500
    height = 900
    left = 150
    right = 60
    top = 125
    panel_h = 135
    gap = 55
    plot_w = width - left - right
    x_min = 0.0
    x_max = 60.0

    panels = [
        ("Capacity (Mbps)", capacities, 0.0, 2.6, "#0070B8", "Configured bottleneck capacity is fixed"),
        ("RTT (ms)", rtts, 70.0, 220.0, "#00B3B0", ""),
        ("Packet loss (%)", losses, 0.0, 20.0, "#2F8F9D", ""),
        ("Link severity index", severities, 0.0, 1.08, "#005F73", ""),
    ]

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white" />',
        '<text x="750" y="52" text-anchor="middle" font-family="Arial, sans-serif" '
        'font-size="30" font-weight="700" fill="#0F172A">Simulated Dynamic Link Fluctuation for Submarine-Cable Test</text>',
        '<text x="750" y="82" text-anchor="middle" font-family="Arial, sans-serif" '
        'font-size="15" fill="#64748B">Short normal state -> gradual degradation -> variable bad state -> gradual recovery -> normal state</text>',
    ]

    for panel_index, (ylabel, values, y_min, y_max, color, note) in enumerate(panels):
        y_top = top + panel_index * (panel_h + gap)
        y_bottom = y_top + panel_h

        for label, start, end, phase_color in PHASES:
            x_start = scale(start, x_min, x_max, left, left + plot_w)
            x_end = scale(end, x_min, x_max, left, left + plot_w)
            parts.append(
                f'<rect x="{x_start:.2f}" y="{y_top:.2f}" width="{x_end - x_start:.2f}" '
                f'height="{panel_h:.2f}" fill="{phase_color}" opacity="0.78" />'
            )
            if panel_index == 0:
                mid = (x_start + x_end) / 2
                parts.append(
                    f'<text x="{mid:.2f}" y="{y_top - 12:.2f}" text-anchor="middle" '
                    'font-family="Arial, sans-serif" font-size="12" fill="#475569">'
                    f'{label}</text>'
                )

        for tick_ratio in [0.0, 0.25, 0.5, 0.75, 1.0]:
            y = y_bottom - tick_ratio * panel_h
            value = y_min + tick_ratio * (y_max - y_min)
            parts.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" '
                'stroke="#CBD5E1" stroke-width="1" opacity="0.55" />'
            )
            label_text = f"{value:.1f}" if y_max <= 3 else f"{value:.0f}"
            parts.append(
                f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
                'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
                f'{label_text}</text>'
            )

        points = [
            (
                scale(t, x_min, x_max, left, left + plot_w),
                scale(v, y_min, y_max, y_bottom, y_top),
            )
            for t, v in zip(times, values)
        ]
        parts.append(area(points, y_bottom, color))
        parts.append(polyline(points, color))
        parts.append(
            f'<rect x="{left}" y="{y_top}" width="{plot_w}" height="{panel_h}" '
            'fill="none" stroke="#94A3B8" stroke-width="1" />'
        )
        parts.append(
            f'<text x="42" y="{(y_top + y_bottom) / 2:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#334155" '
            f'transform="rotate(-90 42 {(y_top + y_bottom) / 2:.2f})">{ylabel}</text>'
        )
        if note:
            parts.append(
                f'<text x="{left + plot_w - 8}" y="{y_top + 25}" text-anchor="end" '
                'font-family="Arial, sans-serif" font-size="13" fill="#0070B8">'
                f'{note}</text>'
            )

    axis_y = top + 3 * (panel_h + gap) + panel_h
    for minute in [0, 10, 20, 30, 40, 50, 60]:
        x = scale(minute, x_min, x_max, left, left + plot_w)
        parts.append(f'<line x1="{x:.2f}" y1="{axis_y}" x2="{x:.2f}" y2="{axis_y + 7}" stroke="#334155" />')
        parts.append(
            f'<text x="{x:.2f}" y="{axis_y + 25}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="12" fill="#334155">'
            f'{minute}</text>'
        )
    parts.append(
        f'<text x="{left + plot_w / 2:.2f}" y="{axis_y + 52}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#334155">'
        'Simulation time (minutes)</text>'
    )
    parts.append(
        '<text x="70" y="865" font-family="Arial, sans-serif" font-size="13" fill="#64748B">'
        'Interpretation: higher severity means larger RTT and higher packet loss. '
        'This profile is used to test protocol selection under time-varying cable conditions.</text>'
    )
    parts.append("</svg>")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--step-min", type=float, default=0.5)
    parser.add_argument(
        "--output",
        default="sample_results/figures/dynamic-link-fluctuation.svg",
    )
    parser.add_argument(
        "--csv-output",
        default="sample_results/protocol_evaluation/dynamic-link-fluctuation.csv",
    )
    args = parser.parse_args()

    rows = build_series(args.seed, args.step_min)
    output = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    csv_output = ROOT / args.csv_output if not Path(args.csv_output).is_absolute() else Path(args.csv_output)
    write_csv(rows, csv_output)
    plot(rows, output)
    print(output)
    print(csv_output)


if __name__ == "__main__":
    main()
