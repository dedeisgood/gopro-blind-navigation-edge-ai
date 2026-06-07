from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework import navigability as nav
from edge_framework import semantic_navigability as semnav


def video_info(video_path: Path) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    duration_s = frames / fps if fps > 0 else 0.0
    return {
        "frames": frames,
        "fps": round(fps, 3),
        "width": width,
        "height": height,
        "duration_s": round(duration_s, 3),
    }


def sample_seconds(duration_s: float, sample_count: int) -> list[float]:
    if duration_s <= 0:
        return [0.0]
    start = min(1.5, max(0.0, duration_s * 0.20))
    end = max(start, duration_s - 1.0)
    samples = np.linspace(start, end, max(1, sample_count))
    return [round(float(value), 2) for value in samples]


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
        upsampled_logits = torch.nn.functional.interpolate(
            outputs.logits,
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
        prediction = torch.nn.functional.interpolate(
            outputs.predicted_depth.unsqueeze(1),
            size=image.size[::-1],
            mode="bicubic",
            align_corners=False,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    depth = prediction.squeeze().detach().cpu().numpy()
    depth_norm = nav.normalize_depth(depth)
    return depth_norm, nav.analyze_depth(depth_norm), latency_ms


def safe_stem(name: str) -> str:
    return Path(name).stem


def analyze_video(
    *,
    video_entry: dict[str, Any],
    dataset_dir: Path,
    out_dir: Path,
    sample_count: int,
    seg_processor: Any,
    seg_model: Any,
    depth_processor: Any,
    depth_model: Any,
    device: str,
    id2label: dict[int, str],
) -> dict[str, Any]:
    video_path = dataset_dir / video_entry["filename"]
    info = video_info(video_path)
    seconds = sample_seconds(float(info["duration_s"]), sample_count)
    video_out_dir = out_dir / safe_stem(video_entry["filename"])
    video_out_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    for second in seconds:
        frame = frame_at(video_path, second)
        visibility = semnav.analyze_visibility(frame)
        seg_map, seg_ms = infer_segmentation(frame, processor=seg_processor, model=seg_model, device=device)
        semantic = semnav.analyze_segmentation(seg_map, id2label)
        depth_norm, depth_analysis, depth_ms = infer_depth(frame, processor=depth_processor, model=depth_model, device=device)
        fusion = semnav.fuse_with_depth(
            semantic_analysis=semantic,
            depth_analysis=depth_analysis,
            visibility_analysis=visibility,
        )

        stem = f"t{str(second).replace('.', '_').zfill(4)}"
        overlay_path = video_out_dir / f"{stem}_fusion_overlay.jpg"
        frame_path = video_out_dir / f"{stem}_frame.jpg"
        seg_path = video_out_dir / f"{stem}_segmentation.png"
        depth_path = video_out_dir / f"{stem}_depth.png"
        cv2.imwrite(str(frame_path), frame)
        cv2.imwrite(str(seg_path), semnav.semantic_color_overlay(seg_map, id2label))
        cv2.imwrite(str(depth_path), (depth_norm * 255).astype(np.uint8))
        cv2.imwrite(str(overlay_path), semnav.draw_semantic_fusion_overlay(frame, seg_map, id2label, semantic, fusion))

        samples.append(
            {
                "second": second,
                "segmentation_ms": round(seg_ms, 2),
                "depth_ms": round(depth_ms, 2),
                "semantic_front_score": semantic["front_score"],
                "semantic_front_wall_ratio": semantic["front_wall_ratio"],
                "semantic_front_floor_ratio": semantic["front_floor_ratio"],
                "depth_front_score": depth_analysis["front_score"],
                "fusion_front_score": fusion["front_score"],
                "mean_luma": visibility["mean_luma"],
                "dark_ratio": visibility["dark_ratio"],
                "low_visibility": visibility["low_visibility"],
                "front_blocked": fusion["front_blocked"],
                "recommendation": fusion["recommendation"],
                "reason": fusion["reason"],
                "speech_zh": fusion["speech_zh"],
                "overlay": str(overlay_path),
                "frame": str(frame_path),
                "segmentation": str(seg_path),
                "depth": str(depth_path),
                "semantic": semantic,
                "depth_analysis": depth_analysis,
                "visibility": visibility,
            }
        )

    recommendation_counts = Counter(sample["recommendation"] for sample in samples)
    reason_counts = Counter(sample["reason"] for sample in samples)
    blocked_count = sum(1 for sample in samples if sample["front_blocked"])
    avg = lambda key: round(float(np.mean([sample[key] for sample in samples])), 4) if samples else 0.0
    representative_overlay = samples[len(samples) // 2]["overlay"] if samples else ""

    return {
        "index": video_entry.get("index"),
        "filename": video_entry["filename"],
        "label_key": video_entry.get("label_key", ""),
        "label_zh": video_entry.get("label_zh", ""),
        "synthetic": bool(video_entry.get("synthetic", False)),
        "transform": video_entry.get("transform", "none"),
        **info,
        "sample_count": len(samples),
        "blocked_count": blocked_count,
        "blocked_ratio": round(blocked_count / max(1, len(samples)), 3),
        "dominant_recommendation": recommendation_counts.most_common(1)[0][0] if recommendation_counts else "",
        "recommendation_counts": dict(recommendation_counts),
        "reason_counts": dict(reason_counts),
        "avg_semantic_front_score": avg("semantic_front_score"),
        "avg_front_wall_ratio": avg("semantic_front_wall_ratio"),
        "avg_front_floor_ratio": avg("semantic_front_floor_ratio"),
        "avg_depth_front_score": avg("depth_front_score"),
        "avg_fusion_front_score": avg("fusion_front_score"),
        "avg_mean_luma": avg("mean_luma"),
        "avg_dark_ratio": avg("dark_ratio"),
        "low_visibility_count": sum(1 for sample in samples if sample["low_visibility"]),
        "avg_segmentation_ms": avg("segmentation_ms"),
        "avg_depth_ms": avg("depth_ms"),
        "representative_overlay": representative_overlay,
        "samples": samples,
    }


def write_csv(summary_path: Path, videos: list[dict[str, Any]]) -> None:
    fields = [
        "index",
        "filename",
        "label_key",
        "synthetic",
        "duration_s",
        "sample_count",
        "blocked_ratio",
        "dominant_recommendation",
        "avg_front_wall_ratio",
        "avg_front_floor_ratio",
        "avg_depth_front_score",
        "avg_fusion_front_score",
        "avg_mean_luma",
        "avg_dark_ratio",
        "low_visibility_count",
        "avg_segmentation_ms",
        "avg_depth_ms",
        "representative_overlay",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for video in videos:
            writer.writerow({field: video.get(field, "") for field in fields})


def write_report(report_path: Path, videos: list[dict[str, Any]]) -> None:
    lines = [
        "# GoPro Dataset Semantic + Depth Evaluation",
        "",
        "This report samples each scenario video and runs SegFormer wall/floor/door segmentation plus Depth Anything V2 depth estimation.",
        "",
        "| # | File | Synthetic | Duration | Blocked ratio | Dominant cue | Front wall | Front floor | Luma | Dark | Fusion score |",
        "| ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for video in videos:
        lines.append(
            "| {index} | {filename} | {synthetic} | {duration_s:.2f}s | {blocked_ratio:.2f} | {dominant_recommendation} | {avg_front_wall_ratio:.2f} | {avg_front_floor_ratio:.2f} | {avg_mean_luma:.1f} | {avg_dark_ratio:.2f} | {avg_fusion_front_score:.2f} |".format(
                **video
            )
        )
    lines.extend(
        [
            "",
            "Representative overlays are saved in each video's output folder. Synthetic videos are useful for left/right logic checks, but should not be counted as real-world validation footage.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contact_sheet(contact_sheet_path: Path, videos: list[dict[str, Any]]) -> None:
    thumbs = []
    for video in videos:
        overlay = video.get("representative_overlay")
        if not overlay:
            continue
        image = Image.open(overlay).convert("RGB")
        image.thumbnail((360, 210))
        canvas = Image.new("RGB", (380, 250), (20, 20, 20))
        canvas.paste(image, (10, 10))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 218), video["filename"][:42], fill=(255, 255, 255))
        draw.text((10, 234), f"{video['dominant_recommendation']} blocked={video['blocked_ratio']:.2f}", fill=(220, 220, 220))
        thumbs.append(canvas)

    if not thumbs:
        return

    cols = 2
    rows = int(np.ceil(len(thumbs) / cols))
    sheet = Image.new("RGB", (cols * 380, rows * 250), (12, 12, 12))
    for idx, thumb in enumerate(thumbs):
        x = (idx % cols) * 380
        y = (idx // cols) * 250
        sheet.paste(thumb, (x, y))
    sheet.save(contact_sheet_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch evaluate GoPro scenario videos with semantic + depth fusion.")
    parser.add_argument("--dataset-dir", default="runs/gopro_dataset_v1")
    parser.add_argument("--manifest", default="dataset_manifest.json")
    parser.add_argument("--out-dir", default="runs/gopro_dataset_analysis_v1")
    parser.add_argument("--sample-count", type=int, default=4)
    parser.add_argument("--seg-model", default=semnav.DEFAULT_SEGMENTATION_MODEL)
    parser.add_argument("--depth-model", default="depth-anything/Depth-Anything-V2-Small-hf")
    args = parser.parse_args()

    from transformers import AutoImageProcessor, AutoModelForDepthEstimation, AutoModelForSemanticSegmentation

    dataset_dir = Path(args.dataset_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dataset_dir / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    started = time.perf_counter()
    seg_processor = AutoImageProcessor.from_pretrained(args.seg_model)
    seg_model = AutoModelForSemanticSegmentation.from_pretrained(args.seg_model).to(device)
    seg_model.eval()
    depth_processor = AutoImageProcessor.from_pretrained(args.depth_model)
    depth_model = AutoModelForDepthEstimation.from_pretrained(args.depth_model).to(device)
    depth_model.eval()
    load_s = time.perf_counter() - started
    id2label = {int(k): v for k, v in seg_model.config.id2label.items()}

    videos = []
    for entry in manifest["videos"]:
        videos.append(
            analyze_video(
                video_entry=entry,
                dataset_dir=dataset_dir,
                out_dir=out_dir,
                sample_count=args.sample_count,
                seg_processor=seg_processor,
                seg_model=seg_model,
                depth_processor=depth_processor,
                depth_model=depth_model,
                device=device,
                id2label=id2label,
            )
        )

    payload = {
        "dataset_dir": str(dataset_dir),
        "manifest": str(manifest_path),
        "out_dir": str(out_dir),
        "device": device,
        "seg_model": args.seg_model,
        "depth_model": args.depth_model,
        "model_load_s": round(load_s, 2),
        "sample_count": args.sample_count,
        "videos": videos,
    }
    summary_json = out_dir / "batch_summary.json"
    summary_csv = out_dir / "batch_summary.csv"
    report_md = out_dir / "batch_report.md"
    contact_sheet = out_dir / "contact_sheet.jpg"
    summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(summary_csv, videos)
    write_report(report_md, videos)
    write_contact_sheet(contact_sheet, videos)

    print(
        json.dumps(
            {
                "summary_json": str(summary_json),
                "summary_csv": str(summary_csv),
                "report_md": str(report_md),
                "contact_sheet": str(contact_sheet),
                "video_count": len(videos),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
