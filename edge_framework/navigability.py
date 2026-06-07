from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from edge_framework.overlays import draw_clock_border


SECTOR_HOURS = [10, 11, 12, 1, 2]
FRONT_BLOCKED_RISK = 0.34
SECTOR_WARN_RISK = 0.34
SECTOR_DANGER_RISK = 0.58
TURN_MARGIN = 0.12

SPEECH_FRONT_PASSABLE = "\u524d\u65b9\u53ef\u901a\u884c"
SPEECH_TURN_LEFT = "\u524d\u65b9\u53ef\u80fd\u4e0d\u53ef\u901a\u884c\uff0c\u5de6\u524d\u65b9\u8f03\u7a7a"
SPEECH_TURN_RIGHT = "\u524d\u65b9\u53ef\u80fd\u4e0d\u53ef\u901a\u884c\uff0c\u53f3\u524d\u65b9\u8f03\u7a7a"
SPEECH_STOP = "\u524d\u65b9\u53ef\u80fd\u4e0d\u53ef\u901a\u884c\uff0c\u8acb\u5148\u505c\u6b62"


def normalize_depth(depth: np.ndarray) -> np.ndarray:
    depth = depth.astype(np.float32)
    low = float(np.percentile(depth, 2))
    high = float(np.percentile(depth, 98))
    if high <= low:
        return np.zeros_like(depth, dtype=np.float32)
    return np.clip((depth - low) / (high - low), 0.0, 1.0)


def sector_mask(width: int, height: int, hour: int) -> np.ndarray:
    # Lower-middle visual field corresponds better to walkable space.
    y1 = int(height * 0.42)
    y2 = int(height * 0.92)
    bins = {
        10: (0.00, 0.22),
        11: (0.22, 0.40),
        12: (0.40, 0.60),
        1: (0.60, 0.78),
        2: (0.78, 1.00),
    }
    x1_ratio, x2_ratio = bins[hour]
    x1 = int(width * x1_ratio)
    x2 = int(width * x2_ratio)
    mask = np.zeros((height, width), dtype=bool)
    mask[y1:y2, x1:x2] = True
    return mask


def analyze_depth(depth_norm: np.ndarray) -> dict[str, Any]:
    height, width = depth_norm.shape[:2]
    sectors = []
    # Depth Anything V2 relative maps are normalized here so larger means closer.
    for hour in SECTOR_HOURS:
        mask = sector_mask(width, height, hour)
        values = depth_norm[mask]
        close_score = float(np.median(values)) if values.size else 0.0
        near_ratio = float(np.mean(values > 0.62)) if values.size else 0.0
        sectors.append(
            {
                "hour": hour,
                "close_score": round(close_score, 4),
                "near_ratio": round(near_ratio, 4),
                "risk_score": round(close_score * 0.7 + near_ratio * 0.3, 4),
            }
        )

    sector_by_hour = {int(s["hour"]): s for s in sectors}
    front = sector_by_hour[12]
    left_score = np.mean([s["risk_score"] for s in sectors if s["hour"] in {10, 11}])
    right_score = np.mean([s["risk_score"] for s in sectors if s["hour"] in {1, 2}])
    front_score = (
        sector_by_hour[11]["risk_score"] * 0.25
        + sector_by_hour[12]["risk_score"] * 0.50
        + sector_by_hour[1]["risk_score"] * 0.25
    )
    front_blocked = front_score >= FRONT_BLOCKED_RISK or front["near_ratio"] > 0.34

    if not front_blocked:
        recommendation = "front_passable"
        speech_zh = SPEECH_FRONT_PASSABLE
        speech_overlay = "FRONT PASSABLE"
    elif left_score + TURN_MARGIN < right_score:
        recommendation = "turn_left"
        speech_zh = SPEECH_TURN_LEFT
        speech_overlay = "FRONT BLOCKED / LEFT CLEARER"
    elif right_score + TURN_MARGIN < left_score:
        recommendation = "turn_right"
        speech_zh = SPEECH_TURN_RIGHT
        speech_overlay = "FRONT BLOCKED / RIGHT CLEARER"
    else:
        recommendation = "stop"
        speech_zh = SPEECH_STOP
        speech_overlay = "FRONT BLOCKED / STOP"

    return {
        "sectors": sectors,
        "front_score": round(float(front_score), 4),
        "front_blocked": bool(front_blocked),
        "left_score": round(float(left_score), 4),
        "right_score": round(float(right_score), 4),
        "recommendation": recommendation,
        "speech_zh": speech_zh,
        "speech_overlay": speech_overlay,
    }


def draw_depth_overlay(frame: np.ndarray, depth_norm: np.ndarray, analysis: dict[str, Any]) -> np.ndarray:
    heat = cv2.applyColorMap((depth_norm * 255).astype(np.uint8), cv2.COLORMAP_MAGMA)
    output = cv2.addWeighted(frame, 0.58, heat, 0.42, 0)
    draw_clock_border(output)
    draw_sector_overlay(output, analysis)
    return output


def draw_sector_overlay(frame: np.ndarray, analysis: dict[str, Any]) -> None:
    height, width = frame.shape[:2]
    for sector in analysis["sectors"]:
        mask = sector_mask(width, height, int(sector["hour"]))
        ys, xs = np.where(mask)
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        color = (0, 255, 0)
        if sector["risk_score"] > SECTOR_DANGER_RISK:
            color = (0, 0, 255)
        elif sector["risk_score"] > SECTOR_WARN_RISK:
            color = (0, 210, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            f"{sector['hour']} risk {sector['risk_score']:.2f}",
            (x1 + 8, y1 + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )

    panel = frame.copy()
    cv2.rectangle(panel, (12, height - 72), (min(width - 12, 760), height - 12), (20, 20, 20), -1)
    cv2.addWeighted(panel, 0.62, frame, 0.38, 0, frame)
    cv2.putText(
        frame,
        analysis["speech_overlay"],
        (28, height - 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
    )
