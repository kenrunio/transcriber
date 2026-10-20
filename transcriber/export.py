"""Transcript -> Word, text, Markdown, subtitles. Speakers given the same name
count as one speaker; consecutive lines by one speaker form one paragraph."""
import os


def stamp(t, millis=False):
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    if millis:
        return f"{h:02d}:{m:02d}:{s:02d},{int(round((t - int(t)) * 1000)):03d}"
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _names(transcript):
    return {s["id"]: s["name"] for s in transcript["speakers"]}


def paragraph_starts(transcript):
    """Ids of lines that start a new paragraph inside one speaker's turn.

    Breaks go after a sentence, where the speaker paused, and grow more willing
    the longer the paragraph gets. On a 90-minute test recording half the pauses
    between sentences were under 0.2 s and one in ten over 1.3 s."""
    names = _names(transcript)
    lines = [l for l in transcript["lines"] if l["text"]]
    starts, words = set(), 0
    for prev, ln in zip(lines, lines[1:]):
        words += len(prev["text"].split())
        if names.get(prev["speaker"]) != names.get(ln["speaker"]):
            words = 0  # a new turn starts its own paragraph anyway
            continue
        if not prev["text"].endswith((".", "?", "!")):
            continue
        pause = ln["start"] - prev["end"]
        if ((words >= 30 and pause >= 3.0) or (words >= 60 and pause >= 1.2)
                or (words >= 120 and pause >= 0.6) or words >= 180):
            starts.add(ln["id"])
            words = 0
    return starts


def paragraphs(transcript):
    """Turns: consecutive lines of one speaker name, each with its paragraphs."""
    names = _names(transcript)
    starts = paragraph_starts(transcript)
    out = []
    for ln in transcript["lines"]:
        if not ln["text"]:
            continue  # a sentence whose wording was cleared
        name = names.get(ln["speaker"], f"Speaker {ln['speaker'] + 1}")
        if out and out[-1]["name"] == name:
            turn = out[-1]
            turn["end"] = ln["end"]
            if ln["id"] in starts:
                turn["paras"].append(ln["text"])
            else:
                turn["paras"][-1] += " " + ln["text"]
        else:
            out.append({"name": name, "start": ln["start"], "end": ln["end"], "paras": [ln["text"]]})
    for turn in out:
        turn["text"] = " ".join(turn["paras"])
    return out


def to_txt(transcript, title):
    parts = [title, ""]
    for p in paragraphs(transcript):
        parts.append(f"[{stamp(p['start'])}] {p['name']}:")
        for para in p["paras"]:
            parts += [para, ""]
    return "\n".join(parts)


def to_md(transcript, title):
    parts = [f"# {title}", ""]
    for p in paragraphs(transcript):
        parts += [f"**{p['name']}** _[{stamp(p['start'])}]_", ""]
        for para in p["paras"]:
            parts += [para, ""]
    return "\n".join(parts)


def to_srt(transcript):
    names = {s["id"]: s["name"] for s in transcript["speakers"]}
    parts = []
    for i, ln in enumerate((l for l in transcript["lines"] if l["text"]), 1):
        parts += [str(i), f"{stamp(ln['start'], True)} --> {stamp(ln['end'], True)}",
                  f"{names.get(ln['speaker'], '')}: {ln['text']}", ""]
    return "\n".join(parts)


def to_docx(transcript, title, path):
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(title, level=1)
    for p in paragraphs(transcript):
        head = doc.add_paragraph()
        head.paragraph_format.space_after = Pt(0)
        head.paragraph_format.keep_with_next = True
        r = head.add_run(p["name"])
        r.bold = True
        r = head.add_run(f"   {stamp(p['start'])}")
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        for para in p["paras"]:
            doc.add_paragraph(para)
    doc.save(path)


FORMATS = {"docx": "Word", "txt": "Text", "md": "Markdown", "srt": "Subtitles"}


def export(transcript, title, fmt, out_dir):
    """Writes "<title> - Transcript.<fmt>" next to the recording. If that file is
    open in another program (Word locks it), writes "... (2)", "... (3)" instead."""
    for n in range(1, 20):
        suffix = "" if n == 1 else f" ({n})"
        path = os.path.join(out_dir, f"{title} - Transcript{suffix}.{fmt}")
        try:
            if fmt == "docx":
                to_docx(transcript, title, path)
            else:
                text = {"txt": lambda: to_txt(transcript, title),
                        "md": lambda: to_md(transcript, title),
                        "srt": lambda: to_srt(transcript)}[fmt]()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            return path
        except PermissionError:
            continue
    raise PermissionError(path)
