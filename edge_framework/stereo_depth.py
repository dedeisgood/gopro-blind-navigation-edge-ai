from __future__ import annotations

import math
from dataclasses import dataclass

from edge_framework.spatial import azimuth_to_clock_hour, x_to_azimuth_deg


@dataclass(frozen=True)
class StereoDepthEstimate:
    disparity_px: float
    distance_m: float | None
    azimuth_deg: float
    clock_hour: int
    clock_label_en: str
    clock_label_zh: str
    distance_source: str


def estimate_stereo_distance(
    *,
    left_bbox_xyxy: tuple[float, float, float, float],
    right_bbox_xyxy: tuple[float, float, float, float],
    frame_width: int,
    frame_height: int,
    baseline_m: float,
    horizontal_fov_deg: float = 118.0,
    distance_scale: float = 1.0,
    min_disparity_px: float = 2.0,
) -> StereoDepthEstimate:
    left_cx = (left_bbox_xyxy[0] + left_bbox_xyxy[2]) / 2.0
    right_cx = (right_bbox_xyxy[0] + right_bbox_xyxy[2]) / 2.0
    disparity_px = abs(left_cx - right_cx)

    azimuth_deg = x_to_azimuth_deg(left_cx, frame_width, horizontal_fov_deg)
    clock_hour = azimuth_to_clock_hour(azimuth_deg)

    distance_m = None
    if disparity_px >= min_disparity_px:
        focal_x_px = frame_width / (2.0 * math.tan(math.radians(horizontal_fov_deg) / 2.0))
        distance_m = (baseline_m * focal_x_px / disparity_px) * distance_scale

    return StereoDepthEstimate(
        disparity_px=round(disparity_px, 2),
        distance_m=round(distance_m, 2) if distance_m is not None else None,
        azimuth_deg=round(azimuth_deg, 2),
        clock_hour=clock_hour,
        clock_label_en=f"{clock_hour} o'clock",
        clock_label_zh=f"{clock_hour}\u9ede\u9418\u65b9\u5411",
        distance_source="stereo_disparity" if distance_m is not None else "insufficient_disparity",
    )
