#!/usr/bin/env python3
"""Aggregate per-seed system-ablation summaries as mean and sample SD."""
from collections import defaultdict
import csv
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
SEEDS = (31, 32, 33, 34, 35)

for source_name, output_name in (("summary.csv", "summary-across-seeds.csv"),
                                ("by-stream.csv", "by-stream-across-seeds.csv")):
    grouped = defaultdict(lambda: defaultdict(list))
    keys = None
    for seed in SEEDS:
        path = HERE / f"seed-{seed}" / source_name
        if not path.exists():
            raise SystemExit(f"Missing completed seed summary: {path}")
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            keys = reader.fieldnames
            for row in reader:
                key = (row["variant"], row["stream"])
                for field, value in row.items():
                    if field in ("variant", "stream") or value == "":
                        continue
                    try:
                        grouped[key][field].append(float(value))
                    except ValueError:
                        continue
    out_fields = ["variant", "stream", "n_seeds"]
    for field in keys or []:
        if field not in ("variant", "stream"):
            out_fields.extend((f"mean_{field}", f"sd_{field}"))
    with (HERE / output_name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for key in sorted(grouped):
            row = {"variant": key[0], "stream": key[1], "n_seeds": len(SEEDS)}
            for field, values in grouped[key].items():
                row[f"mean_{field}"] = statistics.mean(values)
                row[f"sd_{field}"] = statistics.stdev(values) if len(values) > 1 else 0.0
            writer.writerow(row)
    print(f"Wrote {output_name}")
