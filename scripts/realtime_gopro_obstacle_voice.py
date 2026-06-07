from __future__ import annotations

import argparse
import json
import queue
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework.spatial import estimate_spatial, risk_from_distance
from edge_framework.overlays import draw_clock_border
from edge_framework.speech_policy import speech_label
from edge_framework import navigability as nav
from edge_framework import semantic_navigability as semnav
from edge_framework.decision_classifier import DecisionClassifier


RESOLUTION_MAP = {
    "480": (848, 480),
    "720": (1280, 720),
    "1080": (1920, 1080),
}

PROMPT_ZH = {
    "front_passable": "\u524d\u65b9\u53ef\u901a\u884c",
    "turn_left": "\u5de6\u524d\u65b9\u8f03\u7a7a",
    "turn_right": "\u53f3\u524d\u65b9\u8f03\u7a7a",
    "stop": "\u524d\u65b9\u53ef\u80fd\u4e0d\u53ef\u901a\u884c\uff0c\u8acb\u5148\u505c\u6b62",
    "low_visibility_stop": "\u5149\u7dda\u4e0d\u8db3\uff0c\u8acb\u5148\u505c\u6b62",
}

PROMPT_COLOR_RGB = {
    "front_passable": (62, 208, 112),
    "turn_left": (255, 210, 72),
    "turn_right": (255, 210, 72),
    "stop": (255, 88, 88),
    "low_visibility_stop": (255, 88, 88),
}

OBSTACLE_CLASSES = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "traffic light",
    "stop sign",
    "bench",
    "chair",
    "couch",
    "potted plant",
    "backpack",
    "suitcase",
    "sports ball",
}

CLASS_ZH = {
    "person": "人",
    "bicycle": "腳踏車",
    "car": "車",
    "motorcycle": "機車",
    "bus": "公車",
    "truck": "卡車",
    "traffic light": "交通號誌",
    "stop sign": "停止標誌",
    "bench": "長椅",
    "chair": "椅子",
    "couch": "沙發",
    "potted plant": "盆栽",
    "backpack": "背包",
    "suitcase": "行李箱",
    "sports ball": "球",
}

DIRECTION_ZH = {
    "left": "左前方",
    "center": "正前方",
    "right": "右前方",
}


@dataclass(frozen=True)
class ObstacleCue:
    frame_index: int
    timestamp_s: float
    frame_width: int
    frame_height: int
    class_name: str
    confidence: float
    direction: str
    azimuth_deg: float
    clock_hour: int
    clock_label_en: str
    clock_label_zh: str
    distance_m: float | None
    distance_label_en: str
    distance_label_zh: str
    distance_source: str
    risk: str
    area_ratio: float
    bbox_xyxy: list[float]
    speech: str


class Speaker:
    def __init__(self, *, enabled: bool, lang: str, rate: int) -> None:
        self.enabled = enabled
        self.lang = lang
        self.rate = rate
        self.messages: queue.Queue[str | None] = queue.Queue(maxsize=2)
        self.thread = threading.Thread(target=self._run, daemon=True)

        if enabled:
            self.thread.start()

    def say(self, text: str) -> None:
        if not self.enabled:
            print(f"[speech disabled] {text}")
            return

        while self.messages.full():
            try:
                self.messages.get_nowait()
            except queue.Empty:
                break
        self.messages.put_nowait(text)

    def close(self) -> None:
        if self.enabled:
            self.messages.put(None)
            self.thread.join(timeout=3)

    def _run(self) -> None:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)

        voices = engine.getProperty("voices")
        for voice in voices:
            languages = ",".join(getattr(voice, "languages", []) or [])
            if self.lang.lower() in f"{voice.id} {voice.name} {languages}".lower():
                engine.setProperty("voice", voice.id)
                break

        while True:
            text = self.messages.get()
            if text is None:
                break
            engine.say(text)
            engine.runAndWait()


def call(url: str, timeout: float = 5) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def resolve_device(requested_device: str) -> str:
    if requested_device.lower() != "auto":
        return requested_device

    try:
        import torch
    except Exception:
        return "cpu"

    return "0" if torch.cuda.is_available() else "cpu"


def keep_alive(base_url: str, stop_event: threading.Event) -> None:
    while not stop_event.wait(2.0):
        try:
            call(f"{base_url}/gp/gpWebcam/KEEP_ALIVE", timeout=3)
        except Exception:
            pass


def infer_depth_navigation(
    frame: np.ndarray,
    *,
    processor: Any,
    depth_model: Any,
    depth_device: str,
    torch_module: Any,
    image_cls: Any,
) -> tuple[np.ndarray, dict[str, Any], float]:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = image_cls.fromarray(rgb)
    inputs = processor(images=image, return_tensors="pt").to(depth_device)

    started = time.perf_counter()
    with torch_module.no_grad():
        outputs = depth_model(**inputs)
        predicted_depth = outputs.predicted_depth
        prediction = torch_module.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=image.size[::-1],
            mode="bicubic",
            align_corners=False,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0

    depth = prediction.squeeze().detach().cpu().numpy()
    depth_norm = nav.normalize_depth(depth)
    analysis = nav.analyze_depth(depth_norm)
    return depth_norm, analysis, latency_ms


