"""The common requirements most GTA V mods need, each with a status check and an installer."""
import os
import re
import shutil
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from . import game as gamemod, gta5mods, installer, prefix, profiles, util, vdf

OK, MISSING, UPDATE, NA, INFO = "ok", "missing", "update", "n/a", "info"


@dataclass
class Status:
    state: str
    detail: str = ""


class Requirement:
    id = ""
    name = ""
    description = ""
    editions = ("Legacy", "Enhanced")
    recommended = True
    needs = ()          # requirement ids that must be installed first

    def applies(self, game):
        return game.edition in self.editions

    def status(self, game) -> Status:
        raise NotImplementedError

    def install(self, game, log):
        raise NotImplementedError

    def remove(self, game, log):
        rec = _record(game, self.id)
        if rec:
            installer.uninstall(game, rec.id, log=log, scope=_scope(self.id))
        else:
            raise installer.InstallError(f"{self.name} wasn't installed by Santux.")


def _scope(req_id):
    # Archive edits live in a profile's mods folder; everything else is shared by all profiles.
    return None if req_id == "gameconfig" else profiles.SHARED


def _record(game, req_id):
    return installer.Manifest(game, _scope(req_id)).find(f"requirement:{req_id}")


def _install_plan(game, req, plan, version, log):
    rec = installer.install(game, plan, req.name, version=version, source=f"requirement:{req.id}", log=log,
                            scope=_scope(req.id))
    for n in rec.notes:
        log(n)
    return rec


def _extract_download(url, name, sha256=None, referer=None, log=print):
    dest = util.downloads_dir() / name
    if not (dest.is_file() and (not sha256 or util.sha256_file(dest) == sha256)):
        log(f"Downloading {name}")
        util.http.download(url, dest, referer=referer, sha256=sha256)
    out = util.cache_dir() / "extract" / Path(name).stem
    return util.extract(dest, out)


# ------------------------------------------------------------------ prefix

class DotNet48(Requirement):
    id = "dotnet48"
    name = ".NET Framework 4.8"
    description = "Needed by ScriptHookVDotNet scripts and many tools. Installed into the game's Proton prefix (10–20 min)."

    def status(self, game):
        if not game.has_prefix:
            return Status(MISSING, "No prefix yet: launch the game from Steam once")
        return Status(OK) if prefix.dotnet48_installed(game) else Status(MISSING)

    def install(self, game, log):
        prefix.install_dotnet48(game, log)

    def remove(self, game, log):
        raise installer.InstallError("Runtimes can't be removed from the prefix individually.")


class VCRun2022(Requirement):
    id = "vcrun2022"
    name = "Visual C++ 2015–2022 runtime"
    description = "Needed by most .asi plugins. Installed into the game's Proton prefix."

    def status(self, game):
        if not game.has_prefix:
            return Status(MISSING, "No prefix yet: launch the game from Steam once")
        return Status(OK) if prefix.vcrun2022_installed(game) else Status(MISSING)

    def install(self, game, log):
        prefix.winetricks(game, ["vcrun2022"], log)

    remove = DotNet48.remove


# ------------------------------------------------------------------ Script Hook V

SHV_PAGE = "https://www.dev-c.com/gtav/scripthookv/"


def shv_latest():
    """(zip url, version label, supported patch strings) from dev-c.com."""
    page = util.http.text(SHV_PAGE)
    zips = [z for z in re.findall(r'href="([^"]*ScriptHookV_[\d._]+\.zip)"', page) if "SDK" not in z]
    if not zips:
        raise util.HttpError("Couldn't find the Script Hook V download on dev-c.com")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    ver = re.search(r"Version\s+(v[\d.]+\s*/\s*[\d.]+)", text)
    sup = re.search(r"Supported patches\s+([\d. /]+)", text)
    supported = [s.strip() for s in sup.group(1).split("/")] if sup else []
    return urllib.parse.urljoin(SHV_PAGE, zips[0]), (ver.group(1) if ver else zips[0]), supported


