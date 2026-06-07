from __future__ import annotations

import time

from .config import AppConfig
from .detectors import create_detector
from .metrics import Metrics
from .output import EventWriter
from .rules import RuleEngine
from .sources import create_source


class EdgeVideoPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.source = create_source(config.source)
        self.detector = create_detector(config.model, device=config.inference.device)
        self.rule_engine = RuleEngine(config.rules)
        self.metrics = Metrics()

    def run(self) -> dict[str, float | int]:
        frame_skip = max(0, self.config.inference.frame_skip)

        with EventWriter(self.config.output.run_dir) as writer:
            for frame in self.source.frames():
                if frame_skip and frame.index % (frame_skip + 1) != 0:
                    self.metrics.record_skip()
                    continue

                started_at = time.perf_counter()
                detections = self.detector.detect(frame)
                events = self.rule_engine.evaluate(frame, detections)
                writer.write_many(events)

                latency_ms = (time.perf_counter() - started_at) * 1000
                self.metrics.record_frame(latency_ms)
                self.metrics.record_events(len(events))

        return self.metrics.summary()