def infer_semantic_navigation(
    frame: np.ndarray,
    *,
    processor: Any,
    semantic_model: Any,
    semantic_device: str,
    torch_module: Any,
    image_cls: Any,
    id2label: dict[int, str],
) -> tuple[np.ndarray, dict[str, Any], float]:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = image_cls.fromarray(rgb)
    inputs = processor(images=image, return_tensors="pt").to(semantic_device)

    started = time.perf_counter()
    with torch_module.no_grad():
        outputs = semantic_model(**inputs)
        logits = outputs.logits
        upsampled_logits = torch_module.nn.functional.interpolate(
            logits,
            size=frame.shape[:2],
            mode="bilinear",
            align_corners=False,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    seg_map = upsampled_logits.argmax(dim=1).squeeze().detach().cpu().numpy().astype(np.int32)
    analysis = semnav.analyze_segmentation(seg_map, id2label)
    return seg_map, analysis, latency_ms


def get_direction(cx: float, width: int, center_region_ratio: float) -> str:
    center_width = width * center_region_ratio
    left_boundary = (width - center_width) / 2
    right_boundary = left_boundary + center_width

    if cx < left_boundary:
        return "left"
    if cx > right_boundary:
        return "right"
    return "center"


def get_risk(area_ratio: float, direction: str, *, medium: float, high: float) -> str:
    if area_ratio >= high:
        return "high"
    if area_ratio >= medium:
        return "high" if direction == "center" else "medium"
    if direction == "center":
        return "medium"
    return "low"


def speech_for(cue: ObstacleCue, *, lang: str) -> str:
    class_en, class_zh, _generic = speech_label(cue.class_name, cue.confidence)

    if lang.lower().startswith("zh"):
        obj = class_zh
        if cue.distance_m is not None:
            distance = f"約{cue.distance_m:.1f}公尺"
        else:
            distance = cue.distance_label_zh
        if cue.risk == "high":
            return f"注意，{cue.clock_label_zh}，{distance}，有{obj}"
        return f"{cue.clock_label_zh}，{distance}，有{obj}"

    distance = f"about {cue.distance_m:.1f} meters" if cue.distance_m is not None else cue.distance_label_en
    if cue.risk == "high":
        return f"Warning, {class_en} at {cue.clock_label_en}, {distance}"
    return f"{class_en} at {cue.clock_label_en}, {distance}"


def draw_cue(frame: np.ndarray, cue: ObstacleCue | None) -> None:
    if cue is None:
        return

    colors = {
        "low": (80, 220, 80),
        "medium": (0, 210, 255),
        "high": (0, 0, 255),
    }
    color = colors[cue.risk]
    x1, y1, x2, y2 = [int(v) for v in cue.bbox_xyxy]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

    height, width = frame.shape[:2]
    panel_height = 72
    overlay = frame.copy()
    cv2.rectangle(overlay, (12, height - panel_height - 12), (min(width - 12, 920), height - 12), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)
    distance = f"{cue.distance_m:.1f}m" if cue.distance_m is not None else "dist?"
    overlay_text = f"{cue.risk.upper()} | {cue.class_name} {cue.clock_label_en} {distance} | conf {cue.confidence:.2f}"
    cv2.putText(frame, overlay_text, (26, height - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2)


@lru_cache(maxsize=16)
def cjk_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "C:/Windows/Fonts/msjhbd.ttc" if bold else "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/NotoSansTC-VF.ttf",
        "C:/Windows/Fonts/mingliu.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for font_path in font_candidates:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def draw_demo_prompt_panel(
    frame: np.ndarray,
    fusion_analysis: dict[str, Any] | None,
    top_cue: ObstacleCue | None,
    *,
    fps: float,
) -> None:
    height, width = frame.shape[:2]
    panel_w = min(width - 28, 760)
    panel_h = 148
    x0, y0 = 14, 14
    x1, y1 = x0 + panel_w, y0 + panel_h

    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if fusion_analysis is None:
        recommendation = "front_passable"
        prompt = "\u7cfb\u7d71\u555f\u52d5\u4e2d\uff0c\u6b63\u5728\u5206\u6790 GoPro \u756b\u9762"
        decision_text = "\u6c7a\u7b56\uff1a\u5c1a\u672a\u7522\u751f"
        rule_text = "\u898f\u5247\uff1a\u7b49\u5f85\u8a9e\u610f\u5206\u5272\u8207\u6df1\u5ea6\u4f30\u8a08"
        score_text = f"FPS {fps:.1f}"
    else:
        recommendation = str(fusion_analysis.get("recommendation", "stop"))
        prompt = PROMPT_ZH.get(recommendation, str(fusion_analysis.get("speech_zh", "")))
        decision = fusion_analysis.get("decision_model") or {}
        confidence = decision.get("confidence")
        confidence_text = f"{float(confidence):.2f}" if confidence is not None else "--"
        decision_text = f"\u6c7a\u7b56\uff1a{recommendation}  \u4fe1\u5fc3\u5ea6\uff1a{confidence_text}"
        rule_text = (
            f"\u898f\u5247\uff1a{fusion_analysis.get('rule_recommendation', fusion_analysis.get('recommendation'))}"
            f"  \u539f\u56e0\uff1a{fusion_analysis.get('rule_reason', fusion_analysis.get('reason'))}"
        )
        score_text = (
            f"front {float(fusion_analysis.get('front_score', 0.0)):.2f} | "
            f"left {float(fusion_analysis.get('left_score', 0.0)):.2f} | "
            f"right {float(fusion_analysis.get('right_score', 0.0)):.2f} | FPS {fps:.1f}"
        )

    accent = PROMPT_COLOR_RGB.get(recommendation, (255, 88, 88))
    draw.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(10, 10, 10, 210), outline=accent + (255,), width=3)
    draw.rectangle((x0, y0, x0 + 10, y1), fill=accent + (255,))
    draw.text((x0 + 24, y0 + 16), "\u63d0\u793a\u8a5e", font=cjk_font(24, True), fill=(235, 235, 235, 255))
    draw.text((x0 + 128, y0 + 11), prompt, font=cjk_font(33, True), fill=accent + (255,))
    draw.text((x0 + 24, y0 + 70), decision_text, font=cjk_font(20), fill=(240, 240, 240, 255))
    draw.text((x0 + 24, y0 + 99), rule_text, font=cjk_font(18), fill=(210, 220, 230, 255))
    draw.text((x0 + 24, y0 + 124), score_text, font=cjk_font(17), fill=(190, 205, 215, 255))

    if top_cue is not None:
        obj_text = f"\u7269\u4ef6\uff1a{top_cue.clock_label_en} {top_cue.class_name} {top_cue.distance_label_en}"
        draw.text((x0 + panel_w - 250, y0 + 124), obj_text, font=cjk_font(17), fill=(230, 230, 230, 255))

    composed = Image.alpha_composite(image, overlay).convert("RGB")
    frame[:, :] = cv2.cvtColor(np.asarray(composed), cv2.COLOR_RGB2BGR)


