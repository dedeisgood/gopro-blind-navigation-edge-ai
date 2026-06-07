from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework import navigability as nav
from edge_framework import semantic_navigability as semnav


def frame_at(video_path: Path, second: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 12
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(second * fps))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame at {second}s from {video_path}")
    return frame


def infer_segmentation(
    frame: np.ndarray,
    *,
    processor: Any,
    model: Any,
    device: str,
) -> tuple[np.ndarray, float]:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    inputs = processor(images=image, return_tensors="pt").to(device)

    started = time.perf_counter()
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        upsampled_logits = torch.nn.functional.interpolate(
            logits,
            size=frame.shape[:2],
            mode="bilinear",
            align_corners=False,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    seg_map = upsampled_logits.argmax(dim=1).squeeze().detach().cpu().numpy().astype(np.int32)
    return seg_map, latency_ms


def infer_depth(
    frame: np.ndarray,
    *,
    processor: Any,
    model: Any,
    device: str,
) -> tuple[np.ndarray, dict[str, Any], float]:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    inputs = processor(images=image, return_tensors="pt").to(device)

    started = time.perf_counter()
    with torch.no_grad():
        outputs = model(**inputs)
        predicted_depth = outputs.predicted_depth
        prediction = torch.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=image.size[::-1],
            mode="bicubic",
            align_corners=False,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    depth = prediction.squeeze().detach().cpu().numpy()
    depth_norm = nav.normalize_depth(depth)
    return depth_norm, nav.analyze_depth(depth_norm), latency_ms


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe wall/floor/door segmentation and depth-fused navigability.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--seconds", nargs="+", type=float, default=[5, 15, 25, 35])
    parser.add_argument("--seg-model", default=semnav.DEFAULT_SEGMENTATION_MODEL)
    parser.add_argument("--depth-model", default="depth-anything/Depth-Anything-V2-Small-hf")
    parser.add_argument("--no-depth", action="store_true")
    parser.add_argument("--out-dir", default="runs/semantic_navigability_probe")
    args = parser.parse_args()

    from transformers import AutoImageProcessor, AutoModelForDepthEstimation, AutoModelForSemanticSegmentation

    device = "cuda" if torch.cuda.is_available() else "cpu"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    seg_processor = AutoImageProcessor.from_pretrained(args.seg_model)
    seg_model = AutoModelForSemanticSegmentation.from_pretrained(args.seg_model).to(device)
    seg_model.eval()
    seg_load_s = time.perf_counter() - started
    id2label = {int(k): v for k, v in seg_model.config.id2label.items()}

    depth_processor = None
    depth_model = None
    depth_load_s = 0.0
    if not args.no_depth:
        started = time.perf_counter()
        depth_processor = AutoImageProcessor.from_pretrained(args.depth_model)
        depth_model = AutoModelForDepthEstimation.from_pretrained(args.depth_model).to(device)
        depth_model.eval()
        depth_load_s = time.perf_counter() - started

    results = []
    for second in args.seconds:
        frame = frame_at(Path(args.video), second)
        visibility_analysis = semnav.analyze_visibility(frame)
        seg_map, seg_latency_ms = infer_segmentation(frame, processor=seg_processor, model=seg_model, device=device)
        semantic_analysis = semnav.analyze_segmentation(seg_map, id2label)

        depth_norm = None
        depth_analysis = None
        depth_latency_ms = 0.0
        if depth_processor is not None and depth_model is not None:
            depth_norm, depth_analysis, depth_latency_ms = infer_depth(
                frame,
                processor=depth_processor,
                model=depth_model,
                device=device,
            )

        fusion_analysis = semnav.fuse_with_depth(
            semantic_analysis=semantic_analysis,
            depth_analysis=depth_analysis,
            visibility_analysis=visibility_analysis,
        )

        stem = f"semantic_nav_t{int(second):02d}"
        raw_path = out_dir / f"{stem}_frame.jpg"
        seg_color_path = out_dir / f"{stem}_segmentation.png"
        overlay_path = out_dir / f"{stem}_fusion_overlay.jpg"
        depth_path = out_dir / f"{stem}_depth.png"

        cv2.imwrite(str(raw_path), frame)
        cv2.imwrite(str(seg_color_path), semnav.semantic_color_overlay(seg_map, id2label))
        cv2.imwrite(str(overlay_path), semnav.draw_semantic_fusion_overlay(frame, seg_map, id2label, semantic_analysis, fusion_analysis))
        if depth_norm is not None:
            cv2.imwrite(str(depth_path), (depth_norm * 255).astype(np.uint8))

        results.append(
            {
                "second": second,
                "segmentation_ms": round(seg_latency_ms, 2),
                "depth_ms": round(depth_latency_ms, 2),
                "raw_frame": str(raw_path),
                "segmentation": str(seg_color_path),
                "overlay": str(overlay_path),
                "depth": str(depth_path) if depth_norm is not None else "",
                "semantic": semantic_analysis,
                "visibility": visibility_analysis,
                "fusion": {
                    key: value
                    for key, value in fusion_analysis.items()
                    if key not in {"semantic", "depth"}
                },
                "depth_analysis": depth_analysis,
            }
        )

    payload = {
        "seg_model": args.seg_model,
        "depth_model": "" if args.no_depth else args.depth_model,
        "device": device,
        "seg_load_s": round(seg_load_s, 2),
        "depth_load_s": round(depth_load_s, 2),
        "video": args.video,
        "results": results,
    }
    summary_path = out_dir / "semantic_navigability_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
