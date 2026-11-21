"""Install and uninstall mods into a GTA V folder, keeping a record of everything added.

Archive edits (.oiv packages, add-on dlc.rpf packs) are applied natively by oiv.py, always into
the game's mods\\ folder, never into the original .rpf files. Each installed package is kept in
the app's data folder with the list of mods\\ files it touched, so uninstalling one package
deletes those files and re-applies the remaining packages that touch them. Loose files (.asi
plugins, ScriptHookVDotNet scripts, Menyoo data) are copied directly.
"""
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import oiv as oivmod, util

ASI_SIDECARS = {".ini", ".toml", ".xml", ".json", ".cfg", ".txt", ".log"}
SCRIPT_SOURCE = {".cs", ".vb"}
SKIP_ROOT = {"dinput8.dll", "xinput1_4.dll", "scripthookv.dll", "dsound.dll", "version.dll",
             "winmm.dll", "args.txt", "gta5.exe", "gta5_enhanced.exe", "playgtav.exe"}
DOC_EXT = {".txt", ".md", ".pdf", ".url", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".html", ".rtf", ".docx"}

# Libraries such as LemonUI ship one folder per framework. Folders for other platforms are never
# for single-player ScriptHookVDotNet; among ScriptHookVDotNet builds, v3 is the one we install.
OTHER_PLATFORMS = (
    (re.compile(r"^fivem$|^cfx"), "FiveM"),
    (re.compile(r"^rage ?mp$"), "RageMP"),
    (re.compile(r"^alt ?v$|^altv[ ._-]"), "alt:V"),
    (re.compile(r"^rph$|^rage ?plugin ?hook$"), "RagePluginHook"),
    (re.compile(r"^for developers$|^nuget$|^developers?$"), "developers"),
)
SHVDN_BUILD = re.compile(r"^(?:shvdn|scripthookvdotnet|script ?hook ?v ?dot ?net) ?[-_ ]?(v?\d|c|community)$")
PREFERRED_SHVDN = re.compile(r"(?:^|[^\d])3$")


class InstallError(Exception):
    pass


@dataclass
class InstalledMod:
    id: str
    title: str
    version: str = ""
    source: str = ""                      # gta5-mods page or local archive
    installed: float = 0.0
    files: list = field(default_factory=list)      # paths relative to the game folder
    packages: list = field(default_factory=list)   # {name, file, targets} per package in mods\
    notes: list = field(default_factory=list)
    disabled: bool = False                          # files parked, packages left out of mods\


class Manifest:
    """Install records of one scope: a mod profile, or profiles.SHARED for requirements."""

    def __init__(self, game, scope=None):
        from . import profiles
        profiles.ensure(game)
        self.scope = scope or profiles.active(game)
        self.path = profiles.scope_dir(game, self.scope) / "installed.json"
        self.mods = []
        self.created_mods_folder = False
        if self.path.is_file():
            data = json.loads(self.path.read_text())
            self.mods = [InstalledMod(**m) for m in data.get("mods", [])]
            self.created_mods_folder = data.get("created_mods_folder", False)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"mods": [asdict(m) for m in self.mods],
                                   "created_mods_folder": self.created_mods_folder}, indent=2))
        tmp.replace(self.path)

    def owner(self, rel):
        rel = rel.lower()
        return next((m for m in self.mods if rel in (f.lower() for f in m.files)), None)

    def find(self, source):
        return next((m for m in self.mods if source and m.source == source), None)


# ---------------------------------------------------------------- OIV packages

def oiv_name(oiv: Path):
    try:
        with zipfile.ZipFile(oiv) as z:
            xml = z.read("assembly.xml").decode("utf-8", "replace")
        m = re.search(r"<metadata>.*?<name>(.*?)</name>", xml, re.S)
        return m.group(1).strip() if m else oiv.stem
    except (zipfile.BadZipFile, KeyError, OSError):
        return oiv.stem


def oiv_game_version(oiv: Path):
    try:
        with zipfile.ZipFile(oiv) as z:
            xml = z.read("assembly.xml").decode("utf-8", "replace")
        m = re.search(r"<gameversion>(.*?)</gameversion>", xml, re.S | re.I)
        return m.group(1).strip().lower() if m else ""
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""


