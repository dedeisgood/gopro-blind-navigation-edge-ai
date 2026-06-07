from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework.spatial import estimate_spatial, risk_from_distance
from edge_framework.overlays import draw_clock_border
from edge_framework.speech_policy import speech_label


@dataclass(frozen=True)
class ObstacleEvent:
    frame_index: int
    timestamp_s: float
    frame_width: int
    frame_height: int
    class_name: str
    confidence: float
    direction: str
    azimuth_deg: float
    clock_hour: int
    clock_label_en: str
    clock_label_zh: str
    distance_m: float | None
    distance_label_en: str
    distance_label_zh: str
    distance_source: str
    risk: str
    bbox_xyxy: list[float]
    area_ratio: float
    cue: str


def load_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_device(requested_device: str) -> str:
    if requested_device.lower() != "auto":
        return requested_device

    try:
        import torch
    except Exception:
        return "cpu"

    return "0" if torch.cuda.is_available() else "cpu"


def iter_frames(source: dict[str, Any]) -> Iterator[tuple[int, float, Any]]:
    import cv2

    source_type = source["type"]

    if source_type == "image_file":
        image = cv2.imread(source["path"])
        if image is None:
            raise RuntimeError(f"Could not read image file: {source['path']}")

        frames = int(source.get("frames", 30))
        fps = float(source.get("fps", 5))
        frame_interval = 1.0 / fps if fps > 0 else 0

        for index in range(frames):
            yield index, index * frame_interval, image.copy()
        return

    if source_type == "video_file":
        cap = cv2.VideoCapture(source["path"])
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {source['path']}")

        fps = cap.get(cv2.CAP_PROP_FPS) or float(source.get("fps", 30))
        frame_interval = 1.0 / fps if fps > 0 else 0
        max_frames = source.get("max_frames")
        index = 0

        try:
            while True:
                if max_frames is not None and index >= int(max_frames):
                    break

                ok, frame = cap.read()
                if not ok:
                    break

                yield index, index * frame_interval, frame
                index += 1
        finally:
            cap.release()
        return

    raise ValueError(f"Unsupported source type: {source_type}")


def get_direction(cx: float, width: int, center_region_ratio: float) -> str:
    center_width = width * center_region_ratio
    left_boundary = (width - center_width) / 2
    right_boundary = left_boundary + center_width

    if cx < left_boundary:
        return "left"
    if cx > right_boundary:
        return "right"
    return "center"


def get_risk(area_ratio: float, direction: str, risk_config: dict[str, Any]) -> str:
    medium = float(risk_config.get("medium_area_ratio", 0.05))
    high = float(risk_config.get("high_area_ratio", 0.18))

    if area_ratio >= high:
        return "high"

    if area_ratio >= medium:
        if direction == "center" and risk_config.get("center_priority_boost", True):
            return "high"
        return "medium"

    if direction == "center" and risk_config.get("center_priority_boost", True):
        return "medium"

    return "low"


def make_cue(event: ObstacleEvent) -> str:
    distance = f"{event.distance_m:.1f}m" if event.distance_m is not None else event.distance_label_en
    class_name, _class_zh, _generic = speech_label(event.class_name, event.confidence)

    if event.risk == "high":
        return f"High risk {class_name} at {event.clock_label_en}, {distance}"
    if event.risk == "medium":
        return f"{class_name} at {event.clock_label_en}, {distance}"
    return f"Low risk {class_name} at {event.clock_label_en}, {distance}"


def draw_event(frame: Any, event: ObstacleEvent) -> None:
    import cv2

    colors = {
        "low": (80, 220, 80),
        "medium": (0, 210, 255),
        "high": (0, 0, 255),
    }
    color = colors[event.risk]
    x1, y1, x2, y2 = [int(value) for value in event.bbox_xyxy]

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)


