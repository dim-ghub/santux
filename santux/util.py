"""Shared helpers: data paths, throttled HTTP, hashing, archives, subprocesses."""
import hashlib
import http.cookiejar
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_ID = "santux"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
FROZEN = getattr(sys, "frozen", False)


def self_command():
    """argv that runs this program again: the single binary, or `python -m santux`."""
    return [sys.executable] if FROZEN else [sys.executable, "-m", "santux"]


def child_env(env=None, itself=False):
    """Environment for programs we start. In the single binary, the bootloader points
    LD_LIBRARY_PATH, QT_PLUGIN_PATH and QML2_IMPORT_PATH at its bundled copies and adds _PYI_*
    variables; other programs (the game, Wine, protontricks, a browser) get the environment the
    binary was started with. `itself`: the child is this binary again, which unpacks afresh."""
    env = dict(os.environ if env is None else env)
    if not FROZEN:
        return env
    bundle = getattr(sys, "_MEIPASS", None)
    for k in list(env):
        if k.startswith("_PYI_") or (bundle and k != "LD_LIBRARY_PATH" and bundle in env[k]):
            del env[k]
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif bundle and bundle in env.get("LD_LIBRARY_PATH", ""):
        del env["LD_LIBRARY_PATH"]
    if itself:
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloads_dir() -> Path:
    d = data_dir() / "downloads"
    d.mkdir(exist_ok=True)
    return d


class HttpError(Exception):
    pass


class Http:
    """urllib wrapper with a per-host minimum interval and 429 back-off.

    gta5-mods.com blocks an IP for a minute after a burst of requests, so page requests to it
    are spaced out. Image and file hosts are not throttled.
    """

    def __init__(self, min_interval=None):
        self.min_interval = min_interval or {"www.gta5-mods.com": 1.2}
        self._last = {}
        self._lock = threading.Lock()
        self.cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def _wait(self, host):
        gap = self.min_interval.get(host)
        if not gap:
            return
        with self._lock:
            now = time.monotonic()
            due = self._last.get(host, 0) + gap
            if due > now:
                time.sleep(due - now)
            self._last[host] = time.monotonic()

    def open(self, url, referer=None, retries=2):
        host = urllib.parse.urlsplit(url).hostname
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        for attempt in range(retries + 1):
            self._wait(host)
            req = urllib.request.Request(url, headers=headers)
            try:
                return self._opener.open(req, timeout=60)
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries:
                    time.sleep(65)
                    continue
                raise HttpError(f"{e.code} {e.reason}: {url}") from None
            except urllib.error.URLError as e:
                if attempt < retries:
                    time.sleep(2)
                    continue
                raise HttpError(f"{e.reason}: {url}") from None

    def text(self, url, referer=None):
        with self.open(url, referer) as r:
            return r.read().decode("utf-8", "replace")

    def json(self, url):
        import json
        return json.loads(self.text(url))

    def download(self, url, dest: Path, progress=None, referer=None, sha256=None, cancel=None):
        """Download to dest (via a .part file). progress(done, total) is called as data arrives."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        h = hashlib.sha256()
        with self.open(url, referer) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if cancel and cancel.is_set():
                    raise HttpError("cancelled")
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if sha256 and h.hexdigest().lower() != sha256.lower():
            part.unlink(missing_ok=True)
            raise HttpError(f"SHA-256 mismatch for {dest.name}")
        part.replace(dest)
        return dest


http = Http()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(archive: Path, dest: Path) -> Path:
    """Extract zip/7z/rar into dest (emptied first). Uses 7z, falling back to bsdtar/unzip."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for cmd in (["7z", "x", "-y", "-bso0", "-bsp0", f"-o{dest}", str(archive)],
                ["bsdtar", "-xf", str(archive), "-C", str(dest)],
                ["unzip", "-qo", str(archive), "-d", str(dest)]):
        if shutil.which(cmd[0]):
            r = subprocess.run(cmd, capture_output=True, text=True, env=child_env())
            if r.returncode == 0:
                return dest
            last = r.stderr.strip() or r.stdout.strip()
    raise RuntimeError(f"Could not extract {archive.name}: {locals().get('last', 'no 7z, bsdtar or unzip found')}")


def run(cmd, log=None, env=None, cwd=None):
    """Run a command, streaming each output line to log(line). Returns the exit code."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         errors="replace", env=child_env(env), cwd=cwd)
    for line in p.stdout:
        if log:
            log(line.rstrip("\n"))
    return p.wait()


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def settings():
    p = data_dir() / "settings.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def set_setting(key, value):
    s = settings()
    s[key] = value
    p = data_dir() / "settings.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2))
    tmp.replace(p)
