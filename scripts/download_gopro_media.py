from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MEDIA_EXTENSIONS = {".mp4", ".mov", ".360"}


@dataclass(frozen=True)
class GoProMediaFile:
    directory: str
    filename: str
    size: int
    created: str
    modified: str

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()

    @property
    def sort_key(self) -> tuple[str, str]:
        return self.modified or self.created, self.filename


def request_json(url: str, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def media_list(ip: str, timeout: float) -> dict[str, Any]:
    errors = []
    for base_url in (f"http://{ip}:8080", f"http://{ip}"):
        url = f"{base_url}/gopro/media/list"
        try:
            return request_json(url, timeout)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Could not read GoPro media list:\n" + "\n".join(errors))


def flatten_media(payload: dict[str, Any]) -> list[GoProMediaFile]:
    files = []
    for directory in payload.get("media", []):
        dirname = directory.get("d", "")
        for item in directory.get("fs", []):
            files.append(
                GoProMediaFile(
                    directory=dirname,
                    filename=item.get("n", ""),
                    size=int(item.get("s", 0) or 0),
                    created=str(item.get("cre", "")),
                    modified=str(item.get("mod", "")),
                )
            )
    return sorted(files, key=lambda item: item.sort_key)


def download_url(ip: str, media_file: GoProMediaFile) -> str:
    directory = urllib.parse.quote(media_file.directory)
    filename = urllib.parse.quote(media_file.filename)
    return f"http://{ip}:8080/videos/DCIM/{directory}/{filename}"


def download_file(ip: str, media_file: GoProMediaFile, out_dir: Path, timeout: float) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / media_file.filename
    url = download_url(ip, media_file)

    with urllib.request.urlopen(url, timeout=timeout) as response, target.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    return target


def print_table(files: list[GoProMediaFile]) -> None:
    if not files:
        print("No media files found on the GoPro SD card.")
        return
    print(f"{'#':>3} {'directory':<10} {'filename':<18} {'size_mb':>10} {'modified':>12}")
    for index, item in enumerate(files, start=1):
        print(f"{index:>3} {item.directory:<10} {item.filename:<18} {item.size / 1024 / 1024:>10.1f} {item.modified:>12}")


def main() -> None:
    parser = argparse.ArgumentParser(description="List or download media from a GoPro over USB/Wi-Fi HTTP API.")
    parser.add_argument("--gopro-ip", default="172.26.181.51")
    parser.add_argument("--action", choices=["list", "download-index", "download-latest", "download-all"], default="list")
    parser.add_argument("--index", type=int, help="1-based media index from the list output, used with --action download-index.")
    parser.add_argument("--out-dir", default="runs/gopro_media_downloads")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--include-non-video", action="store_true")
    args = parser.parse_args()

    payload = media_list(args.gopro_ip, args.timeout)
    files = flatten_media(payload)
    if not args.include_non_video:
        files = [item for item in files if item.extension in MEDIA_EXTENSIONS]

    print_table(files)
    if args.action == "list":
        return

    if not files:
        raise SystemExit("No downloadable media files found.")

    out_dir = Path(args.out_dir)
    if args.action == "download-index":
        if args.index is None:
            raise SystemExit("--index is required with --action download-index.")
        if args.index < 1 or args.index > len(files):
            raise SystemExit(f"--index must be between 1 and {len(files)}.")
        selected = [files[args.index - 1]]
    elif args.action == "download-latest":
        selected = [files[-1]]
    else:
        selected = files
    downloaded = []
    for item in selected:
        try:
            target = download_file(args.gopro_ip, item, out_dir, args.timeout)
        except urllib.error.URLError as exc:
            print(f"Download failed for {item.filename}: {exc}", file=sys.stderr)
            raise
        downloaded.append(str(target))
        print(f"Downloaded {item.filename} -> {target}")

    print(json.dumps({"downloaded": downloaded}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
