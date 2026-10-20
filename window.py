"""Transcriber in its own window (pywebview on Edge WebView2), with no browser
and no console. Run with pythonw: `pythonw window.py` (the desktop shortcut);
the installed program (Transcriber.exe) starts here too.

The page is served by app.py's local server, which runs inside this
process, so closing the window stops it, and any transcription in progress.
If the app is already running (in a browser or another window), this window
just shows that one."""
import ctypes
import logging
import os
import sys
import threading
import time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from transcriber import paths  # noqa: E402


def _log_to_file():
    # no console: without this, anything printed (download progress bars,
    # errors) has nowhere to go and some libraries fail on it
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    f = open(paths.LOG, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = f
    logging.basicConfig(stream=f, level=logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # not a line per page poll
    print(f"\n--- started {time.strftime('%Y-%m-%d %H:%M:%S')}")


def _ask(title, text):
    """A plain Windows Yes/No box; True for Yes."""
    MB_YESNO, MB_ICONWARNING, IDYES = 0x4, 0x30, 6
    return ctypes.windll.user32.MessageBoxW(None, text, title, MB_YESNO | MB_ICONWARNING) == IDYES


def main():
    if sys.stdout is None or paths.FROZEN or "--log" in sys.argv:
        _log_to_file()
    # its own taskbar entry and icon, not grouped under Python
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Transcriber")

    import webview
    import app

    owner = not app.already_running()
    if owner:
        app.start_worker()
        threading.Thread(target=lambda: app.app.run(host="127.0.0.1", port=app.PORT, threaded=True),
                         daemon=True).start()
        for _ in range(100):  # wait until the server answers
            if app.already_running():
                break
            time.sleep(0.1)

    window = webview.create_window("Transcriber", app.URL, width=1280, height=860,
                                   min_size=(720, 520), text_select=True)

    def pick_file():
        chosen = window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Audio and video (" + ";".join(app.MEDIA) + ")", "All files (*.*)"))
        return os.path.normpath(chosen[0]) if chosen else None

    app.picker = pick_file

    def closing():
        if owner and app.busy():
            return _ask("Transcriber", "A transcription is still running. Closing the window stops "
                        "it; it will carry on from the last finished step next time.\n\nClose anyway?")
        return True

    window.events.closing += closing
    webview.start(icon=paths.app_file("assets", "transcriber.ico"), storage_path=paths.WEBVIEW_DIR)
    # the window is closed: end now rather than wait on a transcription thread
    os._exit(0)


if __name__ == "__main__":
    main()
