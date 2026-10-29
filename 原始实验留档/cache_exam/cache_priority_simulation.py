#!/usr/bin/env python3
"""
Simulate edge-cache data transmission under the dynamic link profile from
cache-mechanism-report.md and priority formulas from
third-stage-cache-mechanism-report.md.

The reports define the total data generation rate but not each sensor's exact
share. The stream rates below are explicit assumptions that sum to 1.5 Mbps;
adjust STREAMS if measured per-source rates become available.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple


EPSILON = 1e-9
DEFAULT_STEP_SECONDS = 10


@dataclass(frozen=True)
class LinkStage:
    name: str
    start_s: int
    end_s: int
    capacity_mbps: float
    packet_loss_rate: float

    @property
    def effective_mbps(self) -> float:
        return self.capacity_mbps * (1.0 - self.packet_loss_rate)


@dataclass(frozen=True)
class LinkProfile:
    profile_id: str
    name: str
    stages: Tuple[LinkStage, ...]

    @property
    def recovery_start_s(self) -> int:
        for stage in self.stages:
            if stage.name == "recovery":
                return stage.start_s
        return self.stages[-1].start_s

    @property
    def total_duration_s(self) -> int:
        return self.stages[-1].end_s


@dataclass(frozen=True)
class StreamSpec:
    stream_id: str
    label: str
    rate_mbps: float
    priority_level: int  # P0 highest, P3 lowest.
    priority_weight: int  # P0=4, P1=3, P2=2, P3=1.
    scientific_value: float  # 0-1.
    ttl_seconds: int
    is_key: bool
    is_video: bool = False


@dataclass
class Chunk:
    chunk_id: int
    stream_id: str
    label: str
    created_s: int
    original_mb: float
    remaining_mb: float
    priority_level: int
    priority_weight: int
    scientific_value: float
    ttl_seconds: int
    event_flag: int
    is_key: bool
    is_video: bool


@dataclass
class StreamMetrics:
    produced_mb: float = 0.0
    delivered_mb: float = 0.0
    dropped_mb: float = 0.0
    pending_mb: float = 0.0


@dataclass
class SimulationResult:
    profile_id: str
    profile_name: str
    strategy: str
    capacity_mb: float
    produced_mb: float
    delivered_mb: float
    dropped_mb: float
    pending_mb: float
    data_loss_rate: float
    delivery_rate: float
    overflow_rate: float
    recovery_coefficient: float
    peak_queue_mb: float
    backlog_at_recovery_start_mb: float
    pending_recovery_backlog_mb: float
    key_loss_rate: float
    stream_metrics: Dict[str, StreamMetrics]


LINK_PROFILES: Tuple[LinkProfile, ...] = (
    LinkProfile(
        "P1",
        "short_outage",
        (
            LinkStage("normal", 0, 5 * 60, 2.0, 0.0),
            LinkStage("outage", 5 * 60, 10 * 60, 0.0, 0.0),
            LinkStage("recovery", 10 * 60, 30 * 60, 2.0, 0.0),
        ),
    ),
    LinkProfile(
        "P2",
        "long_outage",
        (
            LinkStage("normal", 0, 5 * 60, 2.0, 0.0),
            LinkStage("outage", 5 * 60, 25 * 60, 0.0, 0.0),
            LinkStage("recovery", 25 * 60, 55 * 60, 2.0, 0.0),
        ),
    ),
    LinkProfile(
        "P3",
        "severe_degradation",
        (
            LinkStage("normal", 0, 5 * 60, 2.0, 0.0),
            LinkStage("degraded", 5 * 60, 25 * 60, 0.2, 0.0),
            LinkStage("recovery", 25 * 60, 55 * 60, 2.0, 0.0),
        ),
    ),
    LinkProfile(
        "P4",
        "high_bandwidth_recovery",
        (
            LinkStage("normal", 0, 5 * 60, 2.0, 0.0),
            LinkStage("outage", 5 * 60, 15 * 60, 0.0, 0.0),
            LinkStage("recovery", 15 * 60, 35 * 60, 10.0, 0.0),
        ),
    ),
    LinkProfile(
        "P5",
        "fluctuating_link",
        (
            LinkStage("normal", 0, 5 * 60, 2.0, 0.0),
            LinkStage("fluctuating", 5 * 60, 10 * 60, 0.0, 0.0),
            LinkStage("fluctuating", 10 * 60, 15 * 60, 1.0, 0.0),
            LinkStage("fluctuating", 15 * 60, 20 * 60, 0.2, 0.0),
            LinkStage("fluctuating", 20 * 60, 25 * 60, 0.8, 0.0),
            LinkStage("recovery", 25 * 60, 55 * 60, 4.0, 0.0),
        ),
    ),
)

LINK_PROFILE_BY_ID = {profile.profile_id: profile for profile in LINK_PROFILES}


STREAMS: Tuple[StreamSpec, ...] = (
    StreamSpec("D1", "D1 buoy weather", 0.25, 2, 2, 0.60, 600, False),
    StreamSpec("D2", "D2 weather UTF-16", 0.25, 2, 2, 0.55, 600, False),
    StreamSpec("D3", "D3 wave sensor", 0.25, 1, 3, 0.95, 300, True),
    StreamSpec("D4", "D4 current logs", 0.25, 1, 3, 0.90, 300, True),
    StreamSpec("V1", "V1 video file", 0.50, 3, 1, 0.10, 1800, False, True),
)


def stage_at(profile: LinkProfile, second: int) -> LinkStage:
    for stage in profile.stages:
        if stage.start_s <= second < stage.end_s:
            return stage
    raise ValueError(f"second {second} is outside link profile {profile.profile_id}")


def stream_event_flag(spec: StreamSpec, second: int) -> int:
    """Synthetic event windows for key ocean streams.

    The second report labels D3 and D4 as key data but does not define anomaly
    timestamps. These deterministic windows let AoI/utility formulas exercise
    their event terms without adding randomness.
    """

    minute = second / 60.0
    if spec.stream_id == "D3" and 14.0 <= minute < 20.0:
        return 1
    if spec.stream_id == "D4" and 16.0 <= minute < 22.0:
        return 1
    return 0


def freshness(chunk: Chunk, now_s: int) -> float:
    age_seconds = max(0, now_s - chunk.created_s)
    return max(0.0, 1.0 - age_seconds / max(chunk.ttl_seconds, 1))


def waiting_minutes(chunk: Chunk, now_s: int) -> float:
    return max(0.0, now_s - chunk.created_s) / 60.0


def fifo_send_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float]:
    del now_s, water_level
    return (-chunk.created_s, -chunk.chunk_id)


def fifo_evict_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float]:
    del now_s, water_level
    # FIFO baseline uses drop-tail behavior: newest data is discarded first.
    return (-chunk.created_s, -chunk.chunk_id)


def priority_sp_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float, float]:
    del now_s, water_level
    return (-chunk.priority_level, -chunk.created_s, -chunk.chunk_id)


def priority_sp_evict_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float, float]:
    del now_s, water_level
    # Lowest priority is evicted first; within the same level, older data is
    # evicted first to keep more recent samples available.
    return (-chunk.priority_level, chunk.created_s, chunk.chunk_id)


def priority_aging_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float, float]:
    del water_level
    aging_bonus = min(30.0, 10.0 * waiting_minutes(chunk, now_s))
    score = 100.0 * chunk.priority_weight + aging_bonus - 5.0 * chunk.original_mb
    return (score, -chunk.created_s, -chunk.chunk_id)


def priority_aoi_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float, float]:
    del water_level
    score = (
        100.0 * chunk.priority_weight
        + 40.0 * chunk.event_flag
        + 30.0 * freshness(chunk, now_s)
        - 5.0 * chunk.original_mb
    )
    return (score, -chunk.created_s, -chunk.chunk_id)


def priority_utility_score(chunk: Chunk, now_s: int, water_level: float) -> Tuple[float, float, float]:
    wait_factor = min(1.0, waiting_minutes(chunk, now_s) / 10.0)
    utility = (
        60.0 * chunk.event_flag
        + 30.0 * chunk.scientific_value
        + 20.0 * freshness(chunk, now_s)
        + 10.0 * wait_factor
    )
    cost = max(math.log2(chunk.original_mb + 1.0), 0.001)
    score = utility / cost

    # Approximate the water-level actions from mechanism four: ordinary video is
    # penalized as the cache fills, while key/event data remains protected.
    if chunk.is_video:
        score -= 150.0
    if water_level >= 0.95 and not (chunk.is_key or chunk.event_flag):
        score -= 500.0
    elif water_level >= 0.85 and chunk.is_video:
        score -= 300.0
    elif water_level >= 0.70 and chunk.is_video:
        score -= 100.0

    return (score, -chunk.created_s, -chunk.chunk_id)


ScoreFunction = Callable[[Chunk, int, float], Tuple[float, ...]]


STRATEGIES: Dict[str, Tuple[ScoreFunction, ScoreFunction]] = {
    "FIFO": (fifo_send_score, fifo_evict_score),
    "Priority-SP": (priority_sp_score, priority_sp_evict_score),
    "Priority-Aging": (priority_aging_score, priority_aging_score),
    "Priority-AoI": (priority_aoi_score, priority_aoi_score),
    "Priority-Utility": (priority_utility_score, priority_utility_score),
}


def queue_size_mb(queue: Iterable[Chunk]) -> float:
    return sum(chunk.remaining_mb for chunk in queue)


def choose_best_index(queue: List[Chunk], score_fn: ScoreFunction, now_s: int, water_level: float) -> int:
    return max(range(len(queue)), key=lambda i: score_fn(queue[i], now_s, water_level))


def choose_worst_index(queue: List[Chunk], score_fn: ScoreFunction, now_s: int, water_level: float) -> int:
    return min(range(len(queue)), key=lambda i: score_fn(queue[i], now_s, water_level))


def produce_chunks(second: int, next_chunk_id: int, step_seconds: int) -> Tuple[List[Chunk], int]:
    chunks: List[Chunk] = []
    for spec in STREAMS:
        event_flag = stream_event_flag(spec, second)
        size_mb = spec.rate_mbps / 8.0 * step_seconds
        chunks.append(
            Chunk(
                chunk_id=next_chunk_id,
                stream_id=spec.stream_id,
                label=spec.label,
                created_s=second,
                original_mb=size_mb,
                remaining_mb=size_mb,
                priority_level=spec.priority_level,
                priority_weight=spec.priority_weight,
                scientific_value=spec.scientific_value,
                ttl_seconds=spec.ttl_seconds,
                event_flag=event_flag,
                is_key=spec.is_key,
                is_video=spec.is_video,
            )
        )
        next_chunk_id += 1
    return chunks, next_chunk_id


def add_metric(metrics: Dict[str, StreamMetrics], stream_id: str, field_name: str, amount: float) -> None:
    current = getattr(metrics[stream_id], field_name)
    setattr(metrics[stream_id], field_name, current + amount)


def simulate(profile: LinkProfile, strategy_name: str, capacity_mb: float, step_seconds: int) -> SimulationResult:
    send_score, evict_score = STRATEGIES[strategy_name]
    queue: List[Chunk] = []
    metrics = {spec.stream_id: StreamMetrics() for spec in STREAMS}
    next_chunk_id = 1

    peak_queue_mb = 0.0
    backlog_at_recovery_start_mb = 0.0

    recovery_start_s = profile.recovery_start_s
    for second in range(0, profile.total_duration_s, step_seconds):
        if second == recovery_start_s:
            backlog_at_recovery_start_mb = sum(
                chunk.remaining_mb for chunk in queue if chunk.created_s < recovery_start_s
            )

        stage = stage_at(profile, second)
        generated, next_chunk_id = produce_chunks(second, next_chunk_id, step_seconds)
        for chunk in generated:
            queue.append(chunk)
            add_metric(metrics, chunk.stream_id, "produced_mb", chunk.original_mb)

        available_mb = stage.effective_mbps / 8.0 * step_seconds
        while available_mb > EPSILON and queue:
            water_level = 1.0 if capacity_mb <= EPSILON else min(1.0, queue_size_mb(queue) / capacity_mb)
            idx = choose_best_index(queue, send_score, second, water_level)
            chunk = queue[idx]
            sent_mb = min(chunk.remaining_mb, available_mb)
            chunk.remaining_mb -= sent_mb
            available_mb -= sent_mb
            add_metric(metrics, chunk.stream_id, "delivered_mb", sent_mb)
            if chunk.remaining_mb <= EPSILON:
                queue.pop(idx)

        while queue_size_mb(queue) - capacity_mb > EPSILON:
            current_size = queue_size_mb(queue)
            water_level = 1.0 if capacity_mb <= EPSILON else min(1.0, current_size / capacity_mb)
            idx = choose_worst_index(queue, evict_score, second, water_level)
            chunk = queue[idx]
            dropped_mb = min(chunk.remaining_mb, current_size - capacity_mb)
            chunk.remaining_mb -= dropped_mb
            add_metric(metrics, chunk.stream_id, "dropped_mb", dropped_mb)
            if chunk.remaining_mb <= EPSILON:
                queue.pop(idx)

        peak_queue_mb = max(peak_queue_mb, queue_size_mb(queue))

    for chunk in queue:
        add_metric(metrics, chunk.stream_id, "pending_mb", chunk.remaining_mb)

    produced_mb = sum(m.produced_mb for m in metrics.values())
    delivered_mb = sum(m.delivered_mb for m in metrics.values())
    dropped_mb = sum(m.dropped_mb for m in metrics.values())
    pending_mb = sum(m.pending_mb for m in metrics.values())
    pending_recovery_backlog_mb = sum(
        chunk.remaining_mb for chunk in queue if chunk.created_s < recovery_start_s
    )

    key_produced = sum(m.produced_mb for sid, m in metrics.items() if sid in {"D3", "D4"})
    key_dropped = sum(m.dropped_mb for sid, m in metrics.items() if sid in {"D3", "D4"})

    return SimulationResult(
        profile_id=profile.profile_id,
        profile_name=profile.name,
        strategy=strategy_name,
        capacity_mb=capacity_mb,
        produced_mb=produced_mb,
        delivered_mb=delivered_mb,
        dropped_mb=dropped_mb,
        pending_mb=pending_mb,
        data_loss_rate=dropped_mb / produced_mb if produced_mb else 0.0,
        delivery_rate=delivered_mb / produced_mb if produced_mb else 0.0,
        overflow_rate=dropped_mb / produced_mb if produced_mb else 0.0,
        recovery_coefficient=(
            1.0 - pending_recovery_backlog_mb / backlog_at_recovery_start_mb
            if backlog_at_recovery_start_mb > EPSILON
            else 0.0
        ),
        peak_queue_mb=peak_queue_mb,
        backlog_at_recovery_start_mb=backlog_at_recovery_start_mb,
        pending_recovery_backlog_mb=pending_recovery_backlog_mb,
        key_loss_rate=key_dropped / key_produced if key_produced else 0.0,
        stream_metrics=metrics,
    )


def no_cache_baseline(profile: LinkProfile, step_seconds: int) -> SimulationResult:
    """A no-cache baseline matching the second report's metric definition."""

    metrics = {spec.stream_id: StreamMetrics() for spec in STREAMS}
    for second in range(0, profile.total_duration_s, step_seconds):
        stage = stage_at(profile, second)
        generated, _ = produce_chunks(second, 1, step_seconds)
        available_mb = stage.effective_mbps / 8.0 * step_seconds
        for chunk in generated:
            add_metric(metrics, chunk.stream_id, "produced_mb", chunk.original_mb)

        # Direct link transmission without buffering. Use FIFO order here because
        # the baseline has no priority cache to reorder data.
        for chunk in generated:
            if available_mb <= EPSILON:
                add_metric(metrics, chunk.stream_id, "dropped_mb", chunk.remaining_mb)
                continue
            sent_mb = min(chunk.remaining_mb, available_mb)
            add_metric(metrics, chunk.stream_id, "delivered_mb", sent_mb)
            available_mb -= sent_mb
            dropped_mb = chunk.remaining_mb - sent_mb
            if dropped_mb > EPSILON:
                add_metric(metrics, chunk.stream_id, "dropped_mb", dropped_mb)

    produced_mb = sum(m.produced_mb for m in metrics.values())
    delivered_mb = sum(m.delivered_mb for m in metrics.values())
    dropped_mb = sum(m.dropped_mb for m in metrics.values())
    key_produced = sum(m.produced_mb for sid, m in metrics.items() if sid in {"D3", "D4"})
    key_dropped = sum(m.dropped_mb for sid, m in metrics.items() if sid in {"D3", "D4"})

    return SimulationResult(
        profile_id=profile.profile_id,
        profile_name=profile.name,
        strategy="No-Cache",
        capacity_mb=0.0,
        produced_mb=produced_mb,
        delivered_mb=delivered_mb,
        dropped_mb=dropped_mb,
        pending_mb=0.0,
        data_loss_rate=dropped_mb / produced_mb if produced_mb else 0.0,
        delivery_rate=delivered_mb / produced_mb if produced_mb else 0.0,
        overflow_rate=0.0,
        recovery_coefficient=0.0,
        peak_queue_mb=0.0,
        backlog_at_recovery_start_mb=0.0,
        pending_recovery_backlog_mb=0.0,
        key_loss_rate=key_dropped / key_produced if key_produced else 0.0,
        stream_metrics=metrics,
    )


