#!/usr/bin/env python3
"""Simulate edge buffering during link interruption and recovery.

The model follows the parameter table in third-stage-cache-mechanism-report.md.
It is intentionally dependency-free so it can run on the second device before
the ns-3 and compression environments are installed.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path


BYTES_PER_MEGABIT = 1_000_000 / 8
PRIORITY_CLASSES = (("critical", 3, 0.20), ("normal", 2, 0.50), ("bulk", 1, 0.30))


@dataclass
class Segment:
    created_s: float
    size_bytes: int
    data_class: str
    priority: int


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    purpose: str
    capacity_mb: float
    strategy: str
    phases: tuple[tuple[str, int, float], ...]
    production_mbps: float
    multi_class: bool = True

    @property
    def total_seconds(self):
        return sum(duration for _, duration, _ in self.phases)


class EdgeCache:
    def __init__(self, capacity_bytes: int, strategy: str):
        self.capacity_bytes = max(0, capacity_bytes)
        self.strategy = strategy
        self.queue_bytes = 0
        self.queues = {priority: deque() for _, priority, _ in PRIORITY_CLASSES}
        self.fifo = deque()
        self.overflow_bytes = 0
        self.evicted_bytes_by_class = defaultdict(int)
        self.last_evicted_by_class = defaultdict(int)

    def _append(self, segment: Segment) -> None:
        if self.strategy == "fifo":
            self.fifo.append(segment)
        else:
            self.queues[segment.priority].append(segment)
        self.queue_bytes += segment.size_bytes

    def _remove_from_queue(self, queue: deque, amount: int, data_class: str) -> int:
        removed = 0
        while queue and removed < amount:
            segment = queue[-1]
            take = min(segment.size_bytes, amount - removed)
            segment.size_bytes -= take
            removed += take
            self.queue_bytes -= take
            self.evicted_bytes_by_class[data_class] += take
            self.last_evicted_by_class[data_class] += take
            if segment.size_bytes == 0:
                queue.pop()
        return removed

    def enqueue(self, segment: Segment) -> int:
        """Add a segment and return bytes dropped at admission time."""
        self.last_evicted_by_class = defaultdict(int)
        if self.strategy == "none" or self.capacity_bytes == 0:
            self.overflow_bytes += segment.size_bytes
            return segment.size_bytes

        if self.strategy == "fifo":
            available = max(0, self.capacity_bytes - self.queue_bytes)
            accepted = min(segment.size_bytes, available)
            if accepted:
                self._append(Segment(segment.created_s, accepted, segment.data_class, segment.priority))
            dropped = segment.size_bytes - accepted
            self.overflow_bytes += dropped
            return dropped

        # Priority admission can evict lower-priority queued data for a more
        # important segment. Equal-priority data remains FIFO within its class.
        if segment.size_bytes > self.capacity_bytes:
            self.overflow_bytes += segment.size_bytes - self.capacity_bytes
            segment = Segment(
                segment.created_s,
                self.capacity_bytes,
                segment.data_class,
                segment.priority,
            )
        needed = max(0, self.queue_bytes + segment.size_bytes - self.capacity_bytes)
        for priority in sorted(self.queues):
            if priority >= segment.priority:
                continue
            queue = self.queues[priority]
            while queue and needed:
                oldest_class = queue[-1].data_class
                removed = self._remove_from_queue(queue, needed, oldest_class)
                needed -= removed
        if needed:
            dropped = min(segment.size_bytes, needed)
            segment = Segment(segment.created_s, segment.size_bytes - dropped, segment.data_class, segment.priority)
            self.overflow_bytes += dropped
        if segment.size_bytes:
            self._append(segment)
        return self.overflow_bytes

    def dequeue(self, budget_bytes: int, now_s: float) -> tuple[int, float, dict[str, int]]:
        delivered = 0
        wait_byte_seconds = 0.0
        delivered_by_class = defaultdict(int)
        while budget_bytes > 0 and self.queue_bytes > 0:
            if self.strategy == "fifo":
                segment = self.fifo[0]
                queue = self.fifo
            else:
                priority = max(priority for priority, queue in self.queues.items() if queue)
                queue = self.queues[priority]
                segment = queue[0]
            take = min(segment.size_bytes, budget_bytes)
            delivered += take
            budget_bytes -= take
            self.queue_bytes -= take
            wait_byte_seconds += take * max(0.0, now_s - segment.created_s)
            delivered_by_class[segment.data_class] += take
            segment.size_bytes -= take
            if segment.size_bytes == 0:
                queue.popleft()
        return delivered, wait_byte_seconds, dict(delivered_by_class)


def build_scenarios() -> list[Scenario]:
    normal = ("normal", 300, 2.0)
    table_outage = ("outage", 600, 0.0)
    short_outage = ("outage", 300, 0.0)
    long_outage = ("outage", 1200, 0.0)
    recovery_20 = ("recovery", 1200, 2.0)
    return [
        Scenario("E01_baseline_no_cache", "baseline", 0, "none", (normal, table_outage, recovery_20), 1.0),
        Scenario("E02_small_fifo", "capacity", 100, "fifo", (normal, table_outage, recovery_20), 1.0),
        Scenario("E03_medium_fifo", "capacity", 1024, "fifo", (normal, table_outage, recovery_20), 1.0),
        Scenario("E04_large_fifo", "capacity", 10240, "fifo", (normal, table_outage, recovery_20), 1.0),
        Scenario("E05_short_outage", "outage_duration", 100, "fifo", (normal, ("outage", 300, 0.0), recovery_20), 1.0),
        Scenario("E06_long_outage", "outage_duration", 100, "fifo", (normal, long_outage, ("recovery", 1800, 2.0)), 1.0),
        Scenario("E07_degraded_link", "degraded_link", 100, "fifo", (normal, ("degraded", 1200, 0.2), ("recovery", 1800, 2.0)), 1.0),
        Scenario("E08_low_production", "production_rate", 100, "fifo", (normal, table_outage, recovery_20), 0.5),
        Scenario("E09_high_production", "production_rate", 100, "fifo", (normal, table_outage, recovery_20), 2.0),
        Scenario("E10_medium_recovery", "recovery_bandwidth", 100, "fifo", (normal, table_outage, ("recovery", 1200, 4.0)), 1.0),
        Scenario("E11_high_recovery", "recovery_bandwidth", 100, "fifo", (normal, table_outage, ("recovery", 1200, 10.0)), 1.0),
        Scenario("E12_priority_contention", "priority_policy", 100, "priority", (normal, long_outage, ("recovery", 1800, 2.0)), 2.0),
        Scenario("E13_fluctuating_link", "fluctuating_link", 100, "priority", (normal, ("fluctuating", 1200, 0.0), ("recovery", 1800, 4.0)), 1.0),
    ]


def phase_at(scenario: Scenario, second: int) -> tuple[str, float, int]:
    offset = 0
    for index, (name, duration, bandwidth) in enumerate(scenario.phases):
        if second < offset + duration:
            if name == "fluctuating":
                bandwidth = 1.0 if ((second - offset) // 60) % 2 else 0.0
            return name, bandwidth, index
        offset += duration
    last_name, _, last_bandwidth = scenario.phases[-1]
    return last_name, last_bandwidth, len(scenario.phases) - 1


def simulate(scenario: Scenario, drain_seconds: int) -> tuple[dict, list[dict], list[dict]]:
    capacity_bytes = int(scenario.capacity_mb * 1024 * 1024)
    cache = EdgeCache(capacity_bytes, scenario.strategy)
    produced = delivered = 0
    direct_dropped = 0
    wait_byte_seconds = 0.0
    max_queue = 0
    queue_sum = 0
    recovery_start = sum(duration for name, duration, _ in scenario.phases if name != "recovery" and name != "fluctuating")
    recovery_start = scenario.phases[0][1] + scenario.phases[1][1]
    cache_clear_s = None
    rows = []
    class_rows = defaultdict(lambda: {"produced": 0, "delivered": 0, "dropped": 0})
    total_seconds = scenario.total_seconds + drain_seconds

    for second in range(total_seconds):
        phase, bandwidth_mbps, _ = phase_at(scenario, second)
        is_producing = second < scenario.total_seconds
        produced_segments = []
        if is_producing:
            total_bytes = int(round(scenario.production_mbps * BYTES_PER_MEGABIT))
            if scenario.multi_class:
                remaining = total_bytes
                for index, (data_class, priority, fraction) in enumerate(PRIORITY_CLASSES):
                    size = remaining if index == len(PRIORITY_CLASSES) - 1 else int(round(total_bytes * fraction))
                    remaining -= size
                    produced_segments.append(Segment(second, size, data_class, priority))
            else:
                produced_segments.append(Segment(second, total_bytes, "normal", 2))
        for segment in produced_segments:
            produced += segment.size_bytes
            class_rows[segment.data_class]["produced"] += segment.size_bytes

        link_budget = int(round(bandwidth_mbps * BYTES_PER_MEGABIT))
        if scenario.strategy == "none":
            available = sum(segment.size_bytes for segment in produced_segments)
            sent = min(available, link_budget)
            dropped = available - sent
            delivered += sent
            direct_dropped += dropped
            for segment in produced_segments:
                class_rows[segment.data_class]["delivered"] += int(sent * segment.size_bytes / available) if available else 0
                class_rows[segment.data_class]["dropped"] += int(dropped * segment.size_bytes / available) if available else 0
        else:
            for segment in produced_segments:
                before = cache.overflow_bytes
                cache.enqueue(segment)
                new_drop = cache.overflow_bytes - before
                class_rows[segment.data_class]["dropped"] += new_drop
                for data_class, size in cache.last_evicted_by_class.items():
                    class_rows[data_class]["dropped"] += size
            sent, wait_added, sent_classes = cache.dequeue(link_budget, second)
            delivered += sent
            wait_byte_seconds += wait_added
            for data_class, size in sent_classes.items():
                class_rows[data_class]["delivered"] += size

        max_queue = max(max_queue, cache.queue_bytes)
        queue_sum += cache.queue_bytes
        if second >= recovery_start and cache.queue_bytes == 0 and cache_clear_s is None:
            cache_clear_s = max(0, second - recovery_start)
        rows.append({"scenario": scenario.scenario_id, "second": second, "phase": phase, "bandwidth_mbps": bandwidth_mbps, "queue_bytes": cache.queue_bytes, "produced_bytes": sum(item.size_bytes for item in produced_segments), "delivered_bytes": delivered, "overflow_bytes": cache.overflow_bytes})

    dropped = produced - delivered
    summary = {
        "scenario": scenario.scenario_id,
        "purpose": scenario.purpose,
        "capacity_mb": scenario.capacity_mb,
        "strategy": scenario.strategy,
        "production_mbps": scenario.production_mbps,
        "produced_bytes": produced,
        "delivered_bytes": delivered,
        "dropped_bytes": dropped,
        "loss_rate_pct": 100 * dropped / produced if produced else 0,
        "delivery_rate_pct": 100 * delivered / produced if produced else 0,
        "peak_queue_bytes": max_queue,
        "peak_queue_mb": max_queue / (1024 * 1024),
        "average_queue_mb": queue_sum / total_seconds / (1024 * 1024),
        "overflow_bytes": cache.overflow_bytes + direct_dropped,
        "cache_clear_after_recovery_s": "" if cache_clear_s is None else cache_clear_s,
        "average_wait_ms": 1000 * wait_byte_seconds / delivered if delivered else 0,
    }
    class_output = []
    for data_class, values in sorted(class_rows.items()):
        values = dict(values)
        values.update({"scenario": scenario.scenario_id, "data_class": data_class})
        values["loss_rate_pct"] = 100 * values["dropped"] / values["produced"] if values["produced"] else 0
        class_output.append(values)
    return summary, rows, class_output


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate edge cache policies for ocean observation data.")
    parser.add_argument("--output-dir", default="results", help="Directory for CSV outputs.")
    parser.add_argument("--scenario", default="", help="Run one scenario id; empty runs all scenarios.")
    parser.add_argument("--drain-seconds", type=int, default=1800, help="Extra recovery time after the profile ends.")
    args = parser.parse_args()

    scenarios = build_scenarios()
    if args.scenario:
        scenarios = [scenario for scenario in scenarios if scenario.scenario_id == args.scenario]
        if not scenarios:
            raise SystemExit(f"Unknown scenario: {args.scenario}")
    summaries, timeseries, class_rows = [], [], []
    for scenario in scenarios:
        summary, rows, per_class = simulate(scenario, args.drain_seconds)
        summaries.append(summary)
        timeseries.extend(rows)
        class_rows.extend(per_class)
        print(f"{scenario.scenario_id}: loss={summary['loss_rate_pct']:.3f}% peak_queue={summary['peak_queue_mb']:.2f} MB")

    output_dir = Path(args.output_dir)
    write_csv(output_dir / "cache_summary.csv", summaries)
    write_csv(output_dir / "cache_timeseries.csv", timeseries)
    write_csv(output_dir / "cache_delivery_by_class.csv", class_rows)
    print(f"Output directory: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
