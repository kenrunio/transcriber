# PyInstaller recipe for the installed program (one folder, no console).
# Built by packaging\build.bat, in an environment without PyTorch or NVIDIA's
# libraries (those are downloaded by the app on computers with an NVIDIA card).
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "web"), "web"),
    (os.path.join(ROOT, "assets", "transcriber.ico"), "assets"),
    (os.path.join(ROOT, "transcriber", "catalog.json"), "transcriber"),
]
datas += collect_data_files("faster_whisper")      # the Silero speech-detection model
datas += collect_data_files("webview")             # WebView2 loader and JS
binaries = collect_dynamic_libs("ctranslate2")      # the speech engine
binaries += collect_dynamic_libs("onnxruntime")

a = Analysis(
    [os.path.join(ROOT, "window.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=["webview.platforms.winforms", "webview.platforms.edgechromium", "clr",
                   "sklearn.cluster", "app"],
    excludes=["torch", "torchaudio", "speechbrain", "transformers", "tensorflow", "matplotlib",
              "tkinter", "IPython", "notebook", "nvidia"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Transcriber",
    icon=os.path.join(ROOT, "assets", "transcriber.ico"),
    console=False,
    version=os.path.join(SPECPATH, "version_info.txt") if os.path.exists(
        os.path.join(SPECPATH, "version_info.txt")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Transcriber")
