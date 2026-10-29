#!/usr/bin/env python3
"""Run the stage-3 cache experiment with the real experiment-data sizes.

The simulation keeps the stage-3 link schedules, cache capacities and total
production rates, but replaces the synthetic byte stream with file objects:

* text: records are accumulated until one of the four source-file sizes is
  reached, then the file is compressed with the stage-2 2 Mbps winner;
* image: one object uses the median of the nine source-image sizes and the
  median JPEG-Q75 size measured from those nine images;
* video: one object uses each of the nine source-video sizes and the stage-2
  2 Mbps per-file winner/reduction reported in the project report.

This is a discrete-second model. Compression is performed at N1 before the
compressed object enters the cache. Compression CPU time is not charged to
the link schedule; the stage-2 video report already includes encoding when it
selected S1/S2 at 2 Mbps.
"""

from __future__ import annotations

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT.parent / '实验数据/图片文件'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT.parent / 'cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()


import argparse
import csv
import io
import statistics
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - only used on minimal environments
    Image = None


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cache_experiment import BYTES_PER_MEGABIT, build_scenarios, phase_at  # noqa: E402


ROOT = OCEAN_ROOT
DATA_DIR = OCEAN_DATA
IMAGE_DIR = OCEAN_IMAGE_DIR
VIDEO_DIR = DATA_DIR / "视频样本"

TEXT_SPECS = [
    ("D1_big_buoy_weather", "2020年大浮标气象数据.txt", "parquet_zstd", 0.209073784),
    ("D2_weather_utf16", "气象数据.txt", "gzip", 0.115715759),
    ("D3_wave_sensor", "浮标中心波浪传感器.txt", "parquet_zstd", 0.158974476),
]
LOG_NAMES = [
    "1海流log-info-2019-09-29.0.log",
    "2海流log-info-2019-09-28.0.log",
    "3海流log-info-2019-09-30.0.log",
]

# The 2 Mbps Host-16C table in edge-text-compression-experiment-report.md.
# Values are reduction percentages for the selected scheme at 2 Mbps.
VIDEO_2MBPS = {
    "2019-05-30_18.50.28.mkv": ("S1", 0.0880),
    "3f2b041a2f5cf63ddc2e449fa7e3fd80.mp4": ("S2", 0.4865),
    "5fdbdd4dd7b628c0986de9028e8be48a.mp4": ("S2", 0.4999),
    "48290d122823a5cf9af2a146ba3d238b.mp4": ("S2", 0.7223),
    "4a3b00dd39998a85cb1db439bf0bbe93.mp4": ("S2", 0.8011),
    "ba5cd3bd2090f260c1810d600604f038.mp4": ("S2", 0.6190),
    "705ccbb00cfbaab61780706633e3c7ce.mp4": ("S2", 0.8397),
    "5cf7af68d381d7cb80e5567444e894c2.mp4": ("S2", 0.8194),
    "4412e5bfafeaa07161d2082422e349e1.mp4": ("S1", 0.8486),
}

CLASS_PRIORITY = {"text": 3, "image": 2, "video": 1}
CLASS_FRACTION = {"text": 0.20, "image": 0.50, "video": 0.30}


@dataclass(frozen=True)
class Template:
    data_class: str
    name: str
    raw_bytes: int
    compressed_bytes: int
    algorithm: str

    @property
    def compression_ratio(self) -> float:
        return self.compressed_bytes / self.raw_bytes if self.raw_bytes else 0.0


@dataclass
class Segment:
    created_s: int
    compressed_bytes: int
    raw_bytes: float
    data_class: str
    priority: int

    @property
    def raw_per_compressed(self) -> float:
        return self.raw_bytes / self.compressed_bytes if self.compressed_bytes else 0.0


