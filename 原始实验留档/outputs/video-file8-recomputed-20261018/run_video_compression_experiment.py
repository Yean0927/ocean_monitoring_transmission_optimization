from __future__ import annotations

import argparse
import csv
import math
import os
import re
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts"}
BANDWIDTHS_MBPS = [2.0, 4.0, 10.0]
DEFAULT_PACKET_SIZES = [4096]


@dataclass(frozen=True)
class Scheme:
    code: str
    name: str
    output_codec: str
    role: str
    args: tuple[str, ...]


SCHEMES = [
    Scheme("S0", "original_h264_direct", "source", "baseline", ()),
    Scheme(
        "S1",
        "h264_lower_bitrate",
        "h264",
        "compatibility",
        ("-c:v", "libx264", "-preset", "fast", "-crf", "28", "-pix_fmt", "yuv420p"),
    ),
    Scheme(
        "S2",
        "h265_hevc",
        "hevc",
        "main_compression",
        (
            "-c:v",
            "libx265",
            "-preset",
            "fast",
            "-crf",
            "30",
            "-tag:v",
            "hvc1",
            "-pix_fmt",
            "yuv420p",
        ),
    ),
    Scheme(
        "S3",
        "av1",
        "av1",
        "high_compression_reference",
        (
            "-c:v",
            "libaom-av1",
            "-crf",
            "40",
            "-b:v",
            "0",
            "-cpu-used",
            "8",
            "-row-mt",
            "1",
            "-threads",
            "0",
            "-pix_fmt",
            "yuv420p",
        ),
    ),
]

MEASUREMENT_FIELDS = [
    "video_name",
    "container",
    "source_codec",
    "source_profile",
    "source_width",
    "source_height",
    "source_fps",
    "source_duration_s",
    "source_video_bitrate_kbps",
    "source_total_bitrate_kbps",
    "source_size_bytes",
    "algorithm",
    "scheme_name",
    "repeat",
    "output_codec",
    "output_size_bytes",
    "compression_ratio",
    "compression_time_ms",
    "decompression_time_ms",
    "compression_throughput_MBps",
    "decompression_throughput_MBps",
    "integrity",
    "integrity_note",
    "status",
    "skip_reason",
    "output_path",
]

SUMMARY_FIELDS = [
    "video_name",
    "algorithm",
    "scheme_name",
    "source_size_bytes",
    "source_width",
    "source_height",
    "source_fps",
    "source_duration_s",
    "avg_output_size_bytes",
    "avg_compression_ratio",
    "avg_compression_time_ms",
    "avg_decompression_time_ms",
    "avg_compression_throughput_MBps",
    "avg_decompression_throughput_MBps",
    "std_compression_time_ms",
    "std_decompression_time_ms",
    "integrity_pass_count",
    "repeat_count",
    "status",
]

END_FIELDS = [
    "video_name",
    "algorithm",
    "scheme_name",
    "bandwidth_mbps",
    "compression_scope",
    "packet_size_role",
    "packet_size_bytes",
    "packet_count",
    "T_direct_s",
    "T_transfer_s",
    "T_total_s",
    "latency_reduction_pct",
    "best_flag",
]

END_FIELDS_MS_DETAIL = [
    "video_name",
    "algorithm",
    "scheme_name",
    "bandwidth_mbps",
    "compression_scope",
    "packet_size_role",
    "packet_size_bytes",
    "packet_count",
    "T_direct_ms",
    "T_transfer_ms",
    "T_total_ms",
    "T_direct_s",
    "T_transfer_s",
    "T_total_s",
    "latency_reduction_pct",
    "best_flag",
]


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_int_csv(value: str) -> list[int]:
    parsed = [int(item) for item in parse_csv(value)]
    if not parsed:
        raise ValueError("at least one packet size is required")
    return parsed


def parse_scheme_repeats(value: str) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for item in parse_csv(value):
        if "=" not in item:
            raise ValueError(f"invalid scheme repeat item {item!r}; expected SCHEME=COUNT")
        scheme, count_text = item.split("=", 1)
        scheme = scheme.strip()
        count = int(count_text.strip())
        if count < 1:
            raise ValueError(f"repeat count must be positive for {scheme!r}")
        mapping[scheme] = count
    return mapping


def run_command(cmd: list[str], timeout_s: int | None = None) -> tuple[int, float, str]:
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return proc.returncode, elapsed_ms, proc.stdout


