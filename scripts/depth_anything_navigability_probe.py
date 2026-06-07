from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework import navigability as nav


def frame_at(video_path: Path, second: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 12
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(second * fps))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame at {second}s from {video_path}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe navigability using Depth Anything V2 on sampled frames.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--seconds", nargs="+", type=float, default=[5, 15, 25, 35])
    parser.add_argument("--model", default="depth-anything/Depth-Anything-V2-Small-hf")
    parser.add_argument("--out-dir", default="runs/depth_navigability_probe")
    args = parser.parse_args()

    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    device = "cuda" if torch.cuda.is_available() else "cpu"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    processor = AutoImageProcessor.from_pretrained(args.model)
    model = AutoModelForDepthEstimation.from_pretrained(args.model).to(device)
    model.eval()
    load_s = time.perf_counter() - started

    results = []
    for second in args.seconds:
        frame = frame_at(Path(args.video), second)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        inputs = processor(images=image, return_tensors="pt").to(device)

        infer_started = time.perf_counter()
        with torch.no_grad():
            outputs = model(**inputs)
            predicted_depth = outputs.predicted_depth
            prediction = torch.nn.functional.interpolate(
                predicted_depth.unsqueeze(1),
                size=image.size[::-1],
                mode="bicubic",
                align_corners=False,
            )
        infer_ms = (time.perf_counter() - infer_started) * 1000.0

        depth = prediction.squeeze().detach().cpu().numpy()
        depth_norm = nav.normalize_depth(depth)
        analysis = nav.analyze_depth(depth_norm)
        overlay = nav.draw_depth_overlay(frame, depth_norm, analysis)

        stem = f"depth_nav_t{int(second):02d}"
        raw_path = out_dir / f"{stem}_frame.jpg"
        depth_path = out_dir / f"{stem}_depth.png"
        overlay_path = out_dir / f"{stem}_overlay.jpg"
        cv2.imwrite(str(raw_path), frame)
        cv2.imwrite(str(depth_path), (depth_norm * 255).astype(np.uint8))
        cv2.imwrite(str(overlay_path), overlay)
        results.append(
            {
                "second": second,
                "inference_ms": round(infer_ms, 2),
                "raw_frame": str(raw_path),
                "depth": str(depth_path),
                "overlay": str(overlay_path),
                **analysis,
            }
        )

    payload = {
        "model": args.model,
        "device": device,
        "load_s": round(load_s, 2),
        "video": args.video,
        "results": results,
    }
    summary_path = out_dir / "depth_navigability_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
