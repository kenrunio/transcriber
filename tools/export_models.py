"""Makes the ONNX voice and punctuation models the app runs (transcriber/models.py).

The only part of the project that needs PyTorch. Run once, in an environment
with requirements-dev.txt installed:

    python tools/export_models.py

Both exports were checked against PyTorch on an 89-minute recording: the same
speaker for all 5,024 voice windows and the same punctuation on all 10,768
words (ROADMAP.md, step 2)."""
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import torch  # noqa: E402

from transcriber import models  # noqa: E402

ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
PUNCT_SOURCE = "oliverguhr/fullstop-punctuation-multilang-large"
WIN_SAMPLES = 24000  # diarize.WIN seconds at 16 kHz


def export_ecapa():
    from speechbrain.inference.speaker import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy
    enc = EncoderClassifier.from_hparams(
        source=ECAPA_SOURCE, savedir=os.path.join(models.MODELS_DIR, "ecapa", "speechbrain"),
        run_opts={"device": "cpu"}, local_strategy=LocalStrategy.COPY)

    class Full(torch.nn.Module):
        """wav (batch, samples) + relative lengths -> embedding. The audio features
        and their normalisation are inside the model, so nothing is redone by hand."""
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, wav, lens):
            f = self.m.mean_var_norm(self.m.compute_features(wav), lens)
            return self.m.embedding_model(f, lens)

    os.makedirs(os.path.dirname(models.ECAPA), exist_ok=True)
    # the dynamo exporter: the older one cannot export the STFT in the features
    torch.onnx.export(Full(enc.mods).eval(), (torch.randn(4, WIN_SAMPLES) * 0.05, torch.ones(4)),
                      models.ECAPA, input_names=["wav", "lens"], output_names=["emb"],
                      dynamic_axes={"wav": {0: "b"}, "lens": {0: "b"}, "emb": {0: "b"}},
                      opset_version=18, dynamo=True, external_data=False)
    print("voice model ->", models.ECAPA)


def export_punctuation():
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(PUNCT_SOURCE)
    net = AutoModelForTokenClassification.from_pretrained(PUNCT_SOURCE).eval()

    class Logits(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, ids, mask):
            return self.m(input_ids=ids, attention_mask=mask).logits

    os.makedirs(models.PUNCT_DIR, exist_ok=True)
    enc = tok(["hello there how are you"] * 2, return_tensors="pt", padding=True)
    torch.onnx.export(Logits(net), (enc["input_ids"], enc["attention_mask"]), models.PUNCT,
                      input_names=["ids", "mask"], output_names=["logits"],
                      dynamic_shapes={"ids": {0: "b", 1: "n"}, "mask": {0: "b", 1: "n"}},
                      opset_version=18, dynamo=True, external_data=True)  # over 2 GB
    tok.backend_tokenizer.save(models.PUNCT_TOKENIZER)
    with open(models.PUNCT_LABELS, "w") as f:
        json.dump({int(k): v for k, v in net.config.id2label.items()}, f)
    print("punctuation model ->", models.PUNCT_DIR)


if __name__ == "__main__":
    export_ecapa()
    export_punctuation()
