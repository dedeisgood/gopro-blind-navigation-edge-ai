from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework import EdgeVideoPipeline, load_config


CONFIGS = [
    PROJECT_ROOT / "configs" / "person_counting.json",
    PROJECT_ROOT / "configs" / "safety_helmet.json",
]


def main() -> None:
    results = {}

    for config_path in CONFIGS:
        config = load_config(config_path)
        summary = EdgeVideoPipeline(config).run()

        assert summary["processed_frames"] > 0
        assert summary["event_count"] > 0

        results[config.task_name] = summary

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

