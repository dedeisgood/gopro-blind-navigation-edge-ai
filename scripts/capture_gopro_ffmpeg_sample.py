from __future__ import annotations

import argparse
import json
import subprocess
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
    parser = argparse.ArgumentParser(description="Record GoPro USB webcam stream via FFmpeg.")
    parser.add_argument("--gopro-ip", default="172.26.181.51")
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--res", default="720", choices=["480", "720", "1080", "480p", "720p", "1080p"])
    parser.add_argument("--out", default="runs/gopro_udp_test/gopro_ffmpeg_sample.mp4")
    parser.add_argument("--listen-first", action="store_true", help="Start FFmpeg listener before sending GoPro START.")
    args = parser.parse_args()

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    base_url = f"http://{args.gopro_ip}"
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=keep_alive, args=(base_url, stop_event), daemon=True)

    res = args.res.removesuffix("p")
    start_url = f"{base_url}/gp/gpWebcam/START?res={res}"
    stop_url = f"{base_url}/gp/gpWebcam/STOP"

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "info",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-probesize",
        "8192",
        "-analyzeduration",
        "0",
        "-i",
        "udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000",
        "-t",
        str(args.seconds),
        "-c:v",
        "copy",
        str(out_path),
    ]

    try:
        if args.listen_first:
            proc_handle = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(1.0)
            print(json.dumps({"start": start_url, "response": call(start_url)}, ensure_ascii=False))
            keep_alive_thread.start()
            stdout, stderr = proc_handle.communicate(timeout=args.seconds + 20)
            returncode = proc_handle.returncode
        else:
            print(json.dumps({"start": start_url, "response": call(start_url)}, ensure_ascii=False))
            keep_alive_thread.start()
            time.sleep(1.0)
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.seconds + 20)
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode

        result = {
            "returncode": returncode,
            "video": str(out_path),
            "exists": out_path.exists(),
            "size": out_path.stat().st_size if out_path.exists() else 0,
            "stdout": stdout[-1000:],
            "stderr": stderr[-2000:],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not produce a usable video.")
    finally:
        stop_event.set()
        try:
            print(json.dumps({"stop": stop_url, "response": call(stop_url)}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"stop": stop_url, "error": str(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
