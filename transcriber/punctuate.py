"""Put full stops, commas, question marks and capitals back into stretches where
Whisper wrote run-on lowercase text (it does, now and then, for minutes at a time).

Uses oliverguhr/fullstop-punctuation-multilang-large (English, German, French,
Italian), run as ONNX, which labels each word with the punctuation that follows
it. Only paragraphs that clearly lack punctuation are touched."""
import re

import numpy as np

from . import models

LANGS = {"en", "de", "fr", "it"}
CHUNK, OVERLAP = 200, 40
_model = None


def _load():
    """(tokenizer, ONNX session, label per class id); loaded once."""
    global _model
    if _model is None:
        import json
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(models.PUNCT_TOKENIZER)
        tok.enable_truncation(512)
        with open(models.PUNCT_LABELS) as f:
            labels = {int(k): v for k, v in json.load(f).items()}
        _model = (tok, models.session(models.PUNCT), labels)
    return _model


def needs_it(text):
    words = len(text.split())
    marks = len(re.findall(r"[.?!](?=\s|$)", text))
    return words >= 20 and marks < words / 20


def _labels(words):
    tok, sess, id2label = _load()
    out = [None] * len(words)
    start = 0
    while start < len(words):
        chunk = words[start:start + CHUNK]
        enc = tok.encode(chunk, is_pretokenized=True)
        ids = np.array([enc.ids], dtype=np.int64)
        pred = sess.run(None, {"ids": ids, "mask": np.ones_like(ids)})[0].argmax(-1)[0].tolist()
        seen = set()
        for pos, wi in enumerate(enc.word_ids):
            if wi is None or wi in seen:
                continue
            seen.add(wi)
            # keep labels from the middle of overlapping chunks
            if out[start + wi] is None or wi >= OVERLAP // 2:
                out[start + wi] = id2label[pred[pos]]
        if start + CHUNK >= len(words):
            break
        start += CHUNK - OVERLAP
    return out


def restore(text):
    """Re-punctuate and re-capitalise one run of text."""
    words = [re.sub(r"[.,?!:;]+$", "", w) for w in text.split()]
    words = [w for w in words if w]
    if not words:
        return text
    labels = _labels(words)
    out, cap = [], True
    for w, lab in zip(words, labels):
        if cap:
            w = w[:1].upper() + w[1:]
        cap = lab in (".", "?")
        # "-" is the model's mid-sentence break ("point of view - I think"): a comma reads best
        out.append(w + {".": ".", ",": ",", "?": "?", ":": ":", "-": ","}.get(lab, ""))
    s = " ".join(out).rstrip(",:")
    return s if s[-1] in ".?!" else s + "."


ALWAYS_CAPITAL = {m.lower() for m in (
    "January February March April May June July August September October November "
    "December Monday Tuesday Wednesday Thursday Friday Saturday Sunday").split()}


def is_shouting(text):
    """Whisper writes some passages (safe-harbor statements, read-out legal text)
    in capitals. A sentence of 8+ words that is mostly capitals is one; a short
    line of acronyms ("HBM4, HBM4E, CoWoS") is not."""
    letters = re.findall(r"[A-Za-z]", text)
    return (len(text.split()) >= 8 and len(letters) >= 20
            and sum(c.isupper() for c in letters) / len(letters) > 0.6)


def fix_shouting(lines):
    """Puts all-capitals sentences into sentence case. Each word takes the form it
    has elsewhere in the transcript, so "SEC", "GAAP" and company names keep theirs;
    words with digits ("20F") and the word "I" are left as they are."""
    seen = {}
    for ln in lines:
        if is_shouting(ln["text"]):
            continue
        for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", ln["text"]):
            if ln["text"].find(w) == 0:
                continue  # a sentence's first word says nothing about its usual case
            seen.setdefault(w.lower(), {}).setdefault(w, 0)
            seen[w.lower()][w] += 1

    def word_case(m):
        w = m.group(0)
        forms = seen.get(w.lower())
        if forms:
            return max(forms, key=forms.get)
        if w.lower() in ALWAYS_CAPITAL:
            return w.capitalize()
        return w.lower()

    for ln in lines:
        if not is_shouting(ln["text"]):
            continue
        text = re.sub(r"(?<![\w\d])[A-Za-z][A-Za-z'\-]*(?![\w\d])",
                      lambda m: m.group(0) if m.group(0) == "I" else word_case(m), ln["text"])
        ln["text"] = text[:1].upper() + text[1:]
    return lines


def fix_lines(lines, language):
    """lines: transcript lines, split at sentence ends, so a run-on stretch shows
    up as consecutive lines of one speaker that never end a sentence. Such a run is
    re-punctuated and split into sentence lines, timed by word count;
    well-punctuated lines are left alone. Returns the new list. Skipped when the
    punctuation model is not installed (it is optional on the Models page)."""
    import os
    if language not in LANGS or not os.path.exists(models.PUNCT):
        return lines
    out, i = [], 0
    while i < len(lines):
        j = i
        while (j + 1 < len(lines) and lines[j + 1]["speaker"] == lines[i]["speaker"]
               and not lines[j]["text"].endswith((".", "?", "!"))):
            j += 1
        run = lines[i:j + 1]
        text = " ".join(l["text"] for l in run)
        i = j + 1
        if not needs_it(text):
            out += run
            continue
        # split only where a mark is followed by a space: "1.2 billion" stays whole
        sentences = [s for s in re.split(r"(?<=[.?!])\s+", restore(text)) if s]
        a, b = run[0]["start"], run[-1]["end"]
        total = sum(len(s.split()) for s in sentences)
        t = a
        for s in sentences:
            d = (b - a) * len(s.split()) / total
            out.append({"start": round(t, 2), "end": round(t + d, 2),
                        "speaker": run[0]["speaker"], "text": s.strip()})
            t += d
    return out
