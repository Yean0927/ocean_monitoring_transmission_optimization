#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Run real QUIC BBR bulk-send measurements for unique link conditions.

import argparse
import csv
import os
import re
import subprocess
from pathlib import Path


DEFAULT_QUIC_ROOT = Path(os.environ.get("NS3_QUIC_ROOT", str(Path.home() / "ns-allinone-3.32/ns-3.32")))
QUIC_ROOT = DEFAULT_QUIC_ROOT
QUIC_EXP = QUIC_ROOT / "build" / "contrib" / "quic" / "examples" / "ns3.32-quic-variants-comparison-bulksend-debug"
THROUGHPUT_RE = re.compile(r"averageThroughput=([0-9.]+) Mbit/s")


def configure_quic_root(path):
    global QUIC_ROOT, QUIC_EXP
    QUIC_ROOT = Path(path).expanduser().resolve()
    QUIC_EXP = (
        QUIC_ROOT
        / "build"
        / "contrib"
        / "quic"
        / "examples"
        / "ns3.32-quic-variants-comparison-bulksend-debug"
    )


def parse_list(value, cast):
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def parse_scenarios(value):
    scenarios = {}
    for item in value.split(","):
        name, rtt = item.split(":", 1)
        scenarios[name.strip()] = float(rtt)
    return scenarios


def run_command(cmd, cwd, timeout):
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return completed.stdout


def parse_throughput(output):
    match = THROUGHPUT_RE.search(output)
    if not match:
        raise RuntimeError(f"Cannot parse throughput from output:\n{output}")
    return float(match.group(1))


def run_quic(rtt_ms, capacity_mbps, loss_rate, duration, file_size_mb):
    one_way_delay_ms = rtt_ms / 2.0
    args = [
        "--transport_prot=QuicBbr",
        f"--bandwidth={capacity_mbps:g}Mbps",
        f"--delay={one_way_delay_ms:.6f}ms",
        "--access_delay=0ms",
        f"--error_p={loss_rate:g}",
        f"--data={file_size_mb:g}",
        f"--duration={duration:g}",
    ]
    output = run_command([str(QUIC_EXP)] + args, QUIC_ROOT, timeout=max(120, int(duration * 30)))
    return parse_throughput(output), f"cd {QUIC_ROOT} && {' '.join([str(QUIC_EXP)] + args)}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="rtt-80:80,rtt-150:150")
    parser.add_argument("--capacities", default="0.2,0.3,0.5,0.75,1,1.5,2,3,4,5")
    parser.add_argument("--losses", default="0.002,0.005,0.01,0.02,0.04,0.06,0.08,0.12,0.16,0.2")
    parser.add_argument("--file-size-mb", type=float, default=0.2)
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--output", default="02_protocol_evaluation/sample-results/real-anchor-grid-4000/quic-link-grid-results.csv")
    parser.add_argument(
        "--quic-root",
        default=str(DEFAULT_QUIC_ROOT),
        help="Path to the external ns-3.32 QUIC tree. Can also be set with NS3_QUIC_ROOT.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    configure_quic_root(args.quic_root)

    if not QUIC_EXP.exists():
        raise FileNotFoundError(f"QUIC executable not found: {QUIC_EXP}")

    scenarios = parse_scenarios(args.scenarios)
    capacities = parse_list(args.capacities, float)
    losses = parse_list(args.losses, float)
    rows = []
    for scenario, rtt_ms in scenarios.items():
        for capacity in capacities:
            for loss in losses:
                row = {
                    "scenario": scenario,
                    "rtt_ms": rtt_ms,
                    "capacity_mbps": capacity,
                    "packet_loss_rate": loss,
                    "protocol": "QUIC_BBR",
                    "traffic_mode": "quic-bulksend",
                    "file_size_mb": args.file_size_mb,
                    "duration_s": args.duration,
                    "throughput_mbps": "",
                    "status": "ok",
                    "command": "",
                }
                try:
                    throughput, command = run_quic(rtt_ms, capacity, loss, args.duration, args.file_size_mb)
                    row["throughput_mbps"] = f"{throughput:.6f}"
                    row["command"] = command
                    if not args.quiet:
                        print(f"{scenario} QUIC_BBR capacity={capacity:g} loss={loss:g} throughput={throughput:.6f}")
                except Exception as exc:
                    row["status"] = f"failed: {exc}"
                    if not args.quiet:
                        print(f"{scenario} QUIC_BBR capacity={capacity:g} loss={loss:g} failed: {exc}")
                rows.append(row)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"QUIC rows written: {len(rows)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
