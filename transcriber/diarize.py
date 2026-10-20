"""Who spoke when: voice fingerprints (SpeechBrain's ECAPA model, run as ONNX)
over short windows of speech, grouped by similarity. Speakers come out as
numbers; the app names them."""
import numpy as np
import soundfile as sf

from . import models

SR = 16000
WIN = 1.5    # seconds of audio per fingerprint
HOP = 0.75   # step between fingerprints


def load_audio(wav_path):
    audio, sr = sf.read(wav_path, dtype="float32")
    assert sr == SR, f"expected {SR} Hz audio, got {sr}"
    return audio


def speech_regions(audio):
    """[(start_s, end_s)] of speech, from the Silero VAD that ships with faster-whisper."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    ts = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=300, speech_pad_ms=100))
    return [(t["start"] / SR, t["end"] / SR) for t in ts]


def _windows(regions):
    out = []
    for a, b in regions:
        if b - a < 0.5:
            continue
        if b - a <= WIN:
            out.append((a, b))
            continue
        t = a
        while t + WIN <= b:
            out.append((t, t + WIN))
            t += HOP
        if b - (t - HOP + WIN) > HOP / 2:
            out.append((b - WIN, b))
    return out


def embed(audio, windows, progress=None, batch=64):
    sess = models.session(models.ECAPA)
    n = int(WIN * SR)
    embs = []
    for i in range(0, len(windows), batch):
        chunk = windows[i:i + batch]
        x = np.zeros((len(chunk), n), dtype=np.float32)
        lens = np.zeros(len(chunk), dtype=np.float32)
        for j, (a, b) in enumerate(chunk):
            seg = audio[int(a * SR):int(b * SR)][:n]
            x[j, :len(seg)] = seg
            lens[j] = len(seg) / n  # share of the window that is audio, the rest is padding
        embs.append(sess.run(None, {"wav": x, "lens": lens})[0].reshape(len(chunk), -1))
        if progress:
            progress(min(1.0, (i + batch) / len(windows)))
    e = np.concatenate(embs)
    return e / np.linalg.norm(e, axis=1, keepdims=True)


def cluster(embs, windows, num_speakers=None, threshold=0.7, min_speaker_s=8.0):
    """Label per window. Average-linkage grouping, then every window moved to its
    nearest speaker centroid, and speakers with under min_speaker_s of speech
    folded into the nearest bigger one."""
    from sklearn.cluster import AgglomerativeClustering
    if num_speakers:
        ac = AgglomerativeClustering(n_clusters=num_speakers, metric="cosine", linkage="average")
    else:
        ac = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                     distance_threshold=threshold)
    labels = ac.fit_predict(embs)
    for _ in range(3):
        ids = np.unique(labels)
        cents = np.stack([embs[labels == k].mean(0) for k in ids])
        cents /= np.linalg.norm(cents, axis=1, keepdims=True)
        talk = np.array([(labels == k).sum() * HOP for k in ids])
        keep = talk >= min_speaker_s
        if not keep.any():
            keep[:] = True
        labels = ids[keep][np.argmax(embs @ cents[keep].T, axis=1)]
    # renumber by first appearance
    order = {}
    for k in labels:
        order.setdefault(k, len(order))
    return np.array([order[k] for k in labels])


def turns(windows, labels, min_turn=1.0):
    """Contiguous (start, end, speaker) runs; each window owns the middle of its span."""
    pieces = []
    for (a, b), k in zip(windows, labels):
        mid = (a + b) / 2
        pieces.append([max(a, mid - HOP / 2), min(b, mid + HOP / 2), int(k)])
    runs = []
    for p in pieces:
        if runs and runs[-1][2] == p[2] and p[0] - runs[-1][1] < 1.0:
            runs[-1][1] = max(runs[-1][1], p[1])
        else:
            runs.append(p)
    # a blip shorter than min_turn between two runs of one speaker belongs to them
    changed = True
    while changed:
        changed = False
        for i in range(1, len(runs) - 1):
            r = runs[i]
            if r[1] - r[0] < min_turn and runs[i - 1][2] == runs[i + 1][2]:
                runs[i - 1][1] = runs[i + 1][1]
                del runs[i:i + 2]
                changed = True
                break
    return [tuple(r) for r in runs]


def diarize(wav_path, num_speakers=None, progress=None):
    audio = load_audio(wav_path)
    regions = speech_regions(audio)
    windows = _windows(regions)
    embs = embed(audio, windows, progress)
    labels = cluster(embs, windows, num_speakers)
    return {"turns": turns(windows, labels),
            "windows": [list(w) for w in windows], "labels": labels.tolist(),
            "embeddings": embs}
