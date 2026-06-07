from __future__ import annotations

import time
from collections.abc import Iterator

from .config import SourceConfig
from .types import Frame


class VideoSource:
    def frames(self) -> Iterator[Frame]:
        raise NotImplementedError


class SyntheticSource(VideoSource):
    def __init__(self, *, frames: int = 120, width: int = 640, height: int = 360, fps: float = 15) -> None:
        self.total_frames = frames
        self.width = width
        self.height = height
        self.fps = fps

    def frames(self) -> Iterator[Frame]:
        frame_interval = 1.0 / self.fps if self.fps > 0 else 0
        started_at = time.perf_counter()

        for index in range(self.total_frames):
            timestamp_s = time.perf_counter() - started_at
            yield Frame(
                index=index,
                timestamp_s=timestamp_s,
                width=self.width,
                height=self.height,
                data=None,
            )

            if frame_interval:
                time.sleep(frame_interval)


class WebcamSource(VideoSource):
    def __init__(self, *, device_index: int = 0, width: int = 1280, height: int = 720, fps: float = 30) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps

    def frames(self) -> Iterator[Frame]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("WebcamSource requires opencv-python. Install it before using webcam or GoPro input.") from exc

        cap = cv2.VideoCapture(self.device_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not cap.isOpened():
            raise RuntimeError(f"Could not open webcam device_index={self.device_index}")

        started_at = time.perf_counter()
        index = 0

        try:
            while True:
                ok, image = cap.read()
                if not ok:
                    break

                yield Frame(
                    index=index,
                    timestamp_s=time.perf_counter() - started_at,
                    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    data=image,
                )
                index += 1
        finally:
            cap.release()


class ImageFileSource(VideoSource):
    def __init__(self, *, path: str, frames: int = 30, fps: float = 5) -> None:
        self.path = path
        self.total_frames = frames
        self.fps = fps

    def frames(self) -> Iterator[Frame]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("ImageFileSource requires opencv-python.") from exc

        image = cv2.imread(self.path)
        if image is None:
            raise RuntimeError(f"Could not read image file: {self.path}")

        height, width = image.shape[:2]
        frame_interval = 1.0 / self.fps if self.fps > 0 else 0
        started_at = time.perf_counter()

        for index in range(self.total_frames):
            yield Frame(
                index=index,
                timestamp_s=time.perf_counter() - started_at,
                width=width,
                height=height,
                data=image,
            )

            if frame_interval:
                time.sleep(frame_interval)


def create_source(config: SourceConfig) -> VideoSource:
    if config.type == "synthetic":
        return SyntheticSource(**config.params)

    if config.type == "webcam":
        return WebcamSource(**config.params)

    if config.type == "image_file":
        return ImageFileSource(**config.params)

    raise ValueError(f"Unsupported source type: {config.type}")
