# References and Open-Source Ideas

These references are useful for shaping the project. The final implementation does not need to copy them directly; they mainly provide architectural ideas.

## yolo-tonic

GitHub: https://github.com/jordandelbar/yolo-tonic

Useful idea:

- webcam or camera stream input
- YOLO inference
- ONNX Runtime and TensorRT comparison
- gRPC/WebSocket style real-time result delivery

How to borrow the idea:

- Use a separate detector backend abstraction.
- Keep video processing and result streaming independent.
- Compare multiple inference backends as an experiment.

## EVA

Project page: https://git-disl.github.io/EVA/

Useful idea:

- Edge video analytics often faces a mismatch between video ingestion rate and neural-network inference speed.
- A system can adapt frame rate, resolution, and processing policy instead of processing every frame the same way.

How to borrow the idea:

- Add FPS limits, frame skipping, and adaptive inference modes.
- Measure end-to-end latency and dropped frames.

## Intel Edge Video Analytics Microservice

Docker Hub: https://hub.docker.com/r/intel/edge_video_analytics_microservice

Useful idea:

- Package video analytics as a deployable service.
- Use configuration to define the video source, model, and output behavior.

How to borrow the idea:

- Turn the pipeline into a service later with FastAPI or Docker.
- Keep configuration as the main deployment interface.

## LF Edge eKuiper

GitHub: https://github.com/lf-edge/ekuiper

Useful idea:

- Use rules to process edge events.
- Separate raw data collection from event logic.

How to borrow the idea:

- Model output becomes metadata.
- Configurable rules decide when to alert, save, or publish events.

