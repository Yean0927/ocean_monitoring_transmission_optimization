#!/usr/bin/env python3
"""Generate the deterministic 60 minute link profile as CSV (no graphics)."""
from __future__ import annotations
import argparse
import csv
import math
import random
from pathlib import Path

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=31)
    parser.add_argument('--step-min', type=float, default=0.5)
    parser.add_argument('--csv-output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/dynamic-link-fluctuation.csv')
    args = parser.parse_args()
    if not 0 < args.step_min <= 60:
        parser.error('--step-min must be in (0, 60]')
    write_csv(build_series(args.seed, args.step_min), args.csv_output)

if __name__ == '__main__':
    main()
