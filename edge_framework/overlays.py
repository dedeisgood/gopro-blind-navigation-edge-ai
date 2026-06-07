from __future__ import annotations

import math
from typing import Any

import cv2


def draw_clock_border(
    frame: Any,
    *,
    color: tuple[int, int, int] = (255, 255, 0),
    border_color: tuple[int, int, int] = (255, 255, 0),
) -> None:
    height, width = frame.shape[:2]
    margin = max(18, int(min(width, height) * 0.045))
    radius_x = (width / 2.0) - margin * 1.6
    radius_y = (height / 2.0) - margin * 1.6
    center_x = width / 2.0
    center_y = height / 2.0
    font_scale = max(0.62, min(width, height) / 700.0)
    thickness = max(2, round(min(width, height) / 360))

    cv2.rectangle(frame, (margin, margin), (width - margin, height - margin), border_color, 2)

    for hour in range(1, 13):
        angle = 2.0 * math.pi * hour / 12.0
        x = center_x + math.sin(angle) * radius_x
        y = center_y - math.cos(angle) * radius_y
        label = str(hour)
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        origin = (int(x - text_w / 2.0), int(y + text_h / 2.0))
        shadow = (origin[0] + 2, origin[1] + 2)
        cv2.putText(frame, label, shadow, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness + 2)
        cv2.putText(frame, label, origin, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