class Cache:
    """FIFO or priority cache with byte-level proportional accounting."""

    def __init__(self, capacity_bytes: int, strategy: str):
        self.capacity_bytes = capacity_bytes
        self.strategy = strategy
        self.queue_bytes = 0
        self.fifo: deque[Segment] = deque()
        self.queues: dict[int, deque[Segment]] = {1: deque(), 2: deque(), 3: deque()}

    def _queue_for(self, segment: Segment) -> deque[Segment]:
        return self.fifo if self.strategy == "fifo" else self.queues[segment.priority]

    def _append(self, segment: Segment) -> None:
        self._queue_for(segment).append(segment)
        self.queue_bytes += segment.compressed_bytes

    def dequeue(self, budget: int, now_s: int) -> dict[str, float]:
        delivered: dict[str, float] = defaultdict(float)
        while budget > 0 and self.queue_bytes > 0:
            if self.strategy == "fifo":
                queue = self.fifo
            else:
                nonempty = [p for p, q in self.queues.items() if q]
                if not nonempty:
                    break
                queue = self.queues[max(nonempty)]
            segment = queue[0]
            ratio = segment.raw_per_compressed
            take = min(segment.compressed_bytes, budget)
            delivered[segment.data_class] += take * ratio
            segment.compressed_bytes -= take
            segment.raw_bytes -= take * ratio
            budget -= take
            self.queue_bytes -= take
            if segment.compressed_bytes == 0:
                queue.popleft()
        return dict(delivered)


# Replace Cache.enqueue with a compact exact implementation after class
# definition. This avoids a fragile mixed raw/compressed unit in the eviction
# loop and keeps the main class readable.
def _enqueue_exact(self: Cache, segment: Segment):
    new_drops: dict[str, float] = defaultdict(float)
    evicted: dict[str, float] = defaultdict(float)
    if self.strategy == "none" or self.capacity_bytes == 0:
        new_drops[segment.data_class] = segment.raw_bytes
        return dict(new_drops), dict(evicted)
    if self.strategy == "fifo":
        accepted = min(segment.compressed_bytes, max(0, self.capacity_bytes - self.queue_bytes))
        if accepted:
            self._append(Segment(segment.created_s, accepted, accepted * segment.raw_per_compressed, segment.data_class, segment.priority))
        new_drops[segment.data_class] += (segment.compressed_bytes - accepted) * segment.raw_per_compressed
        return dict(new_drops), dict(evicted)
    if segment.compressed_bytes > self.capacity_bytes:
        keep = self.capacity_bytes
        new_drops[segment.data_class] += (segment.compressed_bytes - keep) * segment.raw_per_compressed
        segment = Segment(segment.created_s, keep, keep * segment.raw_per_compressed, segment.data_class, segment.priority)
    needed = max(0, self.queue_bytes + segment.compressed_bytes - self.capacity_bytes)
    for priority in (1, 2, 3):
        if priority >= segment.priority:
            continue
        queue = self.queues[priority]
        while queue and needed > 0:
            old = queue[0]
            ratio = old.raw_per_compressed
            take = min(old.compressed_bytes, needed)
            old.compressed_bytes -= take
            old.raw_bytes -= take * ratio
            self.queue_bytes -= take
            needed -= take
            evicted[old.data_class] += take * ratio
            if old.compressed_bytes == 0:
                queue.popleft()
    if needed:
        ratio = segment.raw_per_compressed
        take = min(segment.compressed_bytes, needed)
        segment.compressed_bytes -= take
        segment.raw_bytes -= take * ratio
        new_drops[segment.data_class] += take * ratio
    if segment.compressed_bytes:
        self._append(segment)
    return dict(new_drops), dict(evicted)


Cache.enqueue = _enqueue_exact


