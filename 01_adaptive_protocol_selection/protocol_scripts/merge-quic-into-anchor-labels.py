#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Merge real QUIC link measurements into real TCP random-traffic anchor labels.

import argparse
import csv
from pathlib import Path


def key(row):
    return (
        row["scenario"],
        round(float(row["rtt_ms"]), 6),
        round(float(row["capacity_mbps"]), 6),
        round(float(row["packet_loss_rate"]), 6),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchors", required=True)
    parser.add_argument("--quic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    quic_by_key = {}
    with Path(args.quic).open(newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            if row.get("status") == "ok" and row.get("throughput_mbps", ""):
                quic_by_key[key(row)] = float(row["throughput_mbps"])

    merged = []
    with Path(args.anchors).open(newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        if "quic_bbr_mbps" not in fieldnames:
            insert_at = fieldnames.index("best_protocol") if "best_protocol" in fieldnames else len(fieldnames)
            fieldnames.insert(insert_at, "quic_bbr_mbps")
        for row in reader:
            quic = quic_by_key.get(key(row))
            if quic is not None:
                row["quic_bbr_mbps"] = f"{quic:.6f}"
            else:
                row.setdefault("quic_bbr_mbps", "")
            values = {
                "TCP_CUBIC": float(row["tcp_cubic_mbps"]) if row.get("tcp_cubic_mbps") else -1.0,
                "TCP_BBR": float(row["tcp_bbr_mbps"]) if row.get("tcp_bbr_mbps") else -1.0,
                "QUIC_BBR": float(row["quic_bbr_mbps"]) if row.get("quic_bbr_mbps") else -1.0,
            }
            row["best_protocol"] = max(values, key=values.get)
            merged.append(row)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    print(f"Merged rows written: {len(merged)}")
    print(f"QUIC link keys used: {len(quic_by_key)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
