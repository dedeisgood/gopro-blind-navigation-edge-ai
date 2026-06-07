# Walk Test Results

Date: 2026-06-06

## Setup

| Item | Value |
| --- | --- |
| Camera | GoPro 9 over USB/RNDIS UDP stream |
| Runtime | `edge_gpu` |
| Device | RTX 5060 Laptop GPU |
| Resolution | 480p |
| Requested analysis FPS | 12 |
| Distance scale | 1.4212 |
| Speech | Enabled |

## Metrics

| Metric | Value |
| --- | ---: |
| Test duration | 60 s |
| Frames processed | 672 |
| Effective FPS | 10.979 |
| Events | 225 |
| Spoken cues | 13 |
| Avg inference latency | 21.876 ms |
| P95 inference latency | 33.557 ms |

## Event Distribution

| Risk | Count |
| --- | ---: |
| High | 125 |
| Medium | 46 |
| Low | 54 |

| Clock direction | Count |
| --- | ---: |
| 10 o'clock | 6 |
| 11 o'clock | 84 |
| 12 o'clock | 89 |
| 1 o'clock | 32 |
| 2 o'clock | 14 |

| Distance band | Count |
| --- | ---: |
| Near | 75 |
| Mid distance | 69 |
| Far | 81 |

## Representative Spoken Cues

```text
10點鐘方向，約1.9公尺，有盆栽
注意，12點鐘方向，約1.1公尺，有椅子
注意，11點鐘方向，約1.1公尺，有椅子
注意，11點鐘方向，約1.1公尺，有長椅
2點鐘方向，約2.7公尺，有交通號誌
注意，1點鐘方向，約1.3公尺，有椅子
```

## Artifacts

```text
runs/realtime_gopro_obstacle_voice/walk_test_480p_calibrated.mp4
runs/realtime_gopro_obstacle_voice/walk_test_events.jsonl
runs/realtime_gopro_obstacle_voice/walk_test_metrics.json
runs/realtime_gopro_obstacle_voice/walk_test_frames/walk_test_t05_chair_12oclock.jpg
runs/realtime_gopro_obstacle_voice/walk_test_frames/walk_test_t20_chair_12oclock.jpg
runs/realtime_gopro_obstacle_voice/walk_test_frames/walk_test_end_chair_1oclock.jpg
```

## Observations

- The calibrated distance scale is active in the live voice pipeline.
- Real-time speed is usable for a controlled indoor prototype: about 11 FPS with around 22 ms average inference latency.
- The clock-direction cue is useful, especially around 11, 12, and 1 o'clock.
- COCO class labels can be noisy indoors. Some objects may be reported as traffic light or car. The next improvement should restrict voice cues to safer indoor obstacle classes and optionally say "障礙物" when class confidence is uncertain.
- The system is still an obstacle-awareness prototype, not a safety-certified mobility aid.
