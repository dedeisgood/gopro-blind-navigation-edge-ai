from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.request
from pathlib import Path


def call(url: str, timeout: float = 5) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def keep_alive(base_url: str, stop_event: threading.Event) -> None:
    while not stop_event.wait(2.0):
        try:
            call(f"{base_url}/gp/gpWebcam/KEEP_ALIVE", timeout=3)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture GoPro USB webcam UDP stream without GoPro Webcam app.")
    parser.add_argument("--gopro-ip", default="172.26.181.51")
    parser.add_argument("--pc-ip", default=None, help="Optional laptop GoPro-interface IP for UDP bind URL.")
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--res", default="720p", choices=["480p", "720p", "1080p"])
    parser.add_argument("--fps", type=float, default=30)
    parser.add_argument("--out", default="runs/gopro_udp_test/gopro_udp_sample.mp4")
    args = parser.parse_args()

    import cv2

    base_url = f"http://{args.gopro_ip}"
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path = out_path.with_suffix(".jpg")

    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=keep_alive, args=(base_url, stop_event), daemon=True)

    start_url = f"{base_url}/gp/gpWebcam/START?res={args.res}"
    stop_url = f"{base_url}/gp/gpWebcam/STOP"

    print(json.dumps({"start": start_url, "response": call(start_url)}, ensure_ascii=False))
    keep_alive_thread.start()
    time.sleep(1.0)

    urls = []
    if args.pc_ip:
        urls.append(f"udp://@{args.pc_ip}:8554?overrun_nonfatal=1&fifo_size=50000000")
    urls.extend(
        [
            "udp://@:8554?overrun_nonfatal=1&fifo_size=50000000",
            "udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000",
        ]
    )

    result = None
    try:
        for stream_url in urls:
            cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
            opened = cap.isOpened()
            frames = 0
            writer = None
            started_at = time.perf_counter()

            while time.perf_counter() - started_at < args.seconds:
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.02)
                    continue

                height, width = frame.shape[:2]
                if writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(str(out_path), fourcc, args.fps, (width, height))
                    cv2.imwrite(str(preview_path), frame)

                writer.write(frame)
                frames += 1

            if writer is not None:
                writer.release()
            cap.release()

            result = {
                "stream_url": stream_url,
                "opened": opened,
                "frames": frames,
                "video": str(out_path),
                "preview": str(preview_path) if preview_path.exists() else None,
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))

            if frames > 0:
                break
    finally:
        stop_event.set()
        try:
            print(json.dumps({"stop": stop_url, "response": call(stop_url)}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"stop": stop_url, "error": str(exc)}, ensure_ascii=False))

    if result is None or result["frames"] == 0:
        raise RuntimeError("No frames captured from GoPro UDP stream.")


if __name__ == "__main__":
    main()