def seconds_from_duration(value: str) -> float | None:
    match = re.search(r"(\d+):(\d+):(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_ffmpeg_probe(output: str) -> dict[str, object]:
    info: dict[str, object] = {
        "container": "",
        "duration_s": None,
        "total_bitrate_kbps": None,
        "video_codec": "",
        "video_profile": "",
        "width": None,
        "height": None,
        "fps": None,
        "video_bitrate_kbps": None,
        "audio_codec": "",
        "audio_bitrate_kbps": None,
    }

    input_match = re.search(r"Input #0,\s*([^,]+(?:,[^,]+)*),\s*from", output)
    if input_match:
        info["container"] = input_match.group(1).strip()

    duration_match = re.search(
        r"Duration:\s*([^,]+),.*?bitrate:\s*(\d+)\s*kb/s", output, re.DOTALL
    )
    if duration_match:
        info["duration_s"] = seconds_from_duration(duration_match.group(1))
        info["total_bitrate_kbps"] = int(duration_match.group(2))

    video_line = next((line.strip() for line in output.splitlines() if " Video: " in line), "")
    if video_line:
        codec_match = re.search(r"Video:\s*([^,\s]+)(?:\s*\(([^)]+)\))?", video_line)
        if codec_match:
            info["video_codec"] = codec_match.group(1)
            info["video_profile"] = codec_match.group(2) or ""
        size_match = re.search(r"(\d{2,5})x(\d{2,5})", video_line)
        if size_match:
            info["width"] = int(size_match.group(1))
            info["height"] = int(size_match.group(2))
        vb_match = re.search(r",\s*(\d+)\s*kb/s", video_line)
        if vb_match:
            info["video_bitrate_kbps"] = int(vb_match.group(1))
        fps_match = re.search(r",\s*([0-9.]+)\s*fps", video_line)
        if fps_match:
            info["fps"] = float(fps_match.group(1))

    audio_line = next((line.strip() for line in output.splitlines() if " Audio: " in line), "")
    if audio_line:
        audio_match = re.search(r"Audio:\s*([^,\s]+)", audio_line)
        if audio_match:
            info["audio_codec"] = audio_match.group(1)
        ab_match = re.search(r",\s*(\d+)\s*kb/s", audio_line)
        if ab_match:
            info["audio_bitrate_kbps"] = int(ab_match.group(1))

    return info


def probe_media(ffmpeg: str, path: Path) -> dict[str, object]:
    returncode, _, output = run_command([ffmpeg, "-hide_banner", "-i", str(path)])
    # ffmpeg returns non-zero when called only for probing; the stderr/stdout content is still valid.
    info = parse_ffmpeg_probe(output)
    info["probe_returncode"] = returncode
    return info


def transcode(ffmpeg: str, source: Path, target: Path, scheme: Scheme) -> tuple[int, float, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_name(f"{target.stem}.tmp{target.suffix}")
    if temp_target.exists():
        temp_target.unlink()
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-nostdin",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        *scheme.args,
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(temp_target),
    ]
    returncode, elapsed_ms, output = run_command(cmd)
    if returncode == 0 and temp_target.exists() and temp_target.stat().st_size > 0:
        temp_target.replace(target)
    elif temp_target.exists():
        temp_target.unlink()
    return returncode, elapsed_ms, output


def decode_to_null(ffmpeg: str, source: Path) -> tuple[int, float, str]:
    null_target = "NUL" if os.name == "nt" else "/dev/null"
    return run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-f",
            "null",
            null_target,
        ]
    )


def save_decode_artifact(ffmpeg: str, source: Path, target_png: Path, target_log: Path, log_text: str) -> None:
    target_png.parent.mkdir(parents=True, exist_ok=True)
    target_log.write_text(log_text, encoding="utf-8", errors="replace")
    run_command(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            str(target_png),
        ]
    )


def mbps(size_bytes: float, elapsed_ms: float) -> float | None:
    if elapsed_ms <= 0:
        return None
    return (size_bytes / (1024 * 1024)) / (elapsed_ms / 1000.0)


