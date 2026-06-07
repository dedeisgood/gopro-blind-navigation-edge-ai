from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan local camera indexes and save preview frames.")
    parser.add_argument("--max-index", type=int, default=8)
    parser.add_argument("--out-dir", default="runs/camera_scan")
    parser.add_argument("--warmup-frames", type=int, default=8)
    args = parser.parse_args()

    import cv2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    devices = []
    for index in range(args.max_index + 1):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            devices.append({"index": index, "opened": False})
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        frame = None
        ok = False
        for _ in range(args.warmup_frames):
            ok, frame = cap.read()
            if ok and frame is not None:
                break

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        preview_path = None

        if ok and frame is not None:
            preview_path = out_dir / f"camera_{index}.jpg"
            cv2.imwrite(str(preview_path), frame)

        cap.release()
        devices.append(
            {
                "index": index,
                "opened": True,
                "frame_ok": bool(ok),
                "width": width,
                "height": height,
                "fps": round(float(fps), 3) if fps else 0,
                "preview": str(preview_path) if preview_path else None,
            }
        )

    report_path = out_dir / "camera_scan.json"
    report_path.write_text(json.dumps(devices, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "devices": devices}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

