from __future__ import annotations

import json
import platform


def main() -> None:
    import cv2
    import torch
    import ultralytics

    report = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda_available": torch.cuda.is_available(),
        "torch_cuda_version": torch.version.cuda,
        "torch_device_count": torch.cuda.device_count(),
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
    }

    if torch.cuda.is_available():
        report["torch_cuda_device_0"] = torch.cuda.get_device_name(0)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

