from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework.stereo_depth import estimate_stereo_distance


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate distance from two matched GoPro detections.")
    parser.add_argument("--left-bbox", nargs=4, type=float, required=True, metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--right-bbox", nargs=4, type=float, required=True, metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--frame-width", type=int, default=1280)
    parser.add_argument("--frame-height", type=int, default=720)
    parser.add_argument("--baseline-m", type=float, required=True, help="Physical distance between the two GoPro lenses.")
    parser.add_argument("--hfov", type=float, default=118.0)
    parser.add_argument("--distance-scale", type=float, default=1.0)
    args = parser.parse_args()

    estimate = estimate_stereo_distance(
        left_bbox_xyxy=tuple(args.left_bbox),
        right_bbox_xyxy=tuple(args.right_bbox),
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        baseline_m=args.baseline_m,
        horizontal_fov_deg=args.hfov,
        distance_scale=args.distance_scale,
    )
    payload = {
        "left_bbox_xyxy": args.left_bbox,
        "right_bbox_xyxy": args.right_bbox,
        "frame_width": args.frame_width,
        "frame_height": args.frame_height,
        "baseline_m": args.baseline_m,
        **asdict(estimate),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
