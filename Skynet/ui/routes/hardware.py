# Skynet/ui/routes/hardware.py
from __future__ import annotations

import psutil
from fastapi import APIRouter

router = APIRouter(prefix="/api/hardware", tags=["hardware"])


def _gpu_stats() -> dict:
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return {
            "gpu_name": pynvml.nvmlDeviceGetName(handle),
            "gpu_percent": util.gpu,
            "vram_used_gb": round(mem.used / 1024 ** 3, 1),
            "vram_total_gb": round(mem.total / 1024 ** 3, 1),
        }
    except Exception:
        return {"gpu_name": None, "gpu_percent": None, "vram_used_gb": None, "vram_total_gb": None}


@router.get("")
def get_hardware():
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    return {
        "cpu_percent": cpu,
        "ram_used_gb": round(mem.used / 1024 ** 3, 1),
        "ram_total_gb": round(mem.total / 1024 ** 3, 1),
        **_gpu_stats(),
    }
