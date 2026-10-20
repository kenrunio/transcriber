"""NVIDIA's libraries for running Whisper on the graphics card (cuBLAS, cuDNN),
downloaded only on computers that have an NVIDIA card. They are about 2 GB, so
the installer leaves them out.

They come as NVIDIA's own pip wheels from PyPI (the versions this app was
tested with); only the DLLs are kept, in paths.CUDA_DIR."""
import glob
import json
import os
import shutil
import site
import sys
import tempfile
import urllib.request
import zipfile

from .paths import CUDA_DIR

PACKAGES = [("nvidia-cublas-cu12", "12.9.2.10"),
            ("nvidia-cudnn-cu12", "9.27.0.42"),
            ("nvidia-cuda-nvrtc-cu12", "12.9.86")]
NEEDED = ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll")


def _pip_dirs():
    """DLL folders of the same wheels installed with pip (running from source)."""
    if getattr(sys, "frozen", False):
        return []
    return [d for sp in site.getsitepackages() for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin"))]


def dll_dirs():
    dirs = _pip_dirs()
    if os.path.isdir(CUDA_DIR):
        dirs.append(CUDA_DIR)
    return dirs


def installed():
    have = {os.path.basename(f).lower() for d in dll_dirs() for f in glob.glob(os.path.join(d, "*.dll"))}
    return all(n.lower() in have for n in NEEDED)


def removable():
    return os.path.isdir(CUDA_DIR) and not _pip_dirs()


def files():
    """[(url, size)] of the Windows wheels."""
    out = []
    for name, version in PACKAGES:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as r:
            meta = json.load(r)
        wheel = next(u for u in meta["urls"] if u["filename"].endswith("win_amd64.whl"))
        out.append((wheel["url"], wheel["size"]))
    return out


def download(state):
    """Fetch the wheels and unpack their DLLs into CUDA_DIR. state: dict with
    done/total/cancel, updated as it goes."""
    wheels = files()
    state["total"] = sum(s for _, s in wheels)
    part = CUDA_DIR + ".part"
    os.makedirs(part, exist_ok=True)
    try:
        for url, _ in wheels:
            with tempfile.TemporaryFile() as tmp:
                req = urllib.request.Request(url, headers={"User-Agent": "Transcriber"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    while True:
                        if state["cancel"]:
                            raise InterruptedError("Cancelled")
                        block = r.read(1 << 20)
                        if not block:
                            break
                        tmp.write(block)
                        state["done"] += len(block)
                tmp.seek(0)
                with zipfile.ZipFile(tmp) as z:
                    for member in z.namelist():
                        if member.lower().endswith(".dll") and "/bin/" in member:
                            with z.open(member) as src, \
                                    open(os.path.join(part, os.path.basename(member)), "wb") as dst:
                                shutil.copyfileobj(src, dst)
        shutil.rmtree(CUDA_DIR, ignore_errors=True)
        os.replace(part, CUDA_DIR)
    finally:
        shutil.rmtree(part, ignore_errors=True)


def remove():
    shutil.rmtree(CUDA_DIR, ignore_errors=True)
