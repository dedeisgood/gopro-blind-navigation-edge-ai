from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from edge_framework.spatial import azimuth_to_clock_hour, horizontal_to_vertical_fov, x_to_azimuth_deg


@dataclass(frozen=True)
class MarkerDistance:
    marker_id: int
    center_x: float
    center_y: float
    side_px: float
    distance_m: float
    distance_side_m: float
    distance_pnp_m: float | None
    azimuth_deg: float
    clock_hour: int
    clock_label_en: str
    clock_label_zh: str
    corners_xy: list[list[float]]


def get_aruco_dictionary(name: str) -> cv2.aruco.Dictionary:
    key = name if name.startswith("DICT_") else f"DICT_{name}"
    dictionary_id = getattr(cv2.aruco, key, None)
    if dictionary_id is None:
        raise ValueError(f"Unsupported ArUco dictionary: {name}")
    return cv2.aruco.getPredefinedDictionary(dictionary_id)


def make_camera_matrix(frame_width: int, frame_height: int, horizontal_fov_deg: float) -> np.ndarray:
    fx = frame_width / (2.0 * math.tan(math.radians(horizontal_fov_deg) / 2.0))
    vertical_fov_deg = horizontal_to_vertical_fov(horizontal_fov_deg, frame_width, frame_height)
    fy = frame_height / (2.0 * math.tan(math.radians(vertical_fov_deg) / 2.0))
    return np.array(
        [
            [fx, 0.0, frame_width / 2.0],
            [0.0, fy, frame_height / 2.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def generate_marker_image(
    *,
    dictionary_name: str,
    marker_id: int,
    marker_px: int,
    margin_px: int,
) -> np.ndarray:
    dictionary = get_aruco_dictionary(dictionary_name)

    if hasattr(cv2.aruco, "generateImageMarker"):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_px)
    else:
        marker = np.zeros((marker_px, marker_px), dtype=np.uint8)
        cv2.aruco.drawMarker(dictionary, marker_id, marker_px, marker, 1)

    canvas_size = marker_px + margin_px * 2
    canvas = np.full((canvas_size, canvas_size), 255, dtype=np.uint8)
    canvas[margin_px : margin_px + marker_px, margin_px : margin_px + marker_px] = marker
    return canvas


def detect_marker_distances(
    frame: np.ndarray,
    *,
    marker_size_m: float,
    dictionary_name: str = "4X4_50",
    target_id: int | None = 0,
    horizontal_fov_deg: float = 118.0,
) -> list[MarkerDistance]:
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dictionary = get_aruco_dictionary(dictionary_name)

    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None:
        return []

    camera_matrix = make_camera_matrix(width, height, horizontal_fov_deg)
    dist_coeffs = np.zeros((5, 1), dtype=np.float64)
    object_points = np.array(
        [
            [-marker_size_m / 2.0, marker_size_m / 2.0, 0.0],
            [marker_size_m / 2.0, marker_size_m / 2.0, 0.0],
            [marker_size_m / 2.0, -marker_size_m / 2.0, 0.0],
            [-marker_size_m / 2.0, -marker_size_m / 2.0, 0.0],
        ],
        dtype=np.float64,
    )

    estimates: list[MarkerDistance] = []
    for marker_corners, marker_id_arr in zip(corners, ids):
        marker_id = int(marker_id_arr[0])
        if target_id is not None and marker_id != target_id:
            continue

        pts = marker_corners.reshape(4, 2).astype(np.float64)
        side_lengths = [
            float(np.linalg.norm(pts[1] - pts[0])),
            float(np.linalg.norm(pts[2] - pts[1])),
            float(np.linalg.norm(pts[3] - pts[2])),
            float(np.linalg.norm(pts[0] - pts[3])),
        ]
        side_px = max(1.0, sum(side_lengths) / len(side_lengths))
        fx = float(camera_matrix[0, 0])
        distance_side_m = marker_size_m * fx / side_px

        distance_pnp_m = None
        ok, _rvec, tvec = cv2.solvePnP(object_points, pts, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if ok:
            distance_pnp_m = float(np.linalg.norm(tvec))

        distance_m = distance_pnp_m if distance_pnp_m is not None else distance_side_m
        center_x = float(np.mean(pts[:, 0]))
        center_y = float(np.mean(pts[:, 1]))
        azimuth_deg = x_to_azimuth_deg(center_x, width, horizontal_fov_deg)
        clock_hour = azimuth_to_clock_hour(azimuth_deg)

        estimates.append(
            MarkerDistance(
                marker_id=marker_id,
                center_x=round(center_x, 2),
                center_y=round(center_y, 2),
                side_px=round(side_px, 2),
                distance_m=round(distance_m, 3),
                distance_side_m=round(distance_side_m, 3),
                distance_pnp_m=round(distance_pnp_m, 3) if distance_pnp_m is not None else None,
                azimuth_deg=round(azimuth_deg, 2),
                clock_hour=clock_hour,
                clock_label_en=f"{clock_hour} o'clock",
                clock_label_zh=f"{clock_hour}\u9ede\u9418\u65b9\u5411",
                corners_xy=[[round(float(x), 2), round(float(y), 2)] for x, y in pts],
            )
        )

    return estimates
