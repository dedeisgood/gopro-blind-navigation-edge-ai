# ArUco 距離校正流程

日期：2026-06-06

## 目的

目前避障系統已經可以輸出「幾點鐘方向」與「約幾公尺」，但一般物件的 bbox 距離估計只是粗估。ArUco marker 可以提供一個已知尺寸的黑白標記，讓 GoPro 用幾何方式估出距離，作為 1m / 2m / 3m 校正基準。

## Marker 圖片

已產生：

```text
assets/aruco_4x4_id0_phone.png
```

顯示方式：

1. 把圖片放到手機螢幕，盡量全螢幕顯示。
2. 手機亮度調高。
3. 量「黑色 marker 方形外框」的實際邊長，不是整支手機寬度。
4. 手機與 GoPro 盡量垂直正對，marker 放在畫面中央。

本次手機上黑色 marker 邊長是 15 cm，參數就是：

```powershell
-MarkerSizeM 0.15
```

## 1 公尺校正命令

```powershell
.\scripts\run_aruco_distance_calibration.ps1 -MarkerSizeM 0.15 -KnownDistanceM 1.0 -Seconds 10 -Label 1m
```

輸出：

```text
runs/aruco_distance_calibration/aruco_measurements_1m.jsonl
runs/aruco_distance_calibration/aruco_metrics_1m.json
runs/aruco_distance_calibration/aruco_annotated_1m.mp4
runs/aruco_distance_calibration/aruco_preview_1m.jpg
```

## 建議量測組合

| 實際距離 | 建議用途 |
| ---: | --- |
| 1.0 m | 近距離高風險提示 |
| 2.0 m | 走路時主要反應距離 |
| 3.0 m | 提前預警距離 |

每個距離都做 10 秒，取 median distance 與 error。若 marker 在手機上太小、偵測不穩，可以改用筆電螢幕、平板或列印更大的 marker。

## 注意

ArUco 校正是為了取得校準基準，不代表真實環境裡每個障礙物都會有 marker。正式避障仍需要 YOLO / depth model / stereo 或其他感測器一起工作。

## 2026-06-06 1m / 2m / 3m 校正結果

注意：第一批影像原本誤標為 1m，後來確認實際擺放距離是 2m，因此已更正為 2m。後續已補拍真正的 1m 與 3m。

設定：

| 項目 | 值 |
| --- | ---: |
| Marker 邊長 | 0.15 m |
| 解析度 | 720p |
| 分析 FPS | 8 |

結果：

| 實際距離 | 偵測幀數 | 原始 median | 原始誤差 | 單點 scale | 三點 scale 後 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 m | 47 | 0.656 m | -0.344 m | 1.5244 | 0.932 m |
| 2.0 m | 53 | 1.311 m | -0.689 m | 1.5256 | 1.863 m |
| 3.0 m | 27 | 2.183 m | -0.817 m | 1.3743 | 3.102 m |

三點 least-squares 整體倍率：

```text
distance_scale = 1.4212
```

本次已將即時 demo 的 `--distance-scale` 改為 `1.4212`。這個倍率讓 1m、2m、3m 的總誤差較平均；若專案重點偏向安全，可以在語音提示中保守地把距離分級成「近 / 中 / 遠」，不要過度相信單一公尺數。

校正前平均絕對誤差約 `0.617 m`，校正後約 `0.102 m`，誤差改善約 `83.41%`。

輸出：

```text
runs/aruco_distance_calibration/aruco_measurements_1m.jsonl
runs/aruco_distance_calibration/aruco_metrics_1m.json
runs/aruco_distance_calibration/aruco_annotated_1m.mp4
runs/aruco_distance_calibration/aruco_preview_1m.jpg
runs/aruco_distance_calibration/aruco_measurements_2m.jsonl
runs/aruco_distance_calibration/aruco_metrics_2m.json
runs/aruco_distance_calibration/aruco_annotated_2m.mp4
runs/aruco_distance_calibration/aruco_preview_2m.jpg
runs/aruco_distance_calibration/aruco_measurements_3m.jsonl
runs/aruco_distance_calibration/aruco_metrics_3m.json
runs/aruco_distance_calibration/aruco_annotated_3m.mp4
runs/aruco_distance_calibration/aruco_preview_3m.jpg
runs/aruco_distance_calibration/aruco_calibration_summary.json
runs/aruco_distance_calibration/aruco_calibration_summary.csv
runs/aruco_distance_calibration/aruco_calibration_curve.png
```

## 校正後管線驗證

離線 GoPro 樣本：

| 指標 | 值 |
| --- | ---: |
| Processed frames | 230 |
| Device | GPU `0` |
| FPS | 26.241 |
| Avg latency | 23.649 ms |
| Near events | 228 |
| Mid-distance events | 268 |

即時 GoPro 480p smoke test：

| 指標 | 值 |
| --- | ---: |
| Frames | 18 |
| Effective FPS | 2.869 |
| Avg latency | 20.683 ms |
| Spoken cue | `注意，12點鐘方向，約1.1公尺，有椅子` |
| Distance scale | 1.4212 |

這代表校正值已經進入實際避障語音管線。