def build_templates(output_dir: Path) -> tuple[dict[str, list[Template]], list[dict[str, object]]]:
    templates: dict[str, list[Template]] = {"text": [], "image": [], "video": []}
    manifest: list[dict[str, object]] = []
    for name, filename, algorithm, ratio in TEXT_SPECS:
        path = DATA_DIR / filename
        raw = path.stat().st_size
        compressed = int(round(raw * ratio))
        item = Template("text", name, raw, compressed, algorithm)
        templates["text"].append(item)
        manifest.append({"data_class": "text", "name": name, "source": str(path), "raw_bytes": raw, "compressed_bytes": compressed, "algorithm": algorithm, "compression_ratio": item.compression_ratio, "basis": "stage2 2 Mbps best_algorithm_by_scenario"})
    raw = sum((DATA_DIR / filename).stat().st_size for filename in LOG_NAMES)
    ratio = 0.04723454
    item = Template("text", "D4_ocean_current_log", raw, int(round(raw * ratio)), "chimp")
    templates["text"].append(item)
    manifest.append({"data_class": "text", "name": item.name, "source": ";".join(str(DATA_DIR / f) for f in LOG_NAMES), "raw_bytes": raw, "compressed_bytes": item.compressed_bytes, "algorithm": item.algorithm, "compression_ratio": item.compression_ratio, "basis": "stage2 2 Mbps best_algorithm_by_scenario"})

    image_paths = sorted(p for p in IMAGE_DIR.iterdir() if p.suffix.lower() == ".png")
    image_raw_sizes = [p.stat().st_size for p in image_paths]
    median_raw = int(statistics.median(image_raw_sizes))
    # Measure the nine current images with Pillow JPEG quality=75. The
    # fallback keeps the experiment runnable on a machine without Pillow and
    # records the same values measured for the current data directory.
    if Image is not None:
        jpeg_sizes = []
        for path in image_paths:
            with Image.open(path) as image:
                converted = image.convert("RGB")
                buffer = io.BytesIO()
                converted.save(buffer, format="JPEG", quality=75, optimize=True)
                jpeg_sizes.append(len(buffer.getvalue()))
    else:
        jpeg_sizes = [6412, 8408, 9957, 16292, 20644, 30908, 31778, 42123, 72521]
    median_jpeg = int(statistics.median(jpeg_sizes))
    item = Template("image", "image_median_9", median_raw, median_jpeg, "jpeg_q75_optimize")
    templates["image"].append(item)
    manifest.append({"data_class": "image", "name": item.name, "source": str(IMAGE_DIR), "raw_bytes": median_raw, "compressed_bytes": median_jpeg, "algorithm": item.algorithm, "compression_ratio": item.compression_ratio, "basis": "nine-image median; Pillow JPEG Q75 measured baseline"})

    for filename, reduction in [(p.name, VIDEO_2MBPS[p.name][1]) for p in sorted(VIDEO_DIR.iterdir()) if p.suffix.lower() in {".mp4", ".mkv"}]:
        raw = (VIDEO_DIR / filename).stat().st_size
        scheme = VIDEO_2MBPS[filename][0]
        item = Template("video", filename, raw, int(round(raw * (1.0 - reduction))), scheme)
        templates["video"].append(item)
        manifest.append({"data_class": "video", "name": filename, "source": str(VIDEO_DIR / filename), "raw_bytes": raw, "compressed_bytes": item.compressed_bytes, "algorithm": scheme, "compression_ratio": item.compression_ratio, "basis": "stage2 report 2 Mbps per-file reduction"})
    return templates, manifest


class Aggregator:
    def __init__(self, data_class: str, templates: list[Template]):
        self.data_class = data_class
        self.templates = templates
        self.index = 0
        self.raw_accumulator = 0.0
        self.generated_raw = 0.0
        self.emitted_raw = 0.0

    def add(self, raw_bytes: int, now_s: int) -> list[tuple[Template, int]]:
        self.generated_raw += raw_bytes
        self.raw_accumulator += raw_bytes
        emitted: list[tuple[Template, int]] = []
        # A source-file threshold applies to each successive template. The
        # current object is emitted only after its raw threshold is complete.
        while self.raw_accumulator >= self.templates[self.index].raw_bytes:
            template = self.templates[self.index]
            self.raw_accumulator -= template.raw_bytes
            self.emitted_raw += template.raw_bytes
            emitted.append((template, now_s))
            self.index = (self.index + 1) % len(self.templates)
        return emitted


