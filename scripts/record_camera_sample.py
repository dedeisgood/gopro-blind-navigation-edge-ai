from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a short local camera sample.")
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--fps", type=float, default=15)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--out", required=True)
    parser.add_argument("--backend", choices=["default", "dshow", "msmf"], default="dshow")
    args = parser.parse_args()

    import cv2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    backend_map = {
        "default": 0,
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
    }

    backend = backend_map[args.backend]
    cap = cv2.VideoCapture(args.index) if backend == 0 else cv2.VideoCapture(args.index, backend)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {args.index}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or args.width
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or args.height
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, args.fps, (actual_width, actual_height))

    started_at = time.perf_counter()
    frame_count = 0
    preview_path = out_path.with_suffix(".jpg")

    try:
        while time.perf_counter() - started_at < args.seconds:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            writer.write(frame)
            frame_count += 1
            if frame_count == 1:
                cv2.imwrite(str(preview_path), frame)
    finally:
        writer.release()
        cap.release()

    elapsed_s = time.perf_counter() - started_at
    print(
        json.dumps(
            {
                "camera_index": args.index,
                "video": str(out_path),
                "preview": str(preview_path),
                "frames": frame_count,
                "elapsed_s": round(elapsed_s, 3),
                "capture_fps": round(frame_count / elapsed_s, 3) if elapsed_s > 0 else 0,
                "width": actual_width,
                "height": actual_height,
                "backend": args.backend,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
