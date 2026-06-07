# Model Accuracy Strategy

日期：2026-06-06

## 問題

60 秒 walk test 中，模型曾在室內輸出：

```text
10點鐘方向，約1.9公尺，有盆栽
2點鐘方向，約2.7公尺，有交通號誌
2點鐘方向，約1.5公尺，有車
```

實際房間內沒有盆栽、交通號誌或車。這不是距離校正問題，而是 COCO 預訓練 YOLO 的類別辨識問題：模型只能從它知道的類別中挑一個最像的名稱。

## 目前先做的修正

新增：

```text
edge_framework/speech_policy.py
```

策略：

- 室內不合理類別，例如 `traffic light`、`car`、`bus`、`truck`，語音統一講「障礙物」。
- 低信心的 `potted plant` 等容易誤判類別，也統一講「障礙物」。
- 原始類別仍保留在 event log，方便分析模型錯在哪裡。

更新後，原本 walk test 的語音會變成：

```text
10點鐘方向，約1.9公尺，有障礙物
注意，12點鐘方向，約1.1公尺，有椅子
注意，11點鐘方向，約1.1公尺，有椅子
注意，11點鐘方向，約1.1公尺，有長椅
2點鐘方向，約2.7公尺，有障礙物
1點鐘方向，約2.7公尺，有椅子
注意，12點鐘方向，約1.5公尺，有椅子
2點鐘方向，約1.5公尺，有障礙物
```

## 是否需要訓練自己的模型

短期不需要先訓練。先用語音政策、信心門檻、類別白名單就能改善使用體驗。

中期需要少量自己的資料。原因是：

- GoPro 魚眼視角和一般資料集差很多。
- 你的使用場景是第一人稱、低角度、走路晃動。
- 避障真正需要的是「會不會擋路」，不一定是精準辨識物件名稱。

建議目標不是先訓練很多類別，而是訓練：

```text
person
chair
bench
bed/couch
bag/suitcase
generic_obstacle
```

## 公開資料集的用途

公開資料集適合當輔助或論文背景，不建議直接取代自己的 GoPro 資料。

| Dataset | 適合用途 |
| --- | --- |
| Open Images | 大量 2D object detection 預訓練或補充資料 |
| Objects365 | 更多日常物件類別，補強 COCO 類別不足 |
| SUN RGB-D | 室內 RGB-D、2D/3D annotations，適合深度/室內理解 |
| NYU Depth V2 | 室內 RGB + depth，適合單眼深度估計比較 |

## 建議下一步

1. 先用現在的語音政策再跑一次 walk test，確認不再出現「交通號誌 / 車」這類荒謬語音。
2. 錄 5 到 10 分鐘 GoPro 室內走路影片。
3. 從影片抽 300 到 500 張 frame。
4. 只標「會擋路的物體」，不要貪多類別。
5. 用 YOLO 微調，和現在的 COCO baseline 比較誤報率、漏報率、語音提示次數。

這樣期末報告可以形成清楚實驗線：

```text
COCO baseline
  -> speech policy filtering
  -> calibrated distance
  -> small GoPro custom fine-tune
```