def write_summary_csv(results: List[SimulationResult], output_dir: Path) -> Path:
    path = output_dir / "cache_priority_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "profile_id",
                "profile_name",
                "strategy",
                "capacity_mb",
                "produced_mb",
                "delivered_mb",
                "dropped_mb",
                "pending_mb",
                "data_loss_rate",
                "delivery_rate",
                "overflow_rate",
                "recovery_coefficient",
                "peak_queue_mb",
                "backlog_at_recovery_start_mb",
                "pending_recovery_backlog_mb",
                "key_loss_rate",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "profile_id": result.profile_id,
                    "profile_name": result.profile_name,
                    "strategy": result.strategy,
                    "capacity_mb": f"{result.capacity_mb:.3f}",
                    "produced_mb": f"{result.produced_mb:.3f}",
                    "delivered_mb": f"{result.delivered_mb:.3f}",
                    "dropped_mb": f"{result.dropped_mb:.3f}",
                    "pending_mb": f"{result.pending_mb:.3f}",
                    "data_loss_rate": f"{result.data_loss_rate:.6f}",
                    "delivery_rate": f"{result.delivery_rate:.6f}",
                    "overflow_rate": f"{result.overflow_rate:.6f}",
                    "recovery_coefficient": f"{result.recovery_coefficient:.6f}",
                    "peak_queue_mb": f"{result.peak_queue_mb:.3f}",
                    "backlog_at_recovery_start_mb": f"{result.backlog_at_recovery_start_mb:.3f}",
                    "pending_recovery_backlog_mb": f"{result.pending_recovery_backlog_mb:.3f}",
                    "key_loss_rate": f"{result.key_loss_rate:.6f}",
                }
            )
    return path


