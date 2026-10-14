# Purpose: keep Qwen activations out of unsafe float16 on older Apple Silicon GPUs.
import importlib
import platform
from typing import Any


def prepare(model: Any) -> str:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return "library_default"
    mx = importlib.import_module("mlx.core")
    name = mx.device_info().get("device_name", "")
    if not name.startswith(("Apple M1", "Apple M2")):
        return "library_default"
    # MLX leaves integer-packed weights quantized; only floating parameters change dtype.
    # Apply before the first forward pass and identically after reloading the checkpoint.
    model.encoder.set_dtype(mx.float32)
    model.head.set_dtype(mx.float32)
    mx.eval(model.parameters())
    print("Qwen precision: float32 activations on M1/M2; packed weights stay quantized.")
    return "mlx_float32_activations"