def integrity_status(
    source_info: dict[str, object],
    output_info: dict[str, object],
    decode_returncode: int,
    output_path: Path,
) -> tuple[str, str]:
    notes: list[str] = []
    if not output_path.exists() or output_path.stat().st_size <= 0:
        notes.append("output_missing_or_empty")
    if decode_returncode != 0:
        notes.append(f"decode_failed_rc={decode_returncode}")

    source_w, source_h = source_info.get("width"), source_info.get("height")
    output_w, output_h = output_info.get("width"), output_info.get("height")
    if source_w and output_w and source_w != output_w:
        notes.append(f"width_changed:{source_w}->{output_w}")
    if source_h and output_h and source_h != output_h:
        notes.append(f"height_changed:{source_h}->{output_h}")

    source_duration = source_info.get("duration_s")
    output_duration = output_info.get("duration_s")
    if isinstance(source_duration, float) and isinstance(output_duration, float):
        tolerance = max(1.0, source_duration * 0.02)
        if abs(source_duration - output_duration) > tolerance:
            notes.append(f"duration_changed:{source_duration:.2f}->{output_duration:.2f}")

    return ("pass" if not notes else "fail", ";".join(notes))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def measurement_key(row: dict[str, object]) -> tuple[str, str, int]:
    return (str(row["video_name"]), str(row["algorithm"]), int(row["repeat"]))


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return statistics.fmean(vals) if vals else math.nan


def stddev(values: Iterable[float]) -> float:
    vals = list(values)
    return statistics.stdev(vals) if len(vals) > 1 else 0.0


def summarize_measurements(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["video_name"]), str(row["algorithm"])), []).append(row)

    summary: list[dict[str, object]] = []
    for (video_name, algorithm), items in sorted(grouped.items()):
        ok_items = [row for row in items if row["status"] == "ok"]
        first = items[0]
        if not ok_items:
            summary.append(
                {
                    "video_name": video_name,
                    "algorithm": algorithm,
                    "scheme_name": first["scheme_name"],
                    "source_size_bytes": first["source_size_bytes"],
                    "avg_output_size_bytes": "",
                    "avg_compression_ratio": "",
                    "avg_compression_time_ms": "",
                    "avg_decompression_time_ms": "",
                    "avg_compression_throughput_MBps": "",
                    "avg_decompression_throughput_MBps": "",
                    "std_compression_time_ms": "",
                    "std_decompression_time_ms": "",
                    "integrity_pass_count": 0,
                    "repeat_count": len(items),
                    "status": "failed",
                }
            )
            continue

        summary.append(
            {
                "video_name": video_name,
                "algorithm": algorithm,
                "scheme_name": first["scheme_name"],
                "source_size_bytes": first["source_size_bytes"],
                "source_width": first["source_width"],
                "source_height": first["source_height"],
                "source_fps": first["source_fps"],
                "source_duration_s": first["source_duration_s"],
                "avg_output_size_bytes": mean(float(row["output_size_bytes"]) for row in ok_items),
                "avg_compression_ratio": mean(float(row["compression_ratio"]) for row in ok_items),
                "avg_compression_time_ms": mean(float(row["compression_time_ms"]) for row in ok_items),
                "avg_decompression_time_ms": mean(float(row["decompression_time_ms"]) for row in ok_items),
                "avg_compression_throughput_MBps": mean(
                    float(row["compression_throughput_MBps"]) for row in ok_items if row["compression_throughput_MBps"] != ""
                ),
                "avg_decompression_throughput_MBps": mean(
                    float(row["decompression_throughput_MBps"]) for row in ok_items
                ),
                "std_compression_time_ms": stddev(float(row["compression_time_ms"]) for row in ok_items),
                "std_decompression_time_ms": stddev(float(row["decompression_time_ms"]) for row in ok_items),
                "integrity_pass_count": sum(1 for row in ok_items if row["integrity"] == "pass"),
                "repeat_count": len(items),
                "status": "ok",
            }
        )
    return summary


