from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework.spatial import estimate_spatial


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate distance_scale from a known-distance detection.")
    parser.add_argument("--class-name", help="Detected class name, e.g. chair/person.")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"), help="Bounding box xyxy.")
    parser.add_argument("--frame-width", type=int, default=1280)
    parser.add_argument("--frame-height", type=int, default=720)
    parser.add_argument("--hfov", type=float, default=118.0)
    parser.add_argument("--known-distance-m", type=float, required=True)
    parser.add_argument("--event-json", help="Optional event JSON line or path to a JSONL file. Uses the first event by default.")
    args = parser.parse_args()

    class_name = args.class_name
    bbox = tuple(args.bbox) if args.bbox else None

    if args.event_json:
        source = Path(args.event_json)
        text = source.read_text(encoding="utf-8").splitlines()[0] if source.exists() else args.event_json
        event = json.loads(text)
        class_name = class_name or event["class_name"]
        bbox = bbox or tuple(float(value) for value in event["bbox_xyxy"])
        args.frame_width = int(event.get("frame_width", args.frame_width))
        args.frame_height = int(event.get("frame_height", args.frame_height))

    if not class_name or bbox is None:
        raise SystemExit("Provide --class-name and --bbox, or provide --event-json.")

    raw = estimate_spatial(
        class_name=class_name,
        bbox_xyxy=bbox,
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        horizontal_fov_deg=args.hfov,
        distance_scale=1.0,
    )

    if raw.distance_m is None:
        raise SystemExit(f"No default object height for class: {class_name}")

    distance_scale = args.known_distance_m / raw.distance_m
    calibrated = estimate_spatial(
        class_name=class_name,
        bbox_xyxy=bbox,
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        horizontal_fov_deg=args.hfov,
        distance_scale=distance_scale,
    )

    print(
        json.dumps(
            {
                "class_name": class_name,
                "bbox_xyxy": list(bbox),
                "raw_distance_m": raw.distance_m,
                "known_distance_m": args.known_distance_m,
                "distance_scale": round(distance_scale, 4),
                "calibrated_distance_m": calibrated.distance_m,
                "clock_label": calibrated.clock_label_en,
                "azimuth_deg": calibrated.azimuth_deg,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
