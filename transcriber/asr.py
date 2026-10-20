"""Speech to text: faster-whisper on the GPU, word timestamps kept."""
import os
import sys


_dll_dirs_added = set()


def _add_cuda_dlls():
    """NVIDIA's DLLs (pip's wheels, or the GPU-support download: cuda.py) are
    outside the folders Windows searches; tell it where."""
    if sys.platform != "win32":
        return
    from . import cuda
    for d in cuda.dll_dirs():
        if d not in _dll_dirs_added:
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
            _dll_dirs_added.add(d)


def extract_audio(media_path, wav_path):
    """Mono 16 kHz WAV, which is what Whisper and the speaker model want. Uses
    PyAV (FFmpeg's libraries, shipped with faster-whisper), so no separate
    ffmpeg program is needed."""
    import soundfile as sf
    from faster_whisper.audio import decode_audio
    sf.write(wav_path, decode_audio(media_path, sampling_rate=16000), 16000,
             subtype="PCM_16", format="WAV")


# Shows Whisper the writing style wanted: sentences, capitals, no "uh". It must
# not name anyone: with the speakers' names as the prompt (or hotwords), an
# 89-minute recording lost a quarter of its Q&A. Names are fixed afterwards (vocab.py).
STYLE_PROMPT = {
    "en": "Hello, and welcome. Thank you all for coming today. Let me begin with an "
          "overview of our results, and then we will take your questions.",
}


def load_model(model_path):
    """The Whisper model on the graphics card if this computer has a usable
    NVIDIA one, else on the CPU at 8-bit."""
    _add_cuda_dlls()
    from faster_whisper import WhisperModel
    from . import hardware
    dev, compute = hardware.device()
    try:
        return WhisperModel(model_path, device=dev, compute_type=compute)
    except Exception:
        if dev == "cpu":
            raise
        return WhisperModel(model_path, device="cpu", compute_type="int8")


def transcribe(wav_path, model_path, language=None, progress=None):
    """Returns a list of segments: {start, end, text, words: [{start, end, word}]}."""
    from faster_whisper.audio import decode_audio

    model = load_model(model_path)
    audio = decode_audio(wav_path)
    if not language:
        language = model.detect_language(audio, vad_filter=True, language_detection_segments=3)[0]
    prompt = STYLE_PROMPT.get(language)
    segments, info = model.transcribe(
        audio,
        language=language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        # The prompt goes in front of every 30 s window. Carrying each window's text
        # into the next instead let one unpunctuated stretch turn the last ten
        # minutes of a Q&A into lowercase run-on text with "um"s.
        initial_prompt=prompt,
        condition_on_previous_text=False,
    )
    out = []
    for s in segments:
        out.append(_seg(s))
        if progress:
            progress(0.9 * s.end / info.duration, s.text.strip())
    out = fill_gaps(model, audio, out, info.duration, info.language,
                    lambda f: progress and progress(0.9 + 0.1 * f, "Checking pauses for missed speech"))
    return out, info.language


def _seg(s, offset=0.0, words=None):
    words = s.words if words is None else words
    return {"start": s.start + offset, "end": s.end + offset, "text": s.text.strip(),
            "words": [{"start": w.start + offset, "end": w.end + offset, "word": w.word}
                      for w in (words or [])]}


def fill_gaps(model, audio, segments, duration, language, progress=None, min_gap=2.5):
    """Whisper sometimes skips a whole passage, and quiet off-mic speech (a question
    from the floor) slips past the speech filter. Transcribe every pause longer than
    min_gap again on its own, unfiltered, keeping confident words over real speech."""
    import numpy as np
    from faster_whisper.vad import get_vad_model
    sr = 16000
    vad = get_vad_model()

    def speechiness(a, b):
        """Mean speech probability over a..b (Silero, 32 ms frames)."""
        x = audio[int(a * sr):int(b * sr)]
        if len(x) < 512:
            return 0.0
        x = np.pad(x, (0, (-len(x)) % 512))
        return float(vad(x).flatten().mean())

    words = [w for s in segments for w in s["words"]]
    edges = [0.0] + [x for w in words for x in (w["start"], w["end"])] + [duration]
    gaps = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)
            if edges[i + 1] - edges[i] >= min_gap]
    found = []
    for n, (a, b) in enumerate(gaps):
        lo, hi = max(0.0, a - 0.2), min(duration, b + 0.2)
        segs, _ = model.transcribe(
            audio[int(lo * sr):int(hi * sr)], language=language, beam_size=5,
            word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
        for s in segs:
            if s.avg_logprob < -1.0 or s.compression_ratio > 2.4 or s.no_speech_prob > 0.6:
                continue
            inside = [w for w in (s.words or []) if a - 0.1 <= w.start + lo and w.end + lo <= b + 0.1]
            # Whisper "hears" things like "Thank you very much" in silence and applause
            if inside and speechiness(inside[0].start + lo, inside[-1].end + lo) >= 0.15:
                seg = _seg(s, lo, inside)
                seg["start"], seg["end"] = seg["words"][0]["start"], seg["words"][-1]["end"]
                seg["text"] = "".join(w["word"] for w in seg["words"]).strip()
                seg["refilled"] = True
                found.append(seg)
        if progress:
            progress((n + 1) / max(1, len(gaps)))
    return sorted(segments + found, key=lambda s: s["start"])
