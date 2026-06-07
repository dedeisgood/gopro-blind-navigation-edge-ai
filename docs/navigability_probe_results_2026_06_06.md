# Navigability Probe Results

Date: 2026-06-06

## Question

The current YOLO obstacle system detects object boxes, but it does not understand walls or non-walkable space. A wall can occupy the whole view while producing no YOLO detection.

## Baseline Test

Command output:

| Metric | Value |
| --- | ---: |
| Frames | 495 |
| Effective FPS | 10.711 |
| Events | 234 |
| Spoken cues | 10 |
| Avg YOLO latency | 22.426 ms |
| P95 YOLO latency | 26.267 ms |

YOLO-only spoken examples:

```text
12點鐘方向，約30.4公尺，有人
注意，11點鐘方向，約1.3公尺，有人
10點鐘方向，約2.0公尺，有障礙物
```

Observation: YOLO still reports only detected objects. It does not produce a wall / blocked-path decision.

## Depth Probe

Added:

```text
scripts/depth_anything_navigability_probe.py
```

Model:

```text
depth-anything/Depth-Anything-V2-Small-hf
```

The script samples video frames, estimates a relative depth map, divides the lower-middle visual field into 10, 11, 12, 1, and 2 o'clock sectors, and estimates a risk score for each sector.

Probe results from the baseline video:

| Frame time | 12 o'clock risk | Recommendation |
| ---: | ---: | --- |
| 5 s | 0.1712 | front passable |
| 15 s | 0.0695 | front passable |
| 25 s | 0.1081 | front passable |
| 35 s | 0.0889 | front passable |

Artifacts:

```text
runs/depth_navigability_probe/wall_baseline/depth_navigability_summary.json
runs/depth_navigability_probe/wall_baseline/depth_nav_t05_overlay.jpg
runs/depth_navigability_probe/wall_baseline/depth_nav_t15_overlay.jpg
runs/depth_navigability_probe/wall_baseline/depth_nav_t25_overlay.jpg
runs/depth_navigability_probe/wall_baseline/depth_nav_t35_overlay.jpg
```

## Wall-Facing Test

Recorded with the GoPro pointed at a nearby wall:

```text
runs/realtime_gopro_obstacle_voice/wall_facing_test_480p.mp4
```

YOLO result:

| Metric | Value |
| --- | ---: |
| Frames | 138 |
| Effective FPS | 8.498 |
| YOLO events | 0 |
| Spoken cues | 0 |

Observation: the detector produced no obstacle events while the camera was facing a wall. This confirms that object detection alone is not enough for blind navigation.

## Tuned Depth Rule

The first depth rule only checked the 12 o'clock sector, so it was too conservative. The tuned rule computes front risk from 11, 12, and 1 o'clock:

```text
front_score = 0.25 * risk_11 + 0.50 * risk_12 + 0.25 * risk_1
front_blocked = front_score >= 0.34
```

If front is blocked, the system compares the 10/11 o'clock average with the 1/2 o'clock average and recommends the clearer side.

Wall-facing results after tuning:

| Frame time | Front score | Recommendation | Speech |
| ---: | ---: | --- | --- |
| 2 s | 0.4454 | turn_left | 前方可能不可通行，左前方較空 |
| 5 s | 0.3659 | turn_left | 前方可能不可通行，左前方較空 |
| 8 s | 0.4689 | turn_left | 前方可能不可通行，左前方較空 |
| 11 s | 0.4210 | turn_left | 前方可能不可通行，左前方較空 |

Baseline walking-room results after tuning:

| Frame time | Front score | Recommendation |
| ---: | ---: | --- |
| 5 s | 0.2057 | front_passable |
| 15 s | 0.0701 | front_passable |
| 25 s | 0.1082 | front_passable |
| 35 s | 0.0885 | front_passable |

Artifacts:

```text
runs/depth_navigability_probe/wall_facing_test_tuned/depth_navigability_summary.json
runs/depth_navigability_probe/wall_facing_test_tuned/depth_nav_t05_overlay.jpg
runs/depth_navigability_probe/wall_baseline_tuned/depth_navigability_summary.json
runs/depth_navigability_probe/wall_baseline_tuned/depth_nav_t05_overlay.jpg
```

## Decision

YOLO remains useful for named obstacles such as person, chair, table, and luggage. Depth-based navigability should handle wall-like surfaces and non-walkable space. The next engineering step is to fuse this tuned depth decision into the real-time GoPro voice loop so the live cue can speak both named object risks and path-blocking risks.

## Real-Time Integration

Added a shared navigability module:

```text
edge_framework/navigability.py
```

The real-time GoPro script now supports optional depth navigation:

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
  --lang zh-TW `
  --save-video .\runs\realtime_gopro_obstacle_voice\depth_nav_live_test.mp4 `
  --events .\runs\realtime_gopro_obstacle_voice\depth_nav_live_test_events.jsonl `
  --metrics .\runs\realtime_gopro_obstacle_voice\depth_nav_live_test_metrics.json
```

The script records YOLO object events and depth navigability events separately:

```text
event_count      = YOLO object events
nav_event_count  = depth path-blocking events
spoken_count     = all spoken cues
nav_spoken_count = depth spoken cues
```
