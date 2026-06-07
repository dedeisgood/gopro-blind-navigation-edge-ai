from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


ADDED_FIELDS = [
    "semantic_left_score",
    "semantic_right_score",
    "depth_left_score",
    "depth_right_score",
    "fusion_left_score",
    "fusion_right_score",
]


def sample_id(video_filename: str, second: Any) -> str:
    return f"{Path(video_filename).stem}__t{str(second).replace('.', '_')}"


def feature_map(summary: dict[str, Any]) -> dict[str, dict[str, float]]:
    features = {}
    for video in summary["videos"]:
        for sample in video["samples"]:
            semantic = sample.get("semantic") or {}
            depth = sample.get("depth_analysis") or {}
            semantic_left = float(semantic.get("left_score", 0.0) or 0.0)
            semantic_right = float(semantic.get("right_score", 0.0) or 0.0)
            depth_left = float(depth.get("left_score", 0.0) or 0.0)
            depth_right = float(depth.get("right_score", 0.0) or 0.0)
            features[sample_id(video["filename"], sample["second"])] = {
                "semantic_left_score": round(semantic_left, 4),
                "semantic_right_score": round(semantic_right, 4),
                "depth_left_score": round(depth_left, 4),
                "depth_right_score": round(depth_right, 4),
                "fusion_left_score": round(max(semantic_left, depth_left), 4),
                "fusion_right_score": round(max(semantic_right, depth_right), 4),
            }
    return features


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def main() -> None:
    parser = argparse.ArgumentParser(description="Add left/right navigation features to an exported annotation CSV.")
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    annotation_path = resolve(args.annotations)
    summary_path = resolve(args.summary)
    out_path = resolve(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    features_by_id = feature_map(summary)
    rows = list(csv.DictReader(annotation_path.open(encoding="utf-8-sig")))
    if not rows:
        raise SystemExit("No annotation rows found.")

    missing = []
    for row in rows:
        features = features_by_id.get(row["sample_id"])
        if not features:
            missing.append(row["sample_id"])
            continue
        row.update({key: str(value) for key, value in features.items()})

    if missing:
        raise SystemExit(f"Could not enrich {len(missing)} sample(s): {missing[:5]}")

    fieldnames = list(rows[0].keys())
    for field in ADDED_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"out": str(out_path), "rows": len(rows), "added_fields": ADDED_FIELDS}, indent=2))


if __name__ == "__main__":
    main()
