from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


LABELS = [
    "front_passable",
    "turn_left",
    "turn_right",
    "stop",
    "low_visibility_stop",
    "uncertain",
]

LABEL_ZH = {
    "front_passable": "前方可走",
    "turn_left": "往左較安全",
    "turn_right": "往右較安全",
    "stop": "先停止",
    "low_visibility_stop": "光線不足，先停止",
    "uncertain": "不確定，不拿去訓練",
}

REASON_ZH = {
    "passable": "模型認為可通行",
    "semantic_wall_or_no_floor": "模型看到牆或缺少地板",
    "depth_close_space": "深度模型認為前方太近",
    "low_visibility": "光線不足",
}

SCENARIO_ZH = {
    "wall_approach": "正對牆走近",
    "corridor_forward": "走廊前進",
    "left_open_right_wall": "左邊可走、右邊牆",
    "right_open_left_wall_synthflip": "右邊可走、左邊牆（翻轉合成）",
    "door_front": "正對門口",
    "table_chair_obstacle": "桌椅擋路",
    "low_light": "低光源",
    "no_light": "無光線",
    "glass_reflection": "玻璃/反光牆面",
}

CONFIDENCE_ZH = {
    "high": "高",
    "medium": "中",
    "low": "低",
}


SCENARIO_ZH.update(
    {
        "left_open_right_wall": "\u5de6\u908a\u53ef\u8d70\u3001\u53f3\u908a\u7246",
        "right_open_left_wall": "\u53f3\u908a\u53ef\u8d70\u3001\u5de6\u908a\u7246",
        "front_wall_turn_left": "\u6b63\u524d\u65b9\u7246\uff0c\u5de6\u908a\u53ef\u7e5e",
        "front_wall_turn_right": "\u6b63\u524d\u65b9\u7246\uff0c\u53f3\u908a\u53ef\u7e5e",
        "front_blocked_no_route": "\u524d\u65b9\u969c\u7919\u7269\uff0c\u5de6\u53f3\u90fd\u4e0d\u80fd\u8d70",
        "front_obstacle_left_route": "\u524d\u65b9\u969c\u7919\u7269\uff0c\u5de6\u908a\u53ef\u8d70",
        "front_obstacle_right_route": "\u524d\u65b9\u969c\u7919\u7269\uff0c\u53f3\u908a\u53ef\u8d70",
        "environment_walkthrough": "\u6574\u9ad4\u74b0\u5883\u8d70\u67e5",
    }
)


GUIDELINE_ZH = """# Decision Annotation Guideline

這份標註不是像素級 wall/floor segmentation，而是訓練小型決策分類器用的 frame-level decision label。

## 標註目標

每一列代表某支 GoPro 影片的一個取樣時間點。請根據「真實場景是否安全可走」標註 `user_label`。

允許標籤：

| Label | 意義 |
| --- | --- |
| front_passable | 前方主要路線可繼續走 |
| turn_left | 前方/右前方較危險，左前方較安全 |
| turn_right | 前方/左前方較危險，右前方較安全 |
| stop | 前方不可通行，或沒有可靠可走方向 |
| low_visibility_stop | 畫面太暗/看不清楚，視覺模型不可信，請先停止 |
| uncertain | 你也無法從畫面判斷，先不要拿去訓練 |

## 重要規則

1. 請標「你認為盲人當下應該收到的提示」，不是標模型目前輸出。
2. `no_light` 不應該拿去教 wall/floor 語意分割；它應該標成 `low_visibility_stop`，當作安全決策的負樣本。
3. 鏡子/玻璃反射如果讓可通行區不可靠，標成 `stop` 或 `uncertain`，不要因為反射看起來有空間就標可走。
4. synthetic flip 影片可以拿來測左右邏輯或做資料增強，但正式實拍驗證表格要和真實影片分開。
5. 如果前方可走但有明顯障礙在一側，標最安全的方向，不要只看畫面中央。
6. 如果你只是不確定，標 `uncertain` 比硬標更好。
"""


