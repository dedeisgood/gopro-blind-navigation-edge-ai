from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Frame:
    index: int
    timestamp_s: float
    width: int
    height: int
    data: Any = None


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class Event:
    rule_name: str
    frame_index: int
    timestamp_s: float
    message: str
    payload: dict[str, Any]

