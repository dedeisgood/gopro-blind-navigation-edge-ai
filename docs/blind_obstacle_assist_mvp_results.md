# 視障輔助避障 MVP 測試結果

日期：2026-06-04

## 測試目標

本次測試先不使用 GoPro live stream，也不建立 WSL/VM。目標是驗證視障輔助避障系統的核心邏輯是否可行：

1. 使用 YOLO 偵測障礙物。
2. 將偵測結果轉換為左/中/右方向。
3. 根據 bounding box 面積與位置估計風險。
4. 輸出輔助提示、event log、metrics 與標註影片。

## 使用環境

使用既有 Windows conda 環境：

```powershell
C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe
```

環境檢查結果：

| 項目 | 值 |
| --- | --- |
| Python | 3.11.15 |
| PyTorch | 2.12.0+cpu |
| CUDA available | false |
| Ultralytics | 8.4.51 |
| OpenCV | 4.11.0 |

## 一鍵執行

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\run_obstacle_assist_cpu_sample.ps1
```

或直接執行：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\run_obstacle_assist.py --config .\configs\blind_obstacle_assist_sample.json
```

## 輸出檔案

```text
runs/blind_obstacle_assist_sample/annotated_obstacle_assist.mp4
runs/blind_obstacle_assist_sample/preview.jpg
runs/blind_obstacle_assist_sample/events.jsonl
runs/blind_obstacle_assist_sample/metrics.json
```

## 測試結果

| 指標 | 值 |
| --- | ---: |
| Processed frames | 30 |
| Event count | 180 |
| Elapsed seconds | 2.388 |
| FPS | 12.561 |
| Average latency | 67.34 ms |
| P95 latency | 73.002 ms |

風險統計：

| Risk | Count |
| --- | ---: |
| High | 60 |
| Medium | 60 |
| Low | 60 |

方向統計：

| Direction | Count |
| --- | ---: |
| Left | 90 |
| Center | 60 |
| Right | 30 |

## Event Log 範例

```json
{"frame_index": 0, "class_name": "bus", "direction": "center", "risk": "high", "cue": "High risk bus ahead"}
{"frame_index": 0, "class_name": "person", "direction": "left", "risk": "medium", "cue": "person left side"}
{"frame_index": 0, "class_name": "person", "direction": "right", "risk": "medium", "cue": "person right side"}
{"frame_index": 0, "class_name": "person", "direction": "center", "risk": "high", "cue": "High risk person ahead"}
```

## 畫面標註邏輯

- 青色垂直線：將畫面分成 left / ahead / right。
- 綠框：low risk。
- 黃框：medium risk。
- 紅框：high risk。
- 底部 cue panel：整理目前畫面中較重要的輔助提示。

## GoPro 影片切換方式

目前 config 使用靜態圖片產生短影片測試。若要改成 GoPro 錄製影片，將影片放到：

```text
assets/gopro_walk_sample.mp4
```

然後執行：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\run_obstacle_assist.py --config .\configs\blind_obstacle_assist_video_template.json
```

## 限制

- 目前是 CPU-only 測試。
- 目前沒有使用 GoPro live stream。
- 單眼 RGB 影像無法可靠估計真實距離。
- 此系統只能作為 obstacle awareness 原型，不可宣稱為正式安全避障輔具。

## 下一步

1. 用 GoPro 錄一段第一人稱走路影片，替換 template config 的影片路徑。
2. 將輸出 cue 從文字改成 beep 或 TTS。
3. 加入簡單 temporal smoothing，避免每一幀重複提醒。
4. 建立 WSL2 on D 槽環境，準備 GPU/CUDA 版本。
5. 若期末時間允許，加入麥克風事件偵測 placeholder 或簡單音量事件。