def draft_label(video: dict[str, Any], sample: dict[str, Any]) -> tuple[str, str, str]:
    key = video.get("label_key", "")
    rec = sample.get("recommendation", "")
    reason = sample.get("reason", "")
    visibility = sample.get("visibility", {})

    if visibility.get("low_visibility") or key == "no_light":
        return "low_visibility_stop", "high", "No-light/low-visibility is unsafe even if segmentation predicts floor."
    if key == "corridor_forward":
        return "front_passable", "high", "Scenario is corridor forward and model also generally keeps it passable."
    if key == "left_open_right_wall":
        return "turn_left", "medium", "Scenario name says left side is the remaining route; review each frame."
    if key == "right_open_left_wall":
        return "turn_right", "medium", "Scenario name says right side is the remaining route; review each frame."
    if key == "front_wall_turn_left":
        return "turn_left", "medium", "Front wall requires moving around it from the left side; review each frame."
    if key == "front_wall_turn_right":
        return "turn_right", "medium", "Front wall requires moving around it from the right side; review each frame."
    if key == "front_blocked_no_route":
        return "stop", "high", "Scenario name says front is blocked and there is no safe route."
    if key == "front_obstacle_left_route":
        return "turn_left", "medium", "Front obstacle with left side route; review each frame."
    if key == "front_obstacle_right_route":
        return "turn_right", "medium", "Front obstacle with right side route; review each frame."
    if key == "right_open_left_wall_synthflip":
        return "turn_right", "medium", "Synthetic horizontal flip of left-open/right-wall; use for left/right logic only."
    if key == "glass_reflection":
        return "stop", "medium", "Glass/mirror reflection is unreliable for assistive navigation."
    if key == "wall_approach":
        return "stop", "medium", "Direct wall approach is unsafe unless a clear side opening is visible."
    if key == "table_chair_obstacle":
        return rec if rec in {"turn_left", "turn_right", "stop"} else "uncertain", "low", "Obstacle scene needs human review for safest side."
    if key == "door_front":
        return "uncertain", "low", "Doorway can be passable or blocked depending on the actual frame."
    if key == "low_light":
        return rec if reason != "passable" else "uncertain", "low", "Low light is visible enough to review manually; do not auto-mark as low_visibility."
    return "uncertain", "low", "Needs human review."


