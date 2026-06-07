from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework.aruco_distance import generate_marker_image


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an ArUco marker image for phone-screen distance calibration.")
    parser.add_argument("--dictionary", default="4X4_50")
    parser.add_argument("--id", type=int, default=0)
    parser.add_argument("--marker-px", type=int, default=1000)
    parser.add_argument("--margin-px", type=int, default=220)
    parser.add_argument("--out", default="assets/aruco_4x4_id0_phone.png")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = generate_marker_image(
        dictionary_name=args.dictionary,
        marker_id=args.id,
        marker_px=args.marker_px,
        margin_px=args.margin_px,
    )
    ok = cv2.imwrite(str(out_path), image)
    if not ok:
        raise SystemExit(f"Could not write marker image: {out_path}")

    meta = {
        "dictionary": args.dictionary,
        "marker_id": args.id,
        "marker_px": args.marker_px,
        "margin_px": args.margin_px,
        "image": str(out_path),
        "instruction": "Display full-screen and measure the black marker square side on the phone screen.",
    }
    meta_path = out_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