def choose_top_cue(cues: list[ObstacleCue]) -> ObstacleCue | None:
    if not cues:
        return None

    risk_rank = {"high": 3, "medium": 2, "low": 1}
    direction_rank = {"center": 3, "left": 2, "right": 2}

    return max(
        cues,
        key=lambda cue: (
            risk_rank[cue.risk],
            direction_rank[cue.direction],
            -(cue.distance_m if cue.distance_m is not None else 999.0),
            cue.area_ratio,
            cue.confidence,
        ),
    )


def should_announce(cue: ObstacleCue, last_spoken: dict[str, float], now: float, cooldown: float, repeat_cooldown: float) -> bool:
    if cue.risk == "low":
        return False

    global_last = last_spoken.get("__global__", -999.0)
    key = f"{cue.risk}:{cue.clock_hour}:{cue.class_name}"
    key_last = last_spoken.get(key, -999.0)

    if now - global_last < cooldown:
        return False
    if now - key_last < repeat_cooldown:
        return False

    last_spoken["__global__"] = now
    last_spoken[key] = now
    return True


def should_announce_navigation(
    analysis: dict[str, Any],
    last_spoken: dict[str, float],
    now: float,
    cooldown: float,
    repeat_cooldown: float,
) -> bool:
    if not analysis.get("front_blocked"):
        return False

    global_last = last_spoken.get("__global__", -999.0)
    key = f"nav:{analysis['recommendation']}"
    key_last = last_spoken.get(key, -999.0)

    if now - global_last < cooldown:
        return False
    if now - key_last < repeat_cooldown:
        return False

    last_spoken["__global__"] = now
    last_spoken[key] = now
    return True


