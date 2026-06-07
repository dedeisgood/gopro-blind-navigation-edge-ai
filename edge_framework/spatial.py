from __future__ import annotations

import math
from dataclasses import dataclass


DEFAULT_OBJECT_HEIGHT_M = {
    "person": 1.70,
    "bicycle": 1.10,
    "car": 1.50,
    "motorcycle": 1.10,
    "bus": 3.00,
    "truck": 3.00,
    "traffic light": 1.00,
    "stop sign": 0.75,
    "bench": 0.90,
    "chair": 0.85,
    "couch": 0.90,
    "potted plant": 0.60,
    "backpack": 0.45,
    "suitcase": 0.65,
    "sports ball": 0.22,
}


@dataclass(frozen=True)
class SpatialEstimate:
    azimuth_deg: float
    clock_hour: int
    clock_label_en: str
    clock_label_zh: str
    distance_m: float | None
    distance_label_en: str
    distance_label_zh: str
    distance_source: str


def estimate_spatial(
    *,
    class_name: str,
    bbox_xyxy: tuple[float, float, float, float],
    frame_width: int,
    frame_height: int,
    horizontal_fov_deg: float = 118.0,
    object_heights_m: dict[str, float] | None = None,
    distance_scale: float = 1.0,
) -> SpatialEstimate:
    x1, y1, x2, y2 = bbox_xyxy
    cx = (x1 + x2) / 2
    bbox_h = max(1.0, y2 - y1)

    azimuth_deg = x_to_azimuth_deg(cx, frame_width, horizontal_fov_deg)
    clock_hour = azimuth_to_clock_hour(azimuth_deg)
    distance_m = estimate_distance_from_bbox_height(
        class_name=class_name,
        bbox_height_px=bbox_h,
        frame_width=frame_width,
        frame_height=frame_height,
        horizontal_fov_deg=horizontal_fov_deg,
        object_heights_m=object_heights_m or DEFAULT_OBJECT_HEIGHT_M,
        distance_scale=distance_scale,
    )

    distance_label_en, distance_label_zh = distance_labels(distance_m)

    return SpatialEstimate(
        azimuth_deg=round(azimuth_deg, 2),
        clock_hour=clock_hour,
        clock_label_en=f"{clock_hour} o'clock",
        clock_label_zh=f"{clock_hour}點鐘方向",
        distance_m=round(distance_m, 2) if distance_m is not None else None,
        distance_label_en=distance_label_en,
        distance_label_zh=distance_label_zh,
        distance_source="bbox_height_pinhole" if distance_m is not None else "unknown_object_height",
    )


def x_to_azimuth_deg(cx: float, frame_width: int, horizontal_fov_deg: float) -> float:
    normalized = (cx / max(frame_width, 1)) - 0.5
    return normalized * horizontal_fov_deg


def azimuth_to_clock_hour(azimuth_deg: float) -> int:
    offset = int(round(azimuth_deg / 30.0))
    hour = 12 + offset
    while hour <= 0:
        hour += 12
    while hour > 12:
        hour -= 12
    return hour


def estimate_distance_from_bbox_height(
    *,
    class_name: str,
    bbox_height_px: float,
    frame_width: int,
    frame_height: int,
    horizontal_fov_deg: float,
    object_heights_m: dict[str, float],
    distance_scale: float,
) -> float | None:
    object_height_m = object_heights_m.get(class_name)
    if object_height_m is None:
        return None

    vertical_fov_deg = horizontal_to_vertical_fov(horizontal_fov_deg, frame_width, frame_height)
    focal_y_px = frame_height / (2.0 * math.tan(math.radians(vertical_fov_deg) / 2.0))
    distance_m = (object_height_m * focal_y_px) / max(bbox_height_px, 1.0)
    return max(0.05, distance_m * distance_scale)


def horizontal_to_vertical_fov(horizontal_fov_deg: float, frame_width: int, frame_height: int) -> float:
    aspect_y_over_x = frame_height / max(frame_width, 1)
    horizontal_rad = math.radians(horizontal_fov_deg)
    vertical_rad = 2.0 * math.atan(math.tan(horizontal_rad / 2.0) * aspect_y_over_x)
    return math.degrees(vertical_rad)


def distance_labels(distance_m: float | None) -> tuple[str, str]:
    if distance_m is None:
        return "unknown distance", "距離未知"
    if distance_m < 1.5:
        return "near", "近距離"
    if distance_m < 3.0:
        return "mid distance", "中距離"
    return "far", "遠距離"


def risk_from_distance(distance_m: float | None, direction: str, area_ratio: float) -> str:
    if distance_m is not None:
        if distance_m < 1.5:
            return "high"
        if distance_m < 3.0:
            return "high" if direction == "center" else "medium"
        if direction == "center":
            return "medium"
        return "low"

    if area_ratio >= 0.16:
        return "high"
    if area_ratio >= 0.045:
        return "high" if direction == "center" else "medium"
    if direction == "center":
        return "medium"
    return "low"

