# MVP Test Results

Date: 2026-06-04

Environment:

- ASUS TUF Gaming A16
- AMD Ryzen 9 8940HX
- 32 GB RAM
- NVIDIA GeForce RTX 5060 Laptop GPU, 8 GB VRAM
- Windows 11
- Python 3.13.5

## Goal

Verify that the same edge video analytics pipeline can switch from one task to another by changing only the configuration file.

## Test 1: Person Counting

Command:

```powershell
python .\scripts\run_pipeline.py --config .\configs\person_counting.json
```

Result:

| Metric | Value |
| --- | ---: |
| Processed frames | 120 |
| Skipped frames | 0 |
| Event count | 65 |
| Elapsed seconds | 8.061 |
| FPS | 14.887 |
| Average latency | 0.125 ms |
| P95 latency | 0.217 ms |

## Test 2: Safety Helmet

Command:

```powershell
python .\scripts\run_pipeline.py --config .\configs\safety_helmet.json
```

Result:

| Metric | Value |
| --- | ---: |
| Processed frames | 120 |
| Skipped frames | 0 |
| Event count | 29 |
| Elapsed seconds | 8.058 |
| FPS | 14.892 |
| Average latency | 0.108 ms |
| P95 latency | 0.241 ms |

## Interpretation

The MVP confirms the central project concept:

- The source module, pipeline, detector interface, rule engine, event writer, and metrics module are reused.
- The application changes from person counting to safety helmet alerting through config files.
- The current detector is a dummy backend, so latency is not a real AI inference measurement yet.
- The next milestone is replacing the dummy backend with GoPro input and YOLO inference.

