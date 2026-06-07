from __future__ import annotations

import math
import random
from typing import Protocol

from .config import ModelConfig
from .types import Detection, Frame


class Detector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]:
        ...


class DummyDetector:
    """Deterministic detector for testing the pipeline without installing an AI model."""

    def __init__(self, classes: list[str]) -> None:
        self.classes = classes or ["object"]
        self.random = random.Random(42)

    def detect(self, frame: Frame) -> list[Detection]:
        detections: list[Detection] = []

        if "person" in self.classes:
            person_count = 1 + int((math.sin(frame.index / 8) + 1) * 1.8)
            for item in range(person_count):
                x1 = 40 + item * 95
                y1 = 80 + (item % 2) * 25
                detections.append(
                    Detection(
                        class_name="person",
                        confidence=0.72 + 0.05 * (item % 3),
                        bbox_xyxy=(x1, y1, x1 + 70, y1 + 140),
                    )
                )

        if "no_helmet" in self.classes and frame.index % 17 in {0, 1, 2, 3}:
            detections.append(
                Detection(
                    class_name="no_helmet",
                    confidence=0.84,
                    bbox_xyxy=(220, 55, 280, 115),
                )
            )

        if "helmet" in self.classes:
            detections.append(
                Detection(
                    class_name="helmet",
                    confidence=0.88,
                    bbox_xyxy=(55, 55, 110, 105),
                )
            )

        return detections


class YoloDetector:
    def __init__(self, weights: str, device: str = "cpu") -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("YoloDetector requires ultralytics. Install it before using backend='yolo'.") from exc

        self.model = YOLO(weights)
        self.device = device

    def detect(self, frame: Frame) -> list[Detection]:
        if frame.data is None:
            return []

        results = self.model.predict(frame.data, device=self.device, verbose=False)
        detections: list[Detection] = []

        for result in results:
            names = result.names
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
                detections.append(
                    Detection(
                        class_name=names[class_id],
                        confidence=confidence,
                        bbox_xyxy=(x1, y1, x2, y2),
                    )
                )

        return detections


def create_detector(config: ModelConfig, *, device: str = "cpu") -> Detector:
    if config.backend == "dummy":
        return DummyDetector(config.classes)

    if config.backend == "yolo":
        if not config.weights:
            raise ValueError("backend='yolo' requires model.weights")
        return YoloDetector(config.weights, device=device)

    raise ValueError(f"Unsupported detector backend: {config.backend}")

