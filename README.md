# Transcriber

Turns a video or audio recording into a transcript with named speakers, on
your own Windows computer: nothing is uploaded. It uses Whisper for the words
(on an NVIDIA graphics card if there is one, otherwise on the processor),
recognises who is speaking, lets you name the speakers and fix mistakes, and
saves the transcript as Word, text, Markdown or subtitles.

## Installing

Download **Transcriber-Setup-<version>.exe** from the
[releases page](https://github.com/kenrunio/transcriber/releases) and run it.
It installs for your user only (no administrator rights), adds Transcriber to
the Start menu and, if you tick it, the desktop.

Until releases are signed, Windows shows "Windows protected your PC": click
**More info**, then **Run anyway**.

On first start the **Models** page opens:

- Download the speech model marked **Recommended** (it suits your computer).
  Hebrew recordings do much better with the ivrit.ai models.
- On a computer with an NVIDIA card, also download **GPU support** (1.4 GB,
  NVIDIA's libraries). Without it the processor is used, which is slower.
- The speaker recognition model (needed) and the punctuation model (optional)
  are not offered for download yet; see [Making the ONNX models](#making-the-onnx-models).

Uninstalling keeps your transcripts' working files and downloaded models in
`%LOCALAPPDATA%\Transcriber`; delete that folder to remove them too.

## Using it

1. **New transcription**: choose the file and the speech model. Optional:
   language, number of speakers, and names/terms to spell right (people's
   names, company and product names, comma-separated).
2. Wait. With an NVIDIA card an hour of audio takes about 10 minutes with the
   most accurate model; the Models page shows an estimate for each model on
   your computer. Closing the window stops the app; if a transcription is
   running it asks first, and the job carries on from its last finished step
   next time.
3. **Speakers**: each voice gets a card with its longest sentence and a ▶ Listen
   button. Type the name. Giving two voices the same name joins them.
4. **Fix mistakes**: click a sentence to hear it, then move it (or the rest of
   the paragraph) to another speaker, or correct its wording. **Replace all**
   fixes a misspelling everywhere. If voices are badly mixed up, **Regroup
   voices** with the right number of speakers (this resets names and moves).
5. **Save as Word** (or text, Markdown, subtitles). The file goes next to the
   recording, named "<recording> - Transcript.docx".

The app checks GitHub for a new version once a day; turn that off on the
Models page. Problems are written to `app.log` in `%LOCALAPPDATA%\Transcriber`.

## Running from source

Needs Python 3.11 or later (`py -3.11`). Run **setup.bat** once (it makes a
virtual environment in `%USERPROFILE%\.venvs\transcription`), then
**start.bat** for the app window, or **start-browser.bat** to use it in a web
browser at http://127.0.0.1:5055. From source, NVIDIA's libraries come with
setup.bat's packages.

## Building the installer

Needs the python.org Python 3.13 (`py -3.13`; a Miniconda Python leaves DLLs
out of the build) and Inno Setup 6 (`winget install JRSoftware.InnoSetup`).
Make the build environment once, without the NVIDIA packages:

    py -3.13 -m venv %USERPROFILE%\.venvs\transcription-build
    findstr /v /b "nvidia" requirements.txt > %TEMP%\req-build.txt
    %USERPROFILE%\.venvs\transcription-build\Scripts\python -m pip install -r %TEMP%\req-build.txt -c constraints.txt pyinstaller

Then run **packaging\build.bat**. It writes `installer\Transcriber-Setup-<version>.exe`
in the project folder (kept out of git); its work files go to
`%LOCALAPPDATA%\Transcriber-build`. The installed program is about 340 MB; the
installer about 90 MB.

`constraints.txt` pins every library to the version the app was tested with
(a newer PyAV once broke audio loading); update it deliberately, with pip
freeze from a tested environment. Its NVIDIA versions must match `PACKAGES` in
`transcriber/cuda.py`. After changing libraries, regenerate
`packaging/THIRD-PARTY-NOTICES.md` with `tools/third_party_notices.py`.

## Releasing a new version

1. Raise `__version__` in `transcriber/__init__.py` and commit.
2. Tag the commit and push the tag: `git tag v0.2.0`, `git push origin v0.2.0`.

GitHub Actions (`.github/workflows/build.yml`) builds the installer, signs it
if SignPath is set up, and publishes a release with the installer attached,
which is what the app's update check looks for.

## Signing

Releases are meant to be signed through [SignPath Foundation](https://signpath.org/),
which signs open-source projects for free. Their certificate is in SignPath
Foundation's name and signs builds made by GitHub Actions. To switch it on:

1. Apply at signpath.org with the public repository. They set up a project
   with a signing policy and two artifact configurations: one for the program
   folder (signing `Transcriber.exe`) and one for the installer.
2. In the repository's Settings > Secrets and variables > Actions, add the
   variable `SIGNPATH_ORGANIZATION_ID` and the secret `SIGNPATH_API_TOKEN`, and
   make the slugs in `.github/workflows/build.yml` match the ones at SignPath.
3. Set `UPDATE_PUBLISHER = "CN=SignPath Foundation"` in
   `transcriber/__init__.py`. From that release on, the update notice offers
   **Install update**: the app downloads the installer, installs it only if
   Windows finds it validly signed by SignPath Foundation *and* it is a
   Transcriber installer, and restarts.

Local builds can be signed with your own certificate too: put the signtool
arguments in `%LOCALAPPDATA%\Transcriber-build\signing.bat` (examples at the top
of `packaging\sign.bat`).

## Making the ONNX models

The speaker recognition and punctuation models are ONNX versions of
[SpeechBrain's ECAPA model](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb)
(Apache-2.0) and
[fullstop-punctuation-multilang-large](https://huggingface.co/oliverguhr/fullstop-punctuation-multilang-large)
(MIT). Until they can be downloaded from the Models page, make them once; this
is the only part that needs PyTorch:

    py -3.11 -m venv %USERPROFILE%\.venvs\transcription-dev
    %USERPROFILE%\.venvs\transcription-dev\Scripts\python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    %USERPROFILE%\.venvs\transcription-dev\Scripts\python -m pip install -r requirements-dev.txt
    %USERPROFILE%\.venvs\transcription-dev\Scripts\python tools\export_models.py

They are written to `%LOCALAPPDATA%\Transcriber\models`.

## How it works

- `transcriber/asr.py`: PyAV (FFmpeg's libraries) pulls out 16 kHz mono audio;
  faster-whisper transcribes it with word timestamps. Then every pause over
  2.5 s is transcribed again on its own, because Whisper sometimes skips a
  passage or a quiet question from the floor; words found there are kept only
  where the voice detector hears speech (Whisper invents "Thank you very much"
  in silence). Whisper gets no names in its prompt: that lost a quarter of the
  words in a Q&A.
- `transcriber/vocab.py`: the names/terms box, applied after transcription:
  capitalised words that sound like a listed term take its spelling.
- `transcriber/punctuate.py`: Whisper sometimes writes minutes of lowercase
  run-on text; those stretches (only) get full stops, commas and capitals back
  from a punctuation model (English, German, French, Italian).
- `transcriber/diarize.py`: Silero VAD finds the speech; the ECAPA model
  fingerprints each 1.5 s window; the fingerprints are grouped by voice
  (average-linkage clustering, then each window moved to its nearest voice).
- `transcriber/models.py` + `tools/export_models.py`: the ONNX voice and
  punctuation models, run by ONNX Runtime; the app itself needs no PyTorch.
- `transcriber/catalog.json` + `catalog.py` + `hardware.py` + `cuda.py`: the
  model menu, downloads, GPU support (NVIDIA's DLLs from their PyPI wheels,
  only on computers with an NVIDIA card), and the hardware check behind the
  recommendation and speed estimates.
- `transcriber/updates.py`: the update check and installing a signed update.
- `transcriber/paths.py`: where data and the app's own files are.
- `transcriber/pipeline.py`: runs the stages (each saved, so a stopped job
  resumes) and gives every word the voice speaking at that moment, one line per
  sentence.
- `transcriber/export.py`: Word / text / Markdown / SRT.
- `app.py` + `web/index.html`: the local web app (Flask).
- `window.py`: the same page in a native window (pywebview, Edge WebView2);
  the installed program starts here.
- `packaging/`: the PyInstaller recipe, the Inno Setup script, build.bat and
  sign.bat. `.github/workflows/build.yml`: the release build.

## Licence

MIT (see LICENSE). The installer bundles other open-source software under its
own licences, listed in `packaging/THIRD-PARTY-NOTICES.md`; the models you
download keep theirs (shown on the Models page).
