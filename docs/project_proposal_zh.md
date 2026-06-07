# 期末專案企劃書

## 題目

**可配置式邊緣影像分析框架：面向多場景快速遷移之設計與實作**

英文題目：

**A Configurable Edge Video Analytics Framework for Rapid Task Adaptation Across Domains**

## 一、研究動機

傳統影像分析專案通常針對單一應用場景設計，例如人流統計、安全帽偵測或車流監控。當應用場景改變時，系統往往需要重新修改輸入流程、模型載入方式、類別定義、後處理邏輯與事件輸出格式，造成部署成本過高。

本專案希望設計一套可配置式的邊緣影像分析框架，讓筆電作為邊緣運算節點，GoPro9 作為影像來源。系統的目標不是只完成單一辨識任務，而是建立一套可快速遷移的 pipeline。當使用者從專案 A 切換到專案 B 時，只需要替換資料集、模型權重、類別設定與規則設定，即可快速部署新的邊緣影像應用。

## 二、設備與環境

目前可用設備如下：

| 設備 | 規格或用途 |
| --- | --- |
| 筆電 | ASUS TUF Gaming A16 |
| CPU | AMD Ryzen 9 8940HX, 16 cores / 32 threads |
| RAM | 約 32 GB |
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU, 8 GB VRAM |
| Camera | GoPro9 |
| OS | Windows 11 |

此設備足以作為單機邊緣節點，進行即時影像串流、AI 推論、事件規則處理與效能量測。

## 三、研究目標

本專案目標如下：

1. 建立一套可配置式邊緣影像分析 pipeline。
2. 支援不同資料來源，例如 GoPro、webcam、影片檔與模擬串流。
3. 支援可替換模型後端，例如 PyTorch YOLO、ONNX Runtime 與 TensorRT。
4. 支援以設定檔切換任務類別、模型權重、解析度、FPS 與事件規則。
5. 以至少兩個應用案例驗證系統可遷移性。
6. 量測邊緣端效能，例如 FPS、latency、資源使用率與事件輸出量。

## 四、系統架構

```text
GoPro9 / Webcam / Video File
        |
        v
影像輸入模組
        |
        v
前處理模組
  - 解析度調整
  - FPS 控制
  - frame skipping
        |
        v
模型推論模組
  - PyTorch
  - ONNX Runtime
  - TensorRT
        |
        v
規則引擎模組
  - 人數超過門檻
  - 偵測到未戴安全帽
  - 特定事件持續超過 N 秒
        |
        v
邊緣端輸出
  - event log
  - dashboard
  - alert
  - metadata
```

## 五、核心設計

### 1. Config-driven pipeline

系統不將任務寫死在程式中，而是透過設定檔指定任務。

範例：

```json
{
  "task_name": "safety_helmet",
  "source": {
    "type": "gopro",
    "device_index": 0
  },
  "model": {
    "backend": "onnx",
    "weights": "models/helmet_yolo.onnx",
    "classes": ["person", "helmet", "no_helmet"]
  },
  "inference": {
    "resolution": [640, 360],
    "fps_limit": 15,
    "precision": "fp16"
  },
  "rules": [
    {
      "name": "no_helmet_alert",
      "type": "class_count",
      "class_name": "no_helmet",
      "operator": ">=",
      "threshold": 1
    }
  ]
}
```

### 2. 可替換式 detector backend

模型推論模組設計成統一介面：

```text
detect(frame) -> List[Detection]
```

因此主 pipeline 不需要知道底層是 PyTorch、ONNX 或 TensorRT。未來若要支援新的模型，只需新增 detector backend。

### 3. 規則引擎

模型只負責產生偵測結果，應用邏輯由規則引擎決定。這使同一個偵測模型可以被用於不同場景。例如 person detector 可用於人流統計、禁區入侵或密度警示。

### 4. 邊緣端效能調整

系統可比較不同部署策略：

| 策略 | 目的 |
| --- | --- |
| 降低解析度 | 提升 FPS，降低延遲 |
| frame skipping | 降低推論負載 |
| FP16 | 使用 GPU 加速 |
| ONNX | 提高部署可攜性 |
| TensorRT | 追求最低延遲 |
| CPU/GPU 切換 | 模擬不同邊緣裝置能力 |

## 六、應用案例

### Case A：人流統計

使用 person detection 模型偵測畫面中的人數，當人數超過門檻時產生事件。

可展示：

- 即時偵測人數
- event log
- FPS 與 latency
- 只改 config 即可調整人數門檻

### Case B：安全帽偵測

使用安全帽資料集訓練或 fine-tune YOLO 模型，偵測 person、helmet、no_helmet。當出現 no_helmet 時產生警示事件。

可展示：

- 更換 dataset 與 model weights
- class map 改變
- rule 改為 no_helmet alert
- 主 pipeline 不需要重寫

## 七、實驗設計

### 實驗一：任務遷移成本

比較從 Case A 遷移到 Case B 所需變更：

| 指標 | 說明 |
| --- | --- |
| 修改程式行數 | 越少代表框架可遷移性越高 |
| 修改設定項目數 | 量化任務切換成本 |
| 重新部署時間 | 從新 config 到可運行所需時間 |
| 模組重用率 | source、pipeline、rule engine 是否可重用 |

### 實驗二：邊緣推論效能

比較不同模式：

| 模式 | 比較項目 |
| --- | --- |
| PyTorch GPU | 開發便利性 |
| ONNX CPU | 跨平台部署 |
| ONNX GPU | 平衡速度與部署性 |
| TensorRT FP16 | 低延遲最佳化 |

量測指標：

- average latency
- p95 latency
- FPS
- dropped frames
- GPU memory usage
- CPU usage

### 實驗三：事件輸出與頻寬節省

比較原始影片輸出與 metadata/event-only 輸出大小。此實驗可凸顯邊緣運算的價值：不需要將全部影片上傳至雲端。

## 八、預期成果

1. 一套可配置式 edge video analytics framework。
2. 至少兩個可展示應用案例。
3. 可切換 config 的 demo。
4. FPS、latency、資源使用率實驗結果。
5. 期末報告與簡報材料。

## 九、可參考的開源方向

- yolo-tonic: webcam/YOLO/ONNX/TensorRT 即時偵測架構。
- EVA: edge video analytics 中處理影片流與模型速度不匹配的研究方向。
- Intel Edge Video Analytics Microservice: containerized edge video pipeline。
- LF Edge eKuiper: edge rule engine 的概念，可借鏡其規則式事件處理方式。

## 十、時程規劃

| 週次 | 工作 |
| --- | --- |
| 第 1 週 | 完成 pipeline skeleton、config、dummy detector |
| 第 2 週 | 接入 GoPro/webcam 與 YOLO 模型 |
| 第 3 週 | 完成 Case A 與 Case B，加入 event log |
| 第 4 週 | 做 ONNX/TensorRT 或 CPU/GPU 效能比較 |
| 第 5 週 | 製作 dashboard、整理實驗資料 |
| 第 6 週 | 完成報告與簡報 |