def simulate(scenario, templates: dict[str, list[Template]], drain_seconds: int):
    capacity = int(scenario.capacity_mb * 1024 * 1024)
    cache = Cache(capacity, scenario.strategy)
    aggregators = {klass: Aggregator(klass, templates[klass]) for klass in CLASS_FRACTION}
    produced_objects = defaultdict(float)
    admitted_drops = defaultdict(float)
    evicted = defaultdict(float)
    delivered = defaultdict(float)
    total_seconds = scenario.total_seconds + drain_seconds
    peak_queue = 0

    for second in range(total_seconds):
        producing = second < scenario.total_seconds
        if producing:
            total_raw = int(round(scenario.production_mbps * BYTES_PER_MEGABIT))
            remaining = total_raw
            classes = list(CLASS_FRACTION)
            for idx, klass in enumerate(classes):
                raw = remaining if idx == len(classes) - 1 else int(round(total_raw * CLASS_FRACTION[klass]))
                remaining -= raw
                for template, created_s in aggregators[klass].add(raw, second):
                    produced_objects[klass] += template.raw_bytes
                    segment = Segment(created_s, template.compressed_bytes, template.raw_bytes, klass, CLASS_PRIORITY[klass])
                    new_drop, old_drop = cache.enqueue(segment)
                    for key, value in new_drop.items():
                        admitted_drops[key] += value
                    for key, value in old_drop.items():
                        evicted[key] += value
        bandwidth_mbps = phase_at(scenario, second)[1]
        delivered_now = cache.dequeue(int(round(bandwidth_mbps * BYTES_PER_MEGABIT)), second)
        for key, value in delivered_now.items():
            delivered[key] += value
        peak_queue = max(peak_queue, cache.queue_bytes)

    class_rows = []
    for klass in ("text", "image", "video"):
        generated = aggregators[klass].generated_raw
        emitted = produced_objects[klass]
        dropped = admitted_drops[klass] + evicted[klass]
        sent = delivered[klass]
        class_rows.append({
            "scenario": scenario.scenario_id,
            "purpose": scenario.purpose,
            "capacity_mb": scenario.capacity_mb,
            "strategy": scenario.strategy,
            "production_mbps": scenario.production_mbps,
            "data_class": klass,
            "generated_raw_bytes": generated,
            "emitted_file_raw_bytes": emitted,
            "pending_aggregation_raw_bytes": max(0.0, generated - emitted),
            "delivered_raw_bytes": sent,
            "dropped_raw_bytes": dropped,
            "loss_rate_pct_emitted": 100.0 * dropped / emitted if emitted else 0.0,
            "pending_rate_pct_generated": 100.0 * max(0.0, generated - emitted) / generated if generated else 0.0,
            "unavailable_rate_pct_generated": 100.0 * (dropped + max(0.0, generated - emitted)) / generated if generated else 0.0,
        })
    emitted_total = sum(produced_objects.values())
    dropped_total = sum(admitted_drops.values()) + sum(evicted.values())
    delivered_total = sum(delivered.values())
    summary = {
        "scenario": scenario.scenario_id,
        "purpose": scenario.purpose,
        "capacity_mb": scenario.capacity_mb,
        "strategy": scenario.strategy,
        "production_mbps": scenario.production_mbps,
        "generated_raw_bytes": sum(a.generated_raw for a in aggregators.values()),
        "emitted_file_raw_bytes": emitted_total,
        "pending_aggregation_raw_bytes": sum(max(0.0, a.generated_raw - a.emitted_raw) for a in aggregators.values()),
        "delivered_raw_bytes": delivered_total,
        "dropped_raw_bytes": dropped_total,
        "loss_rate_pct_emitted": 100.0 * dropped_total / emitted_total if emitted_total else 0.0,
        "pending_rate_pct_generated": 100.0 * sum(max(0.0, a.generated_raw - a.emitted_raw) for a in aggregators.values()) / sum(a.generated_raw for a in aggregators.values()),
        "unavailable_rate_pct_generated": 100.0 * (dropped_total + sum(max(0.0, a.generated_raw - a.emitted_raw) for a in aggregators.values())) / sum(a.generated_raw for a in aggregators.values()),
        "peak_queue_bytes": peak_queue,
        "peak_queue_mb": peak_queue / (1024 * 1024),
    }
    return summary, class_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, manifest: list[dict[str, object]], summaries: list[dict[str, object]], class_rows: list[dict[str, object]], drain_seconds: int) -> None:
    def mb(value: object) -> str:
        return f"{float(value) / 1_000_000:.3f}"

    lines = [
        "# N1 真实数据文件聚合、压缩与阶段三缓存实验",
        "",
        "> 本实验把项目中的“2 MB 带宽”解释为 **2 Mbps**（阶段二、阶段三均使用 Mbps）。",
        "",
        "## 1. 实验口径",
        "",
        "- 阶段三的 13 个场景、缓存容量和原始数据生成速率原样使用；本脚本再追加 3600 s 恢复后排空时间。",
        "- 阶段三总速率按 `text:image:video = 20%:50%:30%` 分配，沿用原阶段三 `critical:normal:bulk` 的 20/50/30 比例，并映射为文本、图片、视频优先级 3、2、1。",
        "- 文本数据按记录流累计；累计达到对应源文件大小才形成一个文件对象，之后在 N1 用阶段二 2 Mbps 的最优算法压缩。D4 是三个海流 log 合计。",
        "- 图片原始对象大小固定为九张图片原始大小的中位数；压缩对象大小使用九张 PNG 经 Pillow JPEG Q75、`optimize=True` 后的中位数。项目中没有给出图片专用阶段二结果，因此这是明确标注的基线假设。",
        "- 视频使用九个实际文件大小；压缩对象大小按阶段二报告 2 Mbps 下每个文件的 S1/S2 选择及其报告压缩下降率换算。",
        "- `loss_rate_pct_emitted` 只统计已经形成文件并进入 N1 后被丢弃的数据；`pending_rate_pct_generated` 是尚未达到文件阈值、仍留在上游聚合器中的数据；`unavailable_rate_pct_generated` 是两者合计，表示实验结束时尚未送达的数据比例。",
        "",
        "## 2. N1 输入对象与压缩大小",
        "",
        "| 类别 | 对象 | 原始大小 (MB) | 压缩后 (MB) | 算法/依据 |",
        "|---|---|---:|---:|---|",
    ]
    for row in manifest:
        lines.append(f"| {row['data_class']} | {row['name']} | {mb(row['raw_bytes'])} | {mb(row['compressed_bytes'])} | {row['algorithm']} |")
    lines += ["", "## 3. 每个场景的总体结果", "", "| 场景 | 策略/容量 MB | 速率 Mbps | 已形成文件的缓存丢失率 | 聚合 pending 率 | 实验结束未送达率 |", "|---|---|---:|---:|---:|---:|"]
    for row in summaries:
        lines.append(f"| {row['scenario']} | {row['strategy']}/{row['capacity_mb']} | {row['production_mbps']} | {float(row['loss_rate_pct_emitted']):.2f}% | {float(row['pending_rate_pct_generated']):.2f}% | {float(row['unavailable_rate_pct_generated']):.2f}% |")
    lines += ["", "## 4. 按数据类别结果", "", "| 场景 | 类别 | 已形成文件原始量 MB | 缓存丢失率 | 聚合 pending 率 | 实验结束未送达率 |", "|---|---|---:|---:|---:|---:|"]
    for row in class_rows:
        lines.append(f"| {row['scenario']} | {row['data_class']} | {mb(row['emitted_file_raw_bytes'])} | {float(row['loss_rate_pct_emitted']):.2f}% | {float(row['pending_rate_pct_generated']):.2f}% | {float(row['unavailable_rate_pct_generated']):.2f}% |")
    lines += ["", "## 5. 结果解释", "", "- E01 无缓存时，已经形成的文件对象在中断/速率不足时直接丢弃；视频在很多短场景中尚未累计到最大源文件阈值，因此视频的缓存丢失率可能显示为 0%，但 pending 率为 100%。",
              "- FIFO 场景的 100 MB 缓存能够在本组数据量和恢复排空时间内保住已形成的文件，主要未送达量来自文件阈值聚合延迟。",
              "- E12 优先级竞争场景下，视频为低优先级，出现缓存淘汰；文本和图片优先级更高，优先级策略使它们不承担本次淘汰。",
              "- 这些结果评价的是“文件聚合后压缩，再进入 N1 缓存”的路径；若改为逐记录压缩/传输，需另设记录级压缩比，不能直接套用这里的文件级比例。",
              ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE.parent / "results" / "n1_real_data")
    parser.add_argument("--drain-seconds", type=int, default=3600)
    args = parser.parse_args()
    templates, manifest = build_templates(args.output_dir)
    summaries: list[dict[str, object]] = []
    class_rows: list[dict[str, object]] = []
    for scenario in build_scenarios():
        summary, rows = simulate(scenario, templates, args.drain_seconds)
        summaries.append(summary)
        class_rows.extend(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "source_manifest.csv", manifest)
    write_csv(args.output_dir / "n1_cache_summary.csv", summaries)
    write_csv(args.output_dir / "n1_cache_by_class.csv", class_rows)
    write_report(args.output_dir / "report.md", manifest, summaries, class_rows, args.drain_seconds)
    print(f"wrote {len(summaries)} scenarios and {len(class_rows)} class rows to {args.output_dir}")


if __name__ == "__main__":
    main()
