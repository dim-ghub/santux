"""GTAVXR (the VR mod by LVL, https://github.com/LVL-VR/GTAVXR) on Proton.

GTAVXR is a Windows app, the "Suite", that installs a rebuilt game exe and launches it with
OpenXR. Steps to get it working under Proton:

1. .NET Framework 4.8 in the prefix (the Suite is a .NET app).
2. GTAVXR.exe (the Suite) next to GTA5.exe. The VR profile launches it instead of PlayGTAV.exe.
3. The user runs the Suite once and clicks Install GTAVXR (it downloads its own files).
4. Wine fix: the Suite's patched exe has a bogus PE export directory that Windows tolerates and
   Wine crashes on. Clearing it gives the same result Windows does; the Suite's records of the
   exe's hash are updated so it doesn't refuse to launch it.
5. tar.exe: the Suite unpacks imported mods with Windows' tar.exe, which Wine lacks.
6. SteamVR (or another OpenXR runtime with an OpenVR shim) running before launch, so Proton
   sets up wineopenxr.
"""
import glob
import hashlib
import json
import os
import shutil
import struct
import time
from pathlib import Path

from . import game as gamemod, prefix, util

REPO = "LVL-VR/GTAVXR"
SUITE_EXE = "GTAVXR.exe"
GAME_EXE = "GTAVXR_SourceBaseline.exe"
STEAMVR_APPID = 250820


def suite_data(game):
    return game.prefix / "drive_c/users/steamuser/AppData/Local/GTAVXR/Suite"


