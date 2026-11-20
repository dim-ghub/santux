"""Proton prefix checks and setup through protontricks."""
import os
import re
import shutil
import time

from . import util

NOISE = re.compile(r"^[0-9a-f]+:(fixme|err|warn|trace):|^\s*$|^pressure-vessel|^wineserver:")


def protontricks_cmd():
    """Base command for protontricks (native, or the Flatpak), or None."""
    if shutil.which("protontricks"):
        return ["protontricks"]
    if shutil.which("flatpak"):
        r = util.run(["flatpak", "info", "com.github.Matoking.protontricks"])
        if r == 0:
            return ["flatpak", "run", "com.github.Matoking.protontricks"]
    return None


def launch_cmd():
    if shutil.which("protontricks-launch"):
        return ["protontricks-launch"]
    if shutil.which("flatpak") and util.run(["flatpak", "info", "com.github.Matoking.protontricks"]) == 0:
        return ["flatpak", "run", "--command=protontricks-launch", "com.github.Matoking.protontricks"]
    return None


def _reg(game, hive="system.reg"):
    try:
        return (game.prefix / hive).read_text(errors="replace")
    except OSError:
        return ""


def dotnet48_installed(game):
    # The registry key alone isn't proof: Proton can leave it behind while wine-mono still
    # provides .NET, which ScriptHookVDotNet doesn't run reliably on. Check the real runtime.
    win = game.prefix / "drive_c/windows"
    if not (win / "Microsoft.NET/Framework64/v4.0.30319/clr.dll").is_file():
        return False
    mscoree = win / "system32/mscoree.dll"
    if mscoree.is_symlink() and "/lib/wine/" in str(mscoree.resolve()):
        return False
    reg = _reg(game)
    i = reg.find("[Software\\\\Microsoft\\\\NET Framework Setup\\\\NDP\\\\v4\\\\Full]")
    if i < 0:
        return False
    m = re.search(r'"Release"=dword:([0-9a-f]+)', reg[i:i + 2000])
    return bool(m) and int(m.group(1), 16) >= 528040


def vcrun2022_installed(game):
    return (game.prefix / "drive_c/windows/system32/msvcp140.dll").is_file() and \
           (game.prefix / "drive_c/windows/system32/vcruntime140_1.dll").is_file()


def backup_registry(game):
    dest = util.data_dir() / "backups" / f"{game.appid}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.mkdir(parents=True)
    for hive in ("system.reg", "user.reg", "userdef.reg"):
        src = game.prefix / hive
        if src.is_file():
            shutil.copy2(src, dest / hive)
    return dest


def winetricks(game, verbs, log=print):
    """Install winetricks verbs into the game's prefix (after backing up its registry)."""
    base = protontricks_cmd()
    if not base:
        raise RuntimeError("protontricks is not installed. Install it from your distro or Flathub.")
    log(f"Registry backed up to {backup_registry(game)}")
    rc = util.run(base + [str(game.appid), "-q", "--force", *verbs],
                  log=lambda l: NOISE.match(l) or log(l))
    if rc != 0:
        raise RuntimeError(f"protontricks exited with {rc}")


def run_in_prefix(game, exe, args, log=print):
    """Run a Windows program inside the game's prefix with the game's Proton. Returns exit code."""
    base = launch_cmd()
    if not base:
        raise RuntimeError("protontricks-launch is not installed (it ships with protontricks).")
    return util.run(base + ["--appid", str(game.appid), str(exe), *args],
                    log=lambda l: NOISE.match(l) or log(l))


# ---------------------------------------------------------------- .NET Framework 4.8

NDP48_URL = "https://download.microsoft.com/download/f/3/a/f3a6af84-da23-40a5-8d1c-49cc10c8e76f/NDP48-x86-x64-AllOS-ENU.exe"
NDP48_SHA256 = "0a3a390c47e639d0f7fc65b21195fee6b7f65b066f80f70c60fab191d14b7e40"
NDP40_URL = "https://download.microsoft.com/download/9/5/A/95A9616B-7A37-4AF6-BC36-D6EA96C8DAAE/dotNetFx40_Full_x86_x64.exe"
NDP40_SHA256 = "65e064258f2e418816b304f646ff9e87af101e4c9552ab064bb74d281c38659f"


def _pt(game, args, log):
    return util.run(protontricks_cmd() + args, log=lambda l: NOISE.match(l) or log(l))


