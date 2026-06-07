# GoPro Edge AI Blind Navigation Prototype

This repository is a master's-level edge computing prototype that uses a laptop as the edge node and a GoPro Hero 9 as the wearable camera input. The goal is to assist blind or low-vision users by detecting blocked walking directions in real time, presenting a 12-o'clock spatial overlay, and producing speech cues such as "front passable", "turn left", "turn right", "stop", or "low visibility, stop".

The project started as a reusable edge video analytics framework, then was adapted into an assistive navigation demo by changing the input source, models, feature extraction, decision rules, and labeled dataset.

## System Overview

```text
GoPro Hero 9
  USB/RNDIS + Open GoPro API
        |
        v
FFmpeg UDP capture / OpenCV frames
        |
        v
Edge AI perception on laptop
  - SegFormer semantic segmentation for wall/floor/door cues
  - Depth Anything V2 monocular depth for near-space risk
  - ArUco-based distance calibration
        |
        v
Navigation decision layer
  - rule-based semantic/depth fusion
  - small human-labeled decision classifier
        |
        v
Demo outputs
  - laptop display with 12-o'clock overlay
  - annotated video
  - Chinese speech prompt
  - metrics and event logs
```

## Hardware Used

- Edge node: ASUS TUF Gaming A16 FA608PM_FA608PM laptop
- CPU: AMD Ryzen 9 8940HX, 16 cores / 32 threads
- GPU: NVIDIA GeForce RTX 5060 Laptop GPU, 8 GB VRAM
- Memory: 32 GB RAM
- Camera: GoPro Hero 9
- Connection: GoPro USB network mode, local GoPro API endpoint `172.26.181.51`

The laptop is treated as a stronger development board. The same pipeline can later be moved toward an embedded edge device with a camera and microphone.

## Models and Training

This project uses three different model roles:

| Component | Model | Fine-tuned? | Purpose |
| --- | --- | --- | --- |
| Semantic segmentation | `nvidia/segformer-b0-finetuned-ade-512-512` | No | Finds wall, floor, door, and ceiling regions |
| Monocular depth | `depth-anything/Depth-Anything-V2-Small-hf` | No | Estimates relative depth / near-space risk |
| Navigation decision classifier | small linear PyTorch classifier | Yes, trained on project labels | Converts semantic/depth features into action labels |

The important distinction is that SegFormer and Depth Anything V2 are pre-trained feature extractors. The project-specific learning happens in the lightweight decision classifier trained from the user's GoPro walking clips and manual labels.

## Dataset Summary

Raw videos are not committed to this repository because they are large and contain private indoor footage. The public repo keeps the code and small annotation/experiment summaries.

Collected scenarios included:

- walking toward a wall
- corridor walking
- left side passable / right side wall
- right side passable / left side wall
- front wall with left or right bypass
- table/chair obstacle
- door and room corner
- low-light and no-light cases
- mirror/glass reflection
- environment walkthrough

Final real-only decision-classifier dataset:

| Label | Count |
| --- | ---: |
| `front_passable` | 36 |
| `stop` | 26 |
| `turn_left` | 14 |
| `turn_right` | 8 |
| `low_visibility_stop` | 4 |
| Total | 88 |

Synthetic horizontal flip samples were used for analysis but excluded from the final real-only classifier result.

## Distance Calibration

Distance calibration used a 15 cm ArUco marker displayed at known distances of 1 m, 2 m, and 3 m.

| Metric | Result |
| --- | ---: |
| Recommended distance scale | `1.4212` |
| Raw MAE | `0.6167 m` |
| Calibrated MAE | `0.1023 m` |
| MAE improvement | `83.41%` |

This calibration does not make monocular depth physically perfect, but it gives the demo a more defensible meter estimate for the specific GoPro/laptop setup.

## Experiment Results

Decision classifier:

| Metric | Result |
| --- | ---: |
| Training samples | 88 |
| Training accuracy | 79.55% |
| Leave-one-out CV accuracy | 53.41% |

The CV result is intentionally reported because the dataset is small and scene-specific. The model should be described as a prototype that can adapt to the collected environment, not a fully generalized outdoor navigation model.

Demo A: learned navigation overlay

- Output video: `runs/realtime_gopro_navigation_learned/annotated_navigation_learned_480p.mp4`
- Processed frames: 209
- Elapsed time: 31.25 s
- Effective FPS: 6.688
- Average latency: 23.273 ms
- P95 latency: 29.859 ms
- Spoken prompts: 10

Demo B: live laptop display demo

- Output video: `runs/realtime_gopro_navigation_demo_display/annotated_demo_display_480p.mp4`
- Processed frames: 862
- Elapsed time: 91.228 s
- Effective FPS: 9.449
- Depth latency average: 20.902 ms
- Semantic latency average: 18.877 ms
- Spoken prompts: 4

## Quick Start

Create an environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For CUDA acceleration, install the PyTorch build that matches your CUDA/runtime from the official PyTorch selector before installing the remaining packages.

Run the framework smoke test:

```powershell
python .\scripts\smoke_test.py
```

Train the project decision classifier from labeled CSV annotations:

```powershell
python .\scripts\train_decision_classifier.py `
  --annotations .\data\annotations\navigation_labels_v2_enriched.csv `
  --out-dir .\runs\decision_classifier_v2_merged_enriched_real_only
```

Run the live GoPro demo after connecting the GoPro through USB network mode:

```powershell
.\scripts\run_realtime_gopro_navigation_demo_display.ps1
```

The demo opens a laptop preview window. Press `q` or `Esc` in the video window to stop.

## Repository Layout

```text
edge_framework/     Core pipeline, spatial logic, overlays, semantic/depth fusion
scripts/            Training, calibration, GoPro capture, demo, and evaluation scripts
configs/            Reusable pipeline configurations
assets/             Small static assets such as the ArUco marker
data/               Small public annotation/calibration summaries
docs/               Notes, experiment logs, and references
runs/               Local generated outputs, videos, model weights, logs (ignored by git)
deliverables/       Local slides and report artifacts (ignored by git)
```

## Public Data Policy

This repository excludes:

- raw GoPro videos
- generated annotated videos
- trained model weights
- PowerPoint deliverables
- cache folders and local environment files

Those files are kept locally under `runs/` and `deliverables/`. If a public release is needed, upload selected demo videos or model weights separately as a GitHub Release asset or cloud-drive artifact.

## References

- SegFormer: Xie et al., "SegFormer: Simple and Efficient Design for Semantic Segmentation with Transformers", 2021.
- ADE20K: Zhou et al., "Scene Parsing through ADE20K Dataset", 2017.
- Depth Anything V2: Yang et al., "Depth Anything V2", 2024.
- Hugging Face model: `nvidia/segformer-b0-finetuned-ade-512-512`.
- Hugging Face model: `depth-anything/Depth-Anything-V2-Small-hf`.
- Open GoPro HTTP API documentation.
- FFmpeg UDP/video capture documentation.
- OpenCV ArUco and video processing documentation.
- PyTorch documentation.
