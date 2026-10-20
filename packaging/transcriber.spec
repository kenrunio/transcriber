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

def version_info():
    """Windows version details for Transcriber.exe: product name and version
    (SignPath requires both on every signed file), from transcriber/__init__.py."""
    import re
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct,
                                                    StringTable, VarFileInfo, VarStruct, VSVersionInfo)
    text = open(os.path.join(ROOT, "transcriber", "__init__.py"), encoding="utf-8").read()
    version = re.search(r'__version__ = "([^"]+)"', text).group(1)
    nums = tuple((list(map(int, re.findall(r"\d+", version))) + [0, 0, 0, 0])[:4])
    strings = [StringStruct(k, v) for k, v in (
        ("CompanyName", "Kenny Green Ltd"), ("FileDescription", "Transcriber"),
        ("FileVersion", version), ("InternalName", "Transcriber"),
        ("LegalCopyright", "Copyright (c) 2026 Kenny Green Ltd. MIT licence."),
        ("OriginalFilename", "Transcriber.exe"), ("ProductName", "Transcriber"),
        ("ProductVersion", version))]
    return VSVersionInfo(ffi=FixedFileInfo(filevers=nums, prodvers=nums),
                         kids=[StringFileInfo([StringTable("040904B0", strings)]),
                               VarFileInfo([VarStruct("Translation", [1033, 1200])])])


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
    version=version_info(),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Transcriber")
