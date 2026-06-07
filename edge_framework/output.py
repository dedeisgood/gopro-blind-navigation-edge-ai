from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import Event


class EventWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "events.jsonl"
        self.file = self.path.open("w", encoding="utf-8")

    def write_many(self, events: list[Event]) -> None:
        for event in events:
            self.file.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()

    def __enter__(self) -> "EventWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

