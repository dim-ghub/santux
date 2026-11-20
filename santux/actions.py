"""Higher-level flows shared by the GUI and the CLI."""
import re
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


def prepare(archive: Path, game, key=None, title=""):
    """Extract an archive (or use a folder / single file as-is) and analyse it."""
    if archive.is_dir():
        root = archive
    elif archive.suffix.lower() in (".oiv", ".asi", ".dll", ".cs", ".vb", ".rpf"):
        root = util.cache_dir() / "extract" / re.sub(r"\W+", "-", key or archive.stem)
        if root.exists():
            import shutil
            shutil.rmtree(root)
        root.mkdir(parents=True)
        import shutil
        dest = root / (archive.parent.name if archive.name.lower() == "dlc.rpf" else "") / archive.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, dest)
    else:
        root = util.extract(archive, util.cache_dir() / "extract" / re.sub(r"\W+", "-", key or archive.stem))
    return installer.analyse(root, game, title)


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