def build_end_to_end(summary_rows: list[dict[str, object]], packet_sizes: list[int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in summary_rows:
        if row["status"] != "ok":
            continue
        original_size = float(row["source_size_bytes"])
        output_size = float(row["avg_output_size_bytes"])
        compression_time = float(row["avg_compression_time_ms"])
        decompression_time = float(row["avg_decompression_time_ms"])
        for bandwidth in BANDWIDTHS_MBPS:
            t_direct_ms = original_size * 8 / (bandwidth * 1_000_000) * 1000
            t_transfer_ms = output_size * 8 / (bandwidth * 1_000_000) * 1000
            if row["algorithm"] == "S0":
                # Keep the direct-transfer baseline free of codec processing.
                t_total_ms = t_direct_ms
            else:
                # The compressed path is measured end to end: FFmpeg encode,
                # compressed-file transfer, then FFmpeg decode-to-null.
                t_total_ms = compression_time + t_transfer_ms + decompression_time
            latency_reduction = (t_direct_ms - t_total_ms) / t_direct_ms * 100
            for packet_size in packet_sizes:
                rows.append(
                    {
                        "video_name": row["video_name"],
                        "algorithm": row["algorithm"],
                        "scheme_name": row["scheme_name"],
                        "bandwidth_mbps": bandwidth,
                        "compression_scope": "encode_then_fragment",
                        "packet_size_role": "transfer_fragment_size_after_video_compression",
                        "packet_size_bytes": packet_size,
                        "packet_count": math.ceil(output_size / packet_size),
                        "T_direct_ms": t_direct_ms,
                        "T_transfer_ms": t_transfer_ms,
                        "T_total_ms": t_total_ms,
                        "T_direct_s": round(t_direct_ms / 1000.0, 2),
                        "T_transfer_s": round(t_transfer_ms / 1000.0, 2),
                        "T_total_s": round(t_total_ms / 1000.0, 2),
                        "latency_reduction_pct": latency_reduction,
                        "best_flag": "",
                    }
                )

    groups: dict[tuple[str, float, int], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(
            (str(row["video_name"]), float(row["bandwidth_mbps"]), int(row["packet_size_bytes"])), []
        ).append(row)
    for group_rows in groups.values():
        best = min(group_rows, key=lambda r: float(r["T_total_ms"]))
        best["best_flag"] = "best"
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run edge video compression experiment.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--scheme-repeats",
        default="",
        help="Optional per-scheme repeat counts, e.g. S0=10,S1=10,S2=5. Falls back to --repeats.",
    )
    parser.add_argument("--schemes", default="S0,S1,S2", help="Comma-separated scheme codes to run.")
    parser.add_argument(
        "--packet-sizes",
        default=",".join(str(item) for item in DEFAULT_PACKET_SIZES),
        help="Comma-separated transfer fragment sizes in bytes after video compression.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip repeat rows already present in compression_measurements.csv.")
    parser.add_argument("--max-videos", type=int, default=0, help="Limit videos for smoke tests. 0 means all.")
    args = parser.parse_args()

    ffmpeg = args.ffmpeg
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    encoded_dir = output_dir / "encoded_outputs"
    artifact_dir = output_dir / "last_repeat_decode_artifacts"
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    videos = sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)
    if not videos:
        raise SystemExit(f"No video files found in {input_dir}")
    if args.max_videos > 0:
        videos = sorted(videos, key=lambda path: (path.stat().st_size, path.name))[: args.max_videos]

    selected_scheme_codes = set(parse_csv(args.schemes))
    schemes = [scheme for scheme in SCHEMES if scheme.code in selected_scheme_codes]
    if not schemes:
        raise SystemExit(f"No supported schemes selected from {args.schemes!r}.")
    scheme_repeats = parse_scheme_repeats(args.scheme_repeats) if args.scheme_repeats else {}
    unknown_repeat_schemes = sorted(set(scheme_repeats) - {scheme.code for scheme in SCHEMES})
    if unknown_repeat_schemes:
        raise SystemExit(f"Unsupported schemes in --scheme-repeats: {unknown_repeat_schemes}")
    packet_sizes = parse_int_csv(args.packet_sizes)

    measurement_path = output_dir / "compression_measurements.csv"
    measurements: list[dict[str, object]] = read_csv(measurement_path) if args.resume else []
    if measurements:
        before_count = len(measurements)
        measurements = [
            row
            for row in measurements
            if str(row.get("algorithm", "")) in selected_scheme_codes
            and int(row.get("repeat", 0)) <= scheme_repeats.get(str(row.get("algorithm", "")), args.repeats)
        ]
        filtered_count = before_count - len(measurements)
        if filtered_count:
            print(f"[resume] filtered {filtered_count} rows outside selected schemes/repeat limits", flush=True)
            write_csv(measurement_path, measurements, MEASUREMENT_FIELDS)
    completed_keys = {measurement_key(row) for row in measurements}
    if args.resume and measurements:
        print(f"[resume] loaded {len(measurements)} existing measurement rows", flush=True)

    for video in videos:
        print(f"[video] {video.name}", flush=True)
        source_info = probe_media(ffmpeg, video)
        original_size = video.stat().st_size

        for scheme in schemes:
            target_repeats = scheme_repeats.get(scheme.code, args.repeats)
            print(f"  [scheme] {scheme.code} {scheme.name}", flush=True)
            for repeat in range(1, target_repeats + 1):
                key = (video.name, scheme.code, repeat)
                if key in completed_keys:
                    print(f"    [skip] repeat {repeat}/{target_repeats} already measured", flush=True)
                    continue
                print(f"    [repeat] {repeat}/{target_repeats}", flush=True)
                status = "ok"
                skip_reason = ""
                if scheme.code == "S0":
                    output_path = video
                    compression_time_ms = 0.0
                    compression_log = "baseline_no_encode"
                    transcode_returncode = 0
                else:
                    output_path = encoded_dir / scheme.code / f"{video.stem}__{scheme.name}__r{repeat}.mp4"
                    transcode_returncode, compression_time_ms, compression_log = transcode(
                        ffmpeg, video, output_path, scheme
                    )
                    (log_dir / f"{video.stem}__{scheme.code}__r{repeat}__encode.log").write_text(
                        compression_log, encoding="utf-8", errors="replace"
                    )
                    if transcode_returncode != 0:
                        status = "failed"
                        skip_reason = f"encode_failed_rc={transcode_returncode}"

                output_available = status == "ok" and output_path.exists()
                output_size = output_path.stat().st_size if output_available else 0
                output_info = probe_media(ffmpeg, output_path) if output_available else {}
                decode_returncode, decompression_time_ms, decode_log = (
                    decode_to_null(ffmpeg, output_path) if output_available else (1, 0.0, "missing_output")
                )

                if repeat == target_repeats and output_available:
                    target_base = artifact_dir / video.stem / scheme.code
                    save_decode_artifact(
                        ffmpeg,
                        output_path,
                        target_base / "decoded_first_frame.png",
                        target_base / "decode.log",
                        decode_log,
                    )

                integrity, integrity_note = (
                    integrity_status(source_info, output_info, decode_returncode, output_path)
                    if status == "ok"
                    else ("fail", skip_reason)
                )
                if integrity != "pass":
                    status = "failed"
                    if not skip_reason:
                        skip_reason = integrity_note

                compression_ratio = output_size / original_size if original_size else math.nan
                compression_tp = "" if scheme.code == "S0" else mbps(original_size, compression_time_ms)
                # Normalize decode throughput by the original source size so schemes with
                # different compressed output sizes remain directly comparable.
                decompression_tp = mbps(original_size, decompression_time_ms)

                row = {
                    "video_name": video.name,
                    "container": source_info.get("container", ""),
                    "source_codec": source_info.get("video_codec", ""),
                    "source_profile": source_info.get("video_profile", ""),
                    "source_width": source_info.get("width", ""),
                    "source_height": source_info.get("height", ""),
                    "source_fps": source_info.get("fps", ""),
                    "source_duration_s": source_info.get("duration_s", ""),
                    "source_video_bitrate_kbps": source_info.get("video_bitrate_kbps", ""),
                    "source_total_bitrate_kbps": source_info.get("total_bitrate_kbps", ""),
                    "source_size_bytes": original_size,
                    "algorithm": scheme.code,
                    "scheme_name": scheme.name,
                    "repeat": repeat,
                    "output_codec": output_info.get("video_codec", scheme.output_codec),
                    "output_size_bytes": output_size,
                    "compression_ratio": compression_ratio,
                    "compression_time_ms": compression_time_ms,
                    "decompression_time_ms": decompression_time_ms,
                    "compression_throughput_MBps": compression_tp if compression_tp is not None else "",
                    "decompression_throughput_MBps": decompression_tp if decompression_tp is not None else "",
                    "integrity": integrity,
                    "integrity_note": integrity_note,
                    "status": status,
                    "skip_reason": skip_reason,
                    "output_path": str(output_path),
                }
                measurements.append(row)
                completed_keys.add(key)
                write_csv(measurement_path, measurements, MEASUREMENT_FIELDS)

    summary = summarize_measurements(measurements)
    write_csv(output_dir / "average_compression_results.csv", summary, SUMMARY_FIELDS)

    end_to_end = build_end_to_end(summary, packet_sizes)
    write_csv(output_dir / "end_to_end_results.csv", end_to_end, END_FIELDS)
    write_csv(output_dir / "end_to_end_results_ms_detail.csv", end_to_end, END_FIELDS_MS_DETAIL)

    print(f"[done] measurements: {output_dir / 'compression_measurements.csv'}")
    print(f"[done] averages: {output_dir / 'average_compression_results.csv'}")
    print(f"[done] end-to-end: {output_dir / 'end_to_end_results.csv'}")
    print(f"[done] last decode artifacts: {artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

