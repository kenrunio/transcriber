"""Where the voice and punctuation models live, as ONNX files run by ONNX Runtime.

They are made once from the original PyTorch models by tools/export_models.py
(the only part that needs PyTorch). Whisper models are separate: faster-whisper
downloads those itself."""
import os

from .paths import MODELS_DIR
ECAPA = os.path.join(MODELS_DIR, "ecapa", "ecapa.onnx")
PUNCT_DIR = os.path.join(MODELS_DIR, "punctuation")
PUNCT = os.path.join(PUNCT_DIR, "model.onnx")
PUNCT_TOKENIZER = os.path.join(PUNCT_DIR, "tokenizer.json")
PUNCT_LABELS = os.path.join(PUNCT_DIR, "labels.json")


def threads():
    return max(1, (os.cpu_count() or 4) - 2)


def session(path):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Model file missing: {path}. Install it on the Models page, or make it "
            "with tools/export_models.py (README, Setting up on another PC).")
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads()
    return ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