def draw_cue_panel(frame: Any, events: list[ObstacleEvent]) -> None:
    import cv2

    visible_events = [event for event in events if event.risk in {"high", "medium"}][:5]
    if not visible_events:
        return

    height, width = frame.shape[:2]
    panel_width = min(width - 24, 720)
    panel_height = 36 + len(visible_events) * 30
    x1 = 12
    y1 = max(12, height - panel_height - 12)
    x2 = x1 + panel_width
    y2 = y1 + panel_height

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)
    cv2.putText(frame, "Assistive cues", (x1 + 14, y1 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

    colors = {
        "medium": (0, 210, 255),
        "high": (0, 0, 255),
    }

    for index, event in enumerate(visible_events):
        y = y1 + 56 + index * 30
        text = f"{event.risk.upper()} | {event.cue} | conf {event.confidence:.2f}"
        cv2.putText(frame, text, (x1 + 14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.66, colors[event.risk], 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run obstacle awareness MVP for visually impaired assistive navigation.")
    parser.add_argument("--config", required=True, help="Path to obstacle assist JSON config.")
    args = parser.parse_args()

    import cv2
    from ultralytics import YOLO

    config = load_config(args.config)
    model_config = config["model"]
    risk_config = config.get("risk", {})
    output_config = config["output"]

    run_dir = Path(output_config.get("run_dir", f"runs/{config['task_name']}"))
    run_dir.mkdir(parents=True, exist_ok=True)

    events_path = run_dir / output_config.get("events", "events.jsonl")
    metrics_path = run_dir / output_config.get("metrics", "metrics.json")
    video_path = run_dir / output_config.get("annotated_video", "annotated_obstacle_assist.mp4")

    model = YOLO(model_config.get("weights", "yolov8n.pt"))
    device = resolve_device(model_config.get("device", "auto"))
    confidence_threshold = float(model_config.get("confidence", 0.25))
    obstacle_classes = set(model_config.get("obstacle_classes", []))
    center_region_ratio = float(risk_config.get("center_region_ratio", 0.34))
    horizontal_fov_deg = float(risk_config.get("horizontal_fov_deg", 118.0))
    distance_scale = float(risk_config.get("distance_scale", 1.0))

    writer = None
    event_count = 0
    risk_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()
    clock_counts: Counter[str] = Counter()
    distance_counts: Counter[str] = Counter()
    latencies_ms: list[float] = []
    started_at = time.perf_counter()
    processed_frames = 0

    with events_path.open("w", encoding="utf-8") as events_file:
        for frame_index, timestamp_s, frame in iter_frames(config["source"]):
            height, width = frame.shape[:2]

            if writer is None:
                source_fps = float(config["source"].get("fps", 30))
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(video_path), fourcc, source_fps, (width, height))

            inference_started = time.perf_counter()
            results = model.predict(frame, device=device, conf=confidence_threshold, verbose=False)
            latency_ms = (time.perf_counter() - inference_started) * 1000
            latencies_ms.append(latency_ms)
            processed_frames += 1

            frame_events: list[ObstacleEvent] = []

            for result in results:
                names = result.names

                for box in result.boxes:
                    class_id = int(box.cls[0])
                    class_name = names[class_id]

                    if obstacle_classes and class_name not in obstacle_classes:
                        continue

                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
                    bbox_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                    area_ratio = bbox_area / float(width * height)
                    cx = (x1 + x2) / 2
                    direction = get_direction(cx, width, center_region_ratio)
                    spatial = estimate_spatial(
                        class_name=class_name,
                        bbox_xyxy=(x1, y1, x2, y2),
                        frame_width=width,
                        frame_height=height,
                        horizontal_fov_deg=horizontal_fov_deg,
                        distance_scale=distance_scale,
                    )
                    risk = risk_from_distance(spatial.distance_m, direction, area_ratio)

                    event = ObstacleEvent(
                        frame_index=frame_index,
                        timestamp_s=round(timestamp_s, 3),
                        frame_width=width,
                        frame_height=height,
                        class_name=class_name,
                        confidence=round(confidence, 4),
                        direction=direction,
                        azimuth_deg=spatial.azimuth_deg,
                        clock_hour=spatial.clock_hour,
                        clock_label_en=spatial.clock_label_en,
                        clock_label_zh=spatial.clock_label_zh,
                        distance_m=spatial.distance_m,
                        distance_label_en=spatial.distance_label_en,
                        distance_label_zh=spatial.distance_label_zh,
                        distance_source=spatial.distance_source,
                        risk=risk,
                        bbox_xyxy=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                        area_ratio=round(area_ratio, 4),
                        cue="",
                    )
                    event = ObstacleEvent(**{**asdict(event), "cue": make_cue(event)})

                    draw_event(frame, event)
                    frame_events.append(event)
                    events_file.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
                    event_count += 1
                    risk_counts[risk] += 1
                    direction_counts[direction] += 1
                    clock_counts[str(event.clock_hour)] += 1
                    distance_counts[event.distance_label_en] += 1

            draw_cue_panel(frame, frame_events)
            draw_clock_border(frame)
            writer.write(frame)

    if writer is not None:
        writer.release()

    elapsed_s = time.perf_counter() - started_at
    sorted_latencies = sorted(latencies_ms)
    p95_index = round((len(sorted_latencies) - 1) * 0.95) if sorted_latencies else 0
    metrics = {
        "task_name": config["task_name"],
        "processed_frames": processed_frames,
        "device": device,
        "event_count": event_count,
        "elapsed_s": round(elapsed_s, 3),
        "fps": round(processed_frames / elapsed_s, 3) if elapsed_s > 0 else 0,
        "avg_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 3) if latencies_ms else 0,
        "p95_latency_ms": round(sorted_latencies[p95_index], 3) if sorted_latencies else 0,
        "risk_counts": dict(risk_counts),
        "direction_counts": dict(direction_counts),
        "clock_counts": dict(clock_counts),
        "distance_counts": dict(distance_counts),
        "events_path": str(events_path),
        "annotated_video": str(video_path),
    }

    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
