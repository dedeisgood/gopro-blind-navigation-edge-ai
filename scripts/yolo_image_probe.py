from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run YOLO on one image and save annotated output.")
    parser.add_argument("--image", default="assets/ultralytics_bus.jpg")
    parser.add_argument("--weights", default="yolov8n.pt")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--out-dir", default="runs/yolo_image_probe")
    args = parser.parse_args()

    from ultralytics import YOLO

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    results = model.predict(args.image, device=args.device, verbose=False)

    detections = []
    for result in results:
        annotated = result.plot()
        names = result.names

        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
            detections.append(
                {
                    "class_name": names[class_id],
                    "confidence": round(confidence, 4),
                    "bbox_xyxy": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                }
            )

        import cv2

        cv2.imwrite(str(out_dir / "annotated.jpg"), annotated)

    (out_dir / "detections.json").write_text(
        json.dumps(detections, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "detections": len(detections),
                "annotated_image": str(out_dir / "annotated.jpg"),
                "detections_json": str(out_dir / "detections.json"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

