# GoPro Connection Test

Date: 2026-06-05

## Summary

The GoPro is physically connected and reachable from the laptop. Windows exposes it as a USB network device, and the GoPro HTTP API responds to read-only requests. However, the GoPro Webcam virtual camera currently does not provide a live camera image to OpenCV; it returns either the GoPro Webcam placeholder or black frames.

## Windows Device Status

Detected device:

```text
GoPro RNDIS Device
Interface: 乙太網路 3
Laptop IP: 172.26.181.54/24
GoPro IP: 172.26.181.51
```

The GoPro Webcam utility process is running:

```text
GoPro Webcam
```

## Camera Index Scan

OpenCV found two readable indexes:

| Index | Result |
| --- | --- |
| 0 | Laptop webcam / normal webcam image |
| 2 | GoPro Webcam virtual camera |

Preview outputs:

```text
runs/camera_scan/camera_0.jpg
runs/camera_scan/camera_2.jpg
```

`camera_2.jpg` shows the GoPro Webcam placeholder rather than the live lens image.

## Short Recording Test

Recording from camera index 2 produced files:

```text
runs/gopro_webcam_test/gopro_index2_sample.mp4
runs/gopro_webcam_test/gopro_index2_sample.jpg
runs/gopro_webcam_test/gopro_index2_default.mp4
runs/gopro_webcam_test/gopro_index2_default.jpg
```

The preview frames are black, so the webcam stream is not currently usable for the obstacle-awareness pipeline.

## HTTP API Test

Reachability:

| Test | Result |
| --- | --- |
| Ping 172.26.181.51 | OK |
| TCP 80 | Open |
| TCP 8080 | Open |
| TCP 8081 | Open |

Read-only endpoints:

| Endpoint | Result |
| --- | --- |
| `/gopro/version` | `{"version" : "2.0"}` |
| `/gopro/camera/state` | 200 OK |
| `/gp/gpControl/status` | 200 OK |
| `/gopro/media/list` | `{"media":[]}` |
| `/gp/gpMediaList` | `{"media":[]}` |

Recording command tests:

| Endpoint | Result |
| --- | --- |
| `/gp/gpControl/command/shutter?p=1` | 500 |
| `/gp/gpControl/command/shutter?p=0` | 500 |
| `/gopro/camera/shutter/start` | 404 |
| `/gopro/camera/shutter/stop` | 404 |

No media file was created during the command tests.

## Interpretation

The GoPro is connected at the USB/RNDIS level and can be queried over HTTP. The current blocker is the video feed:

- The GoPro Webcam virtual camera exists.
- OpenCV can open camera index 2.
- The stream is not a real live image yet.

This likely needs a GoPro-side or GoPro Webcam Utility-side change before live capture works.

## Suggested Next Fixes

1. On the GoPro, confirm the USB mode is set to **GoPro Connect**, not MTP.
2. In the GoPro Webcam app, open/enable preview and confirm it shows the real lens image.
3. Close apps that may own the virtual camera, such as Teams, Discord, OBS, browser tabs, or Camera app.
4. Replug the camera and wait until the GoPro Webcam app status indicates a connected camera.
5. If webcam live remains unreliable, record on the GoPro itself and process the saved MP4 through `blind_obstacle_assist_video_template.json`.

## Re-run Commands

Scan cameras:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\scan_cameras.py --max-index 8 --out-dir .\runs\camera_scan
```

Record camera index 2:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\record_camera_sample.py --index 2 --seconds 5 --fps 15 --width 1280 --height 720 --backend default --out .\runs\gopro_webcam_test\gopro_index2_default.mp4
```

## 2026-06-06 Reboot Verification

After reboot, the GoPro USB/RNDIS connection came back correctly.

| Item | Result |
| --- | --- |
| Windows adapter | `GoPro RNDIS Device` |
| Interface alias | `乙太網路 3` |
| Laptop IP | `172.26.181.54` |
| GoPro IP | `172.26.181.51` |
| `/gopro/version` | `{"version" : "2.0"}` |
| CUDA env | `edge_gpu`, `torch 2.11.0+cu128` |
| GPU | `NVIDIA GeForce RTX 5060 Laptop GPU` |

The old GoPro Webcam tray app is no longer required for the project. The working path is:

```text
GoPro USB/RNDIS API
  -> /gp/gpWebcam/START?res=480
  -> UDP 8554
  -> FFmpeg raw frames
  -> YOLO GPU inference
  -> clock direction + rough distance + Chinese voice cue
```

Smoke-test command:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\realtime_gopro_obstacle_voice.py --gopro-ip 172.26.181.51 --seconds 5 --res 480 --analysis-fps 12 --device auto --hfov 118 --distance-scale 1.0 --min-stable-frames 2 --cooldown 1.2 --repeat-cooldown 4 --lang zh-TW --no-speech --save-video .\runs\realtime_gopro_obstacle_voice\reboot_smoke_480p.mp4 --events .\runs\realtime_gopro_obstacle_voice\reboot_smoke_events.jsonl --metrics .\runs\realtime_gopro_obstacle_voice\reboot_smoke_metrics.json
```

Result:

| Metric | Value |
| --- | ---: |
| Frames | 13 |
| Effective FPS | 2.093 |
| Event count | 13 |
| Spoken cue | `注意，12點鐘方向，約0.7公尺，有椅子` |
| Avg inference latency | 27.840 ms |
| P95 inference latency | 31.262 ms |

Short 5-second tests include GoPro UDP startup time, so the effective FPS is lower than a normal 15-second run. The important result is that the full pipeline works immediately after reboot.
