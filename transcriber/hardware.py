"""What this computer can run: NVIDIA graphics card and its memory, RAM, CPU
cores and free disk, and from that which speech model to recommend."""
import ctypes
import os
import shutil
import subprocess

from . import models


def _ram_gb():
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    s = MemoryStatus()
    s.dwLength = ctypes.sizeof(s)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return s.ullTotalPhys / 2**30


def _gpu():
    """(name, memory GB) of the first NVIDIA card, or None."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, creationflags=0x08000000)  # no console flash
        name, mem = out.stdout.strip().splitlines()[0].rsplit(",", 1)
        return name.strip(), float(mem) / 1024
    except Exception:
        return None


def _cuda_driver():
    """Whether the speech engine sees the card (NVIDIA driver present)."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


_cache = None


def detect():
    global _cache
    if _cache is None:
        os.makedirs(models.MODELS_DIR, exist_ok=True)
        gpu = _gpu()
        _cache = {
            "gpu": gpu[0] if gpu else None,
            "gpu_mem_gb": round(gpu[1], 1) if gpu else 0,
            "gpu_driver": bool(gpu) and _cuda_driver(),
            "ram_gb": round(_ram_gb(), 1),
            "cores": os.cpu_count() or 4,
        }
    from . import cuda
    info = dict(_cache)
    # these two change while the app runs (GPU support download, models)
    info["cuda_libs"] = cuda.installed()
    info["cuda"] = info["gpu_driver"] and info["cuda_libs"]  # the card will actually be used
    info["disk_free_gb"] = round(shutil.disk_usage(models.MODELS_DIR).free / 2**30, 1)
    return info


def device(info=None):
    """(device, compute type) for the speech engine on this computer."""
    info = info or detect()
    if info["cuda"]:
        # float16 is the best; half-precision weights with 8-bit maths fit small cards
        return "cuda", "float16" if info["gpu_mem_gb"] >= 6 else "int8_float16"
    return "cpu", "int8"


def recommended_speech(info=None):
    """For the card if there is one (its GPU-support download is recommended too)."""
    info = info or detect()
    if info["gpu_driver"]:
        return "large-v3" if info["gpu_mem_gb"] >= 6 else "large-v3-turbo"
    return "large-v3-turbo" if info["ram_gb"] >= 12 and info["cores"] >= 8 else "small"


# Minutes of work per minute of audio for a model of cost 1.0 (large-v3), from
# measurements: about 0.11 on an RTX 5090 laptop (89 minutes in under 10), held
# at 0.15 for a typical card; faster-whisper's published CPU figures put
# large-v3 at roughly real time with 8 cores at 8-bit.
GPU_RATE, CPU_RATE_8_CORES = 0.15, 1.0


def minutes_per_hour(cost, info=None):
    """Rough minutes to transcribe an hour of audio, voices included."""
    info = info or detect()
    rate = GPU_RATE if info["cuda"] else CPU_RATE_8_CORES * 8 / max(2, min(info["cores"], 16))
    voices = 2.0 * 22 / max(2, info["cores"] - 2)  # 159 s per 89 min on 22 threads
    return round(60 * cost * rate + voices)