def _package_store(game, scope=None):
    from . import profiles
    d = profiles.scope_dir(game, scope or profiles.active(game)) / "packages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def owner_anywhere(game, rel):
    """The install record (shared or active profile) that owns a game-folder file."""
    from . import profiles
    for scope in (profiles.SHARED, profiles.active(game)):
        m = Manifest(game, scope).owner(rel)
        if m:
            return m
    return None


def _editable_scope(game, scope):
    """Resolve where an install goes; mods go into the active profile, which must be a mod profile."""
    from . import profiles
    if scope == profiles.SHARED:
        return scope
    scope = scope or profiles.active(game)
    p = profiles.get(game, scope)
    if p is None or not p.editable:
        raise InstallError("Choose one of your mod profiles first (Vanilla and GTAVXR can't hold mods).")
    profiles.activate(game, scope)
    return scope


def _known_targets(man):
    out = set()
    for m in man.mods:
        for r in _package_records(m):
            out |= set(r.get("targets", []))
    return out


def _session(game, man, log):
    return oivmod.Session(game, log, known=_known_targets(man), base_dir=_package_store(game, man.scope) / "base")


def _package_records(mod):
    """Package records of a mod; older records stored just a name and can't be replayed."""
    return [p for p in mod.packages if isinstance(p, dict)]


