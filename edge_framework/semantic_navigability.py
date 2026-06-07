from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from edge_framework import navigability as nav
from edge_framework.overlays import draw_clock_border


DEFAULT_SEGMENTATION_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"
SEMANTIC_FRONT_BLOCKED_RISK = 0.45
FUSION_TURN_MARGIN = 0.12
LOW_VISIBILITY_MEAN_LUMA = 45.0
LOW_VISIBILITY_DARK_RATIO = 0.65
SPEECH_LOW_VISIBILITY = "\u5149\u7dda\u4e0d\u8db3\uff0c\u8acb\u5148\u505c\u6b62"

WALL_LABELS = {"wall"}
FLOOR_LABELS = {"floor"}
DOOR_LABELS = {"door", "screen door"}
CEILING_LABELS = {"ceiling"}


def label_id_sets(id2label: dict[int | str, str]) -> dict[str, set[int]]:
    labels = {int(k): v.lower() for k, v in id2label.items()}
    return {
        "wall": {idx for idx, label in labels.items() if label in WALL_LABELS},
        "floor": {idx for idx, label in labels.items() if label in FLOOR_LABELS},
        "door": {idx for idx, label in labels.items() if label in DOOR_LABELS},
        "ceiling": {idx for idx, label in labels.items() if label in CEILING_LABELS},
    }


def _ratio(values: np.ndarray, ids: set[int]) -> float:
    if values.size == 0 or not ids:
        return 0.0
    return float(np.mean(np.isin(values, list(ids))))


def analyze_segmentation(seg_map: np.ndarray, id2label: dict[int | str, str]) -> dict[str, Any]:
    height, width = seg_map.shape[:2]
    ids = label_id_sets(id2label)
    sectors = []

    for hour in nav.SECTOR_HOURS:
        mask = nav.sector_mask(width, height, hour)
        values = seg_map[mask]
        wall_ratio = _ratio(values, ids["wall"])
        floor_ratio = _ratio(values, ids["floor"])
        door_ratio = _ratio(values, ids["door"])
        ceiling_ratio = _ratio(values, ids["ceiling"])
        lack_floor_score = max(0.0, (0.45 - floor_ratio) / 0.45)
        risk_score = wall_ratio * 0.75 + lack_floor_score * 0.25 + ceiling_ratio * 0.15 - door_ratio * 0.10
        risk_score = float(np.clip(risk_score, 0.0, 1.0))
        sectors.append(
            {
                "hour": hour,
                "wall_ratio": round(wall_ratio, 4),
                "floor_ratio": round(floor_ratio, 4),
                "door_ratio": round(door_ratio, 4),
                "ceiling_ratio": round(ceiling_ratio, 4),
                "risk_score": round(risk_score, 4),
            }
        )

    sector_by_hour = {int(s["hour"]): s for s in sectors}
    front_score = (
        sector_by_hour[11]["risk_score"] * 0.25
        + sector_by_hour[12]["risk_score"] * 0.50
        + sector_by_hour[1]["risk_score"] * 0.25
    )
    left_score = np.mean([s["risk_score"] for s in sectors if s["hour"] in {10, 11}])
    right_score = np.mean([s["risk_score"] for s in sectors if s["hour"] in {1, 2}])
    front_floor_ratio = (
        sector_by_hour[11]["floor_ratio"] * 0.25
        + sector_by_hour[12]["floor_ratio"] * 0.50
        + sector_by_hour[1]["floor_ratio"] * 0.25
    )
    front_wall_ratio = (
        sector_by_hour[11]["wall_ratio"] * 0.25
        + sector_by_hour[12]["wall_ratio"] * 0.50
        + sector_by_hour[1]["wall_ratio"] * 0.25
    )
    front_blocked = front_score >= SEMANTIC_FRONT_BLOCKED_RISK or (front_wall_ratio >= 0.42 and front_floor_ratio <= 0.20)

    return {
        "sectors": sectors,
        "front_score": round(float(front_score), 4),
        "front_blocked": bool(front_blocked),
        "front_floor_ratio": round(float(front_floor_ratio), 4),
        "front_wall_ratio": round(float(front_wall_ratio), 4),
        "left_score": round(float(left_score), 4),
        "right_score": round(float(right_score), 4),
    }