def write_stream_csv(results: List[SimulationResult], output_dir: Path) -> Path:
    path = output_dir / "cache_priority_by_stream.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "profile_id",
                "profile_name",
                "strategy",
                "capacity_mb",
                "stream_id",
                "produced_mb",
                "delivered_mb",
                "dropped_mb",
                "pending_mb",
                "loss_rate",
            ],
        )
        writer.writeheader()
        for result in results:
            for stream_id, metric in result.stream_metrics.items():
                writer.writerow(
                    {
                        "profile_id": result.profile_id,
                        "profile_name": result.profile_name,
                        "strategy": result.strategy,
                        "capacity_mb": f"{result.capacity_mb:.3f}",
                        "stream_id": stream_id,
                        "produced_mb": f"{metric.produced_mb:.3f}",
                        "delivered_mb": f"{metric.delivered_mb:.3f}",
                        "dropped_mb": f"{metric.dropped_mb:.3f}",
                        "pending_mb": f"{metric.pending_mb:.3f}",
                        "loss_rate": f"{metric.dropped_mb / metric.produced_mb:.6f}" if metric.produced_mb else "0.000000",
                    }
                )
    return path


def format_percent(value: float) -> str:
    return f"{100.0 * value:6.2f}%"


def print_summary(results: List[SimulationResult]) -> None:
    print("\nSimulation summary")
    print("- Link profiles: P1 short outage, P2 long outage, P3 severe degradation, P4 high recovery, P5 fluctuating link")
    print("- Total generation rate: 1.5 Mbps")
    print("- Capacities: no-cache baseline plus requested cache capacities\n")
    header = (
        f"{'profile':<7} {'strategy':<17} {'cap_MB':>8} {'peak_MB':>9} {'drop_MB':>9} "
        f"{'loss':>9} {'key_loss':>9} {'recovery':>9}"
    )
    print(header)
    print("-" * len(header))
    for result in results:
        print(
            f"{result.profile_id:<7} {result.strategy:<17} {result.capacity_mb:8.0f} {result.peak_queue_mb:9.1f} "
            f"{result.dropped_mb:9.1f} {format_percent(result.data_loss_rate):>9} "
            f"{format_percent(result.key_loss_rate):>9} {format_percent(result.recovery_coefficient):>9}"
        )


