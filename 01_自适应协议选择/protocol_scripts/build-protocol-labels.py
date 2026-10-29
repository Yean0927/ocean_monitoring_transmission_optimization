#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Build a labeled protocol-selection table from per-protocol evaluation rows.

import argparse
import csv
from collections import defaultdict
from pathlib import Path


KEY_FIELDS = [
    "scenario",
    "rtt_ms",
    "capacity_mbps",
    "packet_loss_rate",
    "traffic_mode",
    "packet_size_min",
    "packet_size_max",
    "packet_size_mean",
    "min_send_interval_ms",
    "max_send_interval_ms",
    "mean_send_interval_ms",
    "offered_load_mbps",
    "file_size_mb",
    "duration_s",
]

PROTOCOLS = {"TCP_CUBIC", "TCP_BBR", "QUIC_BBR"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--required-protocols",
        default="",
        help=(
            "Comma-separated protocols that must be present in each labeled condition. "
            "If omitted, all protocols observed in the input are required."
        ),
    )
    args = parser.parse_args()

    groups = defaultdict(dict)
    metadata = {}
    observed_protocols = set()
    with Path(args.input).open(newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            if row.get("status") != "ok" or row.get("throughput_mbps", "") == "":
                continue
            protocol = row.get("protocol", "")
            if protocol not in PROTOCOLS:
                continue
            observed_protocols.add(protocol)
            key = tuple(row.get(field, "") for field in KEY_FIELDS)
            metadata[key] = {field: row.get(field, "") for field in KEY_FIELDS}
            groups[key][protocol] = float(row["throughput_mbps"])

    if args.required_protocols:
        required_protocols = {
            item.strip() for item in args.required_protocols.split(",") if item.strip()
        }
        unknown = required_protocols - PROTOCOLS
        if unknown:
            raise ValueError(f"Unknown required protocols: {sorted(unknown)}")
    else:
        required_protocols = observed_protocols

    fieldnames = KEY_FIELDS + [
        "tcp_cubic_mbps",
        "tcp_bbr_mbps",
        "quic_bbr_mbps",
        "best_protocol",
    ]
    rows = []
    for key in sorted(groups):
        values = groups[key]
        if not required_protocols.issubset(values):
            continue
        candidate_values = {
            protocol: values[protocol]
            for protocol in required_protocols
        }
        if not any(value > 0 for value in candidate_values.values()):
            best_protocol = "NO_DELIVERY"
        else:
            best_protocol = max(candidate_values, key=candidate_values.get)
        row = dict(metadata[key])
        row["tcp_cubic_mbps"] = f"{values['TCP_CUBIC']:.6f}" if "TCP_CUBIC" in values else ""
        row["tcp_bbr_mbps"] = f"{values['TCP_BBR']:.6f}" if "TCP_BBR" in values else ""
        row["quic_bbr_mbps"] = f"{values['QUIC_BBR']:.6f}" if "QUIC_BBR" in values else ""
        row["best_protocol"] = best_protocol
        rows.append(row)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Labeled rows written: {len(rows)}")
    print(f"Required protocols: {','.join(sorted(required_protocols))}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
