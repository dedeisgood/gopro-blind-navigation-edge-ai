from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field


@dataclass
class Metrics:
    processed_frames: int = 0
    skipped_frames: int = 0
    event_count: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    latencies_ms: list[float] = field(default_factory=list)

    def record_frame(self, latency_ms: float) -> None:
        self.processed_frames += 1
        self.latencies_ms.append(latency_ms)

    def record_skip(self) -> None:
        self.skipped_frames += 1

    def record_events(self, count: int) -> None:
        self.event_count += count

    def summary(self) -> dict[str, float | int]:
        elapsed_s = max(time.perf_counter() - self.started_at, 1e-9)
        avg_latency = statistics.fmean(self.latencies_ms) if self.latencies_ms else 0.0
        p95_latency = percentile(self.latencies_ms, 0.95) if self.latencies_ms else 0.0

        return {
            "processed_frames": self.processed_frames,
            "skipped_frames": self.skipped_frames,
            "event_count": self.event_count,
            "elapsed_s": round(elapsed_s, 3),
            "fps": round(self.processed_frames / elapsed_s, 3),
            "avg_latency_ms": round(avg_latency, 3),
            "p95_latency_ms": round(p95_latency, 3),
        }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0

    index = int(round((len(ordered) - 1) * q))
    return ordered[index]

