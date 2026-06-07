from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    type: str
    params: dict[str, Any]


@dataclass(frozen=True)
class ModelConfig:
    backend: str
    classes: list[str]
    weights: str | None = None
    params: dict[str, Any] | None = None


@dataclass(frozen=True)
class InferenceConfig:
    resolution: tuple[int, int]
    fps_limit: float
    frame_skip: int
    precision: str
    device: str


@dataclass(frozen=True)
class RuleConfig:
    name: str
    type: str
    params: dict[str, Any]


@dataclass(frozen=True)
class OutputConfig:
    run_dir: Path


@dataclass(frozen=True)
class AppConfig:
    task_name: str
    source: SourceConfig
    model: ModelConfig
    inference: InferenceConfig
    rules: list[RuleConfig]
    output: OutputConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    source = SourceConfig(
        type=raw["source"]["type"],
        params={k: v for k, v in raw["source"].items() if k != "type"},
    )

    model = ModelConfig(
        backend=raw["model"]["backend"],
        weights=raw["model"].get("weights"),
        classes=list(raw["model"].get("classes", [])),
        params={k: v for k, v in raw["model"].items() if k not in {"backend", "weights", "classes"}},
    )

    inference = InferenceConfig(
        resolution=tuple(raw["inference"].get("resolution", [640, 360])),
        fps_limit=float(raw["inference"].get("fps_limit", 15)),
        frame_skip=int(raw["inference"].get("frame_skip", 0)),
        precision=raw["inference"].get("precision", "fp32"),
        device=raw["inference"].get("device", "cpu"),
    )

    rules = [
        RuleConfig(
            name=rule["name"],
            type=rule["type"],
            params={k: v for k, v in rule.items() if k not in {"name", "type"}},
        )
        for rule in raw.get("rules", [])
    ]

    output = OutputConfig(run_dir=Path(raw.get("output", {}).get("run_dir", f"runs/{raw['task_name']}")))

    return AppConfig(
        task_name=raw["task_name"],
        source=source,
        model=model,
        inference=inference,
        rules=rules,
        output=output,
    )