def _pt_cmd(game, command, log):
    return _pt(game, ["-c", command, str(game.appid)], log)


def install_dotnet48(game, log=print):
    """Install Microsoft's .NET Framework 4.8 into a Proton prefix.

    winetricks' dotnet48 doesn't work with current Proton: its .NET 4.0 step fails, and the 4.8
    installer can't overwrite Proton's stub files in Framework*\\v4.0.30319, which are symlinks
    into Proton's read-only install inside Steam's container (error 1603). This removes wine-mono
    and those links, clears registry keys that make setup think 4.8 is already there, runs the
    4.8 offline installer, and supplies mscoree.dll (Windows ships it with the OS) from the 4.0
    installer. On failure the prefix is put back as it was.
    """
    if not protontricks_cmd():
        raise RuntimeError("protontricks is not installed. Install it from your distro or Flathub.")
    pt = str(game.appid)
    win = game.prefix / "drive_c/windows"
    dl = util.downloads_dir() / "dotnet"
    ndp48 = dl / "ndp48-x86-x64-allos-enu.exe"
    ndp40 = dl / "dotNetFx40_Full_x86_x64.exe"
    for url, sha, dest in ((NDP48_URL, NDP48_SHA256, ndp48), (NDP40_URL, NDP40_SHA256, ndp40)):
        if not (dest.is_file() and util.sha256_file(dest) == sha):
            log(f"Downloading {dest.name}")
            util.http.download(url, dest, sha256=sha)

    backup = backup_registry(game)
    log(f"Registry backed up to {backup}")
    links = {}
    for sub in ("system32", "syswow64"):
        m = win / sub / "mscoree.dll"
        if m.is_symlink():
            links[m] = os.readlink(m)
    try:
        log("Removing wine-mono…")
        _pt(game, [pt, "-q", "remove_mono"], log)
        for key in ("HKLM\\Software\\Microsoft\\NET Framework Setup\\NDP\\v4",
                    "HKLM\\Software\\Wow6432Node\\Microsoft\\NET Framework Setup\\NDP\\v4"):
            _pt_cmd(game, f'wine reg delete "{key}" /f', lambda l: None)
        for fw in ("Framework", "Framework64"):
            d = win / "Microsoft.NET" / fw / "v4.0.30319"
            if d.is_dir():
                for p in d.iterdir():
                    if p.is_symlink():
                        p.unlink()
        _pt(game, [pt, "-q", "win7"], log)
        log("Running the .NET Framework 4.8 installer (several minutes)…")
        _pt_cmd(game, f"WINEDLLOVERRIDES=fusion=b wine '{ndp48}' /sfxlang:1027 /q /norestart", log)
        if not (win / "Microsoft.NET/Framework64/v4.0.30319/clr.dll").is_file():
            raise RuntimeError("The .NET 4.8 installer didn't install the runtime")
        log("Adding mscoree.dll…")
        tmp = util.cache_dir() / "ndp40"
        shutil.rmtree(tmp, ignore_errors=True)
        util.extract(ndp40, tmp)
        found = {}
        for cab in tmp.rglob("netfx_Core.mzz"):
            out = tmp / "core"
            util.extract(cab, out)
            for arch, sub in (("amd64", "system32"), ("x86", "syswow64")):
                src = next(out.rglob(f"*mscoree_dll_{arch}"), None)
                if src:
                    found[sub] = src
        if len(found) != 2:
            raise RuntimeError("Couldn't find mscoree.dll in the .NET 4.0 installer")
        for sub, src in found.items():
            dest = win / sub / "mscoree.dll"
            if dest.is_symlink() or dest.exists():
                dest.unlink()
            shutil.copyfile(src, dest)
        shutil.rmtree(tmp, ignore_errors=True)
        _pt_cmd(game, 'wine reg add "HKCU\\Software\\Wine\\DllOverrides" /v mscoree /d native /f', lambda l: None)
        _pt(game, [pt, "-q", "win10"], log)
    except Exception:
        log("Install failed; restoring the prefix as it was…")
        for hive in ("system.reg", "user.reg", "userdef.reg"):
            if (backup / hive).is_file():
                shutil.copy2(backup / hive, game.prefix / hive)
        for link, target in links.items():
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(target)
        raise
    if not dotnet48_installed(game):
        raise RuntimeError(".NET 4.8 files are in place but the install check still fails")
    log(".NET Framework 4.8 is installed.")