def stability_key(cue: ObstacleCue) -> str:
    distance_band = cue.distance_label_en
    return f"{cue.clock_hour}:{cue.class_name}:{distance_band}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time GoPro obstacle awareness with voice cues.")
    parser.add_argument("--gopro-ip", default="172.26.181.51")
    parser.add_argument("--seconds", type=float, default=15, help="0 means run until interrupted.")
    parser.add_argument("--res", default="480", choices=["480", "720", "1080"])
    parser.add_argument("--analysis-fps", type=float, default=12)
    parser.add_argument("--weights", default="yolov8n.pt")
    parser.add_argument("--disable-object-cues", action="store_true", help="Skip YOLO object cues for a cleaner/faster navigation-only demo.")
    parser.add_argument("--device", default="auto", help="auto uses CUDA GPU when available, otherwise CPU.")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--hfov", type=float, default=118.0, help="Estimated GoPro horizontal field of view in degrees.")
    parser.add_argument("--distance-scale", type=float, default=1.0, help="Calibration multiplier for bbox-based distance.")
    parser.add_argument("--cooldown", type=float, default=1.2)
    parser.add_argument("--repeat-cooldown", type=float, default=4.0)
    parser.add_argument("--min-stable-frames", type=int, default=2)
    parser.add_argument("--lang", default="zh-TW")
    parser.add_argument("--no-speech", action="store_true")
    parser.add_argument("--enable-depth-nav", action="store_true", help="Fuse Depth Anything navigability cues for walls and blocked paths.")
    parser.add_argument("--depth-model", default="depth-anything/Depth-Anything-V2-Small-hf")
    parser.add_argument("--depth-every", type=int, default=2, help="Run depth navigation every N frames when enabled.")
    parser.add_argument("--depth-min-stable-frames", type=int, default=2)
    parser.add_argument("--enable-semantic-nav", action="store_true", help="Fuse SegFormer wall/floor/door segmentation into navigability cues.")
    parser.add_argument("--seg-model", default=semnav.DEFAULT_SEGMENTATION_MODEL)
    parser.add_argument("--seg-every", type=int, default=2, help="Run semantic navigation every N frames when enabled.")
    parser.add_argument("--semantic-min-stable-frames", type=int, default=2)
    parser.add_argument("--decision-model", default="", help="Optional trained decision classifier .pt for learned voice cues.")
    parser.add_argument("--decision-threshold", type=float, default=0.50)
    parser.add_argument("--decision-blocked-front-threshold", type=float, default=0.0, help="If >0, do not let the decision model turn a low-risk front_passable rule into blocked.")
    parser.add_argument("--display", action="store_true", help="Show a live annotated demo window on the laptop.")
    parser.add_argument("--display-scale", type=float, default=1.0)
    parser.add_argument("--display-stable-frames", type=int, default=2, help="Keep the visible prompt stable until the same navigation result repeats this many semantic frames.")
    parser.add_argument("--display-window", default="GoPro Blind Navigation Demo")
    parser.add_argument("--save-video", default="runs/realtime_gopro_obstacle_voice/annotated_realtime_clock_distance_480p.mp4")
    parser.add_argument("--events", default="runs/realtime_gopro_obstacle_voice/events_clock_distance.jsonl")
    parser.add_argument("--metrics", default="runs/realtime_gopro_obstacle_voice/metrics_clock_distance.json")
    args = parser.parse_args()

    import imageio_ffmpeg
    YOLO = None
    if not args.disable_object_cues:
        from ultralytics import YOLO

    width, height = RESOLUTION_MAP[args.res]
    frame_size = width * height * 3
    base_url = f"http://{args.gopro_ip}"

    events_path = Path(args.events)
    metrics_path = Path(args.metrics)
    video_path = Path(args.save_video)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.parent.mkdir(parents=True, exist_ok=True)

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

    warmup_frame = np.zeros((height, width, 3), dtype=np.uint8)
    device = resolve_device(args.device)
    model = None
    if not args.disable_object_cues:
        print(json.dumps({"stage": "loading_model", "weights": args.weights, "device": device}, ensure_ascii=False))
        model = YOLO(args.weights)
        print(json.dumps({"stage": "model_warmup", "device": device, "imgsz": args.imgsz}, ensure_ascii=False))
        model.predict(warmup_frame, device=device, conf=args.conf, imgsz=args.imgsz, verbose=False)
    else:
        print(json.dumps({"stage": "object_cues_disabled", "device": device}, ensure_ascii=False))

    depth_processor = None
    depth_model = None
    depth_torch = None
    depth_image_cls = None
    depth_device = "cpu"
    if args.enable_depth_nav:
        from PIL import Image
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        depth_torch = torch
        depth_image_cls = Image
        depth_device = "cuda" if torch.cuda.is_available() and device != "cpu" else "cpu"
        print(json.dumps({"stage": "loading_depth_model", "model": args.depth_model, "device": depth_device}, ensure_ascii=False))
        depth_processor = AutoImageProcessor.from_pretrained(args.depth_model)
        depth_model = AutoModelForDepthEstimation.from_pretrained(args.depth_model).to(depth_device)
        depth_model.eval()
        print(json.dumps({"stage": "depth_model_warmup", "device": depth_device}, ensure_ascii=False))
        infer_depth_navigation(
            warmup_frame,
            processor=depth_processor,
            depth_model=depth_model,
            depth_device=depth_device,
            torch_module=depth_torch,
            image_cls=depth_image_cls,
        )

    semantic_processor = None
    semantic_model = None
    semantic_torch = None
    semantic_image_cls = None
    semantic_id2label: dict[int, str] = {}
    semantic_device = "cpu"
    if args.enable_semantic_nav:
        from PIL import Image
        import torch
        from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

        semantic_torch = torch
        semantic_image_cls = Image
        semantic_device = "cuda" if torch.cuda.is_available() and device != "cpu" else "cpu"
        print(json.dumps({"stage": "loading_semantic_model", "model": args.seg_model, "device": semantic_device}, ensure_ascii=False))
        semantic_processor = AutoImageProcessor.from_pretrained(args.seg_model)
        semantic_model = AutoModelForSemanticSegmentation.from_pretrained(args.seg_model).to(semantic_device)
        semantic_model.eval()
        semantic_id2label = {int(k): v for k, v in semantic_model.config.id2label.items()}
        print(json.dumps({"stage": "semantic_model_warmup", "device": semantic_device}, ensure_ascii=False))
        infer_semantic_navigation(
            warmup_frame,
            processor=semantic_processor,
            semantic_model=semantic_model,
            semantic_device=semantic_device,
            torch_module=semantic_torch,
            image_cls=semantic_image_cls,
            id2label=semantic_id2label,
        )

    decision_classifier = None
    if args.decision_model:
        decision_model_path = Path(args.decision_model)
        if not decision_model_path.is_absolute():
            decision_model_path = PROJECT_ROOT / decision_model_path
        print(json.dumps({"stage": "loading_decision_model", "model": str(decision_model_path)}, ensure_ascii=False))
        decision_classifier = DecisionClassifier(decision_model_path)

    speaker = Speaker(enabled=not args.no_speech, lang=args.lang, rate=185)
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), args.analysis_fps, (width, height))
    if args.display:
        cv2.namedWindow(args.display_window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(args.display_window, int(width * args.display_scale), int(height * args.display_scale))

    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=keep_alive, args=(base_url, stop_event), daemon=True)

    print(json.dumps({"stage": "starting_ffmpeg_listener", "cmd": cmd}, ensure_ascii=False))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    started_at = time.perf_counter()
    frame_index = 0
    event_count = 0
    nav_event_count = 0
    semantic_event_count = 0
    spoken_count = 0
    nav_spoken_count = 0
    semantic_spoken_count = 0
    inference_latencies: list[float] = []
    depth_latencies: list[float] = []
    semantic_latencies: list[float] = []
    risk_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()
    clock_counts: Counter[str] = Counter()
    distance_counts: Counter[str] = Counter()
    nav_recommendation_counts: Counter[str] = Counter()
    semantic_recommendation_counts: Counter[str] = Counter()
    last_spoken: dict[str, float] = {}
    last_stability_key = ""
    stable_frames = 0
    last_nav_key = ""
    nav_stable_frames = 0
    last_nav_analysis: dict[str, Any] | None = None
    last_semantic_key = ""
    semantic_stable_frames = 0
    last_semantic_analysis: dict[str, Any] | None = None
    last_seg_map: np.ndarray | None = None
    last_fusion_analysis: dict[str, Any] | None = None
    display_fusion_analysis: dict[str, Any] | None = None

    try:
        time.sleep(1.0)
        start_url = f"{base_url}/gp/gpWebcam/START?res={args.res}"
        print(json.dumps({"stage": "gopro_start", "url": start_url, "response": call(start_url)}, ensure_ascii=False))
        keep_alive_thread.start()

        with events_path.open("w", encoding="utf-8") as event_file:
            while True:
                if args.seconds > 0 and time.perf_counter() - started_at >= args.seconds:
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

                cues: list[ObstacleCue] = []
                latency_ms = 0.0
                if model is not None:
                    inference_started = time.perf_counter()
                    results = model.predict(frame, device=device, conf=args.conf, imgsz=args.imgsz, verbose=False)
                    latency_ms = (time.perf_counter() - inference_started) * 1000
                    inference_latencies.append(latency_ms)

                    for result in results:
                        names = result.names
                        for box in result.boxes:
                            class_id = int(box.cls[0])
                            class_name = names[class_id]
                            if class_name not in OBSTACLE_CLASSES:
                                continue

                            confidence = float(box.conf[0])
                            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
                            bbox_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                            area_ratio = bbox_area / float(width * height)
                            direction = get_direction((x1 + x2) / 2, width, 0.34)
                            spatial = estimate_spatial(
                                class_name=class_name,
                                bbox_xyxy=(x1, y1, x2, y2),
                                frame_width=width,
                                frame_height=height,
                                horizontal_fov_deg=args.hfov,
                                distance_scale=args.distance_scale,
                            )
                            risk = risk_from_distance(spatial.distance_m, direction, area_ratio)

                            cue = ObstacleCue(
                                frame_index=frame_index,
                                timestamp_s=round(timestamp_s, 3),
                                frame_width=width,
                                frame_height=height,
                                class_name=class_name,
                                confidence=round(confidence, 4),
                                direction=direction,
                                azimuth_deg=spatial.azimuth_deg,
                                clock_hour=spatial.clock_hour,
                                clock_label_en=spatial.clock_label_en,
                                clock_label_zh=spatial.clock_label_zh,
                                distance_m=spatial.distance_m,
                                distance_label_en=spatial.distance_label_en,
                                distance_label_zh=spatial.distance_label_zh,
                                distance_source=spatial.distance_source,
                                risk=risk,
                                area_ratio=round(area_ratio, 4),
                                bbox_xyxy=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                                speech="",
                            )
                            cue = ObstacleCue(**{**asdict(cue), "speech": speech_for(cue, lang=args.lang)})
                            cues.append(cue)

                current_depth_norm: np.ndarray | None = None
                current_nav_analysis: dict[str, Any] | None = None
                current_seg_map: np.ndarray | None = None
                current_semantic_analysis: dict[str, Any] | None = None
                current_visibility_analysis = semnav.analyze_visibility(frame) if args.enable_semantic_nav else None
                if args.enable_depth_nav and frame_index % max(1, args.depth_every) == 0:
                    if depth_processor is None or depth_model is None or depth_torch is None or depth_image_cls is None:
                        raise RuntimeError("Depth navigation was enabled but the depth model was not loaded.")
                    current_depth_norm, current_nav_analysis, depth_latency_ms = infer_depth_navigation(
                        frame,
                        processor=depth_processor,
                        depth_model=depth_model,
                        depth_device=depth_device,
                        torch_module=depth_torch,
                        image_cls=depth_image_cls,
                    )
                    depth_latencies.append(depth_latency_ms)
                    last_nav_analysis = current_nav_analysis
                    nav_recommendation_counts[current_nav_analysis["recommendation"]] += 1

                    current_nav_key = current_nav_analysis["recommendation"]
                    if current_nav_key == last_nav_key:
                        nav_stable_frames += 1
                    else:
                        last_nav_key = current_nav_key
                        nav_stable_frames = 1

                    if current_nav_analysis["front_blocked"] and not args.enable_semantic_nav:
                        nav_event = {
                            "event_type": "navigability",
                            "frame_index": frame_index,
                            "timestamp_s": round(timestamp_s, 3),
                            "front_score": current_nav_analysis["front_score"],
                            "left_score": current_nav_analysis["left_score"],
                            "right_score": current_nav_analysis["right_score"],
                            "recommendation": current_nav_analysis["recommendation"],
                            "speech": current_nav_analysis["speech_zh"],
                            "sectors": current_nav_analysis["sectors"],
                        }
                        event_file.write(json.dumps(nav_event, ensure_ascii=False) + "\n")
                        event_file.flush()
                        nav_event_count += 1

                    if (
                        not args.enable_semantic_nav
                        and nav_stable_frames >= args.depth_min_stable_frames
                        and should_announce_navigation(
                        current_nav_analysis,
                        last_spoken,
                        timestamp_s,
                        args.cooldown,
                        args.repeat_cooldown,
                        )
                    ):
                        speaker.say(current_nav_analysis["speech_zh"])
                        spoken_count += 1
                        nav_spoken_count += 1
                        print(
                            json.dumps(
                                {
                                    "spoken": current_nav_analysis["speech_zh"],
                                    "event_type": "navigability",
                                    "recommendation": current_nav_analysis["recommendation"],
                                    "front_score": current_nav_analysis["front_score"],
                                    "left_score": current_nav_analysis["left_score"],
                                    "right_score": current_nav_analysis["right_score"],
                                    "t": round(timestamp_s, 2),
                                    "depth_latency_ms": round(depth_latency_ms, 1),
                                },
                                ensure_ascii=False,
                            )
                        )

                if args.enable_semantic_nav and frame_index % max(1, args.seg_every) == 0:
                    if (
                        semantic_processor is None
                        or semantic_model is None
                        or semantic_torch is None
                        or semantic_image_cls is None
                    ):
                        raise RuntimeError("Semantic navigation was enabled but the segmentation model was not loaded.")
                    current_seg_map, current_semantic_analysis, semantic_latency_ms = infer_semantic_navigation(
                        frame,
                        processor=semantic_processor,
                        semantic_model=semantic_model,
                        semantic_device=semantic_device,
                        torch_module=semantic_torch,
                        image_cls=semantic_image_cls,
                        id2label=semantic_id2label,
                    )
                    semantic_latencies.append(semantic_latency_ms)
                    last_seg_map = current_seg_map
                    last_semantic_analysis = current_semantic_analysis
                    last_fusion_analysis = semnav.fuse_with_depth(
                        semantic_analysis=last_semantic_analysis,
                        depth_analysis=last_nav_analysis if args.enable_depth_nav else None,
                        visibility_analysis=current_visibility_analysis,
                    )
                    if decision_classifier is not None:
                        decision = decision_classifier.predict_from_fusion(last_fusion_analysis)
                        last_fusion_analysis = decision_classifier.apply_to_fusion(
                            last_fusion_analysis,
                            decision,
                            min_confidence=args.decision_threshold,
                            blocked_front_threshold=args.decision_blocked_front_threshold
                            if args.decision_blocked_front_threshold > 0
                            else None,
                        )
                    semantic_recommendation_counts[last_fusion_analysis["recommendation"]] += 1

                    current_semantic_key = last_fusion_analysis["recommendation"]
                    if current_semantic_key == last_semantic_key:
                        semantic_stable_frames += 1
                    else:
                        last_semantic_key = current_semantic_key
                        semantic_stable_frames = 1
                    if semantic_stable_frames >= args.display_stable_frames:
                        display_fusion_analysis = last_fusion_analysis

                    if last_fusion_analysis["front_blocked"]:
                        semantic_event = {
                            "event_type": "semantic_navigability",
                            "frame_index": frame_index,
                            "timestamp_s": round(timestamp_s, 3),
                            "front_score": last_fusion_analysis["front_score"],
                            "left_score": last_fusion_analysis["left_score"],
                            "right_score": last_fusion_analysis["right_score"],
                            "recommendation": last_fusion_analysis["recommendation"],
                            "reason": last_fusion_analysis["reason"],
                            "speech": last_fusion_analysis["speech_zh"],
                            "decision_model": last_fusion_analysis.get("decision_model"),
                            "decision_applied": last_fusion_analysis.get("decision_applied", False),
                            "rule_recommendation": last_fusion_analysis.get("rule_recommendation"),
                            "rule_reason": last_fusion_analysis.get("rule_reason"),
                            "visibility": current_visibility_analysis,
                            "semantic": last_semantic_analysis,
                            "depth": last_nav_analysis if args.enable_depth_nav else None,
                        }
                        event_file.write(json.dumps(semantic_event, ensure_ascii=False) + "\n")
                        event_file.flush()
                        semantic_event_count += 1

                    if semantic_stable_frames >= args.semantic_min_stable_frames and should_announce_navigation(
                        last_fusion_analysis,
                        last_spoken,
                        timestamp_s,
                        args.cooldown,
                        args.repeat_cooldown,
                    ):
                        speaker.say(last_fusion_analysis["speech_zh"])
                        spoken_count += 1
                        semantic_spoken_count += 1
                        print(
                            json.dumps(
                                {
                                    "spoken": last_fusion_analysis["speech_zh"],
                                    "event_type": "semantic_navigability",
                                    "recommendation": last_fusion_analysis["recommendation"],
                                    "reason": last_fusion_analysis["reason"],
                                    "decision_model": last_fusion_analysis.get("decision_model"),
                                    "decision_applied": last_fusion_analysis.get("decision_applied", False),
                                    "rule_recommendation": last_fusion_analysis.get("rule_recommendation"),
                                    "visibility": current_visibility_analysis,
                                    "front_score": last_fusion_analysis["front_score"],
                                    "left_score": last_fusion_analysis["left_score"],
                                    "right_score": last_fusion_analysis["right_score"],
                                    "t": round(timestamp_s, 2),
                                    "semantic_latency_ms": round(semantic_latency_ms, 1),
                                },
                                ensure_ascii=False,
                            )
                        )

                top_cue = choose_top_cue(cues)
                if args.enable_semantic_nav and last_seg_map is not None and last_semantic_analysis is not None and last_fusion_analysis is not None:
                    frame = semnav.draw_semantic_fusion_overlay(
                        frame,
                        last_seg_map,
                        semantic_id2label,
                        last_semantic_analysis,
                        last_fusion_analysis,
                    )
                elif last_nav_analysis is not None:
                    if current_depth_norm is not None:
                        frame = nav.draw_depth_overlay(frame, current_depth_norm, last_nav_analysis)
                    else:
                        nav.draw_sector_overlay(frame, last_nav_analysis)
                draw_cue(frame, top_cue)
                draw_clock_border(frame)
                draw_demo_prompt_panel(
                    frame,
                    display_fusion_analysis or last_fusion_analysis,
                    top_cue,
                    fps=frame_index / max(time.perf_counter() - started_at, 1e-9),
                )
                writer.write(frame)
                if args.display:
                    cv2.imshow(args.display_window, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in {ord("q"), 27}:
                        print(json.dumps({"stage": "display_exit", "key": key}, ensure_ascii=False))
                        break

                if top_cue is not None:
                    current_stability_key = stability_key(top_cue)
                    if current_stability_key == last_stability_key:
                        stable_frames += 1
                    else:
                        last_stability_key = current_stability_key
                        stable_frames = 1

                    event_file.write(json.dumps(asdict(top_cue), ensure_ascii=False) + "\n")
                    event_file.flush()
                    event_count += 1
                    risk_counts[top_cue.risk] += 1
                    direction_counts[top_cue.direction] += 1
                    clock_counts[str(top_cue.clock_hour)] += 1
                    distance_counts[top_cue.distance_label_en] += 1

                    if stable_frames >= args.min_stable_frames and should_announce(
                        top_cue,
                        last_spoken,
                        timestamp_s,
                        args.cooldown,
                        args.repeat_cooldown,
                    ):
                        speaker.say(top_cue.speech)
                        spoken_count += 1
                        print(
                            json.dumps(
                                {
                                    "spoken": top_cue.speech,
                                    "risk": top_cue.risk,
                                    "direction": top_cue.direction,
                                    "clock": top_cue.clock_label_zh,
                                    "distance_m": top_cue.distance_m,
                                    "class": top_cue.class_name,
                                    "t": round(timestamp_s, 2),
                                    "latency_ms": round(latency_ms, 1),
                                },
                                ensure_ascii=False,
                            )
                        )

                frame_index += 1

    except KeyboardInterrupt:
        print(json.dumps({"stage": "interrupted"}, ensure_ascii=False))
    finally:
        stop_event.set()
        try:
            print(json.dumps({"stage": "gopro_stop", "response": call(f"{base_url}/gp/gpWebcam/STOP")}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"stage": "gopro_stop_failed", "error": str(exc)}, ensure_ascii=False))

        writer.release()
        speaker.close()

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

        elapsed_s = max(time.perf_counter() - started_at, 1e-9)
        sorted_latencies = sorted(inference_latencies)
        p95_index = round((len(sorted_latencies) - 1) * 0.95) if sorted_latencies else 0
        sorted_depth_latencies = sorted(depth_latencies)
        p95_depth_index = round((len(sorted_depth_latencies) - 1) * 0.95) if sorted_depth_latencies else 0
        sorted_semantic_latencies = sorted(semantic_latencies)
        p95_semantic_index = round((len(sorted_semantic_latencies) - 1) * 0.95) if sorted_semantic_latencies else 0
        metrics: dict[str, Any] = {
            "frames": frame_index,
            "elapsed_s": round(elapsed_s, 3),
            "effective_fps": round(frame_index / elapsed_s, 3),
            "event_count": event_count,
            "nav_event_count": nav_event_count,
            "semantic_event_count": semantic_event_count,
            "spoken_count": spoken_count,
            "nav_spoken_count": nav_spoken_count,
            "semantic_spoken_count": semantic_spoken_count,
            "device": device,
            "hfov": args.hfov,
            "distance_scale": args.distance_scale,
            "min_stable_frames": args.min_stable_frames,
            "avg_latency_ms": round(sum(inference_latencies) / len(inference_latencies), 3) if inference_latencies else 0,
            "p95_latency_ms": round(sorted_latencies[p95_index], 3) if sorted_latencies else 0,
            "depth_nav_enabled": args.enable_depth_nav,
            "depth_model": args.depth_model if args.enable_depth_nav else "",
            "depth_every": args.depth_every if args.enable_depth_nav else 0,
            "avg_depth_latency_ms": round(sum(depth_latencies) / len(depth_latencies), 3) if depth_latencies else 0,
            "p95_depth_latency_ms": round(sorted_depth_latencies[p95_depth_index], 3) if sorted_depth_latencies else 0,
            "semantic_nav_enabled": args.enable_semantic_nav,
            "seg_model": args.seg_model if args.enable_semantic_nav else "",
            "seg_every": args.seg_every if args.enable_semantic_nav else 0,
            "avg_semantic_latency_ms": round(sum(semantic_latencies) / len(semantic_latencies), 3) if semantic_latencies else 0,
            "p95_semantic_latency_ms": round(sorted_semantic_latencies[p95_semantic_index], 3) if semantic_latencies else 0,
            "decision_model": args.decision_model,
            "decision_threshold": args.decision_threshold,
            "risk_counts": dict(risk_counts),
            "direction_counts": dict(direction_counts),
            "clock_counts": dict(clock_counts),
            "distance_counts": dict(distance_counts),
            "nav_recommendation_counts": dict(nav_recommendation_counts),
            "semantic_recommendation_counts": dict(semantic_recommendation_counts),
            "display_enabled": args.display,
            "video": str(video_path),
            "events": str(events_path),
        }
        metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"stage": "metrics", **metrics}, indent=2, ensure_ascii=False))
        if args.display:
            cv2.destroyWindow(args.display_window)


if __name__ == "__main__":
    main()