def _pe_export_dir(path):
    b = path.read_bytes()
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    if b[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", b, pe + 24)[0] != 0x20B:
        raise RuntimeError(f"{path.name} isn't a 64-bit PE image")
    off = pe + 24 + 112
    return b, off, struct.unpack_from("<II", b, off)


def steamvr_installed(game):
    return any((lib / "steamapps" / f"appmanifest_{STEAMVR_APPID}.acf").is_file()
               for lib in gamemod.steam_libraries())


def steamvr_running():
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
            except OSError:
                continue
            if b"vrserver" in cmd or b"vrcompositor" in cmd:
                return True
    return False


def status(game):
    """Each setup step with its state ("ok"/"missing"/"info") and a detail line."""
    pfx_ok = game.has_prefix
    steps = []
    steps.append({"id": "dotnet48", "name": ".NET Framework 4.8",
                  "state": "ok" if pfx_ok and prefix.dotnet48_installed(game) else "missing",
                  "detail": "The Suite is a .NET Framework app."})
    ver = (util.data_dir() / "gtavxr" / "VERSION")
    have_suite = (game.folder / SUITE_EXE).is_file()
    steps.append({"id": "suite", "name": "GTAVXR Suite",
                  "state": "ok" if have_suite else "missing",
                  "detail": (f"Release {ver.read_text().strip()}" if ver.is_file() else "In the game folder") if have_suite
                  else "Downloads the latest GTAVXR.exe from GitHub into the game folder."})
    installed = (game.folder / GAME_EXE).is_file()
    steps.append({"id": "install", "name": "Install GTAVXR (in the Suite)",
                  "state": "ok" if installed else "missing",
                  "detail": "Done." if installed else
                  "Opens the Suite: choose the GTA V folder, keep the default data location, click Install GTAVXR, then close it."})
    fixed = False
    if installed:
        try:
            _, _, (rva, size) = _pe_export_dir(game.folder / GAME_EXE)
            fixed = rva == 0 and size == 0
        except Exception:
            fixed = False
    steps.append({"id": "fix", "name": "Wine startup fix",
                  "state": "ok" if fixed else ("missing" if installed else "info"),
                  "detail": "Applied." if fixed else
                  "Clears a bogus export table in GTAVXR's game exe that crashes it under Wine. Re-apply after "
                  "updating GTAVXR or using the Suite's Check files."})
    tar = game.prefix / "drive_c/windows/system32/tar.exe"
    steps.append({"id": "tar", "name": "tar.exe for mod imports",
                  "state": "ok" if tar.is_file() else "missing",
                  "detail": "Lets the Suite's Mods → Add mod unpack .zip and .oiv files."})
    svr = steamvr_installed(game)
    steps.append({"id": "steamvr", "name": "SteamVR",
                  "state": "ok" if svr else "info",
                  "detail": ("Installed. Start it with the headset connected before launching the VR profile."
                             if svr else "Install SteamVR in Steam (or another OpenXR runtime with xrizer).")})
    return steps


def download_suite(game, log=print):
    rel = util.http.json(f"https://api.github.com/repos/{REPO}/releases/latest")
    asset = next((a for a in rel["assets"] if a["name"] == SUITE_EXE), None)
    if not asset:
        raise RuntimeError(f"The latest GTAVXR release has no {SUITE_EXE}")
    sha = (asset.get("digest") or "").removeprefix("sha256:") or None
    d = util.data_dir() / "gtavxr"
    d.mkdir(parents=True, exist_ok=True)
    log(f"Downloading GTAVXR {rel['tag_name']}")
    util.http.download(asset["browser_download_url"], d / SUITE_EXE, sha256=sha)
    shutil.copy2(d / SUITE_EXE, game.folder / SUITE_EXE)
    (d / "VERSION").write_text(rel["tag_name"])
    log(f"Copied {SUITE_EXE} into the game folder")


def open_suite(game, log=print):
    exe = game.folder / SUITE_EXE
    if not exe.is_file():
        raise RuntimeError("Download the Suite first.")
    log("Opening the GTAVXR Suite. Install GTAVXR there, then close it and come back.")
    rc = prefix.run_in_prefix(game, exe, [], log)
    log(f"The Suite exited ({rc}).")


def _running(names):
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")
            except OSError:
                continue
            if cmd.replace("\\", "/").rsplit("/", 1)[-1] in names:
                return True
    return False


def apply_fix(game, log=print):
    """Clear GTAVXR_SourceBaseline.exe's export directory and update the Suite's hash records."""
    exe = game.folder / GAME_EXE
    suite = suite_data(game)
    if not exe.is_file():
        raise RuntimeError("Install GTAVXR from the Suite first.")
    if _running({GAME_EXE, SUITE_EXE}):
        raise RuntimeError("Close the GTAVXR Suite and the game first.")
    backup = util.data_dir() / "gtavxr" / "backup"
    backup.mkdir(parents=True, exist_ok=True)
    b, off, (rva, size) = _pe_export_dir(exe)
    b = bytearray(b)
    old = hashlib.sha256(b).hexdigest().upper()
    if rva or size:
        dst = backup / f"{GAME_EXE[:-4]}-{old[:12].lower()}.exe"
        if not dst.exists():
            shutil.copy2(exe, dst)
        log(f"Clearing export directory (rva={rva:#x} size={size:#x}); original kept at {dst}")
        struct.pack_into("<II", b, off, 0, 0)
        exe.write_bytes(b)
    else:
        log("Export directory already cleared.")
    new = hashlib.sha256(b).hexdigest().upper()
    records = [suite / "game" / "state.json"] + [Path(p) for p in glob.glob(str(suite / "versions" / "*.json"))]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for p in records:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8-sig")
        files = json.loads(text).get("files") or []
        stale = {f["sha256"] for f in files if f.get("path") == GAME_EXE and f["sha256"].upper() != new}
        if not stale:
            continue
        for f in files:
            if f.get("path") == GAME_EXE and f.get("bytes") not in (None, len(b)):
                raise RuntimeError(f"Size of {GAME_EXE} differs from {p.name}'s record")
        shutil.copy2(p, backup / f"{p.parent.name}-{p.name}.{stamp}")
        for h in stale:
            text = text.replace(h, new)
        json.loads(text)
        p.write_text(text, encoding="utf-8")
        log(f"Updated the Suite's record in {p.relative_to(suite)}")
    log("Wine fix applied.")


def install_tar(game, log=print):
    """Build the tar.exe stand-in and put it in the prefix's system32."""
    src = Path(__file__).parent / "data" / "tar.cs"
    out = util.data_dir() / "gtavxr" / "tar.exe"
    out.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("mcs"):
        rc = util.run(["mcs", "-nologo", "-sdk:4.5", "-target:exe", "-platform:anycpu", "-optimize+",
                       "-r:System.IO.Compression.dll", "-r:System.IO.Compression.FileSystem.dll",
                       f"-out:{out}", str(src)], log)
    else:
        if not prefix.dotnet48_installed(game):
            raise RuntimeError("Install .NET Framework 4.8 first (it provides the C# compiler).")
        csc = "C:\\windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe"
        rc = util.run(prefix.protontricks_cmd() + ["-c", f"wine '{csc}' /nologo /target:exe /optimize+ "
                       f"/r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll "
                       f"/out:'{game.winpath(out)}' '{game.winpath(src)}'", str(game.appid)],
                      log=lambda l: prefix.NOISE.match(l) or log(l))
    if rc != 0 or not out.is_file():
        raise RuntimeError("Couldn't build tar.exe")
    dst = game.prefix / "drive_c/windows/system32/tar.exe"
    if dst.is_file() and dst.read_bytes() != out.read_bytes() and b"only handles .zip/.oiv" not in dst.read_bytes():
        raise RuntimeError(f"A different tar.exe is already at {dst}; leaving it.")
    shutil.copy2(out, dst)
    log(f"Installed {dst}")


def run_step(game, step, log=print):
    if step == "dotnet48":
        prefix.install_dotnet48(game, log)
    elif step == "suite":
        download_suite(game, log)
    elif step == "install":
        open_suite(game, log)
    elif step == "fix":
        apply_fix(game, log)
    elif step == "tar":
        install_tar(game, log)
    elif step == "steamvr":
        import subprocess
        subprocess.Popen(["xdg-open", f"steam://install/{STEAMVR_APPID}"], start_new_session=True,
                         env=util.child_env())
        log("Asked Steam to install SteamVR.")
    else:
        raise RuntimeError(f"Unknown step {step}")


def setup_all(game, log=print):
    """Every automatic step that's still missing. Stops at the one that needs the user (the Suite)."""
    for s in status(game):
        if s["state"] == "ok":
            continue
        if s["id"] == "install":
            log("Next: open the Suite and click Install GTAVXR, then run the remaining steps.")
            return False
        if s["id"] in ("steamvr", "fix") and s["state"] == "info":
            continue
        log(f"== {s['name']}")
        run_step(game, s["id"], log)
    return True
