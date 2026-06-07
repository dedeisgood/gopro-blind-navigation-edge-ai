from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from edge_framework import EdgeVideoPipeline, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the configurable edge video analytics pipeline.")
    parser.add_argument("--config", required=True, help="Path to a JSON task config.")
    args = parser.parse_args()

    config = load_config(args.config)
    pipeline = EdgeVideoPipeline(config)
    summary = pipeline.run()

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

