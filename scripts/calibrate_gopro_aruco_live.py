from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework.aruco_distance import MarkerDistance, detect_marker_distances


RESOLUTION_MAP = {
    "480": (848, 480),
    "720": (1280, 720),
    "1080": (1920, 1080),
}


def call(url: str, timeout: float = 5) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def keep_alive(base_url: str, stop_event: threading.Event) -> None:
    while not stop_event.wait(2.0):
        try:
            call(f"{base_url}/gp/gpWebcam/KEEP_ALIVE", timeout=3)
        except Exception:
            pass


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = round((len(ordered) - 1) * pct)
    return ordered[idx]


def draw_estimate(frame: np.ndarray, estimate: MarkerDistance | None, known_distance_m: float | None) -> None:
    if estimate is None:
        cv2.putText(frame, "No ArUco marker", (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (0, 0, 255), 2)
        return

    pts = np.array(estimate.corners_xy, dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=3)
    center = (int(estimate.center_x), int(estimate.center_y))
    cv2.circle(frame, center, 5, (0, 255, 255), -1)

    text = f"id {estimate.marker_id} | {estimate.distance_m:.2f} m | {estimate.clock_label_en}"
    cv2.putText(frame, text, (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2)

    if known_distance_m is not None:
        error = estimate.distance_m - known_distance_m
        cv2.putText(frame, f"error {error:+.2f} m", (24, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 255, 255), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure GoPro distance with a phone-displayed ArUco marker.")
    parser.add_argument("--gopro-ip", default="172.26.181.51")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--res", default="720", choices=["480", "720", "1080"])
    parser.add_argument("--analysis-fps", type=float, default=8)
    parser.add_argument("--dictionary", default="4X4_50")
    parser.add_argument("--marker-id", type=int, default=0)
    parser.add_argument("--marker-size-m", type=float, required=True, help="Measured black marker square side on the phone.")
    parser.add_argument("--known-distance-m", type=float, help="Measured GoPro-to-marker distance for error reporting.")
    parser.add_argument("--hfov", type=float, default=118.0)
    parser.add_argument("--out-dir", default="runs/aruco_distance_calibration")
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    import imageio_ffmpeg

    width, height = RESOLUTION_MAP[args.res]
    frame_size = width * height * 3
    base_url = f"http://{args.gopro_ip}"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = args.label or (f"{args.known_distance_m:g}m" if args.known_distance_m is not None else "unknown")
    safe_suffix = suffix.replace(".", "p").replace(" ", "_")
    events_path = out_dir / f"aruco_measurements_{safe_suffix}.jsonl"
    metrics_path = out_dir / f"aruco_metrics_{safe_suffix}.json"
    video_path = out_dir / f"aruco_annotated_{safe_suffix}.mp4"
    preview_path = out_dir / f"aruco_preview_{safe_suffix}.jpg"

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    stream_url = "udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000"
    vf = f"fps={args.analysis_fps},scale={width}:{height},format=bgr24"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-probesize",
        "8192",
        "-analyzeduration",
        "0",
        "-i",
        stream_url,
        "-an",
        "-vf",
        vf,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "pipe:1",
    ]

    print(json.dumps({"stage": "starting_ffmpeg_listener", "res": args.res, "analysis_fps": args.analysis_fps}, ensure_ascii=False))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), args.analysis_fps, (width, height))
    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=keep_alive, args=(base_url, stop_event), daemon=True)

    started_at = time.perf_counter()
    frame_index = 0
    distances: list[float] = []
    side_distances: list[float] = []
    pnp_distances: list[float] = []
    detections = 0
    preview_saved = False

    try:
        time.sleep(1.0)
        start_url = f"{base_url}/gp/gpWebcam/START?res={args.res}"
        print(json.dumps({"stage": "gopro_start", "url": start_url, "response": call(start_url)}, ensure_ascii=False))
        keep_alive_thread.start()

        with events_path.open("w", encoding="utf-8") as events_file:
            while True:
                if time.perf_counter() - started_at >= args.seconds:
                    break
                if proc.stdout is None:
                    raise RuntimeError("FFmpeg stdout is not available.")

                raw = proc.stdout.read(frame_size)
                if len(raw) != frame_size:
                    if proc.poll() is not None:
                        raise RuntimeError("FFmpeg exited before a full frame was read.")
                    continue

                frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
                timestamp_s = time.perf_counter() - started_at
                estimates = detect_marker_distances(
                    frame,
                    marker_size_m=args.marker_size_m,
                    dictionary_name=args.dictionary,
                    target_id=args.marker_id,
                    horizontal_fov_deg=args.hfov,
                )
                estimate = estimates[0] if estimates else None

                if estimate is not None:
                    payload: dict[str, Any] = {
                        "frame_index": frame_index,
                        "timestamp_s": round(timestamp_s, 3),
                        "known_distance_m": args.known_distance_m,
                        "marker_size_m": args.marker_size_m,
                        "res": args.res,
                        **asdict(estimate),
                    }
                    if args.known_distance_m is not None:
                        payload["error_m"] = round(estimate.distance_m - args.known_distance_m, 3)
                        payload["abs_error_m"] = round(abs(estimate.distance_m - args.known_distance_m), 3)
                    events_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    events_file.flush()

                    detections += 1
                    distances.append(estimate.distance_m)
                    side_distances.append(estimate.distance_side_m)
                    if estimate.distance_pnp_m is not None:
                        pnp_distances.append(estimate.distance_pnp_m)

                draw_estimate(frame, estimate, args.known_distance_m)
                writer.write(frame)

                if estimate is not None and not preview_saved:
                    cv2.imwrite(str(preview_path), frame)
                    preview_saved = True

                frame_index += 1

    finally:
        stop_event.set()
        try:
            print(json.dumps({"stage": "gopro_stop", "response": call(f"{base_url}/gp/gpWebcam/STOP")}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"stage": "gopro_stop_failed", "error": str(exc)}, ensure_ascii=False))

        writer.release()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    elapsed_s = max(time.perf_counter() - started_at, 1e-9)
    median_distance = statistics.median(distances) if distances else 0.0
    metrics: dict[str, Any] = {
        "frames": frame_index,
        "detections": detections,
        "elapsed_s": round(elapsed_s, 3),
        "effective_fps": round(frame_index / elapsed_s, 3),
        "marker_size_m": args.marker_size_m,
        "known_distance_m": args.known_distance_m,
        "median_distance_m": round(median_distance, 3),
        "mean_distance_m": round(statistics.mean(distances), 3) if distances else 0.0,
        "p10_distance_m": round(percentile(distances, 0.10), 3) if distances else 0.0,
        "p90_distance_m": round(percentile(distances, 0.90), 3) if distances else 0.0,
        "median_side_distance_m": round(statistics.median(side_distances), 3) if side_distances else 0.0,
        "median_pnp_distance_m": round(statistics.median(pnp_distances), 3) if pnp_distances else 0.0,
        "events": str(events_path),
        "video": str(video_path),
        "preview": str(preview_path) if preview_saved else None,
    }
    if args.known_distance_m is not None and distances:
        metrics["error_m"] = round(median_distance - args.known_distance_m, 3)
        metrics["abs_error_m"] = round(abs(median_distance - args.known_distance_m), 3)
        metrics["relative_error_pct"] = round(abs(median_distance - args.known_distance_m) / args.known_distance_m * 100.0, 2)

    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"stage": "metrics", **metrics}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