class ScriptHookV(Requirement):
    id = "scripthookv"
    name = "Script Hook V + ASI loader"
    description = "Lets the game load .asi plugins and scripts. Must match the game's exact build, so it needs updating after every Rockstar patch."

    def status(self, game):
        dll = game.folder / "ScriptHookV.dll"
        loader = game.folder / game.asi_loader
        if not dll.is_file() or not loader.is_file():
            return Status(MISSING)
        rec = _record(game, self.id)
        note = f"version {rec.version}" if rec else "found in the game folder (not installed by Santux)"
        return Status(OK, note)

    def check_update(self, game):
        url, label, supported = shv_latest()
        build = game.version or ""
        ok = any(build == s or build.startswith(s) for s in supported) if supported else True
        return url, label, ok

    def install(self, game, log):
        url, label, compatible = self.check_update(game)
        if not compatible:
            log(f"Warning: Script Hook V {label} doesn't list game version {game.version} as supported.")
        root = _extract_download(url, url.rsplit("/", 1)[-1], referer=SHV_PAGE, log=log)
        bindir = root / "bin"
        plan = installer.Plan(root)
        for f in ("ScriptHookV.dll", game.asi_loader) + (("args.txt",) if game.legacy else ()):
            if (bindir / f).is_file():
                plan.copies.append((bindir / f, f))
        old = _record(game, self.id)
        if old:
            installer.uninstall(game, old.id, log=log, scope=profiles.SHARED)
        # The loader files are on installer's skip list for mods, so copy them directly here.
        man = installer.Manifest(game, profiles.SHARED)
        rec = installer.InstalledMod(id=os.urandom(6).hex(), title=self.name, version=label,
                                     source=f"requirement:{self.id}", installed=time.time())
        for src, dest in plan.copies:
            target = game.folder / dest
            if target.exists() and not man.owner(dest):
                bak = target.with_name(target.name + ".santux.bak")
                shutil.copy2(target, bak)
                rec.notes.append(f"Replaced existing {dest} (backup: {bak.name})")
            shutil.copy2(src, target)
            rec.files.append(dest)
            log(f"copied {dest}")
        man.mods.append(rec)
        man.save()


# ------------------------------------------------------------------ mods folder loader

class RageOpenV(Requirement):
    id = "rageopenv"
    name = "Mods folder loader (RageOpenV)"
    description = "Open-source replacement for OpenIV.asi: makes the game load archive edits from the mods folder, so original files stay untouched."
    needs = ("scripthookv",)
    REPO = "Chiheb-Bacha/RageOpenV"

    def status(self, game):
        for f in ("RageOpenV.asi", "OpenIV.asi", "OpenRPF.asi"):
            if (game.folder / f).is_file():
                return Status(OK, f)
        return Status(MISSING)

    def install(self, game, log):
        rel = util.http.json(f"https://api.github.com/repos/{self.REPO}/releases/latest")
        asset = next(a for a in rel["assets"] if a["name"].lower().endswith(".zip"))
        sha = (asset.get("digest") or "").removeprefix("sha256:") or None
        root = _extract_download(asset["browser_download_url"], f"RageOpenV-{rel['tag_name']}.zip", sha, log=log)
        asi = next(p for p in root.rglob("RageOpenV.asi") if "MoreLogs" not in str(p))
        plan = installer.Plan(root, copies=[(asi, "RageOpenV.asi")])
        _install_plan(game, self, plan, rel["tag_name"], log)


# ------------------------------------------------------------------ ScriptHookVDotNet