def analyze_visibility(frame: np.ndarray) -> dict[str, Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_luma = float(np.mean(gray))
    std_luma = float(np.std(gray))
    dark_ratio = float(np.mean(gray < 35))
    very_dark_ratio = float(np.mean(gray < 18))
    low_visibility = mean_luma < LOW_VISIBILITY_MEAN_LUMA or dark_ratio > LOW_VISIBILITY_DARK_RATIO
    return {
        "mean_luma": round(mean_luma, 2),
        "std_luma": round(std_luma, 2),
        "dark_ratio": round(dark_ratio, 4),
        "very_dark_ratio": round(very_dark_ratio, 4),
        "low_visibility": bool(low_visibility),
    }


def fuse_with_depth(
    *,
    semantic_analysis: dict[str, Any] | None,
    depth_analysis: dict[str, Any] | None,
    visibility_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    semantic_front = float(semantic_analysis["front_score"]) if semantic_analysis else 0.0
    depth_front = float(depth_analysis["front_score"]) if depth_analysis else 0.0
    front_score = max(semantic_front, depth_front)

    semantic_left = float(semantic_analysis["left_score"]) if semantic_analysis else 0.0
    semantic_right = float(semantic_analysis["right_score"]) if semantic_analysis else 0.0
    depth_left = float(depth_analysis["left_score"]) if depth_analysis else 0.0
    depth_right = float(depth_analysis["right_score"]) if depth_analysis else 0.0
    left_score = max(semantic_left, depth_left)
    right_score = max(semantic_right, depth_right)

    front_blocked = bool(semantic_analysis and semantic_analysis["front_blocked"]) or bool(
        depth_analysis and depth_analysis["front_blocked"]
    )

    if visibility_analysis and visibility_analysis.get("low_visibility"):
        front_score = max(front_score, 1.0)
        front_blocked = True
        recommendation = "stop"
        speech_zh = SPEECH_LOW_VISIBILITY
        speech_overlay = "LOW VISIBILITY / STOP"
        reason = "low_visibility"
    elif not front_blocked:
        recommendation = "front_passable"
        speech_zh = nav.SPEECH_FRONT_PASSABLE
        speech_overlay = "FRONT PASSABLE"
    else:
        if left_score + FUSION_TURN_MARGIN < right_score:
            recommendation = "turn_left"
            speech_zh = nav.SPEECH_TURN_LEFT
            speech_overlay = "FRONT BLOCKED / LEFT CLEARER"
        elif right_score + FUSION_TURN_MARGIN < left_score:
            recommendation = "turn_right"
            speech_zh = nav.SPEECH_TURN_RIGHT
            speech_overlay = "FRONT BLOCKED / RIGHT CLEARER"
        else:
            recommendation = "stop"
            speech_zh = nav.SPEECH_STOP
            speech_overlay = "FRONT BLOCKED / STOP"
        if semantic_front >= depth_front:
            reason = "semantic_wall_or_no_floor"
        else:
            reason = "depth_close_space"
    if not front_blocked:
        reason = "passable"

    return {
        "front_score": round(float(front_score), 4),
        "front_blocked": front_blocked,
        "left_score": round(float(left_score), 4),
        "right_score": round(float(right_score), 4),
        "recommendation": recommendation,
        "speech_zh": speech_zh,
        "speech_overlay": speech_overlay,
        "reason": reason,
        "semantic": semantic_analysis,
        "depth": depth_analysis,
        "visibility": visibility_analysis,
    }


def semantic_color_overlay(seg_map: np.ndarray, id2label: dict[int | str, str]) -> np.ndarray:
    ids = label_id_sets(id2label)
    colors = np.zeros((*seg_map.shape[:2], 3), dtype=np.uint8)
    if ids["wall"]:
        colors[np.isin(seg_map, list(ids["wall"]))] = (0, 0, 220)
    if ids["floor"]:
        colors[np.isin(seg_map, list(ids["floor"]))] = (0, 180, 0)
    if ids["door"]:
        colors[np.isin(seg_map, list(ids["door"]))] = (220, 120, 0)
    if ids["ceiling"]:
        colors[np.isin(seg_map, list(ids["ceiling"]))] = (160, 160, 0)
    return colors


def draw_semantic_fusion_overlay(
    frame: np.ndarray,
    seg_map: np.ndarray,
    id2label: dict[int | str, str],
    semantic_analysis: dict[str, Any],
    fusion_analysis: dict[str, Any],
) -> np.ndarray:
    sem_colors = semantic_color_overlay(seg_map, id2label)
    output = cv2.addWeighted(frame, 0.62, sem_colors, 0.38, 0)
    draw_clock_border(output)

    height, width = output.shape[:2]
    for sector in semantic_analysis["sectors"]:
        mask = nav.sector_mask(width, height, int(sector["hour"]))
        ys, xs = np.where(mask)
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        color = (0, 255, 0)
        if sector["risk_score"] > 0.58:
            color = (0, 0, 255)
        elif sector["risk_score"] > 0.34:
            color = (0, 210, 255)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        label = f"{sector['hour']} W{sector['wall_ratio']:.2f} F{sector['floor_ratio']:.2f}"
        cv2.putText(output, label, (x1 + 8, y1 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 2)

    panel = output.copy()
    cv2.rectangle(panel, (12, height - 88), (min(width - 12, 820), height - 12), (20, 20, 20), -1)
    cv2.addWeighted(panel, 0.68, output, 0.32, 0, output)
    cv2.putText(
        output,
        fusion_analysis["speech_overlay"],
        (28, height - 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        output,
        f"semantic front {semantic_analysis['front_score']:.2f} | fused {fusion_analysis['front_score']:.2f} | {fusion_analysis['reason']}",
        (28, height - 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (230, 230, 230),
        1,
    )
    return output
