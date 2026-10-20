"""Fix the spelling of names and terms after transcription.

Giving Whisper the names as a prompt made it skip whole passages, so instead the
words it wrote are matched against the list by sound: capitalised words (or
pairs of them, for full names) that sound close to a listed term are replaced
by it. With "Contoso" listed, "Kontoso" and "Contosso" become "Contoso"."""
import re
from difflib import SequenceMatcher


def _sound(s):
    s = s.lower()
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("ph", "f"), ("ck", "k"), ("ch", "k"), ("q", "k"), ("c", "k"),
                 ("z", "s"), ("y", "i"), ("w", "v")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)


def terms(vocabulary):
    """Split the free-text box into terms: commas, semicolons, full stops or new lines."""
    out = []
    for t in re.split(r"[,;\n]+|\.\s+", vocabulary or ""):
        t = re.sub(r"^(speakers?|names?|terms?)\s*:\s*", "", t.strip(), flags=re.I).strip(" .")
        if len(t) >= 3:
            out.append(t)
    return out


def _variants(vocab_terms):
    """(term, threshold): full terms, then each part of a multi-word name on its own,
    held to a stricter match."""
    out = [(t, 0.8) for t in vocab_terms]
    whole = {t.lower() for t in vocab_terms}
    for t in vocab_terms:
        parts = t.split()
        if len(parts) > 1:
            out += [(p, 0.85) for p in parts if len(p) >= 4 and p.lower() not in whole]
    return out


TOKEN = re.compile(r"[A-Z][A-Za-z'\-]+")


def correct(text, vocab_terms):
    """Returns (text, count of replacements)."""
    count = 0
    for term, threshold in sorted(_variants(vocab_terms), key=lambda v: -len(v[0].split())):
        n = len(term.split())
        target = _sound(term)
        if len(target) < 4:
            continue
        # Try every run of n capitalised words separated by spaces. Every starting
        # word is tried: in "I'm Dana Levy", "I'm Dana" must not hide "Dana Levy".
        toks = [m for m in TOKEN.finditer(text)
                if not re.match(r"[\w']", text[m.start() - 1:m.start()] or " ")]
        out, pos, i = [], 0, 0
        while i + n <= len(toks):
            run = toks[i:i + n]
            a, b = run[0].start(), run[-1].end()
            joined_by_spaces = all(text[x.end():y.start()].isspace() for x, y in zip(run, run[1:]))
            ends_word = not re.match(r"[\w']", text[b:b + 1])
            found = text[a:b]
            if found.endswith("'s") and not term.endswith("'s"):
                b -= 2  # "ComTech's": match the name, keep the 's
                found = text[a:b]
            ok = (joined_by_spaces and found != term and ends_word
                  # a lone first name at the start of a sentence is too often an
                  # ordinary word ("Admit" is not "Amit")
                  and not (threshold > 0.8 and re.search(r"(^|[.?!]\s+)$", text[:a])))
            if ok:
                snd = _sound(found)
                ok = snd[:1] == target[:1] and SequenceMatcher(None, snd, target).ratio() >= threshold
            if ok:
                out += [text[pos:a], term]
                pos = b
                count += 1
                i += n
            else:
                i += 1
        text = "".join(out) + text[pos:]
    return text, count
