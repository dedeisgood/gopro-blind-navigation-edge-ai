# Semantic + Depth Fusion for Wall/Floor Navigability

Date: 2026-06-06

## Goal

The previous YOLO-only pipeline could detect named objects, but it could not understand walls or non-walkable areas. The depth-only rule could estimate whether a region was close, but it still could not explicitly distinguish wall, floor, door, or ceiling.

This upgrade adds a semantic segmentation branch:

```text
GoPro frame
-> YOLO object detection
-> Depth Anything V2 relative depth
-> SegFormer ADE20K semantic segmentation
-> wall/floor/depth fusion
-> clock-direction voice cue
```

## Added Files

```text
edge_framework/semantic_navigability.py
scripts/semantic_navigability_probe.py
```

The real-time script also supports semantic fusion:

```text
scripts/realtime_gopro_obstacle_voice.py
```

## Models

```text
Semantic segmentation: nvidia/segformer-b0-finetuned-ade-512-512
Depth estimation: depth-anything/Depth-Anything-V2-Small-hf
```

ADE20K labels used in this prototype:

| Label | ID |
| --- | ---: |
| wall | 0 |
| floor | 3 |
| ceiling | 5 |
| door | 14 |
| screen door | 58 |

## Fusion Rule

Each frame is divided into 10, 11, 12, 1, and 2 o'clock sectors.

For each sector, the semantic branch computes:

```text
wall_ratio
floor_ratio
door_ratio
ceiling_ratio
semantic_risk_score
```

The front semantic score is weighted across 11, 12, and 1 o'clock:

```text
semantic_front_score = 0.25 * risk_11 + 0.50 * risk_12 + 0.25 * risk_1
```

The fused front score is:

```text
fused_front_score = max(semantic_front_score, depth_front_score)
```

The system marks the front as blocked when the semantic branch sees a wall-like/no-floor front area, or when the depth branch sees a close front area.

## Visibility Safety Gate

Low-visibility frames must not be treated as passable, even if the segmentation model predicts floor. In an assistive navigation setting, insufficient visual evidence is a safety risk.

The prototype now computes:

```text
mean_luma
dark_ratio
very_dark_ratio
```

If the frame is too dark:

```text
mean_luma < 45
or dark_ratio > 0.65
```

the system overrides the fused decision:

```text
recommendation = stop
reason = low_visibility
speech = 光線不足，請先停止
```

## Probe Commands

Wall-facing test:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\semantic_navigability_probe.py `
  --video .\runs\realtime_gopro_obstacle_voice\wall_facing_test_480p.mp4 `
  --seconds 2 5 8 11 `
  --out-dir .\runs\semantic_navigability_probe\wall_facing_test
```

Baseline walking-room test:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\semantic_navigability_probe.py `
  --video .\runs\realtime_gopro_obstacle_voice\wall_baseline_yolo_only.mp4 `
  --seconds 5 15 25 35 `
  --out-dir .\runs\semantic_navigability_probe\wall_baseline
```

## Results

Wall-facing video:

| Time | Front wall ratio | Front floor ratio | Fused front score | Recommendation | Reason |
| ---: | ---: | ---: | ---: | --- | --- |
| 2 s | 0.9631 | 0.0000 | 0.9687 | turn_left | semantic_wall_or_no_floor |
| 5 s | 0.9750 | 0.0000 | 0.9790 | turn_left | semantic_wall_or_no_floor |
| 8 s | 0.9606 | 0.0000 | 0.9665 | turn_left | semantic_wall_or_no_floor |
| 11 s | 0.9663 | 0.0000 | 0.9714 | turn_left | semantic_wall_or_no_floor |

Baseline walking-room video:

| Time | Front wall ratio | Front floor ratio | Fused front score | Recommendation | Reason |
| ---: | ---: | ---: | ---: | --- | --- |
| 5 s | 0.1738 | 0.6077 | 0.2057 | front_passable | passable |
| 15 s | 0.2533 | 0.4002 | 0.2458 | front_passable | passable |
| 25 s | 0.1481 | 0.3087 | 0.2135 | front_passable | passable |
| 35 s | 0.2138 | 0.3276 | 0.2545 | front_passable | passable |

After model warmup, observed GPU inference time was roughly:

| Branch | Typical latency |
| --- | ---: |
| SegFormer semantic segmentation | 22-26 ms |
| Depth Anything V2 | 26-30 ms |

The first frame is slower because model kernels are still warming up.

## No-Light Test Result

The no-light walking clip should be treated as a negative / unsafe sample. After adding the visibility safety gate, all sampled frames are stopped:

| Time | Mean luma | Dark ratio | Recommendation | Reason |
| ---: | ---: | ---: | --- | --- |
| 1.5 s | 14.9 | 0.99 | stop | low_visibility |
| 4.34 s | 16.9 | 0.97 | stop | low_visibility |
| 7.17 s | 17.9 | 0.95 | stop | low_visibility |
| 10.01 s | 22.4 | 0.90 | stop | low_visibility |

Updated batch analysis:

```text
runs/gopro_dataset_analysis_v2_visibility_gate/batch_summary.json
runs/gopro_dataset_analysis_v2_visibility_gate/batch_report.md
runs/gopro_dataset_analysis_v2_visibility_gate/contact_sheet.jpg
```

## Artifacts

```text
runs/semantic_navigability_probe/wall_facing_test/semantic_navigability_summary.json
runs/semantic_navigability_probe/wall_facing_test/semantic_nav_t05_fusion_overlay.jpg
runs/semantic_navigability_probe/wall_baseline/semantic_navigability_summary.json
runs/semantic_navigability_probe/wall_baseline/semantic_nav_t05_fusion_overlay.jpg
```

## Live Test Command

Use this when the GoPro is connected and streaming over USB:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\realtime_gopro_obstacle_voice.py `
  --gopro-ip 172.26.181.51 `
  --seconds 15 `
  --res 480 `
  --analysis-fps 12 `
  --device auto `
  --hfov 118 `
  --distance-scale 1.4212 `
  --enable-depth-nav `
  --depth-every 1 `
  --enable-semantic-nav `
  --seg-every 1 `
  --lang zh-TW `
  --save-video .\runs\realtime_gopro_obstacle_voice\semantic_depth_live_test.mp4 `
  --events .\runs\realtime_gopro_obstacle_voice\semantic_depth_live_test_events.jsonl `
  --metrics .\runs\realtime_gopro_obstacle_voice\semantic_depth_live_test_metrics.json
```

## Current Limitation

This is still a rule-based fusion prototype. It can now explicitly use wall/floor/door evidence, but it is not yet a fully validated assistive navigation system. More real GoPro tests are still needed for doorways, corridors, glass, low light, reflective surfaces, and turning scenes.