def parse_capacities(raw_values: List[str]) -> List[float]:
    capacities: List[float] = []
    for raw in raw_values:
        lowered = raw.strip().lower()
        if lowered.endswith("gb"):
            capacities.append(float(lowered[:-2]) * 1024.0)
        elif lowered.endswith("mb"):
            capacities.append(float(lowered[:-2]))
        else:
            capacities.append(float(lowered))
    return capacities


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate edge-cache priority mechanisms.")
    parser.add_argument(
        "--capacities",
        nargs="+",
        default=["100MB", "250MB", "500MB", "1GB"],
        help="Cache capacities, e.g. 100MB 250MB 500MB 1GB.",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=[profile.profile_id for profile in LINK_PROFILES],
        help="Link profiles to simulate. Defaults to P1 P2 P3 P4 P5.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory for CSV outputs.",
    )
    parser.add_argument(
        "--step-seconds",
        type=int,
        default=DEFAULT_STEP_SECONDS,
        help="Simulation time step. Default 10 seconds keeps minute-level stages exact and runs quickly.",
    )
    args = parser.parse_args()

    selected_profiles = [LINK_PROFILE_BY_ID[profile_id] for profile_id in args.profiles]
    for profile in selected_profiles:
        if profile.total_duration_s % args.step_seconds != 0:
            raise ValueError(f"--step-seconds must divide total duration for {profile.profile_id}")

    capacities = parse_capacities(args.capacities)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: List[SimulationResult] = []
    for profile in selected_profiles:
        results.append(no_cache_baseline(profile, args.step_seconds))
        for capacity_mb in capacities:
            # FIFO is kept as a baseline; the four priority mechanisms are the
            # Priority-* strategies below.
            for strategy in ["FIFO", "Priority-SP", "Priority-Aging", "Priority-AoI", "Priority-Utility"]:
                results.append(simulate(profile, strategy, capacity_mb, args.step_seconds))

    summary_path = write_summary_csv(results, args.output_dir)
    stream_path = write_stream_csv(results, args.output_dir)
    print_summary(results)
    print(f"\nWrote {summary_path}")
    print(f"Wrote {stream_path}")


if __name__ == "__main__":
    main()