def make_oiv(dest: Path, name, version, author, content_xml, files):
    """Write a minimal .oiv. files maps names under content/ to source paths."""
    staging = dest.with_suffix(".staging")
    shutil.rmtree(staging, ignore_errors=True)
    (staging / "content").mkdir(parents=True)
    for rel, src in files.items():
        (staging / "content" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, staging / "content" / rel)
    (staging / "assembly.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<package version="2.1" id="{{{str(uuid.uuid4()).upper()}}}" target="Five">
<metadata>
<name>{_x(name)}</name>
<version><major>{_x(version or "1")}</major><minor>0</minor><tag>Stable</tag></version>
<author><displayName>{_x(author or "unknown")}</displayName></author>
<description><![CDATA[Generated by Santux]]></description>
</metadata>
<colors><headerBackground useBlackTextColor="True">$FF808080</headerBackground><iconBackground>$FF808080</iconBackground></colors>
<content>
{content_xml}
</content>
</package>
""")
    dest.unlink(missing_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(staging).as_posix())
    shutil.rmtree(staging)
    return dest


def _x(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def addon_oiv(dlc_rpf: Path, pack: str, workdir: Path):
    """Wrap an add-on DLC (dlc.rpf) in an .oiv that registers it in dlclist.xml."""
    pack = re.sub(r"[^a-z0-9_]", "", pack.lower()) or "addon"
    content = f"""<archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">
<xml path="common\\data\\dlclist.xml">
<remove xpath="/SMandatoryPacksData/Paths/Item[text()='dlcpacks:/{pack}/']"/>
<add xpath="/SMandatoryPacksData/Paths" append="Last"><Item>dlcpacks:/{pack}/</Item></add>
</xml>
</archive>
<add source="dlc.rpf">update\\x64\\dlcpacks\\{pack}\\dlc.rpf</add>"""
    return make_oiv(workdir / f"addon-{pack}.oiv", f"Add-on {pack}", "1", "santux",
                    content, {"dlc.rpf": dlc_rpf})


def file_replacement_oiv(src: Path, archive_path: str, inner_path: str, name, version, author, workdir: Path):
    content = f"""<archive path="{_x(archive_path)}" createIfNotExist="True" type="RPF7">
<add source="{_x(src.name)}">{_x(inner_path)}</add>
</archive>"""
    return make_oiv(workdir / (re.sub(r"\W+", "-", name).strip("-") + ".oiv"), name, version, author,
                    content, {src.name: src})


# ---------------------------------------------------------------- archive analysis

@dataclass
class Plan:
    """What an extracted mod archive contains, and what will be installed."""
    root: Path
    oivs: list = field(default_factory=list)        # all .oiv found
    chosen_oivs: list = field(default_factory=list) # pre-selected ones
    addons: list = field(default_factory=list)      # (dlc.rpf, pack name)
    copies: list = field(default_factory=list)      # (src, dest rel to game folder)
    skipped: list = field(default_factory=list)     # (rel path, reason)

    @property
    def empty(self):
        return not (self.chosen_oivs or self.addons or self.copies)


def _is_shvdn_assembly(p: Path):
    try:
        data = p.read_bytes()
    except OSError:
        return False
    return b"ScriptHookVDotNet" in data or b"S\x00c\x00r\x00i\x00p\x00t\x00H\x00o\x00o\x00k\x00V\x00D\x00o\x00t\x00N\x00e\x00t" in data


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(p))]


def link_or_copy(src: Path, dest: Path):
    """Hard-link when src and dest share a filesystem (multi-GB packages), otherwise copy."""
    dest.unlink(missing_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def _other_framework_files(files, root):
    """{file: reason} for files built for another platform or another ScriptHookVDotNet version."""
    out = {}
    shvdn_dirs = {}                                   # (parent parts) -> {folder name, ...}
    for p in files:
        parts = p.relative_to(root).parts[:-1]
        if p.suffix.lower() == ".nupkg":
            out[p] = "developer package (NuGet)"
            continue
        for i, d in enumerate(parts):
            name = d.lower()
            hit = next((label for rx, label in OTHER_PLATFORMS if rx.search(name)), None)
            if hit:
                out[p] = f"for {hit}, not single-player ScriptHookVDotNet"
                break
            if SHVDN_BUILD.search(name):
                shvdn_dirs.setdefault(parts[:i], set()).add(d)
    # Several ScriptHookVDotNet builds side by side: keep the v3 one.
    for parent, names in shvdn_dirs.items():
        keep = {n for n in names if PREFERRED_SHVDN.search(n.lower())}
        if len(names) < 2 or not keep:
            continue
        for p in files:
            parts = p.relative_to(root).parts
            if p not in out and parts[:len(parent)] == parent and len(parts) > len(parent) + 1 \
                    and parts[len(parent)] in names - keep:
                out[p] = f"built for a different ScriptHookVDotNet version than {sorted(keep)[0]}"
    return out


def _oiv_score(p: Path, game):
    s = str(p).lower()
    score = 0
    if "uninstall" in s or "original files" in s or "vanilla" in s:
        return -100
    if "fivem" in s:
        score -= 50
    other = "enhanced" if game.legacy else "legacy"
    mine = game.edition.lower()
    if mine in s:
        score += 10
    if other in s and mine not in s:
        score -= 40
    gv = oiv_game_version(p)
    if gv and gv not in (mine, "any", "both"):
        score -= 40
    if "optional" in s or "compatib" in s or "addon" in s.split("/")[-1]:
        score -= 5
    if "manual" in s:
        score -= 20
    if re.search(r"\bold(er)?\b", s):
        score -= 10
    return score


def analyse(root: Path, game, title="") -> Plan:
    plan = Plan(root)
    files = [p for p in root.rglob("*") if p.is_file()]
    # Natural order, so "2. Part TWO" comes before "10. Part TEN": multi-part packages are usually
    # numbered in the order they must be installed.
    plan.oivs = sorted((p for p in files if p.suffix.lower() in (".oiv",)), key=natural_key)
    if plan.oivs:
        scored = sorted(((_oiv_score(p, game), p) for p in plan.oivs), key=lambda t: -t[0])
        best = scored[0][0]
        if best > -40:
            # Keep every package scoring as well as the best one (e.g. North + South halves),
            # unless their names differ a lot: then keep the ones named most like the mod
            # (SERO 4.4v over an optional "Weapon physics" pack).
            tied = [p for s, p in scored if s == best]
            if len(tied) > 1 and title:
                from difflib import SequenceMatcher
                def sim(p):
                    return SequenceMatcher(None, oiv_name(p).lower() + " " + p.stem.lower(), title.lower()).ratio()
                top = max(sim(p) for p in tied)
                tied = [p for p in tied if sim(p) >= top - 0.15]
            plan.chosen_oivs = tied
        handled = set(plan.oivs)
    else:
        handled = set()

    def rel(p):
        return p.relative_to(root).as_posix()

    for p, why in _other_framework_files(files, root).items():
        if p not in handled:
            handled.add(p)
            if p.suffix.lower() not in DOC_EXT:
                plan.skipped.append((rel(p), why))

    # Packages with .oiv files often ship extras (ENB/ReShade presets, alternative plugins) in
    # "optional" folders. Those are left for the user to pick by hand.
    if plan.oivs:
        for p in files:
            if p not in handled and any(re.match(r"optional|extra|addon|enb|reshade", x.lower())
                                        for x in p.relative_to(root).parts[:-1]):
                handled.add(p)
                if p.suffix.lower() not in DOC_EXT:
                    plan.skipped.append((rel(p), "optional extra"))

    # Folders with a known meaning inside the archive.
    for p in files:
        if p in handled:
            continue
        parts = [x.lower() for x in p.relative_to(root).parts]
        if "scripts" in parts[:-1]:
            i = parts.index("scripts")
            dest = "scripts/" + "/".join(p.relative_to(root).parts[i + 1:])
            plan.copies.append((p, dest)); handled.add(p)
        elif "menyoostuff" in parts[:-1]:
            i = parts.index("menyoostuff")
            dest = "menyooStuff/" + "/".join(p.relative_to(root).parts[i + 1:])
            plan.copies.append((p, dest)); handled.add(p)

    # Add-on DLC packs: <pack>/dlc.rpf, only when no .oiv covers them.
    if not plan.oivs:
        for p in files:
            if p.name.lower() == "dlc.rpf" and p not in handled:
                pack = p.parent.name if p.parent != root else root.name
                plan.addons.append((p, pack)); handled.add(p)

    # ASI plugins and their config files.
    for p in files:
        if p in handled or p.suffix.lower() != ".asi":
            continue
        plan.copies.append((p, p.name)); handled.add(p)
        for side in p.parent.iterdir():
            if side.is_file() and side not in handled and side.suffix.lower() in ASI_SIDECARS \
                    and not side.name.lower().startswith(("readme", "read me", "install", "changelog", "license")):
                plan.copies.append((side, side.name)); handled.add(side)
            elif side.is_dir() and side.name.lower() == p.stem.lower():
                for q in side.rglob("*"):
                    if q.is_file():
                        plan.copies.append((q, f"{side.name}/{q.relative_to(side).as_posix()}")); handled.add(q)

    # ScriptHookVDotNet scripts outside a scripts/ folder.
    for p in files:
        if p in handled:
            continue
        ext = p.suffix.lower()
        if ext in SCRIPT_SOURCE or (ext == ".dll" and _is_shvdn_assembly(p) and
                                    not p.name.lower().startswith("scripthookvdotnet")):
            plan.copies.append((p, "scripts/" + p.name)); handled.add(p)
            for side in p.parent.iterdir():
                if side.is_file() and side not in handled and side.suffix.lower() in {".ini", ".xml", ".json", ".pdb"}:
                    plan.copies.append((side, "scripts/" + side.name)); handled.add(side)
                elif side.is_dir() and side.name.lower() == p.stem.lower():
                    for q in side.rglob("*"):
                        if q.is_file():
                            plan.copies.append((q, f"scripts/{side.name}/{q.relative_to(side).as_posix()}"))
                            handled.add(q)

    # Anything in the game root that the Requirements page manages, or that is just docs.
    final = []
    for src, dest in plan.copies:
        if "/" not in dest and dest.lower() in SKIP_ROOT:
            plan.skipped.append((rel(src), "managed by Requirements"))
        else:
            final.append((src, dest))
    plan.copies = final
    for p in files:
        if p in handled or p.suffix.lower() in DOC_EXT:
            continue
        if p.name.lower() in SKIP_ROOT:
            plan.skipped.append((rel(p), "managed by Requirements"))
        else:
            plan.skipped.append((rel(p), "not recognised; install manually if needed"))
    return plan


# ---------------------------------------------------------------- install / uninstall

def _check_closed():
    from .game import running_game_processes
    if running_game_processes():
        raise InstallError("Close GTA V first.")


def install(game, plan: Plan, title, version="", source="", author="", oivs=None, log=print, scope=None):
    """Install a Plan into a profile (default: the active one) or profiles.SHARED.
    oivs overrides plan.chosen_oivs. Returns the InstalledMod record."""
    _check_closed()
    scope = _editable_scope(game, scope)
    man = Manifest(game, scope)
    old = man.find(source) if source else None
    if old:
        log(f"Replacing previously installed {old.title} {old.version}")
        uninstall(game, old.id, log=log, scope=scope)
        man = Manifest(game, scope)
    mod = InstalledMod(id=uuid.uuid4().hex[:12], title=title, version=version, source=source,
                       installed=time.time())

    for src, dest in plan.copies:
        target = game.folder / dest
        owner = man.owner(dest) or owner_anywhere(game, dest)
        if target.exists() and not owner:
            mod.notes.append(f"Skipped {dest}: already in the game folder and not installed by Santux")
            log(f"skip {dest} (exists, not ours)")
            continue
        if owner and owner.id != mod.id:
            if not any(o.id == owner.id for o in man.mods):
                mod.notes.append(f"Skipped {dest}: it belongs to {owner.title}")
                log(f"skip {dest} (belongs to {owner.title})")
                continue
            log(f"{dest} was installed by {owner.title}; replacing")
            owner.files = [f for f in owner.files if f.lower() != dest.lower()]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        mod.files.append(dest)
        log(f"copied {dest}")

    packages = list(plan.chosen_oivs if oivs is None else oivs)
    work = util.cache_dir() / "generated"
    work.mkdir(exist_ok=True)
    for rpf, pack in plan.addons:
        packages.append(addon_oiv(rpf, pack, work))
    if packages:
        if not game.mods_folder.exists():
            man.created_mods_folder = True
        store = _package_store(game, scope)
        session = _session(game, man, log)
        try:
            for i, src in enumerate(packages):
                pkg = oivmod.Package.load(src)
                kept = store / f"{mod.id}-{i}.oiv"
                link_or_copy(src, kept)
                log(f"== {pkg.name} {pkg.version}".rstrip())
                rec = {"name": pkg.name, "file": kept.name, "targets": []}
                mod.packages.append(rec)
                rec["targets"] = sorted(session.apply(pkg))
            session.flush()
        except Exception as e:
            # Archives edited in memory weren't written; files the packages already put into mods\
            # are recorded, so uninstalling this mod rebuilds them.
            mod.files += session.loose
            mod.notes.append(f"Install failed: {e}")
            man.mods.append(mod)
            man.save()
            raise InstallError(f"{e}\n\nNothing was written to the game's archives. Uninstall {title} to clean up.") from e
        mod.files += session.loose
    man.mods.append(mod)
    man.save()
    return mod


def uninstall(game, mod_id, log=print, scope=None):
    _check_closed()
    scope = _editable_scope(game, scope)
    man = Manifest(game, scope)
    mod = next((m for m in man.mods if m.id == mod_id), None)
    if not mod:
        return
    parked = _parked_dir(game, scope, mod.id)
    for rel in mod.files:
        p = game.folder / rel
        if p.is_file():
            p.unlink()
            log(f"removed {rel}")
        (parked / rel).unlink(missing_ok=True)
        d = p.parent
        while d != game.folder and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    targets = set()
    for rec in _package_records(mod):
        targets |= set(rec.get("targets", []))
        (_package_store(game, scope) / rec["file"]).unlink(missing_ok=True)
    shutil.rmtree(parked, ignore_errors=True)
    man.mods = [m for m in man.mods if m.id != mod_id]
    man.save()
    if targets and not mod.disabled:
        rebuild(game, targets, log, scope=scope)


def rebuild(game, targets=None, log=print, scope=None):
    """Recreate mods\\ files from the original game files plus every installed package, in install
    order. targets limits this to those mods\\ paths (normalised); None rebuilds everything, which
    is what's needed after a game update changes the original archives."""
    _check_closed()
    scope = _editable_scope(game, scope)
    man = Manifest(game, scope)
    store = _package_store(game, scope)
    records = [(m, r) for m in sorted(man.mods, key=lambda m: m.installed) if not m.disabled
               for r in _package_records(m)]
    if targets is None:
        targets = set()
        for _, r in records:
            targets |= set(r.get("targets", []))
    for t in sorted(targets):
        p = oivmod.resolve_ci(game.mods_folder, t)
        if p and p.is_file():
            p.unlink()
            log(f"removed mods/{t}")
    session = _session(game, man, log)
    for m, r in records:
        if not set(r.get("targets", [])) & targets:
            continue
        f = store / r["file"]
        if not f.is_file():
            log(f"!! {r['name']} ({m.title}) is missing from the package store; skipped")
            continue
        log(f"== Re-applying {r['name']} ({m.title})")
        session.apply(oivmod.Package.load(f), only=targets)
    session.flush()
    # A mods\\ file that existed before Santux and that no package touches any more
    # goes back to how it was.
    base = store / "base"
    for t in sorted(targets):
        b = oivmod.resolve_ci(base, t)
        if b and b.is_file() and not oivmod.resolve_ci(game.mods_folder, t):
            dest = game.mods_folder / t
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(b), dest)
            log(f"restored your original mods/{t}")
    _prune_empty(game.mods_folder)


