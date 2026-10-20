"""Where the app keeps its data (jobs, models, GPU libraries, log), and where its
own files are when it runs as an installed program.

Data goes in %LOCALAPPDATA%\\Transcriber, except on a computer that already has
the folder the app used before it was installable (%USERPROFILE%\\.cache\\
transcription): that one is kept, so its jobs and models carry on."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)  # running as the installed program
# the app's own files: web page, icon, catalogue (PyInstaller unpacks them here)
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_old = os.path.join(os.path.expanduser("~"), ".cache", "transcription")
_new = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Transcriber")
DATA_DIR = os.environ.get("TRANSCRIBER_DATA") or (_old if os.path.isdir(_old) else _new)

JOBS_DIR = os.path.join(DATA_DIR, "jobs")
MODELS_DIR = os.path.join(DATA_DIR, "models")
CUDA_DIR = os.path.join(DATA_DIR, "cuda")  # NVIDIA libraries, downloaded on demand
LOG = os.path.join(DATA_DIR, "app.log")
WEBVIEW_DIR = os.path.join(DATA_DIR, "webview")


def app_file(*parts):
    return os.path.join(APP_DIR, *parts)
