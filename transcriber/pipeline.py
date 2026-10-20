"""A job: one media file taken through audio -> words -> speakers -> transcript.

Each job lives in its own folder under JOBS_DIR, in the data folder (the audio
copy is large). Every stage saves its result, so a stopped job resumes where
it left off."""
import bisect
import json
import os
import re
import time
import traceback
from datetime import datetime

import numpy as np

from . import asr, catalog, diarize, punctuate, vocab
from .paths import JOBS_DIR


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class Job:
    def __init__(self, job_id):
        self.id = job_id
        self.dir = os.path.join(JOBS_DIR, job_id)

    def path(self, name):
        return os.path.join(self.dir, name)

    @property
    def meta(self):
        return _read(self.path("job.json"), {})

    def update_meta(self, **kw):
        m = self.meta
        m.update(kw)
        _write(self.path("job.json"), m)
        return m

    def status(self, stage, progress=0.0, message=""):
        self.update_meta(stage=stage, progress=round(progress, 3), message=message,
                         updated=time.time())

    @property
    def transcript(self):
        return _read(self.path("transcript.json"))

    def save_transcript(self, t):
        _write(self.path("transcript.json"), t)

    # -- running ---------------------------------------------------------
    def run(self):
        m = self.meta
        try:
            wav = self.path("audio.wav")
            if not os.path.exists(wav):
                self.status("audio", 0, "Extracting audio")
                asr.extract_audio(m["source"], wav + ".part.wav")
                os.replace(wav + ".part.wav", wav)

            # check the models before the long work starts
            model_path = catalog.path(m.get("model", "large-v3"))
            if not model_path and not os.path.exists(self.path("asr.json")):
                raise RuntimeError(f"The speech model '{catalog.get(m.get('model', 'large-v3'))['name']}' "
                                   "is not installed. Download it on the Models page, then Try again.")
            if not catalog.path("ecapa") and not os.path.exists(self.path("speakers.npz")):
                raise RuntimeError("The speaker recognition model is not installed (Models page).")

            words_file = self.path("asr.json")
            if not os.path.exists(words_file):
                self.status("transcribe", 0, "Loading the speech model")
                last = [0.0]

                def p(f, text):
                    if f - last[0] >= 0.005:
                        last[0] = f
                        self.status("transcribe", f, text[:120])
                segs, lang = asr.transcribe(wav, model_path, language=m.get("language") or None,
                                            progress=p)
                _write(words_file, {"language": lang, "segments": segs})

            diar_file = self.path("speakers.npz")
            if not os.path.exists(diar_file):
                self.status("speakers", 0, "Finding speech")
                audio = diarize.load_audio(wav)
                windows = diarize._windows(diarize.speech_regions(audio))
                self.status("speakers", 0, "Recognising voices")
                embs = diarize.embed(audio, windows,
                                     lambda f: self.status("speakers", f, "Recognising voices"))
                np.savez(diar_file + ".part.npz", windows=np.array(windows), embs=embs)
                os.replace(diar_file + ".part.npz", diar_file)

            if not self.transcript:
                self.status("merge", 0, "Putting it together")
                self.save_transcript(build_transcript(
                    _read(words_file), np.load(diar_file), m.get("num_speakers"),
                    m.get("vocabulary", "")))

            self.status("done", 1, "")
        except Exception as e:
            traceback.print_exc()
            self.status("error", 0, f"{type(e).__name__}: {e}")

    def regroup(self, num_speakers):
        """Re-run the voice grouping with a different speaker count; drops names and edits."""
        self.update_meta(num_speakers=num_speakers)
        self.save_transcript(build_transcript(
            _read(self.path("asr.json")), np.load(self.path("speakers.npz")), num_speakers,
            self.meta.get("vocabulary", "")))


