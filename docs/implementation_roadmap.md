# Implementation Roadmap

## Phase 1: Current Scaffold

Status: done

- Config-driven pipeline
- Synthetic source
- Dummy detector
- Rule engine
- Event log
- Metrics summary

## Phase 2: GoPro/Webcam Input

Goal:

- Use GoPro9 as a webcam source through GoPro Webcam Utility or HDMI capture.
- Read frames through OpenCV.

Tasks:

- Install `opencv-python`.
- Test `configs/gopro_template.json`.
- Verify device index.
- Add frame preview or output image annotation.

## Phase 3: YOLO Detector

Goal:

- Use Ultralytics YOLO as the first real detector backend.

Tasks:

- Install `ultralytics`.
- Run `yolov8n.pt` on webcam input.
- Save per-frame detection metadata.
- Add confidence threshold and class filtering to config.

## Phase 4: Adaptation Case Studies

Goal:

- Demonstrate rapid migration from project A to project B.

Case A:

- Person counting.
- Rule: person count >= N.

Case B:

- Safety helmet detection.
- Rule: no_helmet count >= 1.

Measurements:

- Modified source code lines.
- Changed config fields.
- Deployment time.
- FPS and latency before/after task switch.

## Phase 5: Edge Optimization

Goal:

- Compare different edge inference strategies.

Tasks:

- Export YOLO to ONNX.
- Test ONNX Runtime CPU.
- Test ONNX Runtime GPU if environment supports it.
- Optionally test TensorRT FP16.

Metrics:

- average latency
- p95 latency
- FPS
- GPU memory
- CPU usage

## Phase 6: Dashboard

Goal:

- Make the demo presentation-friendly.

Options:

- FastAPI + WebSocket dashboard.
- Streamlit dashboard.
- Local browser visualization.

Minimum dashboard:

- live FPS
- latest event
- detection counts
- event timeline

