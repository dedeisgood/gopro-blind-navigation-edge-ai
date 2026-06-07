# 時鐘方位與距離估計升級

日期：2026-06-05

## 原本缺少的技術

目前專案已經有：

- GoPro USB 串流
- YOLO 障礙物偵測
- left / ahead / right 區域判斷
- 中文語音提示

但若要更貼近視障者使用習慣，還缺：

| 缺口 | 原因 | 本次狀態 |
| --- | --- | --- |
| 時鐘方位 | 視障者常用 10 點鐘、12 點鐘、2 點鐘描述方向 | 已補上 |
| 距離估計 | 單純 high/medium/low 不夠具體 | 已補上粗估公尺 |
| 距離校正 | GoPro 廣角、安裝位置會影響估距 | 已補上校正工具 |
| Temporal smoothing | 避免模型一閃一閃就重複提示 | 已補上 |
| 真實深度 | 單眼 RGB 無法保證精準距離 | 已補上 stereo helper；單眼深度模型仍是下一步 |

## 已新增功能

### 1. 時鐘方位

新增模組：

```text
edge_framework/spatial.py
```

將 bounding box 中心點轉換成水平角度，再映射到時鐘方向。

範例：

| 畫面位置 | 角度概念 | 語音方位 |
| --- | --- | --- |
| 偏左 | 約 -30 度 | 11 點鐘方向 |
| 中央 | 約 0 度 | 12 點鐘方向 |
| 偏右 | 約 +30 度 | 1 點鐘方向 |
| 更右 | 約 +60 度 | 2 點鐘方向 |

### 2. 粗距離估計

目前使用 pinhole camera approximation：

```text
distance = object_real_height * focal_length_px / bbox_height_px
```

物件高度先用常見預設值，例如：

| 類別 | 預設高度 |
| --- | ---: |
| person | 1.70 m |
| chair | 0.85 m |
| car | 1.50 m |
| bus | 3.00 m |
| bicycle | 1.10 m |

語音可輸出：

```text
注意，12點鐘方向，約1.4公尺，有椅子
```

### 3. Temporal smoothing

即時語音腳本現在預設需要同一類 cue 穩定出現 2 幀才會講話。

參數：

```powershell
--min-stable-frames 2
--cooldown 1.2
--repeat-cooldown 4
```

### 4. GPU 加速

已新增 `edge_gpu` conda 環境與檢查腳本：

```powershell
.\scripts\setup_edge_gpu_env.ps1
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\check_torch_cuda.py
```

目前驗證結果：

```json
{
  "torch_version": "2.11.0+cu128",
  "cuda_available": true,
  "device_name": "NVIDIA GeForce RTX 5060 Laptop GPU"
}
```

離線 GoPro 樣本實測：

| 環境 | FPS | 平均推論延遲 |
| --- | ---: | ---: |
| CPU | 17.864 | 42.818 ms |
| GPU | 24.803 | 24.881 ms |

即時 GoPro 串流實測：

| 設定 | 有效 FPS | 平均推論延遲 |
| --- | ---: | ---: |
| 720p / 8fps request | 5.731 | 30.881 ms |
| 480p / 12fps request | 8.652 | 20.619 ms |

## 目前輸出欄位

Event log 現在包含：

```json
{
  "class_name": "chair",
  "direction": "center",
  "azimuth_deg": 1.2,
  "clock_hour": 12,
  "clock_label_en": "12 o'clock",
  "clock_label_zh": "12點鐘方向",
  "distance_m": 1.4,
  "distance_label_zh": "近距離",
  "distance_source": "bbox_height_pinhole",
  "speech": "注意，12點鐘方向，約1.4公尺，有椅子"
}
```

## 距離校正

因為 GoPro 是廣角鏡頭，且安裝角度會影響 bbox 大小，建議用已知距離做一次校正。

例如：把椅子放在實際 2 公尺處，取得 detection event 後執行：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\calibrate_distance_scale.py --event-json .\runs\realtime_gopro_obstacle_voice\events_clock_distance.jsonl --known-distance-m 2.0
```

得到：

```json
{
  "distance_scale": 1.32
}
```

之後即時腳本可加：

```powershell
--distance-scale 1.32
```

## 下次開機測試流程

GoPro 接 USB、螢幕亮起後，在專案根目錄直接跑：

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\run_realtime_gopro_voice_sample.ps1
```

這個腳本現在會輸出時鐘方向、估計公尺數，並使用：

```powershell
--device auto
--res 480
--analysis-fps 12
--hfov 118
--distance-scale 1.0
--min-stable-frames 2
```

目前 480p 比 720p 更適合即時導航；720p 可以留給展示錄影或截圖品質。

若之後量出校正倍率，只要把 `--distance-scale 1.0` 改成校正後的數字。

## 第二台 GoPro / Stereo 距離骨架

若之後有第二台 GoPro，可以先用兩台 GoPro 看到的同一個物件框做簡化 stereo 估距：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\stereo_distance_from_boxes.py --left-bbox 620 280 900 714 --right-bbox 590 280 870 714 --baseline-m 0.12
```

這不是完整 stereo calibration，但可以作為 pseudo ground truth 的第一版。正式實驗仍需要固定兩台 GoPro 的 baseline、同步影像、校正內外參，再和單眼估距比較誤差。

## 單眼深度估計下一步

目前 `bbox_height_pinhole` 是粗估法，適合先做 MVP。若要更進一步，可接單眼深度估計：

```text
GoPro frame
  -> YOLO bbox
  -> monocular depth map
  -> bbox 中位數 depth
  -> clock direction + estimated meters
```

候選模型：

- Depth Anything V2
- MiDaS
- ZoeDepth
- Metric3D

建議順序：

1. 先保留目前 bbox 幾何估距作為 baseline。
2. 用實測距離做 calibration。
3. 再接單眼深度模型，比較兩種方法的距離誤差。
4. 若有第二台 GoPro，再做 stereo depth 作為 pseudo ground truth。

## 目前限制

- 現在的距離是估計，不是真正 ground truth。
- COCO 類別高度是假設值，不同椅子、人、車會有誤差。
- GoPro 廣角邊緣變形會使左右側距離誤差變大。
- 單眼 RGB 對玻璃、坑洞、細柱等障礙物仍不穩。
