# 視障輔助避障邊緣感知系統大綱

## 一、暫定題目

**基於 GoPro 第一人稱影像之視障者輔助避障邊緣感知系統原型**

英文題目：

**Edge-Based Assistive Obstacle Awareness System for Visually Impaired Users Using GoPro First-Person Vision**

## 二、專案定位

本專案不是要取代白手杖、導盲犬或正式醫療/安全輔具，而是建立一個視障者行走輔助的邊緣 AI 原型系統。

系統使用 GoPro 作為可穿戴第一人稱影像感測器，筆電暫時作為高性能 edge development board。未來實際部署時，可將筆電替換為 Jetson、Raspberry Pi、NPU board 或其他嵌入式開發板，並可加入麥克風、IMU、超音波或深度感測器。

## 三、核心問題

視障者在移動時，除了需要知道前方是否有障礙物，也需要知道障礙物大概位於哪個方向，以及是否可能造成即時風險。

本專案要回答：

1. GoPro 第一人稱影像是否能作為移動式邊緣感測來源？
2. YOLO 等即時物件偵測模型是否能在 edge node 上提供足夠低延遲的障礙物感知？
3. 系統能否將偵測結果轉換為簡單、可理解的方向提示？
4. 筆電原型未來是否能遷移到嵌入式 edge board？

## 四、系統架構

```text
GoPro9 第一人稱影像
        |
        v
Edge Node Prototype
筆電 / 未來開發板
        |
        v
YOLO 物件偵測
person / car / bicycle / motorcycle / bus / chair / obstacle
        |
        v
區域與風險分析
left / center / right
low / medium / high risk
        |
        v
提示輸出
audio cue / beep / text-to-speech / event log / dashboard
```

## 五、GoPro 在本題目的價值

GoPro 不只是 webcam 替代品，而是此專案的移動式視覺感測器。

| GoPro 特性 | 專案價值 |
| --- | --- |
| 可穿戴 | 可模擬視障者第一人稱移動視角 |
| 廣角 | 可捕捉較大範圍的前方環境 |
| 適合移動場景 | 可測試走路、轉頭、晃動等高動態影像 |
| 可戶外使用 | 更接近真實行走場景 |
| 可錄影或 webcam stream | 可先離線測試，再做即時 demo |

## 六、MVP 功能

第一階段先做最小可行版本，不做模型微調。

功能：

1. 輸入 GoPro 錄製影片或測試影片。
2. 使用 YOLOv8n 預訓練模型偵測常見障礙物。
3. 將畫面切成左、中、右三區。
4. 根據偵測框位置與大小估計風險。
5. 輸出事件：
   - left obstacle
   - center obstacle
   - right obstacle
   - high risk object ahead
6. 輸出標註影片、event log、FPS 與 latency。

## 七、風險判斷邏輯

先用簡單規則，不做深度估計。

```text
if object_center_x in left region:
    direction = left
elif object_center_x in center region:
    direction = center
else:
    direction = right

if bbox_area_ratio > threshold_high:
    risk = high
elif bbox_area_ratio > threshold_medium:
    risk = medium
else:
    risk = low
```

注意：單眼 GoPro 無法可靠估計真實距離，因此此版本只做 obstacle awareness，不宣稱精準避障。

## 八、後續可加入的多模態感測

未來可加入麥克風與其他感測器。

| 感測器 | 可偵測內容 |
| --- | --- |
| 麥克風 | 喇叭聲、煞車聲、撞擊聲、人聲求助 |
| IMU | 使用者行走狀態、轉向、晃動程度 |
| 超音波 | 近距離障礙物 |
| 深度相機 | 距離估計 |
| GPS | 戶外位置與路線 |

融合規則範例：

```text
if center_object_detected and loud_vehicle_sound:
    event = high_risk_front_vehicle
```

## 九、實驗設計

### 實驗一：即時性

量測：

- FPS
- average latency
- p95 latency
- event delay

### 實驗二：方向提示正確性

將畫面分成左、中、右，檢查系統是否能正確判斷障礙物方向。

量測：

- direction classification accuracy
- left / center / right event count

### 實驗三：移動場景穩定性

比較靜態影片與 GoPro 行走影片。

量測：

- frame drop
- latency jitter
- detection count stability
- 高晃動情境下的誤報/漏報

### 實驗四：邊緣部署可行性

在筆電 edge prototype 上測試 CPU/GPU 模式，並討論未來遷移至開發板的資源需求。

量測：

- CPU usage
- GPU usage
- memory usage
- model size
- estimated embedded deployment feasibility

## 十、預期成果

1. GoPro 第一人稱影像避障輔助 demo。
2. YOLO 偵測與方向/風險分析模組。
3. annotated video。
4. event log。
5. FPS、latency 與穩定性分析。
6. 可遷移到開發板的系統架構設計。
7. 期末報告與簡報。

## 十一、環境規劃

目前先不動環境，只做大綱。

後續若要正式建環境，建議：

1. 優先使用 WSL2。
2. WSL 發行版放在 D 槽，例如 `D:\wsl\edge-obstacle`.
3. 在 WSL 中建立 Python/conda 或 venv 環境。
4. GPU 支援確認後，再安裝 PyTorch CUDA 版本。
5. 若 WSL2 的 GPU 或 USB/video capture 不穩，再考慮完整虛擬機。

環境選擇建議：

| 方案 | 優點 | 缺點 | 建議 |
| --- | --- | --- | --- |
| WSL2 on D 槽 | 輕量、適合 Python/AI 開發、較好管理 | 攝影機/USB 串流可能要額外處理 | 優先 |
| 一般 VM on D 槽 | 隔離完整、環境乾淨 | GPU passthrough 與攝影機支援較麻煩 | 備案 |
| Windows conda | 已可跑 CPU YOLO、最快 | CUDA/套件相容性較容易混亂 | MVP 可用 |

## 十二、專案邊界

本系統只作為研究與原型展示，不作為正式安全輔具。

限制：

- 單眼相機距離估計有限。
- 無法保證所有障礙物都能偵測。
- 不能取代白手杖或導盲犬。
- 實際部署前需要使用者研究、安全測試與硬體冗餘設計。

