# YOLO CPU Test Results

Date: 2026-06-04

This test intentionally does not use GoPro input. The goal is to verify that the laptop can run the YOLO-based edge inference pipeline with a static image source.

## Environment

Command:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\check_yolo_env.py
```

Result:

| Item | Value |
| --- | --- |
| Python | 3.11.15 |
| PyTorch | 2.12.0+cpu |
| CUDA available in PyTorch | false |
| Ultralytics | 8.4.51 |
| OpenCV | 4.11.0 |

## Static Image Probe

Command:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\yolo_image_probe.py --image .\assets\ultralytics_bus.jpg --device cpu
```

Result:

| Metric | Value |
| --- | ---: |
| Detections | 6 |

Detected classes:

- bus
- person
- stop sign

Outputs:

```text
runs/yolo_image_probe/annotated.jpg
runs/yolo_image_probe/detections.json
```

## Framework Pipeline Test

Command:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\run_pipeline.py --config .\configs\yolo_sample_person_counting.json
```

Result from the one-command script:

| Metric | Value |
| --- | ---: |
| Processed frames | 20 |
| Skipped frames | 0 |
| Event count | 40 |
| Elapsed seconds | 5.655 |
| FPS | 3.537 |
| Average latency | 81.947 ms |
| P95 latency | 79.929 ms |

## One-Command Reproduction

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\run_yolo_cpu_sample.ps1
```

## Notes

- This is a CPU-only MVP test.
- It proves that the framework can run a real YOLO detector backend without GoPro.
- The existing `torch5060` environment detects the RTX 5060 Laptop GPU but uses an older PyTorch build that does not support the GPU's `sm_120` CUDA capability.
- GPU acceleration should be set up later in a separate environment to avoid breaking the working CPU MVP.

