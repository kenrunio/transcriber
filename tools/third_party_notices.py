"""Writes packaging/THIRD-PARTY-NOTICES.md: the software the installer bundles
and its licences. Run with the build environment's Python before a release:

    %USERPROFILE%\\.venvs\\transcription-build\\Scripts\\python tools\\third_party_notices.py

Python packages are read from the environment's own records; native libraries
that come inside those packages (FFmpeg in PyAV and so on) are listed by hand
below, because their licences are not in the package records."""
import importlib.metadata as md
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "packaging", "THIRD-PARTY-NOTICES.md")
SKIP = {"pip", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile", "setuptools",
        "packaging", "pywin32-ctypes"}  # build tools, not in the program
LICENCE_FIXES = {"clr_loader": "MIT"}  # packages whose records do not state it

NATIVE = [
    ("Python", "3.13", "PSF-2.0", "https://www.python.org/", "the interpreter, python313.dll"),
    ("FFmpeg libraries (in PyAV)", "8.1", "LGPL-3.0-or-later", "https://ffmpeg.org/",
     "avcodec, avformat, avutil, ...; source: https://ffmpeg.org/download.html, build: https://github.com/PyAV-Org/pyav-ffmpeg"),
    ("x264 (in PyAV)", "", "GPL-2.0-or-later", "https://www.videolan.org/developers/x264.html",
     "H.264 encoder linked by FFmpeg; not used by Transcriber; source: https://code.videolan.org/videolan/x264"),
    ("x265 (in PyAV)", "", "GPL-2.0-or-later", "https://www.videolan.org/developers/x265.html",
     "H.265 encoder linked by FFmpeg; not used by Transcriber; source: https://bitbucket.org/multicoreware/x265_git"),
    ("LAME (in PyAV)", "", "LGPL-2.0-or-later", "https://lame.sourceforge.io/", ""),
    ("libvpx, dav1d, SVT-AV1, Opus, libwebp, opencore-amr (in PyAV)", "", "BSD-style / Apache-2.0",
     "https://github.com/PyAV-Org/pyav-ffmpeg", "codec libraries linked by FFmpeg"),
    ("libsndfile (in soundfile)", "", "LGPL-2.1-or-later", "https://libsndfile.github.io/libsndfile/", ""),
    ("OpenBLAS (in NumPy and SciPy)", "", "BSD-3-Clause", "https://www.openblas.net/", ""),
    ("Intel OpenMP runtime, libiomp5md (in CTranslate2)", "", "Intel Simplified Software License",
     "https://github.com/OpenNMT/CTranslate2", ""),
    ("OpenSSL", "3", "Apache-2.0", "https://www.openssl.org/", "libcrypto, libssl"),
    ("SQLite", "", "Public domain", "https://www.sqlite.org/", ""),
    ("Microsoft Edge WebView2 loader (in pywebview)", "", "Microsoft WebView2 SDK licence (BSD-style)",
     "https://www.nuget.org/packages/Microsoft.Web.WebView2", ""),
]


def licence(dist):
    m = dist.metadata
    lic = m.get("License-Expression") or ""
    if not lic:
        classifiers = [c.split("::")[-1].strip() for c in m.get_all("Classifier") or []
                       if c.startswith("License ::")]
        lic = ", ".join(classifiers) or (m.get("License") or "").splitlines()[0][:80] if (
            classifiers or m.get("License")) else "see project"
    return lic.replace("|", "/")


def homepage(dist):
    m = dist.metadata
    for url in m.get_all("Project-URL") or []:
        label, _, link = url.partition(",")
        if re.search(r"home|source|repository|github", label, re.I):
            return link.strip()
    return m.get("Home-page") or ""


def main():
    rows = []
    for dist in md.distributions():
        name = dist.metadata["Name"]
        if not name or name.lower() in SKIP:
            continue
        rows.append((name, dist.version, LICENCE_FIXES.get(name) or licence(dist), homepage(dist)))
    rows.sort(key=lambda r: r[0].lower())
    lines = ["# Third-party software in the Transcriber installer", "",
             "Transcriber itself is MIT-licensed (LICENSE). The installer bundles the",
             "software below, each under its own licence. The speech, speaker and",
             "punctuation models are not bundled: users download the ones they choose,",
             "and the Models page shows each one's licence. NVIDIA's GPU libraries are",
             "not bundled either; the app downloads them from PyPI on request.", "",
             "## Python packages", "", "| Package | Version | Licence | Project |", "|---|---|---|---|"]
    lines += [f"| {n} | {v} | {l} | {h} |" for n, v, l, h in rows]
    lines += ["", "## Native libraries inside those packages", "",
              "| Library | Version | Licence | Project | Notes |", "|---|---|---|---|---|"]
    lines += [f"| {n} | {v} | {l} | {h} | {note} |" for n, v, l, h, note in NATIVE]
    lines += ["", "The full licence texts are in each package's folder inside the installed",
              "program (`_internal\\<package>*.dist-info`), and at the projects above. The",
              "source code of the LGPL and GPL libraries is available from the links given.", ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{OUT}: {len(rows)} packages, {len(NATIVE)} native libraries")


if __name__ == "__main__":
    main()
