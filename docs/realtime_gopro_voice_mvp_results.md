# GoPro 即時語音避障 MVP 結果

日期：2026-06-05

## 核心定位

本版本將 GoPro 視為視障者的第一人稱視覺感測器，筆電作為 edge prototype。系統不要求使用者觀看標註框，而是將影像辨識結果轉換成即時語音提示。

```text
GoPro USB stream
        |
        v
FFmpeg UDP receiver
        |
        v
YOLO obstacle detection
        |
        v
left / ahead / right + risk ranking
        |
        v
Chinese TTS voice cue
```

## 成功條件

已完成：

- 不依賴會 crash 的 GoPro Webcam tray app。
- 直接透過 GoPro USB API 啟動 webcam stream。
- 先啟動 FFmpeg UDP listener，再呼叫 `/gp/gpWebcam/START?res=720`。
- 即時讀取 GoPro 影像。
- 即時做 YOLO 偵測。
- 即時輸出中文語音，例如：

```text
注意，正前方有椅子
正前方有盆栽
注意，右前方有椅子
```

## 執行指令

短測 15 秒：

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\run_realtime_gopro_voice_sample.ps1
```

直接執行主腳本：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\realtime_gopro_obstacle_voice.py --gopro-ip 172.26.181.51 --seconds 15 --res 720 --analysis-fps 8 --lang zh-TW
```

## 測試結果一：15 秒測試

| 指標 | 值 |
| --- | ---: |
| Frames processed | 86 |
| Effective FPS | 5.299 |
| Event count | 86 |
| Spoken count | 5 |
| Average latency | 48.719 ms |
| P95 latency | 61.985 ms |

語音輸出範例：

```text
注意，正前方有椅子
正前方有盆栽
注意，正前方有椅子
```

## 測試結果二：8 秒短測

| 指標 | 值 |
| --- | ---: |
| Frames processed | 33 |
| Effective FPS | 3.590 |
| Event count | 33 |
| Spoken count | 1 |
| Average latency | 57.758 ms |
| P95 latency | 64.937 ms |

語音輸出範例：

```text
注意，右前方有椅子
```

## 測試結果三：GPU + 480p 即時設定

這次使用 `edge_gpu` 環境、RTX 5060 Laptop GPU、GoPro 480p、analysis FPS 12。

| 指標 | 值 |
| --- | ---: |
| Frames processed | 141 |
| Effective FPS | 8.664 |
| Event count | 0 |
| Spoken count | 0 |
| Average latency | 20.910 ms |
| P95 latency | 24.662 ms |

這次鏡頭前沒有偵測到障礙物，所以沒有語音輸出。重點是 GPU 推論與 GoPro UDP 串流可一起運作。

## 輸出檔案

```text
runs/realtime_gopro_obstacle_voice/annotated_realtime_clock_distance_480p.mp4
runs/realtime_gopro_obstacle_voice/preview.jpg
runs/realtime_gopro_obstacle_voice/events_clock_distance.jsonl
runs/realtime_gopro_obstacle_voice/metrics_clock_distance.json
```

## 目前限制

- GPU 環境已可用，目前 480p 即時設定約 8 到 9 FPS；若要更快，下一步可測 YOLO export ONNX / TensorRT。
- 系統只能做 obstacle awareness，不能宣稱為正式安全避障輔具。
- 單眼 GoPro 無法保證真實距離，目前已加入 bounding box 幾何估距與校正倍率，但仍需要實測校正或深度模型。
- YOLO COCO 預訓練模型不包含所有路上障礙，例如路緣、坑洞、玻璃門、細柱子。
- 語音提示已加入 cooldown 與 temporal smoothing，避免每一幀重複講話。

## 下一步

1. 將 `analysis-fps`、`imgsz`、`cooldown` 調成適合走路速度的參數。
2. 實測 `distance_scale`，把「約幾公尺」校正到可展示的誤差範圍。
3. 加入更輕量模型或 ONNX/TensorRT，提高即時性。
4. 加入 beep pattern 或骨傳導耳機輸出設計。
5. 加入麥克風事件，做視覺 + 聲音的多模態風險提示。