def rel(path: str | Path, base: Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    try:
        return str(p.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def build_rows(summary: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    rows = []
    for video in summary["videos"]:
        for sample_index, sample in enumerate(video["samples"], start=1):
            draft, confidence, note = draft_label(video, sample)
            sample_id = f"{Path(video['filename']).stem}__t{str(sample['second']).replace('.', '_')}"
            semantic = sample.get("semantic") or {}
            depth = sample.get("depth_analysis") or {}
            semantic_left = float(semantic.get("left_score", 0.0) or 0.0)
            semantic_right = float(semantic.get("right_score", 0.0) or 0.0)
            depth_left = float(depth.get("left_score", 0.0) or 0.0)
            depth_right = float(depth.get("right_score", 0.0) or 0.0)
            fusion_left = max(semantic_left, depth_left)
            fusion_right = max(semantic_right, depth_right)
            rows.append(
                {
                    "sample_id": sample_id,
                    "video": video["filename"],
                    "label_key": video.get("label_key", ""),
                    "synthetic": str(bool(video.get("synthetic", False))).lower(),
                    "sample_index": sample_index,
                    "second": sample["second"],
                    "overlay_path": rel(sample["overlay"], project_root),
                    "frame_path": rel(sample["frame"], project_root),
                    "model_prediction": sample["recommendation"],
                    "model_reason": sample["reason"],
                    "assistant_draft_label": draft,
                    "assistant_confidence": confidence,
                    "assistant_note": note,
                    "user_label": "",
                    "user_note": "",
                    "front_wall_ratio": sample["semantic_front_wall_ratio"],
                    "front_floor_ratio": sample["semantic_front_floor_ratio"],
                    "semantic_left_score": round(semantic_left, 4),
                    "semantic_right_score": round(semantic_right, 4),
                    "depth_front_score": sample["depth_front_score"],
                    "depth_left_score": round(depth_left, 4),
                    "depth_right_score": round(depth_right, 4),
                    "fusion_front_score": sample["fusion_front_score"],
                    "fusion_left_score": round(fusion_left, 4),
                    "fusion_right_score": round(fusion_right, 4),
                    "mean_luma": sample.get("mean_luma", ""),
                    "dark_ratio": sample.get("dark_ratio", ""),
                    "low_visibility": str(bool(sample.get("low_visibility", False))).lower(),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, rows: list[dict[str, Any]]) -> None:
    label_descriptions = {
        label: f"{LABEL_ZH[label]} ({label})" for label in LABELS
    }
    body = []
    for row in rows:
        overlay_abs = PROJECT_ROOT / row["overlay_path"]
        overlay = html.escape(rel(overlay_abs, path.parent))
        options = "\n".join(
            f'<option value="{label}"{" selected" if label == row["assistant_draft_label"] else ""}>{html.escape(label_descriptions[label])}</option>'
            for label in LABELS
        )
        body.append(
            f"""
            <article class="card" data-sample-id="{html.escape(row['sample_id'])}">
              <img src="{overlay}" alt="{html.escape(row['sample_id'])}">
              <div class="meta">
                <h2>{html.escape(row['video'])} @ {row['second']}s</h2>
                <p><b>場景:</b> {html.escape(SCENARIO_ZH.get(row['label_key'], row['label_key']))} | <b>合成影片:</b> {"是" if row['synthetic'] == "true" else "否"}</p>
                <p><b>模型目前判斷:</b> {html.escape(LABEL_ZH.get(row['model_prediction'], row['model_prediction']))} | <b>原因:</b> {html.escape(REASON_ZH.get(row['model_reason'], row['model_reason']))}</p>
                <p><b>我先幫你預標:</b> {html.escape(LABEL_ZH.get(row['assistant_draft_label'], row['assistant_draft_label']))} | <b>信心:</b> {html.escape(CONFIDENCE_ZH.get(row['assistant_confidence'], row['assistant_confidence']))}</p>
                <p><b>模型特徵:</b> 牆 {row['front_wall_ratio']} | 地板 {row['front_floor_ratio']} | 亮度 {row['mean_luma']} | 暗區比例 {row['dark_ratio']}</p>
                <label>你認為正確的提示
                  <select data-field="user_label">
                    {options}
                  </select>
                </label>
                <label>備註
                  <input data-field="user_note" type="text" placeholder="可不填，例如：這張其實應該往左">
                </label>
              </div>
            </article>
            """
        )
    page = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>GoPro 避障提示標註</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #111; color: #eee; }}
    header {{ position: sticky; top: 0; background: #181818; padding: 14px 18px; border-bottom: 1px solid #333; z-index: 2; }}
    button {{ padding: 8px 12px; margin-right: 8px; cursor: pointer; }}
    .help {{ margin-top: 10px; max-width: 1100px; line-height: 1.45; color: #ddd; }}
    .help code {{ background: #2a2a2a; padding: 1px 5px; border-radius: 4px; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(520px, 1fr)); gap: 14px; padding: 14px; }}
    .card {{ background: #1f1f1f; border: 1px solid #333; display: grid; grid-template-columns: 1fr; }}
    img {{ width: 100%; display: block; }}
    .meta {{ padding: 10px; }}
    h2 {{ font-size: 16px; margin: 0 0 8px; }}
    p {{ margin: 5px 0; font-size: 13px; }}
    label {{ display: block; margin-top: 8px; font-size: 13px; }}
    select, input {{ width: 100%; box-sizing: border-box; padding: 7px; margin-top: 4px; background: #111; color: #eee; border: 1px solid #555; }}
  </style>
</head>
<body>
  <header>
    <button id="fillDrafts">全部改回我的預標</button>
    <button id="exportCsv">匯出 CSV</button>
    <span>{len(rows)} samples</span>
    <div class="help">
      操作方式：每張圖是一個取樣時間點。你只要看圖，決定盲人當下應該聽到什麼提示。
      下拉選單已經先填入我的預標；你同意就不用動，不同意才改。
      <code>前方可走</code> 是可以繼續走，<code>往左較安全</code>/<code>往右較安全</code> 是轉向提示，
      <code>先停止</code> 是不該冒險，<code>光線不足，先停止</code> 是畫面太暗，<code>不確定</code> 是不要拿去訓練。
      全部看完按「匯出 CSV」。
    </div>
  </header>
  <main>
    {''.join(body)}
  </main>
  <script>
    const rows = {json.dumps(rows, ensure_ascii=False)};
    const cards = [...document.querySelectorAll('.card')];
    document.getElementById('fillDrafts').onclick = () => {{
      cards.forEach((card, i) => {{
        card.querySelector('[data-field="user_label"]').value = rows[i].assistant_draft_label;
      }});
    }};
    document.getElementById('exportCsv').onclick = () => {{
      const exported = rows.map((row, i) => {{
        const card = cards[i];
        return {{
          ...row,
          user_label: card.querySelector('[data-field="user_label"]').value,
          user_note: card.querySelector('[data-field="user_note"]').value.replace(/\\r?\\n/g, ' ')
        }};
      }});
      const keys = Object.keys(exported[0]);
      const escapeCsv = value => `"${{String(value ?? '').replaceAll('"', '""')}}"`;
      const csv = [keys.join(','), ...exported.map(row => keys.map(key => escapeCsv(row[key])).join(','))].join('\\n');
      const blob = new Blob([csv], {{type: 'text/csv;charset=utf-8'}});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'annotation_tasks_labeled.csv';
      a.click();
    }};
  </script>
</body>
</html>
"""
    path.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a frame-level decision annotation pack.")
    parser.add_argument("--summary", default="runs/gopro_dataset_analysis_v2_visibility_gate/batch_summary.json")
    parser.add_argument("--out-dir", default="runs/annotation_pack_v1")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.is_absolute():
        summary_path = PROJECT_ROOT / summary_path
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = build_rows(summary, PROJECT_ROOT)
    write_csv(out_dir / "annotation_tasks.csv", rows)
    (out_dir / "annotation_guideline_zh.md").write_text(GUIDELINE_ZH, encoding="utf-8")
    write_html(out_dir / "annotation_review.html", rows)
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "tasks": len(rows),
                "csv": str(out_dir / "annotation_tasks.csv"),
                "html": str(out_dir / "annotation_review.html"),
                "guideline": str(out_dir / "annotation_guideline_zh.md"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
