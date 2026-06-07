# 一頁式題目提案

## 題目

**可配置式邊緣影像分析框架：面向多場景快速遷移之設計與實作**

## 核心想法

本專案不是開發單一影像辨識應用，而是建立一套可重用、可配置、可快速遷移的邊緣影像分析框架。筆電作為邊緣運算節點，GoPro9 作為影像來源。當應用場景從專案 A 轉換到專案 B 時，系統不需要重寫主程式，只需要更換資料集、模型權重、類別設定與事件規則。

## 為什麼符合邊緣計算

- 影像在本機 edge node 即時處理，不依賴雲端推論。
- 系統可量測 FPS、latency、CPU/GPU 使用率與事件輸出量。
- 可透過 event-only output 降低原始影片上傳頻寬。
- 可比較 CPU/GPU、PyTorch/ONNX/TensorRT 等不同 edge deployment 策略。

## 系統架構

```text
GoPro9 / Webcam / Video File
        |
        v
Video Source Module
        |
        v
Inference Backend
        |
        v
Rule Engine
        |
        v
Event Log / Dashboard / Alert
```

## 預計展示案例

| 案例 | 說明 | 主要更換內容 |
| --- | --- | --- |
| Case A | 人流統計 | class map、rule threshold |
| Case B | 安全帽偵測 | dataset、model weights、class map、alert rule |

## 預計實驗

1. **任務遷移成本**：從人流統計切換到安全帽偵測時，統計需要修改多少程式碼、設定項目與部署時間。
2. **邊緣效能比較**：比較不同模型後端與硬體模式的 FPS、latency、p95 latency。
3. **頻寬節省分析**：比較上傳原始影片與只輸出事件 metadata 的資料量差異。

## 預期貢獻

本專案的貢獻在於提出並實作一套 config-driven edge video analytics framework，讓不同影像任務能以較低成本快速部署到邊緣節點。相較於單一任務 demo，本系統更強調可遷移性、模組化、效能量測與實際部署可行性。

