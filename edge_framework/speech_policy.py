from __future__ import annotations


GENERIC_CLASS_EN = "obstacle"
GENERIC_CLASS_ZH = "\u969c\u7919\u7269"


CLASS_ZH = {
    "person": "\u4eba",
    "bicycle": "\u8173\u8e0f\u8eca",
    "car": "\u8eca",
    "motorcycle": "\u6a5f\u8eca",
    "bus": "\u516c\u8eca",
    "truck": "\u5361\u8eca",
    "traffic light": "\u4ea4\u901a\u865f\u8a8c",
    "stop sign": "\u505c\u6b62\u6a19\u8a8c",
    "bench": "\u9577\u6905",
    "chair": "\u6905\u5b50",
    "couch": "\u6c99\u767c",
    "potted plant": "\u76c6\u683d",
    "backpack": "\u80cc\u5305",
    "suitcase": "\u884c\u674e\u7bb1",
    "sports ball": "\u7403",
}


# Indoor assistive walking should prefer useful obstacle cues over exact COCO names.
# Classes not listed here are still logged, but spoken as a generic obstacle.
INDOOR_NAMED_MIN_CONF = {
    "person": 0.25,
    "chair": 0.25,
    "bench": 0.30,
    "couch": 0.30,
    "backpack": 0.35,
    "suitcase": 0.35,
    "bicycle": 0.40,
    "potted plant": 0.50,
}


INDOOR_ALWAYS_GENERIC = {
    "car",
    "motorcycle",
    "bus",
    "truck",
    "traffic light",
    "stop sign",
    "sports ball",
}


def speech_label(class_name: str, confidence: float, *, mode: str = "indoor") -> tuple[str, str, bool]:
    if mode != "indoor":
        return class_name, CLASS_ZH.get(class_name, GENERIC_CLASS_ZH), False

    if class_name in INDOOR_ALWAYS_GENERIC:
        return GENERIC_CLASS_EN, GENERIC_CLASS_ZH, True

    min_conf = INDOOR_NAMED_MIN_CONF.get(class_name)
    if min_conf is None or confidence < min_conf:
        return GENERIC_CLASS_EN, GENERIC_CLASS_ZH, True

    return class_name, CLASS_ZH.get(class_name, GENERIC_CLASS_ZH), False
