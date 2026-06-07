from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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


class LinearDecisionClassifier(torch.nn.Module):
    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(in_features, out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


def parse_bool(value: str) -> float:
    return 1.0 if str(value).strip().lower() in {"true", "1", "yes"} else 0.0


def parse_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_rows(path: Path, *, include_synthetic: bool) -> list[dict[str, str]]:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    cleaned = []
    for row in rows:
        label = row.get("user_label", "").strip()
        if label == "uncertain" or not label:
            continue
        if label not in LABELS:
            raise ValueError(f"Unsupported label {label!r} in sample {row.get('sample_id')}")
        if not include_synthetic and parse_bool(row.get("synthetic", "")):
            continue
        cleaned.append(row)
    return cleaned


def row_features(row: dict[str, str]) -> list[float]:
    numeric = {name: parse_float(row.get(name, 0.0)) for name in NUMERIC_FEATURES if name != "low_visibility"}
    numeric["semantic_left_minus_right"] = numeric.get("semantic_left_score", 0.0) - numeric.get("semantic_right_score", 0.0)
    numeric["depth_left_minus_right"] = numeric.get("depth_left_score", 0.0) - numeric.get("depth_right_score", 0.0)
    numeric["fusion_left_minus_right"] = numeric.get("fusion_left_score", 0.0) - numeric.get("fusion_right_score", 0.0)

    features = []
    for name in NUMERIC_FEATURES:
        if name == "low_visibility":
            features.append(parse_bool(row.get(name, "")))
        else:
            features.append(float(numeric.get(name, 0.0)))

    prediction = row.get("model_prediction", "")
    features.extend(1.0 if prediction == value else 0.0 for value in MODEL_PREDICTIONS)

    reason = row.get("model_reason", "")
    features.extend(1.0 if reason == value else 0.0 for value in MODEL_REASONS)
    return features


def featurize(rows: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    feature_names = (
        NUMERIC_FEATURES
        + [f"model_prediction={value}" for value in MODEL_PREDICTIONS]
        + [f"model_reason={value}" for value in MODEL_REASONS]
    )
    x = np.array([row_features(row) for row in rows], dtype=np.float32)
    y = np.array([LABELS.index(row["user_label"].strip()) for row in rows], dtype=np.int64)
    sample_ids = [row["sample_id"] for row in rows]
    return x, y, feature_names, sample_ids


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std < 1e-6] = 1.0
    return (x - mean) / std, mean, std


def standardize_apply(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (x - mean) / std


def class_weights(y: np.ndarray, num_classes: int) -> torch.Tensor:
    counts = np.bincount(y, minlength=num_classes).astype(np.float32)
    weights = np.zeros(num_classes, dtype=np.float32)
    present = counts > 0
    weights[present] = counts[present].sum() / (present.sum() * counts[present])
    weights[~present] = 0.0
    return torch.tensor(weights, dtype=torch.float32)


def train_model(
    x: np.ndarray,
    y: np.ndarray,
    *,
    epochs: int,
    lr: float,
    seed: int,
    verbose: bool = False,
) -> LinearDecisionClassifier:
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    model = LinearDecisionClassifier(x.shape[1], len(LABELS))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights(y, len(LABELS)))

    xt = torch.tensor(x, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.long)
    for epoch in range(epochs):
        optimizer.zero_grad()
        logits = model(xt)
        loss = loss_fn(logits, yt)
        loss.backward()
        optimizer.step()
        if verbose and (epoch + 1) % 250 == 0:
            pred = logits.argmax(dim=1)
            acc = float((pred == yt).float().mean().item())
            print(f"epoch={epoch+1} loss={loss.item():.4f} acc={acc:.3f}")
    return model


def predict(model: LinearDecisionClassifier, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    with torch.no_grad():
        logits = model(torch.tensor(x, dtype=torch.float32))
        probs = torch.softmax(logits, dim=1).cpu().numpy()
        preds = probs.argmax(axis=1)
    return preds, probs


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> list[list[int]]:
    matrix = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    for true, pred in zip(y_true, y_pred):
        matrix[int(true), int(pred)] += 1
    return matrix.tolist()


def loo_evaluate(x_raw: np.ndarray, y: np.ndarray, *, epochs: int, lr: float, seed: int) -> dict[str, Any]:
    predictions = []
    skipped = []
    for i in range(len(y)):
        train_idx = [j for j in range(len(y)) if j != i]
        y_train = y[train_idx]
        if y[i] not in set(int(v) for v in y_train):
            skipped.append(i)
            continue
        x_train_std, mean, std = standardize_fit(x_raw[train_idx])
        model = train_model(x_train_std, y_train, epochs=epochs, lr=lr, seed=seed + i)
        x_test_std = standardize_apply(x_raw[[i]], mean, std)
        pred, prob = predict(model, x_test_std)
        predictions.append(
            {
                "index": i,
                "true": int(y[i]),
                "pred": int(pred[0]),
                "confidence": float(prob[0, pred[0]]),
            }
        )

    if predictions:
        y_true = np.array([item["true"] for item in predictions], dtype=np.int64)
        y_pred = np.array([item["pred"] for item in predictions], dtype=np.int64)
        acc = float(np.mean(y_true == y_pred))
        per_label = {}
        for label_id, label in enumerate(LABELS):
            mask = y_true == label_id
            if mask.any():
                per_label[label] = float(np.mean(y_pred[mask] == y_true[mask]))
        matrix = confusion(y_true, y_pred)
    else:
        acc = 0.0
        per_label = {}
        matrix = confusion(np.array([], dtype=np.int64), np.array([], dtype=np.int64))

    return {
        "evaluated_count": len(predictions),
        "skipped_count": len(skipped),
        "skipped_indices": skipped,
        "accuracy": round(acc, 4),
        "per_label_accuracy": {k: round(v, 4) for k, v in per_label.items()},
        "confusion_matrix": matrix,
        "predictions": predictions,
    }


def write_confusion_csv(path: Path, matrix: list[list[int]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\pred", *LABELS])
        for label, row in zip(LABELS, matrix):
            writer.writerow([label, *row])


def write_predictions_csv(path: Path, rows: list[dict[str, str]], preds: np.ndarray, probs: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fields = ["sample_id", "video", "second", "user_label", "predicted_label", "confidence", *[f"p_{label}" for label in LABELS]]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row, pred, prob in zip(rows, preds, probs):
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "video": row["video"],
                    "second": row["second"],
                    "user_label": row["user_label"],
                    "predicted_label": LABELS[int(pred)],
                    "confidence": round(float(prob[int(pred)]), 4),
                    **{f"p_{label}": round(float(prob[i]), 4) for i, label in enumerate(LABELS)},
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a small frame-level navigation decision classifier.")
    parser.add_argument("--annotations", default="runs/annotation_pack_v1/annotation_tasks_labeled.csv")
    parser.add_argument("--out-dir", default="runs/decision_classifier_v1")
    parser.add_argument("--include-synthetic", action="store_true")
    parser.add_argument("--epochs", type=int, default=1500)
    parser.add_argument("--loo-epochs", type=int, default=450)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    annotation_path = Path(args.annotations)
    if not annotation_path.is_absolute():
        annotation_path = PROJECT_ROOT / annotation_path
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(annotation_path, include_synthetic=args.include_synthetic)
    x_raw, y, feature_names, sample_ids = featurize(rows)
    x_std, mean, std = standardize_fit(x_raw)

    final_model = train_model(x_std, y, epochs=args.epochs, lr=args.lr, seed=args.seed, verbose=True)
    train_pred, train_probs = predict(final_model, x_std)
    train_acc = float(np.mean(train_pred == y))
    loo = loo_evaluate(x_raw, y, epochs=args.loo_epochs, lr=args.lr, seed=args.seed + 1000)

    model_path = out_dir / "decision_classifier.pt"
    torch.save(
        {
            "state_dict": final_model.state_dict(),
            "labels": LABELS,
            "feature_names": feature_names,
            "mean": mean.tolist(),
            "std": std.tolist(),
        },
        model_path,
    )

    label_counts = Counter(row["user_label"].strip() for row in rows)
    metrics = {
        "annotations": str(annotation_path),
        "include_synthetic": args.include_synthetic,
        "sample_count": len(rows),
        "label_counts": dict(label_counts),
        "labels": LABELS,
        "feature_names": feature_names,
        "train_accuracy": round(train_acc, 4),
        "train_confusion_matrix": confusion(y, train_pred),
        "loo": loo,
        "model_path": str(model_path),
        "warning": "This is a small prototype classifier. Classes with very few samples, especially turn_left, need more labels before claiming generalization.",
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    write_confusion_csv(out_dir / "train_confusion_matrix.csv", metrics["train_confusion_matrix"])
    write_confusion_csv(out_dir / "loo_confusion_matrix.csv", loo["confusion_matrix"])
    write_predictions_csv(out_dir / "train_predictions.csv", rows, train_pred, train_probs)

    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
