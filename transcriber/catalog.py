"""The model menu: what can be downloaded (catalog.json), what is installed,
and downloading or removing models.

Speech models go in MODELS_DIR/speech/<id>. A Whisper model that faster-whisper
had already downloaded into the Hugging Face cache also counts as installed."""
import json
import os
import shutil
import threading
import urllib.request

from . import cuda, hardware, models
from .paths import app_file

SPEECH_DIR = os.path.join(models.MODELS_DIR, "speech")
SKIP = {"README.md", ".gitattributes"}

_lock = threading.Lock()
downloads = {}  # id -> {done, total, error, cancel}


def entries():
    with open(app_file("transcriber", "catalog.json"), encoding="utf-8") as f:
        return json.load(f)["models"]


def get(model_id):
    for m in entries():
        if m["id"] == model_id:
            return m
    raise KeyError(f"No model called {model_id!r} in the catalogue")


def _target(m):
    return {"voice": os.path.dirname(models.ECAPA), "punctuation": models.PUNCT_DIR}.get(
        m["kind"], os.path.join(SPEECH_DIR, m["id"]))


def _hf_cache_path(repo):
    """The snapshot folder faster-whisper downloaded into the Hugging Face cache.
    Found by hand: faster-whisper fetches only the model files, and
    huggingface_hub calls such a snapshot incomplete (no README)."""
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        base = os.path.join(HF_HUB_CACHE, "models--" + repo.replace("/", "--"))
        with open(os.path.join(base, "refs", "main")) as f:
            p = os.path.join(base, "snapshots", f.read().strip())
        return p if os.path.exists(os.path.join(p, "model.bin")) else None
    except Exception:
        return None


def path(m):
    """Where an installed model is, or None."""
    m = get(m) if isinstance(m, str) else m
    if m["kind"] == "gpu":
        return cuda.CUDA_DIR if cuda.installed() else None
    target = _target(m)
    if m["kind"] == "speech":
        if all(os.path.exists(os.path.join(target, f)) for f in ("model.bin", "config.json")):
            return target
        return _hf_cache_path(m["source"]["repo"])
    return target if all(os.path.exists(os.path.join(target, f)) for f in m["files"]) else None


def listing():
    """Every model with its status and the speed estimate for this computer."""
    info = hardware.detect()
    rec = hardware.recommended_speech(info)
    out = []
    for m in entries():
        if m["kind"] == "gpu" and not info["gpu_driver"]:
            continue  # no NVIDIA card: nothing to offer
        m = dict(m)
        m["installed"] = path(m) is not None
        m["downloadable"] = bool(m["source"].get("repo") or m["source"].get("pypi"))
        m["removable"] = m["installed"] and (m["kind"] != "gpu" or cuda.removable())
        m["recommended"] = m["id"] == rec or (m["kind"] == "gpu" and not m["installed"])
        if m["kind"] == "speech":
            m["minutes_per_hour"] = hardware.minutes_per_hour(m["cost"], info)
            m["fits"] = not info["cuda"] or info["gpu_mem_gb"] >= m["vram_gb"]
        with _lock:
            m["download"] = dict(downloads[m["id"]]) if m["id"] in downloads else None
        out.append(m)
    return out


def installed_speech():
    return [m for m in entries() if m["kind"] == "speech" and path(m)]


# -- downloading ----------------------------------------------------------------

def _files(m):
    """[(file name, size)] to fetch."""
    if m["kind"] == "speech":
        from huggingface_hub import HfApi
        info = HfApi().model_info(m["source"]["repo"], files_metadata=True)
        return [(s.rfilename, s.size or 0) for s in info.siblings if s.rfilename not in SKIP]
    return [(f, 0) for f in m["files"]]


def start_download(model_id):
    m = get(model_id)
    if not (m["source"].get("repo") or m["source"].get("pypi")):
        raise ValueError("This model is not offered for download yet.")
    with _lock:
        if model_id in downloads and not downloads[model_id].get("error"):
            return  # already going
        downloads[model_id] = {"done": 0, "total": 0, "error": None, "cancel": False}
    threading.Thread(target=_download, args=(m,), daemon=True).start()


def cancel_download(model_id):
    with _lock:
        if model_id in downloads:
            downloads[model_id]["cancel"] = True


def _download(m):
    state = downloads[m["id"]]
    if m["kind"] == "gpu":
        try:
            cuda.download(state)
            with _lock:
                del downloads[m["id"]]
        except Exception as e:
            with _lock:
                if isinstance(e, InterruptedError):
                    del downloads[m["id"]]
                else:
                    state["error"] = f"{type(e).__name__}: {e}"
        return
    target = _target(m)
    part = target + ".part"
    try:
        files = _files(m)
        state["total"] = sum(s for _, s in files) or m["size_mb"] * 1e6
        os.makedirs(part, exist_ok=True)
        for name, _ in files:
            url = f"https://huggingface.co/{m['source']['repo']}/resolve/main/{name}"
            req = urllib.request.Request(url, headers={"User-Agent": "Transcriber"})
            with urllib.request.urlopen(req, timeout=60) as r, \
                    open(os.path.join(part, name), "wb") as f:
                while True:
                    if state["cancel"]:
                        raise InterruptedError("Cancelled")
                    block = r.read(1 << 20)
                    if not block:
                        break
                    f.write(block)
                    state["done"] += len(block)
        os.makedirs(target, exist_ok=True)
        for name, _ in files:
            os.replace(os.path.join(part, name), os.path.join(target, name))
        shutil.rmtree(part, ignore_errors=True)
        with _lock:
            del downloads[m["id"]]
    except Exception as e:
        shutil.rmtree(part, ignore_errors=True)
        with _lock:
            if isinstance(e, InterruptedError):
                del downloads[m["id"]]
            else:
                state["error"] = f"{type(e).__name__}: {e}"


def remove(model_id):
    m = get(model_id)
    if m["kind"] == "gpu":
        if cuda.removable():
            cuda.remove()
        return
    p = path(m)
    if not p:
        return
    if m["kind"] == "speech" and not p.startswith(SPEECH_DIR):
        # in the Hugging Face cache: remove the whole repository folder there
        while os.path.basename(p) and not os.path.basename(p).startswith("models--"):
            p = os.path.dirname(p)
        if os.path.basename(p).startswith("models--"):
            shutil.rmtree(p)
        return
    if m["kind"] == "speech":
        shutil.rmtree(p)
    else:
        for f in m["files"]:
            fp = os.path.join(p, f)
            if os.path.exists(fp):
                os.remove(fp)