class SHVDN(Requirement):
    id = "shvdn"
    name = "ScriptHookVDotNet"
    description = "Runs .NET (C#) script mods from the scripts folder. Uses the nightly build, which supports current game patches."
    editions = ("Legacy",)
    needs = ("scripthookv", "dotnet48")
    REPO = "scripthookvdotnet/scripthookvdotnet-nightly"

    def status(self, game):
        if (game.folder / "ScriptHookVDotNet.asi").is_file() or (game.folder / "ScriptHookVDotNet-Loader.asi").is_file():
            rec = _record(game, self.id)
            return Status(OK, rec.version if rec else "found in the game folder")
        return Status(MISSING)

    def install(self, game, log):
        rel = util.http.json(f"https://api.github.com/repos/{self.REPO}/releases/latest")
        asset = next(a for a in rel["assets"] if a["name"].lower().endswith(".zip"))
        sha = (asset.get("digest") or "").removeprefix("sha256:") or None
        root = _extract_download(asset["browser_download_url"], asset["name"], sha, log=log)
        plan = installer.Plan(root)
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in (".asi", ".dll", ".ini"):
                plan.copies.append((p, p.name))
        (game.folder / "scripts").mkdir(exist_ok=True)
        _install_plan(game, self, plan, rel["tag_name"], log)


# ------------------------------------------------------------------ stability patches

class GtaModsAsi(Requirement):
    """An .asi tool hosted on gta5-mods.com, installed with its config files."""
    pages = {}          # edition -> page url

    def applies(self, game):
        return game.edition in self.pages

    def status(self, game):
        rec = _record(game, self.id)
        if rec and all((game.folder / f).is_file() for f in rec.files):
            return Status(OK, rec.version)
        hint = getattr(self, "asi_hint", None)
        if hint and any(p.name.lower().startswith(hint) for p in game.folder.glob("*.asi")):
            return Status(OK, "found in the game folder")
        return Status(MISSING)

    def install(self, game, log):
        d, f = gta5mods.latest_file(self.pages[game.edition])
        url = gta5mods.resolve_file(f.page)
        root = _extract_download(url, gta5mods.file_name(url), f.sha256 or None, log=log)
        plan = installer.analyse(root, game)
        plan.chosen_oivs = []
        if not plan.copies:
            raise installer.InstallError(f"No .asi found in {d.title}")
        _install_plan(game, self, plan, d.version, log)


class HeapAdjuster(GtaModsAsi):
    id = "heapadjuster"
    name = "Heap Adjuster"
    description = "Raises the game's memory heap. Fixes ERR_MEM_EMBEDDEDALLOC crashes with large mods."
    needs = ("scripthookv",)
    asi_hint = "heapadjuster"
    pages = {"Legacy": "https://www.gta5-mods.com/tools/heapadjuster",
             "Enhanced": "https://www.gta5-mods.com/tools/heapadjuster-enhanced"}


class PackfileLimit(GtaModsAsi):
    id = "packfilelimit"
    name = "Packfile Limit Adjuster"
    description = "Doubles how many .rpf archives the game can load. Fixes ERR_FIL_PACK_1 with many add-ons."
    needs = ("scripthookv",)
    asi_hint = "packfilelimitadjuster"
    pages = {"Legacy": "https://www.gta5-mods.com/tools/packfile-limit-adjuster",
             "Enhanced": "https://www.gta5-mods.com/scripts/packfile-limit-adjuster-enhanced"}


class Gameconfig(Requirement):
    id = "gameconfig"
    name = "Modded gameconfig.xml"
    description = "Raises the game's pool limits for add-on cars, maps and peds (from pnwparksfan/gameconfig, matched to your build)."
    editions = ("Legacy",)
    needs = ("rageopenv",)
    REPO = "pnwparksfan/gameconfig"

    def status(self, game):
        rec = _record(game, self.id)
        if rec and rec.packages:
            build = gamemod.build_number(game.version)
            if rec.version and build and rec.version != str(build):
                return Status(UPDATE, f"installed for {rec.version}, game is {build}")
            return Status(OK, f"for build {rec.version}")
        return Status(MISSING)

    def install(self, game, log):
        build = gamemod.build_number(game.version)
        versions = [x["name"] for x in util.http.json(
            f"https://api.github.com/repos/{self.REPO}/contents/versions") if x["type"] == "dir"]
        pick = str(build) if str(build) in versions else None
        if not pick:
            nums = sorted(int(v) for v in versions if v.isdigit() and build and int(v) <= build)
            if not nums:
                raise installer.InstallError(f"No gameconfig for build {build}")
            pick = str(nums[-1])
            log(f"No gameconfig for build {build}; using the one for {pick}")
        src = util.downloads_dir() / f"gameconfig-{pick}.xml"
        util.http.download(f"https://raw.githubusercontent.com/{self.REPO}/master/versions/{pick}/gameconfig.xml", src)
        work = util.cache_dir() / "generated"
        work.mkdir(parents=True, exist_ok=True)
        tmp = work / "gameconfig.xml"
        shutil.copy2(src, tmp)
        oiv = installer.file_replacement_oiv(tmp, "update\\update.rpf", "common\\data\\gameconfig.xml",
                                             f"Gameconfig {pick}", pick, "pnwparksfan/gameconfig", work)
        plan = installer.Plan(work, chosen_oivs=[oiv])
        _install_plan(game, self, plan, pick, log)