def _prune_empty(folder):
    if not folder.is_dir():
        return
    for d in sorted((p for p in folder.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            d.rmdir()


def reset_mods_folder(game, log=print):
    """Delete the whole mods\\ folder and forget every package installed into it."""
    _check_closed()
    scope = _editable_scope(game, None)
    if game.mods_folder.exists():
        shutil.rmtree(game.mods_folder)
        log("Deleted mods folder")
    man = Manifest(game, scope)
    for m in man.mods:
        for r in _package_records(m):
            (_package_store(game, scope) / r["file"]).unlink(missing_ok=True)
        m.packages = []
    man.mods = [m for m in man.mods if m.files]
    man.created_mods_folder = False
    man.save()


def adopt(game, rels, title, scope=None, source="", log=print):
    """Record files that are already in the game folder as installed (e.g. by hand or another tool),
    so profiles manage them from now on."""
    from . import profiles
    scope = scope if scope == profiles.SHARED else _editable_scope(game, scope)
    man = Manifest(game, scope)
    rels = [r for r in rels if (game.folder / r).is_file() and not owner_anywhere(game, r)]
    if not rels:
        return None
    mod = InstalledMod(id=uuid.uuid4().hex[:12], title=title, source=source or f"adopted:{title}",
                       installed=time.time(), files=sorted(rels))
    man.mods.append(mod)
    man.save()
    log(f"Adopted {len(rels)} file(s) as {title}")
    return mod


def unmanaged_files(game):
    """Mod-looking files in the game folder that no install record owns."""
    from . import profiles
    owned = set()
    for scope in (profiles.SHARED, profiles.active(game)):
        for m in Manifest(game, scope).mods:
            owned |= {f.lower() for f in m.files}
    out = []
    f = game.folder
    cands = list(f.glob("*.asi")) + [f / n for n in ("ScriptHookV.dll", "dinput8.dll", "xinput1_4.dll", "args.txt")]
    for sub in ("scripts", "menyooStuff"):
        if (f / sub).is_dir():
            cands += [p for p in (f / sub).rglob("*") if p.is_file()]
    for p in cands:
        if p.is_file():
            rel = p.relative_to(f).as_posix()
            if rel.lower() not in owned:
                out.append(rel)
    return sorted(set(out))


def _parked_dir(game, scope, mod_id):
    """Where a disabled mod's loose files wait (same filesystem as the game, so moves are renames)."""
    from . import profiles
    return profiles.store_dir(game, scope) / "disabled" / mod_id


def set_enabled(game, mod_id, enabled, log=print, scope=None):
    """Disable a mod without uninstalling it, or turn it back on.

    Disabling moves its loose files out of the game folder and rebuilds the mods\\ files its
    packages touched without them. Enabling moves the files back and re-applies its packages."""
    import os
    _check_closed()
    scope = _editable_scope(game, scope)
    man = Manifest(game, scope)
    mod = next((m for m in man.mods if m.id == mod_id), None)
    if not mod or mod.disabled == (not enabled):
        return
    parked = _parked_dir(game, scope, mod.id)
    moved = 0
    for rel in mod.files:
        src, dst = (parked / rel, game.folder / rel) if enabled else (game.folder / rel, parked / rel)
        if src.is_file():
            if dst.exists():
                log(f"!! {rel} already exists at {dst.parent}; left where it is")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            moved += 1
            d = src.parent
            stop = game.folder if not enabled else parked
            while d != stop and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
    if enabled:
        shutil.rmtree(parked, ignore_errors=True)
    mod.disabled = not enabled
    man.save()
    log(f"{'Enabled' if enabled else 'Disabled'} {mod.title} ({moved} file{'s' if moved != 1 else ''} moved)")
    targets = set()
    for rec in _package_records(mod):
        targets |= set(rec.get("targets", []))
    if targets:
        rebuild(game, targets, log, scope=scope)
