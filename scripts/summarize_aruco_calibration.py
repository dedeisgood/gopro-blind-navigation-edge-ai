from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_metric(run_dir: Path, label: str) -> dict[str, Any]:
    path = run_dir / f"aruco_metrics_{label}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize 1m/2m/3m ArUco calibration results.")
    parser.add_argument("--run-dir", default="runs/aruco_distance_calibration")
    parser.add_argument("--labels", nargs="+", default=["1m", "2m", "3m"])
    parser.add_argument("--out-json", default="runs/aruco_distance_calibration/aruco_calibration_summary.json")
    parser.add_argument("--out-csv", default="runs/aruco_distance_calibration/aruco_calibration_summary.csv")
    parser.add_argument("--out-plot", default="runs/aruco_distance_calibration/aruco_calibration_curve.png")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    metrics = [load_metric(run_dir, label) for label in args.labels]

    points = []
    for label, metric in zip(args.labels, metrics):
        known = float(metric["known_distance_m"])
        raw = float(metric["median_distance_m"])
        points.append(
            {
                "label": label,
                "known_distance_m": known,
                "raw_median_distance_m": raw,
                "single_point_scale": known / raw if raw > 0 else 0.0,
                "detections": int(metric["detections"]),
                "raw_error_m": raw - known,
                "raw_abs_error_m": abs(raw - known),
                "relative_error_pct": float(metric["relative_error_pct"]),
            }
        )

    least_squares_scale = sum(p["raw_median_distance_m"] * p["known_distance_m"] for p in points) / sum(
        p["raw_median_distance_m"] ** 2 for p in points
    )

    for point in points:
        calibrated = point["raw_median_distance_m"] * least_squares_scale
        point["after_ls_scale_m"] = calibrated
        point["after_ls_error_m"] = calibrated - point["known_distance_m"]
        point["after_ls_abs_error_m"] = abs(calibrated - point["known_distance_m"])

    raw_mae = sum(p["raw_abs_error_m"] for p in points) / len(points)
    calibrated_mae = sum(p["after_ls_abs_error_m"] for p in points) / len(points)

    summary = {
        "points": [{k: round(v, 4) if isinstance(v, float) else v for k, v in p.items()} for p in points],
        "least_squares_scale": round(least_squares_scale, 4),
        "recommended_distance_scale": round(least_squares_scale, 4),
        "raw_mae_m": round(raw_mae, 4),
        "calibrated_mae_m": round(calibrated_mae, 4),
        "mae_improvement_pct": round((raw_mae - calibrated_mae) / raw_mae * 100.0, 2) if raw_mae > 0 else 0.0,
        "note": "Recommended scale minimizes squared error across the ArUco median distances.",
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    out_csv = Path(args.out_csv)
    with out_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(summary["points"][0].keys()))
        writer.writeheader()
        writer.writerows(summary["points"])

    try:
        import matplotlib.pyplot as plt

        known = [p["known_distance_m"] for p in points]
        raw = [p["raw_median_distance_m"] for p in points]
        calibrated = [p["after_ls_scale_m"] for p in points]
        max_axis = max(max(known), max(raw), max(calibrated)) + 0.25

        fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
        ax.plot([0, max_axis], [0, max_axis], color="#444", linewidth=1.5, linestyle="--", label="ideal")
        ax.scatter(known, raw, color="#d64b3c", s=64, label="raw estimate")
        ax.scatter(known, calibrated, color="#1b8a5a", s=64, label="after scale")
        ax.plot(known, raw, color="#d64b3c", linewidth=1.2, alpha=0.7)
        ax.plot(known, calibrated, color="#1b8a5a", linewidth=1.2, alpha=0.7)
        ax.set_title("GoPro ArUco Distance Calibration")
        ax.set_xlabel("Known distance (m)")
        ax.set_ylabel("Estimated distance (m)")
        ax.set_xlim(0, max_axis)
        ax.set_ylim(0, max_axis)
        ax.grid(True, alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.out_plot)
        plt.close(fig)
    except Exception as exc:
        summary["plot_error"] = str(exc)
        out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
