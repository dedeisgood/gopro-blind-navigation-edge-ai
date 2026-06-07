from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch

from edge_framework import navigability as nav
from edge_framework import semantic_navigability as semnav


LABELS = [
    "front_passable",
    "turn_left",
    "turn_right",
    "stop",
    "low_visibility_stop",
]

MODEL_PREDICTIONS = [
    "front_passable",
    "turn_left",
    "turn_right",
    "stop",
    "low_visibility_stop",
    "uncertain",
]

MODEL_REASONS = [
    "passable",
    "semantic_wall_or_no_floor",
    "depth_close_space",
    "low_visibility",
]

NUMERIC_FEATURES = [
    "front_wall_ratio",
    "front_floor_ratio",
    "semantic_left_score",
    "semantic_right_score",
    "depth_front_score",
    "depth_left_score",
    "depth_right_score",
    "fusion_front_score",
    "fusion_left_score",
    "fusion_right_score",
    "semantic_left_minus_right",
    "depth_left_minus_right",
    "fusion_left_minus_right",
    "mean_luma",
    "dark_ratio",
    "low_visibility",
]

SPEECH_BY_LABEL = {
    "front_passable": nav.SPEECH_FRONT_PASSABLE,
    "turn_left": nav.SPEECH_TURN_LEFT,
    "turn_right": nav.SPEECH_TURN_RIGHT,
    "stop": nav.SPEECH_STOP,
    "low_visibility_stop": semnav.SPEECH_LOW_VISIBILITY,
}

OVERLAY_BY_LABEL = {
    "front_passable": "LEARNED / FRONT PASSABLE",
    "turn_left": "LEARNED / LEFT CLEARER",
    "turn_right": "LEARNED / RIGHT CLEARER",
    "stop": "LEARNED / STOP",
    "low_visibility_stop": "LEARNED / LOW VISIBILITY STOP",
}


class _LinearDecisionClassifier(torch.nn.Module):
    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(in_features, out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool_float(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return 1.0 if str(value).strip().lower() in {"true", "1", "yes"} else 0.0


class DecisionClassifier:
    def __init__(self, model_path: str | Path, *, device: str = "cpu") -> None:
        self.model_path = Path(model_path)
        self.device = device
        checkpoint = torch.load(self.model_path, map_location=device)
        self.labels = list(checkpoint.get("labels", LABELS))
        self.feature_names = list(checkpoint["feature_names"])
        self.mean = np.array(checkpoint["mean"], dtype=np.float32)
        self.std = np.array(checkpoint["std"], dtype=np.float32)
        self.std[self.std < 1e-6] = 1.0

        self.model = _LinearDecisionClassifier(len(self.feature_names), len(self.labels)).to(device)
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()

    def feature_dict_from_fusion(self, fusion_analysis: dict[str, Any]) -> dict[str, float]:
        semantic = fusion_analysis.get("semantic") or {}
        depth = fusion_analysis.get("depth") or {}
        visibility = fusion_analysis.get("visibility") or {}
        model_prediction = str(fusion_analysis.get("recommendation", "uncertain"))
        model_reason = str(fusion_analysis.get("reason", ""))

        values: dict[str, float] = {
            "front_wall_ratio": _as_float(semantic.get("front_wall_ratio")),
            "front_floor_ratio": _as_float(semantic.get("front_floor_ratio")),
            "semantic_left_score": _as_float(semantic.get("left_score")),
            "semantic_right_score": _as_float(semantic.get("right_score")),
            "depth_front_score": _as_float(depth.get("front_score")),
            "depth_left_score": _as_float(depth.get("left_score")),
            "depth_right_score": _as_float(depth.get("right_score")),
            "fusion_front_score": _as_float(fusion_analysis.get("front_score")),
            "fusion_left_score": _as_float(fusion_analysis.get("left_score")),
            "fusion_right_score": _as_float(fusion_analysis.get("right_score")),
            "mean_luma": _as_float(visibility.get("mean_luma")),
            "dark_ratio": _as_float(visibility.get("dark_ratio")),
            "low_visibility": _as_bool_float(visibility.get("low_visibility")),
        }
        values["semantic_left_minus_right"] = values["semantic_left_score"] - values["semantic_right_score"]
        values["depth_left_minus_right"] = values["depth_left_score"] - values["depth_right_score"]
        values["fusion_left_minus_right"] = values["fusion_left_score"] - values["fusion_right_score"]
        values.update({f"model_prediction={value}": 1.0 if model_prediction == value else 0.0 for value in MODEL_PREDICTIONS})
        values.update({f"model_reason={value}": 1.0 if model_reason == value else 0.0 for value in MODEL_REASONS})
        return values

    def predict_from_fusion(self, fusion_analysis: dict[str, Any]) -> dict[str, Any]:
        values = self.feature_dict_from_fusion(fusion_analysis)
        features = np.array([[values.get(name, 0.0) for name in self.feature_names]], dtype=np.float32)
        features = (features - self.mean) / self.std
        with torch.no_grad():
            logits = self.model(torch.tensor(features, dtype=torch.float32, device=self.device))
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        pred_index = int(np.argmax(probs))
        label = self.labels[pred_index]
        return {
            "label": label,
            "confidence": round(float(probs[pred_index]), 4),
            "probabilities": {label_name: round(float(probs[i]), 4) for i, label_name in enumerate(self.labels)},
            "model_path": str(self.model_path),
        }

    def apply_to_fusion(
        self,
        fusion_analysis: dict[str, Any],
        decision: dict[str, Any],
        *,
        min_confidence: float = 0.50,
        blocked_front_threshold: float | None = None,
    ) -> dict[str, Any]:
        updated = dict(fusion_analysis)
        label = str(decision["label"])
        updated["decision_model"] = decision
        updated["rule_recommendation"] = fusion_analysis.get("recommendation")
        updated["rule_reason"] = fusion_analysis.get("reason")
        updated["decision_applied"] = bool(float(decision["confidence"]) >= min_confidence)

        if not updated["decision_applied"]:
            return updated

        if (
            blocked_front_threshold is not None
            and label != "front_passable"
            and fusion_analysis.get("recommendation") == "front_passable"
            and float(fusion_analysis.get("front_score", 0.0)) < blocked_front_threshold
            and not ((fusion_analysis.get("visibility") or {}).get("low_visibility"))
        ):
            updated["decision_applied"] = False
            updated["decision_gate"] = "front_score_too_low_for_blocked_override"
            return updated

        updated["recommendation"] = label
        updated["front_blocked"] = label != "front_passable"
        updated["speech_zh"] = SPEECH_BY_LABEL.get(label, nav.SPEECH_STOP)
        updated["speech_overlay"] = OVERLAY_BY_LABEL.get(label, "LEARNED / STOP")
        updated["reason"] = "decision_classifier"
        return updated