def create_job(source, language=None, vocabulary="", num_speakers=None, model="large-v3"):
    stem = os.path.splitext(os.path.basename(source))[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-")[:40] or "job"
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + slug
    os.makedirs(os.path.join(JOBS_DIR, job_id))
    job = Job(job_id)
    job.update_meta(id=job_id, source=source, title=stem, language=language,
                    vocabulary=vocabulary, num_speakers=num_speakers, model=model,
                    created=time.time())
    job.status("queued", 0, "Waiting to start")
    return job


def list_jobs():
    if not os.path.isdir(JOBS_DIR):
        return []
    jobs = [Job(d) for d in sorted(os.listdir(JOBS_DIR), reverse=True)
            if os.path.exists(os.path.join(JOBS_DIR, d, "job.json"))]
    return jobs


# -- words + voices -> transcript ---------------------------------------------

def build_transcript(asr_data, diar, num_speakers=None, vocabulary=""):
    vocab_terms = vocab.terms(vocabulary)
    windows = [tuple(w) for w in diar["windows"]]
    labels = diarize.cluster(diar["embs"], windows, num_speakers)
    turns = diarize.turns(windows, labels)
    starts = [t[0] for t in turns]

    def speaker_at(t):
        """Speaker of the voice turn holding time t, else of the nearest turn."""
        i = bisect.bisect_right(starts, t) - 1
        best, gap = 0, float("inf")
        for j in (i, i + 1):
            if 0 <= j < len(turns):
                a, b, k = turns[j]
                d = 0 if a <= t <= b else min(abs(a - t), abs(b - t))
                if d < gap:
                    best, gap = k, d
        return best

    def dur(run):
        return run["words"][-1]["end"] - run["words"][0]["start"]

    lines = []
    for seg in asr_data["segments"]:
        words = seg["words"] or [{"start": seg["start"], "end": seg["end"], "word": seg["text"]}]
        runs = []
        for w in words:
            k = speaker_at((w["start"] + w["end"]) / 2)
            if runs and runs[-1]["speaker"] == k:
                runs[-1]["words"].append(w)
            else:
                runs.append({"speaker": k, "words": [w]})
        # a sliver under 0.6 s inside a sentence is the voice model wobbling
        while len(runs) > 1:
            i = min(range(len(runs)), key=lambda j: dur(runs[j]))
            if dur(runs[i]) >= 0.6:
                break
            # into the longer neighbour; the words keep their order
            if i == 0 or (i + 1 < len(runs) and dur(runs[i + 1]) > dur(runs[i - 1])):
                runs[i + 1]["words"][:0] = runs[i]["words"]
            else:
                runs[i - 1]["words"].extend(runs[i]["words"])
            del runs[i]
            # neighbours that now share a speaker become one run
            j = 1
            while j < len(runs):
                if runs[j]["speaker"] == runs[j - 1]["speaker"]:
                    runs[j - 1]["words"].extend(runs.pop(j)["words"])
                else:
                    j += 1
        for r in runs:
            # one line per sentence, so a single sentence can be moved to another speaker
            sentence = []
            for i, w in enumerate(r["words"]):
                sentence.append(w)
                if w["word"].rstrip().endswith((".", "?", "!")) or i == len(r["words"]) - 1:
                    text = "".join(x["word"] for x in sentence).strip()
                    if text:
                        lines.append({"start": round(sentence[0]["start"], 2),
                                      "end": round(sentence[-1]["end"], 2),
                                      "speaker": int(r["speaker"]), "text": text})
                    sentence = []
    lines = punctuate.fix_shouting(punctuate.fix_lines(lines, asr_data.get("language")))
    for i, ln in enumerate(lines):
        ln["id"] = i
        # Whisper sometimes drops capitals; a line that starts a sentence or a turn gets one
        prev = lines[i - 1] if i else None
        if not prev or prev["speaker"] != ln["speaker"] or prev["text"].endswith((".", "?", "!")):
            ln["text"] = ln["text"][:1].upper() + ln["text"][1:]
        ln["text"] = re.sub(r"(?<![\w.'])i(?=['\s,?!]|\.(?!e\.)|$)", "I", ln["text"])  # not "i.e."
        ln["text"] = vocab.correct(ln["text"], vocab_terms)[0]

    talk = {}
    for ln in lines:
        talk[ln["speaker"]] = talk.get(ln["speaker"], 0) + ln["end"] - ln["start"]
    used = sorted(talk, key=lambda k: min(l["start"] for l in lines if l["speaker"] == k))
    renum = {k: i for i, k in enumerate(used)}
    for ln in lines:
        ln["speaker"] = renum[ln["speaker"]]
    speakers = [{"id": renum[k], "name": f"Speaker {renum[k] + 1}",
                 "talk_s": round(talk[k], 1)} for k in used]
    return {"language": asr_data.get("language"), "speakers": speakers, "lines": lines}
