"""Higher-level flows shared by the GUI and the CLI."""
import os
import re
import shutil
from pathlib import Path

from . import deps, gta5mods, installer, util


def download_mod_file(details, mod_file, progress=None, log=print, cancel=None):
    """Download one version of a gta5-mods.com mod into the downloads folder (verified when possible)."""
    url = gta5mods.resolve_file(mod_file.page)
    name = f"{details.slug}--{gta5mods.file_name(url)}"
    dest = util.downloads_dir() / name
    if dest.is_file() and mod_file.sha256 and util.sha256_file(dest) == mod_file.sha256:
        log(f"Using cached {name}")
        return dest
    log(f"Downloading {gta5mods.file_name(url)} ({mod_file.size or 'unknown size'})")
    util.http.download(url, dest, progress=progress, sha256=mod_file.sha256 or None, cancel=cancel)
    log("SHA-256 verified" if mod_file.sha256 else "No SHA-256 published for this file; not verified")
    return dest


LOOSE = (".oiv", ".asi", ".dll", ".cs", ".vb", ".rpf")
ARCHIVES = (".zip", ".7z", ".rar")


def _work_dir(key):
    root = util.cache_dir() / "extract" / re.sub(r"\W+", "-", key)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _place(src: Path, root: Path):
    dest = root / (src.parent.name if src.name.lower() == "dlc.rpf" else "") / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    installer.link_or_copy(src, dest)


def prepare(archive: Path, game, key=None, title=""):
    """Extract an archive (or use a folder / single file as-is) and analyse it."""
    if archive.is_dir():
        root = archive
    elif archive.suffix.lower() in ARCHIVES:
        root = util.extract(archive, util.cache_dir() / "extract" / re.sub(r"\W+", "-", key or archive.stem))
    else:
        root = _work_dir(key or archive.stem)
        _place(archive, root)
    return installer.analyse(root, game, title)


def prepare_many(paths, game, title):
    """Several files opened together (e.g. the parts of a multi-part .oiv mod), as one plan.
    Archives among them are unpacked next to the loose files."""
    root = _work_dir(title)
    for p in paths:
        if p.is_dir():
            shutil.copytree(p, root / p.name, copy_function=installer.link_or_copy, dirs_exist_ok=True)
        elif p.suffix.lower() in ARCHIVES:
            util.extract(p, root / p.stem)
        else:
            _place(p, root)
    return installer.analyse(root, game, title)


def package_title(paths):
    """A name for opened files: the .oiv's own name for a single package, else the file or folder."""
    if len(paths) == 1 and paths[0].suffix.lower() == ".oiv":
        try:
            return installer.oiv_name(paths[0]) or paths[0].stem
        except Exception:
            return paths[0].stem
    if len(paths) == 1:
        return paths[0].stem if paths[0].is_file() else paths[0].name
    # "1. Liberty City Installer - Part ONE" + "2. ... Part TWO" -> "Liberty City Installer"
    stems = [re.sub(r"^\s*\d+\s*[.)_-]?\s*", "", p.stem) for p in paths]
    prefix = re.sub(r"[\s_-]*(part|pt|vol)?[\s.]*$", "", os.path.commonprefix(stems), flags=re.I).strip(" -_.")
    return prefix or f"{paths[0].stem} and {len(paths) - 1} more"


def missing_for_plan(game, plan):
    """Requirement ids a plan needs that aren't installed yet."""
    need = set()
    if plan.chosen_oivs or plan.addons:
        need.add("rageopenv")
    for _, dest in plan.copies:
        if dest.lower().endswith(".asi") or dest.lower().startswith("scripts/"):
            need.add("scripthookv")
        if dest.lower().startswith("scripts/"):
            need.add("shvdn")
    if plan.chosen_oivs or plan.addons or any(d.lower().endswith(".asi") for _, d in plan.copies):
        need.add("launchoption")
    out = []
    for rid in ("scripthookv", "launchoption", "rageopenv", "shvdn"):
        r = deps.BY_ID[rid]
        if rid in need and r.applies(game) and r.status(game).state not in (deps.OK, deps.INFO):
            out.append(r)
    return out


def install_requirement(game, req, log=print, done=None):
    """Install a requirement and, first, anything it depends on."""
    done = set() if done is None else done
    for dep in req.needs:
        d = deps.BY_ID[dep]
        if dep not in done and d.applies(game) and d.status(game).state in (deps.MISSING, deps.UPDATE):
            install_requirement(game, d, log, done)
    log(f"== {req.name}")
    req.install(game, log)
    done.add(req.id)


def default_file(details, game):
    """The file version to offer first: the current one, unless the mod labels files per edition
    and another file is the one for this game's edition."""
    files = details.files
    if not files:
        return None
    current = next((f for f in files if f.current), files[0])
    mine, other = game.edition.lower(), ("enhanced" if game.legacy else "legacy")
    label = current.label.lower()
    if other in label and mine not in label:
        match = next((f for f in files if mine in f.label.lower() and other not in f.label.lower()), None)
        if match:
            return match
    return current
