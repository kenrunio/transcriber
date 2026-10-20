"""Is there a newer version? Asks GitHub for the latest release of UPDATE_REPO,
at most once a day (or when asked), and says so. Turned off in settings, or
while UPDATE_REPO is empty.

The installed program can also install it: download the installer, check that
Windows finds it validly signed by UPDATE_PUBLISHER, run it silently and quit;
the installer starts the new version. Without UPDATE_PUBLISHER (no signed
builds yet), or running from source, only a download link is offered.

A release is a GitHub release tagged vX.Y.Z with Transcriber-Setup-X.Y.Z.exe
attached (.github/workflows/build.yml makes one from a version tag)."""
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.request

from . import UPDATE_PUBLISHER, UPDATE_REPO, __version__
from .paths import DATA_DIR, FROZEN

SETTINGS = os.path.join(DATA_DIR, "settings.json")
DAY = 24 * 3600


def _api_url():
    # TRANSCRIBER_UPDATE_URL points the check somewhere else (used for testing)
    if os.environ.get("TRANSCRIBER_UPDATE_URL"):
        return os.environ["TRANSCRIBER_UPDATE_URL"]
    return f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest" if UPDATE_REPO else None


def settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s = json.load(f)
    except (FileNotFoundError, ValueError):
        s = {}
    s.setdefault("check_updates", True)
    return s


def save_settings(**changes):
    s = settings()
    s.update(changes)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    return s


def version_tuple(v):
    """'v1.2.10' -> (1, 2, 10); anything unreadable sorts lowest."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", (v or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"Transcriber/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        rel = json.load(r)
    installer = next((a for a in rel.get("assets", [])
                      if re.match(r"Transcriber-Setup-.*\.exe$", a.get("name", ""))), None)
    return {"latest": rel.get("tag_name", "").lstrip("v"),
            "page": rel.get("html_url"),
            "installer": installer and installer.get("browser_download_url"),
            "notes": (rel.get("body") or "").strip()[:1500]}


def status(force=False):
    """What the page shows: current version, whether checks are on, and the
    latest release if one was found (cached for a day)."""
    s = settings()
    url = _api_url()
    out = {"current": __version__, "enabled": bool(url) and s["check_updates"],
           "configured": bool(url), "skipped": s.get("skipped_version")}
    if not out["enabled"]:
        return out
    cached = s.get("last_check") or {}
    if force or time.time() - cached.get("at", 0) > DAY:
        try:
            cached = dict(_fetch(url), at=time.time())
        except Exception as e:
            cached = dict(cached, error=f"{type(e).__name__}: {e}", at=time.time())
        else:
            cached.pop("error", None)
        save_settings(last_check=cached)
    out.update(cached)
    out["newer"] = bool(cached.get("latest")) and version_tuple(cached["latest"]) > version_tuple(__version__)
    out["can_install"] = bool(FROZEN and UPDATE_PUBLISHER and out["newer"] and cached.get("installer"))
    out["install"] = dict(install_state) if install_state else None
    return out


# -- installing ------------------------------------------------------------------

install_state = {}  # {stage: download|verify|starting|error, done, total, error}


def signature(path):
    """(status, signer subject) from Windows' own Authenticode check. Status
    "Valid" means signed, unaltered, and by a certificate Windows trusts."""
    return _inspect(path)[:2]


def _inspect(path):
    """(signature status, signer subject, product name in the file's version info)."""
    cmd = ("$s = Get-AuthenticodeSignature -LiteralPath $env:TR_FILE; "
           "$v = (Get-Item -LiteralPath $env:TR_FILE).VersionInfo; "
           "@{status = [string]$s.Status; subject = [string]$s.SignerCertificate.Subject; "
           "product = [string]$v.ProductName} | ConvertTo-Json")
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                         capture_output=True, text=True, timeout=60, creationflags=0x08000000,
                         env=dict(os.environ, TR_FILE=path))
    d = json.loads(out.stdout or "{}")
    return d.get("status") or "Unknown", d.get("subject") or "", d.get("product") or ""


def trusted(path, publisher=None, product="Transcriber"):
    """Whether path is validly signed by the expected publisher and is this
    app's installer; (ok, reason). The product check matters with SignPath
    Foundation, whose one certificate signs many open-source projects."""
    publisher = UPDATE_PUBLISHER if publisher is None else publisher
    if not publisher:
        return False, "No publisher is set to check the signature against."
    status, subject, prod = _inspect(path)
    if status != "Valid":
        return False, f"The download's signature is not valid (Windows says: {status})."
    if publisher.lower() not in subject.lower():
        return False, f"The download is signed by someone else ({subject})."
    if product and prod.strip() != product:
        return False, f"The download is not a {product} installer (it says: {prod or 'nothing'})."
    return True, subject


def start_install(on_exit):
    """Download, check and run the installer in the background. on_exit() is
    called once the installer is running, to close this app."""
    st = status()
    if not st.get("can_install"):
        raise ValueError("Installing updates from the app needs a signed release.")
    if install_state.get("stage") in ("download", "verify", "starting"):
        return
    install_state.clear()
    install_state.update(stage="download", done=0, total=0, error=None)
    threading.Thread(target=_install, args=(st["installer"], on_exit), daemon=True).start()


def _install(url, on_exit):
    try:
        if not url.startswith("https://github.com/"):
            raise ValueError("The installer link is not on GitHub.")
        path = os.path.join(tempfile.mkdtemp(prefix="transcriber-update-"), url.rsplit("/", 1)[-1])
        req = urllib.request.Request(url, headers={"User-Agent": f"Transcriber/{__version__}"})
        with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
            install_state["total"] = int(r.headers.get("Content-Length") or 0)
            while True:
                block = r.read(1 << 20)
                if not block:
                    break
                f.write(block)
                install_state["done"] += len(block)
        install_state["stage"] = "verify"
        ok, reason = trusted(path)
        if not ok:
            os.remove(path)
            raise ValueError(reason)
        install_state["stage"] = "starting"
        run_installer(path)
        on_exit()
    except Exception as e:
        install_state.update(stage="error", error=str(e))


def run_installer(path):
    """Silent install over this one; /UPDATE=1 makes it start the new version."""
    subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/UPDATE=1"],
                     close_fds=True)
