# Roadmap

The aim: a Windows app that installs like any other, lets the user pick models
from a menu, downloads only what that computer needs, and is open source.

## Done

1. **Its own window.** `window.py` shows the app in a native window
   (pywebview on Edge WebView2); it asks before closing while a transcription
   is running. It is the only way to run the app.
2. **No PyTorch.** The speaker recognition (ECAPA) and punctuation models run
   through ONNX Runtime. `tools/export_models.py` makes the ONNX files and is
   the only part needing PyTorch. On a 90-minute test recording the ONNX
   versions gave exactly the PyTorch results: every one of 5,024 voice windows
   assigned to the same speaker (embedding cosine ≥ 0.999999), the same label
   on all 10,768 words for punctuation, and the same 714-line transcript.
   Export notes: `torch.onnx.export(..., dynamo=True, opset_version=18)` (the
   older exporter cannot export the STFT); the punctuation model needs
   `external_data=True` (it is over 2 GB).
3. **Hardware check and model menu.** The app detects the NVIDIA card, memory,
   cores and disk, recommends a speech model and estimates its speed; without a
   usable card it runs on the processor. `transcriber/catalog.json` lists the
   models (Whisper sizes, turbo, distil English, ivrit.ai Hebrew, and the two
   ONNX models from huggingface.co/kenrunio, each file pinned by SHA-256) with
   size, languages, licence and source; the Models page downloads and removes
   them. Tested from Hugging Face into an empty data folder: both ONNX models
   downloaded and verified, then a transcription with them.
4. **Installer.** `packaging\build.bat` (or the GitHub Actions build) makes
   `Transcriber-Setup-<version>.exe`: about 90 MB, installs per user without
   admin rights. No PyTorch, NVIDIA libraries or ffmpeg inside; on computers
   with an NVIDIA card the Models page offers "GPU support" (NVIDIA's
   cuBLAS/cuDNN from PyPI, 1.4 GB). `constraints.txt` pins tested versions.
5. **Update notices.** The app checks the repository's latest release once a
   day and offers it (Download, What's new, Later); the check can be turned
   off. Releases are built and published by `.github/workflows/build.yml`
   from a version tag.
6. **Signing, ready.** Builds sign Transcriber.exe, Setup and the uninstaller
   when a certificate is configured (`packaging\sign.bat` locally, SignPath in
   GitHub Actions). With `UPDATE_PUBLISHER` set, the app installs updates
   itself, but only installers that Windows finds validly signed by that
   publisher and that identify as Transcriber. Tested with a self-made
   certificate (refused, as it should be) and with installing over a running
   copy (closed, installed, restarted).

## Next

- **SignPath Foundation**: apply with the public repository; then add the
  repository variable and secret, match the slugs in the workflow, and set
  `UPDATE_PUBLISHER = "CN=SignPath Foundation"` (README, Signing).

- **Try it on a second computer**, including one without an NVIDIA card, and
  installing a new version over an old one.
- The bundled FFmpeg (inside PyAV) includes the GPL-licensed x264 and x265
  encoders, which Transcriber does not use. They are listed in
  THIRD-PARTY-NOTICES.md; a trimmed FFmpeg build without them would avoid
  shipping GPL code at all.
