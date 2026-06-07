# Environment Setup

## Current Fast MVP Environment

Use the existing conda environment:

```powershell
C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe
```

Installed and verified packages:

- Python 3.11.15
- PyTorch CPU build
- Ultralytics YOLO
- OpenCV
- ONNX Runtime CPU

Check the environment:

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\check_yolo_env.py
```

Run the non-GoPro YOLO sample:

```powershell
.\scripts\run_yolo_cpu_sample.ps1
```

This command performs three checks:

1. Prints the Python/YOLO/OpenCV environment report.
2. Runs YOLO on a static image and saves an annotated result.
3. Runs the framework pipeline with YOLO as the detector backend.

Probe outputs:

```text
runs/yolo_image_probe/annotated.jpg
runs/yolo_image_probe/detections.json
```

## GPU Environment

The project now has a separate GPU environment so the working CPU environment remains available as a fallback:

```powershell
C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe
```

Install or refresh it:

```powershell
.\scripts\setup_edge_gpu_env.ps1
```

Verify CUDA:

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_gpu\python.exe .\scripts\check_torch_cuda.py
```

Verified result:

```json
{
  "torch_version": "2.11.0+cu128",
  "cuda_available": true,
  "cuda_version": "12.8",
  "device_name": "NVIDIA GeForce RTX 5060 Laptop GPU"
}
```

`edge_cpu` remains useful for safe fallback testing; `edge_gpu` is now the preferred environment for the real-time GoPro voice demo.

## GoPro Status

GoPro input is intentionally not used in this setup test. The current test path uses a static image source:

```text
assets/ultralytics_bus.jpg
```
