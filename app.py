"""Transcriber: a small local web app. Run start.bat (or `python app.py`) and it
opens http://127.0.0.1:5055 in the browser. Jobs run one at a time on this PC."""
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import webbrowser

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from transcriber import __version__, catalog, export, hardware, pipeline, updates

PORT = 5055
from transcriber.paths import app_file
app = Flask(__name__, static_folder=None)
work = queue.Queue()
edit_lock = threading.Lock()
picker = None  # set by window.py: shows a file dialog, returns the chosen path
MEDIA = ("*.mp4", "*.m4a", "*.mp3", "*.wav", "*.mov", "*.mkv", "*.webm", "*.aac",
         "*.flac", "*.ogg", "*.wma", "*.avi", "*.m4v")


def worker():
    while True:
        job = work.get()
        job.run()


def job_or_404(job_id):
    job = pipeline.Job(job_id)
    if not os.path.isdir(job.dir) or "/" in job_id or "\\" in job_id or ".." in job_id:
        abort(404)
    return job


@app.get("/")
def index():
    return send_from_directory(app_file("web"), "index.html")


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app_file("assets"), "transcriber.ico")


@app.get("/api/jobs")
def jobs():
    return jsonify([j.meta for j in pipeline.list_jobs()])


@app.post("/api/jobs")
def new_job():
    d = request.get_json()
    source = (d.get("source") or "").strip().strip('"')
    if not os.path.isfile(source):
        return jsonify(error=f"File not found: {source}"), 400
    model = d.get("model") or hardware.recommended_speech()
    if not catalog.path(model):
        return jsonify(error="That speech model is not installed. Download it on the Models page."), 400
    if not catalog.path("ecapa"):
        return jsonify(error="The speaker recognition model is not installed (Models page)."), 400
    n = d.get("num_speakers")
    job = pipeline.create_job(source, language=d.get("language") or None,
                              vocabulary=d.get("vocabulary", ""),
                              num_speakers=int(n) if n else None, model=model)
    work.put(job)
    return jsonify(job.meta)


@app.post("/api/browse")
def browse():
    if picker:  # the app window's own file dialog (window.py sets this)
        return jsonify(path=picker() or "")
    # Browser mode: the native Windows file picker, in its own process so Tk
    # stays off Flask's threads.
    code = ("import tkinter as tk, tkinter.filedialog as fd; r=tk.Tk(); r.withdraw(); "
            "r.attributes('-topmost', True); print(fd.askopenfilename(title='Choose a recording', "
            "filetypes=[('Audio and video', '*.mp4 *.m4a *.mp3 *.wav *.mov *.mkv *.webm *.aac "
            "*.flac *.ogg *.wma *.avi *.m4v'), ('All files', '*.*')]))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return jsonify(path=os.path.normpath(out.stdout.strip()) if out.stdout.strip() else "")


@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    job = job_or_404(job_id)
    return jsonify(meta=job.meta, transcript=with_breaks(job.transcript))


def with_breaks(t):
    """The transcript plus the ids of lines that start a paragraph, so the page
    shows the paragraphs the saved files will have."""
    if t:
        t["breaks"] = sorted(export.paragraph_starts(t))
    return t


@app.delete("/api/jobs/<job_id>")
def delete_job(job_id):
    job = job_or_404(job_id)
    if job.meta.get("stage") not in ("done", "error"):
        return jsonify(error="That job is still running."), 409
    shutil.rmtree(job.dir)
    return jsonify(ok=True)


@app.post("/api/jobs/<job_id>/resume")
def resume(job_id):
    job = job_or_404(job_id)
    job.status("queued", 0, "Waiting to start")
    work.put(job)
    return jsonify(job.meta)


@app.get("/api/jobs/<job_id>/audio")
def audio(job_id):
    path = job_or_404(job_id).path("audio.wav")
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="audio/wav", conditional=True)


@app.put("/api/jobs/<job_id>/speakers")
def rename(job_id):
    """Body: [{id, name}] for any speakers to rename; a new id adds a speaker."""
    job = job_or_404(job_id)
    with edit_lock:
        t = job.transcript
        by_id = {s["id"]: s for s in t["speakers"]}
        for s in request.get_json():
            name = (s.get("name") or "").strip() or f"Speaker {s['id'] + 1}"
            if s["id"] in by_id:
                by_id[s["id"]]["name"] = name
            else:
                t["speakers"].append({"id": int(s["id"]), "name": name, "talk_s": 0})
        job.save_transcript(t)
    return jsonify(with_breaks(t))


@app.put("/api/jobs/<job_id>/lines")
def reassign(job_id):
    """Body: {ids: [line ids], speaker}: give those lines to that speaker."""
    job = job_or_404(job_id)
    d = request.get_json()
    with edit_lock:
        t = job.transcript
        ids = set(d["ids"])
        for ln in t["lines"]:
            if ln["id"] in ids:
                ln["speaker"] = int(d["speaker"])
        talk = {}
        for ln in t["lines"]:
            talk[ln["speaker"]] = talk.get(ln["speaker"], 0) + ln["end"] - ln["start"]
        for s in t["speakers"]:
            s["talk_s"] = round(talk.get(s["id"], 0), 1)
        job.save_transcript(t)
    return jsonify(with_breaks(t))