# ------------------------------------------------------------------ Steam launch option

def steam_running():
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                exe = os.readlink(f"/proc/{pid}/exe")
            except OSError:
                continue
            if exe.endswith(("/ubuntu12_32/steam", "/steam-runtime/steam")) or exe.rsplit("/", 1)[-1] == "steam":
                return True
    return False


def _localconfigs(game):
    return sorted(Path(game.steam_root, "userdata").glob("*/config/localconfig.vdf"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def launch_options(game):
    for cfg in _localconfigs(game):
        data = vdf.loads(cfg.read_text(errors="replace"))
        app = vdf.get_ci(data, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", str(game.appid))
        if app is not None:
            return vdf.get_ci(app, "LaunchOptions") or ""
    return ""


def modloader_command():
    """How Steam should call us: the installed command, this binary, or this checkout's script."""
    installed = Path.home() / ".local/bin/santux"
    if installed.exists():
        return str(installed)
    found = shutil.which("santux")
    if found:
        return found
    if util.FROZEN:
        return sys.executable
    return str(Path(__file__).resolve().parent.parent / "bin" / "santux")


class LaunchOption(Requirement):
    id = "launchoption"
    name = "Steam launch option"
    description = ("Routes GTA V's Steam launch through Santux, which switches to the chosen profile "
                   "and tells Proton to load the ASI loader for modded profiles. Steam must be closed to set it.")

    def wanted(self, game):
        return f"{modloader_command()} launch %command%"

    def status(self, game):
        cur = launch_options(game)
        if "santux" in cur and " launch" in cur:
            return Status(OK, cur)
        if cur:
            return Status(INFO, f"custom launch options: {cur}")
        return Status(MISSING, "no launch options set")

    def install(self, game, log):
        if steam_running():
            raise installer.InstallError(
                "Steam is running and would overwrite the change. Close Steam and retry, or paste this into "
                f"GTA V → Properties → Launch Options:\n{self.wanted(game)}")
        cfgs = _localconfigs(game)
        if not cfgs:
            raise installer.InstallError("No Steam user config found. Log into Steam once first.")
        cfg = cfgs[0]
        data = vdf.loads(cfg.read_text(errors="replace"))
        app = vdf.ensure_ci(data, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", str(game.appid))
        cur = vdf.get_ci(app, "LaunchOptions") or ""
        shutil.copy2(cfg, cfg.with_name("localconfig.vdf.santux.bak"))
        key = next((k for k in app if k.lower() == "launchoptions"), "LaunchOptions")
        app[key] = self.wanted(game)
        cfg.write_text(vdf.dumps(data))
        log(f"Launch options set to: {app[key]}" + (f" (were: {cur})" if cur else ""))

    def remove(self, game, log):
        raise installer.InstallError("Edit GTA V's launch options in Steam to remove it.")


ALL = [VCRun2022(), DotNet48(), ScriptHookV(), LaunchOption(), RageOpenV(),
       SHVDN(), Gameconfig(), HeapAdjuster(), PackfileLimit()]
BY_ID = {r.id: r for r in ALL}


def for_game(game):
    return [r for r in ALL if r.applies(game)]
