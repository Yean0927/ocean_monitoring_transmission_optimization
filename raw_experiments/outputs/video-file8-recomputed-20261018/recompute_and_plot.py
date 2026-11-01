#!/usr/bin/env python3
"""Recompute file 8 from all new technical repeats and audit collinearity."""
from pathlib import Path
import csv
import json
import math
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
VIDEO = "5cf7af68d381d7cb80e5567444e894c2.mp4"
BANDS = (2.0, 4.0, 10.0)
STYLES = {
    "S0": ("S0 original direct", "#6B7280", "o"),
    "S1": ("S1 H.264 lower bitrate", "#2563EB", "s"),
    "S2": ("S2 H.265/HEVC", "#10B981", "^"),
    "S3": ("S3 AV1", "#F59E0B", "D"),
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name, rows):
    with (HERE / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def calculate():
    raw = read_csv(HERE / "measurements/compression_measurements.csv")
    assert len(raw) == 12
    assert all(r["video_name"] == VIDEO and r["integrity"] == "pass"
               and r["status"] == "ok" for r in raw)
    summary = {r["algorithm"]: r for r in read_csv(
        HERE / "measurements/average_compression_results.csv")}
    existing = {(r["algorithm"], float(r["bandwidth_mbps"])): r
                for r in read_csv(HERE / "measurements/end_to_end_results.csv")}
    source, parameters, checks = [], [], []
    for algorithm in STYLES:
        repeats = [r for r in raw if r["algorithm"] == algorithm]
        assert sorted(int(r["repeat"]) for r in repeats) == [1, 2, 3]
        sizes = {int(r["source_size_bytes"]) for r in repeats}
        assert len(sizes) == 1
        original = sizes.pop()
        output = statistics.fmean(float(r["output_size_bytes"]) for r in repeats)
        encode = statistics.fmean(float(r["compression_time_ms"]) for r in repeats) / 1000
        decode = statistics.fmean(float(r["decompression_time_ms"]) for r in repeats) / 1000
        for key, value in [("avg_output_size_bytes", output),
                           ("avg_compression_time_ms", encode * 1000),
                           ("avg_decompression_time_ms", decode * 1000)]:
            assert math.isclose(value, float(summary[algorithm][key]), rel_tol=1e-12)
        cost = 0.0 if algorithm == "S0" else encode + decode
        intercept = 100 * (1 - output / original)
        slope = -100 * cost * 1e6 / (8 * original)
        parameters.append(dict(algorithm=algorithm, repeat_count=3,
            original_size_bytes=original, avg_output_size_bytes=output,
            compression_ratio=output / original, avg_encode_s=encode,
            avg_decode_s=decode, encode_sd_s=statistics.stdev(
                float(r["compression_time_ms"]) / 1000 for r in repeats),
            decode_sd_s=statistics.stdev(
                float(r["decompression_time_ms"]) / 1000 for r in repeats),
            effective_processing_s=cost, intercept_pct=intercept,
            slope_percentage_points_per_mbps=slope,
            break_even_mbps=-intercept / slope if slope else ""))
        values = []
        for bandwidth in BANDS:
            direct = original * 8 / (bandwidth * 1e6)
            transfer = output * 8 / (bandwidth * 1e6)
            total = direct if algorithm == "S0" else cost + transfer
            reduction = 100 * (direct - total) / direct
            affine = intercept + slope * bandwidth
            assert abs(reduction - affine) < 1e-10
            assert math.isclose(reduction, float(existing[algorithm, bandwidth][
                "latency_reduction_pct"]), abs_tol=1e-10)
            values.append(reduction)
            source.append(dict(video_name=VIDEO, algorithm=algorithm,
                bandwidth_mbps=bandwidth, packet_size_bytes=4096,
                original_size_bytes=original, avg_output_size_bytes=output,
                avg_encode_s=encode, avg_decode_s=decode,
                T_direct_s=direct, T_transfer_s=transfer, T_total_s=total,
                latency_reduction_pct=reduction,
                data_origin="new_local_measurement_2026_10_18_n3_ideal_transfer"))
        slope24 = (values[1] - values[0]) / 2
        slope410 = (values[2] - values[1]) / 6
        residual = values[1] - (values[0] + (values[2] - values[0]) / 4)
        assert abs(slope24 - slope410) < 1e-10
        checks.append(dict(algorithm=algorithm, slope_2_to_4=slope24,
            slope_4_to_10=slope410, slope_difference=slope24 - slope410,
            middle_point_residual_percentage_points=residual,
            tolerance_percentage_points=1e-10, result="PASS"))
    write_csv("source_data.csv", source)
    write_csv("measurement_parameters.csv", parameters)
    write_csv("linearity_check.csv", checks)
    old = read_csv(HERE.parent / "video-latency-redraw/digitized_plot_data.csv")
    historical = []
    for algorithm in STYLES:
        points = sorted((r for r in old if r["algorithm"] == algorithm),
                        key=lambda r: float(r["bandwidth_mbps"]))
        values = [float(r["latency_reduction_pct"]) for r in points]
        expected = values[0] + (values[2] - values[0]) / 4
        historical.append(dict(algorithm=algorithm,
            old_2_mbps_pct=values[0], old_4_mbps_pct=values[1], old_10_mbps_pct=values[2],
            middle_point_expected_from_endpoints_pct=expected,
            middle_point_residual_percentage_points=values[1] - expected,
            data_origin="historical_digitized_values_not_raw_measurements"))
    write_csv("historical_digitization_audit.csv", historical)
    print(json.dumps({"raw_repeats": len(raw), "integrity_passes": len(raw),
                      "linearity": checks, "parameters": parameters}, indent=2))
    return source


def plot(source):
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "font.size": 16, "axes.labelsize": 20, "axes.labelweight": "bold",
        "axes.linewidth": 1.7, "xtick.labelsize": 16, "ytick.labelsize": 16,
        "pdf.fonttype": 42, "svg.fonttype": "none",
    })
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.subplots_adjust(left=0.18, right=0.97, bottom=0.16, top=0.97)
    for algorithm, (label, color, marker) in STYLES.items():
        subset = [r for r in source if r["algorithm"] == algorithm]
        ax.plot([r["bandwidth_mbps"] for r in subset],
                [r["latency_reduction_pct"] for r in subset],
                color=color, marker=marker, label=label,
                linewidth=3, markersize=8, markeredgewidth=1.2, zorder=3)
    ax.axhline(0, color="#374151", linewidth=2, linestyle="--", alpha=0.65, zorder=4)
    ax.set_xlabel("Bandwidth (Mbps)", labelpad=10)
    ax.set_ylabel("Latency reduction (%)", labelpad=8)
    ax.set_xlim(1.6, 10.4)
    ax.set_ylim(-290, 110)
    ax.set_xticks(BANDS)
    ax.set_yticks([-250, -200, -150, -100, -50, 0, 50, 100])
    ax.tick_params(width=1.7, length=6)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontweight("bold")
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.9, alpha=0.75, zorder=0)
    ax.legend(loc="lower left", bbox_to_anchor=(0.025, 0.025), ncol=2,
              frameon=False, fontsize=12, borderaxespad=0.3, labelspacing=0.5,
              markerscale=0.8, columnspacing=1, handlelength=1.8, handletextpad=0.5)
    fig.canvas.draw()
    (HERE / "file8_latency_recomputed.alignment.json").write_text(json.dumps({
        "verdict": "NOT APPLICABLE", "reason": "Single quantitative panel", "axes": 1}))
    stem = HERE / "file8_latency_recomputed"
    fig.savefig(stem.with_suffix(".png"), dpi=600, facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    plot(calculate())