@app.put("/api/jobs/<job_id>/text")
def edit_text(job_id):
    """Body: {id, text}: rewrite one sentence."""
    job = job_or_404(job_id)
    d = request.get_json()
    with edit_lock:
        t = job.transcript
        for ln in t["lines"]:
            if ln["id"] == d["id"]:
                ln["text"] = d.get("text", "").strip()
        job.save_transcript(t)
    return jsonify(with_breaks(t))


@app.post("/api/jobs/<job_id>/replace")
def replace(job_id):
    """Body: {find, replace}: the exact phrase as whole words, any capitalisation."""
    job = job_or_404(job_id)
    d = request.get_json()
    find = d.get("find", "").strip()
    if not find:
        return jsonify(error="Nothing to find."), 400
    pat = re.compile(r"(?<!\w)" + re.escape(find) + r"(?!\w)", re.IGNORECASE)
    repl = d.get("replace", "")
    count = 0
    with edit_lock:
        t = job.transcript
        for ln in t["lines"]:
            ln["text"], n = pat.subn(lambda _: repl, ln["text"])
            count += n
        job.save_transcript(t)
    return jsonify(transcript=with_breaks(t), count=count)


@app.post("/api/jobs/<job_id>/regroup")
def regroup(job_id):
    job = job_or_404(job_id)
    n = request.get_json().get("num_speakers")
    with edit_lock:
        job.regroup(int(n) if n else None)
    return jsonify(with_breaks(job.transcript))


@app.get("/api/models")
def models_list():
    info = hardware.detect()
    dev, compute = hardware.device(info)
    return jsonify(system=dict(info, device=dev, compute=compute, version=__version__,
                               recommended=hardware.recommended_speech(info)),
                   models=catalog.listing())


@app.post("/api/models/<model_id>/download")
def model_download(model_id):
    m = catalog.get(model_id)
    need = m["size_mb"] / 1024 + 0.5
    if hardware.detect()["disk_free_gb"] < need:
        return jsonify(error=f"Not enough free disk space: this model needs about {need:.1f} GB."), 409
    try:
        catalog.start_download(model_id)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.post("/api/models/<model_id>/cancel")
def model_cancel(model_id):
    catalog.cancel_download(model_id)
    return jsonify(ok=True)


@app.delete("/api/models/<model_id>")
def model_remove(model_id):
    if busy():
        return jsonify(error="Wait until the running transcription finishes."), 409
    catalog.remove(model_id)
    return jsonify(ok=True)


@app.get("/api/update")
def update_status():
    return jsonify(updates.status(force=request.args.get("force") == "1"))


@app.put("/api/update/settings")
def update_settings():
    d = request.get_json()
    allowed = {k: d[k] for k in ("check_updates", "skipped_version") if k in d}
    updates.save_settings(**allowed)
    return jsonify(updates.status())


@app.post("/api/update/install")
def update_install():
    if busy():
        return jsonify(error="Wait until the running transcription finishes."), 409

    def quit_app():
        # the installer is running and replaces this program's files: get out of its way
        threading.Timer(1.5, lambda: os._exit(0)).start()
    try:
        updates.start_install(quit_app)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.post("/api/open")
def open_link():
    """Opens a release page or installer link in the user's own browser (not in
    the app window). Only GitHub addresses, so the page cannot open anything else."""
    url = request.get_json().get("url", "")
    found = updates.settings().get("last_check") or {}
    if not re.match(r"https://github\.com/", url) and url not in (found.get("page"), found.get("installer")):
        return jsonify(error="Not a GitHub link."), 400
    webbrowser.open(url)
    return jsonify(ok=True)


@app.post("/api/jobs/<job_id>/export")
def do_export(job_id):
    job = job_or_404(job_id)
    fmt = request.get_json().get("format", "docx")
    if fmt not in export.FORMATS:
        abort(400)
    m = job.meta
    out_dir = os.path.dirname(m["source"])
    try:
        path = export.export(job.transcript, m["title"], fmt, out_dir)
    except PermissionError:
        return jsonify(error="Couldn't write the file. Is it open in Word?"), 409
    return jsonify(path=path)


@app.post("/api/reveal")
def reveal():
    path = request.get_json().get("path", "")
    if os.path.exists(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    return jsonify(ok=True)


def already_running():
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


URL = f"http://127.0.0.1:{PORT}"


def busy():
    """True while a job is queued or running."""
    return any(j.meta.get("stage") not in ("done", "error") for j in pipeline.list_jobs())


def start_worker():
    threading.Thread(target=worker, daemon=True).start()
    for job in reversed(pipeline.list_jobs()):  # pick up jobs a restart interrupted
        if job.meta.get("stage") not in ("done", "error"):
            work.put(job)


def main():
    """Browser mode: `python app.py` (start-browser.bat)."""
    if already_running():
        # A second start must not pick up the first one's jobs and run them twice.
        print(f"Transcriber is already running; opening {URL}")
        if "--no-browser" not in sys.argv:
            webbrowser.open(URL)
        return
    start_worker()
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    print(f"Transcriber running at {URL}  (close this window to stop it)")
    app.run(host="127.0.0.1", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
