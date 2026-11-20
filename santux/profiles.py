"""Mod profiles.

The game folder holds one profile's mods at a time. Requirements (Script Hook V, ASI plugins
that every modded profile needs) are shared and always present. Each modded profile owns:

- its loose mod files (.asi plugins, scripts, Menyoo data), and
- its own mods\\ folder (archive edits from .oiv packages).

Switching profile moves the outgoing profile's files and mods\\ folder into
<game>/santux/<profile>/ and moves the incoming one's back. Those are renames on the
same filesystem, so switching is instant however big the mods folder is.

Two built-in profiles have no files of their own: "vanilla" launches the game without the ASI
loader (nothing modded loads), and "gtavxr" launches the GTAVXR Suite for VR.
"""
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, asdict

from . import util

SHARED = "_shared"
VANILLA = "vanilla"
VR = "gtavxr"
DEFAULT = "default"
STORE = "santux"          # folder inside the game folder for inactive profiles


class ProfileError(Exception):
    pass


@dataclass
class Profile:
    slug: str
    name: str
    kind: str                     # "modded" | "vanilla" | "vr"
    created: float = 0.0
    notes: str = ""

    @property
    def editable(self):
        return self.kind == "modded"


def game_dir(game):
    d = util.data_dir() / "games" / str(game.appid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def scope_dir(game, scope):
    d = game_dir(game) / ("shared" if scope == SHARED else f"profiles/{scope}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_dir(game, slug):
    return game.folder / STORE / slug


def _state_path(game):
    return game_dir(game) / "profiles.json"


def _load(game):
    p = _state_path(game)
    if p.is_file():
        return json.loads(p.read_text())
    return {"active": None, "profiles": [], "launch": "ask"}


def _save(game, st):
    p = _state_path(game)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2))
    tmp.replace(p)


def ensure(game):
    """Create the built-in profiles and migrate single-profile installs. Returns the state."""
    st = _load(game)
    have = {p["slug"] for p in st["profiles"]}
    changed = False
    for slug, name, kind, notes in (
            (VANILLA, "Vanilla", "vanilla", "The unmodified game: no ASI loader, no mods folder."),
            (DEFAULT, "Modded", "modded", ""),
            (VR, "GTAVXR (VR)", "vr", "Launches the GTAVXR Suite. Its mods are managed in the Suite.")):
        if slug not in have:
            st["profiles"].append(asdict(Profile(slug, name, kind, time.time(), notes)))
            changed = True
    if st.get("active") is None:
        st["active"] = DEFAULT
        changed = True
    if changed:
        _save(game, st)
    _migrate_v1(game)
    return st


def _migrate_v1(game):
    """Before profiles, everything lived in games/<appid>/installed.json and packages/."""
    gd = game_dir(game)
    old = gd / "installed.json"
    if not old.is_file():
        return
    data = json.loads(old.read_text())
    shared, mine = [], []
    for m in data.get("mods", []):
        src = m.get("source", "")
        (shared if src.startswith("requirement:") and src != "requirement:gameconfig" else mine).append(m)
    (scope_dir(game, SHARED) / "installed.json").write_text(json.dumps({"mods": shared}, indent=2))
    d = scope_dir(game, DEFAULT)
    (d / "installed.json").write_text(json.dumps({"mods": mine, "created_mods_folder": data.get("created_mods_folder", False)}, indent=2))
    if (gd / "packages").is_dir():
        shutil.rmtree(d / "packages", ignore_errors=True)
        shutil.move(str(gd / "packages"), d / "packages")
    old.rename(gd / "installed.v1.json")


def profiles(game):
    return [Profile(**p) for p in ensure(game)["profiles"]]


def get(game, slug):
    return next((p for p in profiles(game) if p.slug == slug), None)


def active(game):
    return ensure(game)["active"]


def active_profile(game):
    return get(game, active(game))


def launch_default(game):
    return ensure(game).get("launch", "ask")


def set_launch_default(game, value):
    st = ensure(game)
    st["launch"] = value
    _save(game, st)


def _slugify(name, taken):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"
    slug, n = base, 2
    while slug in taken or slug in (SHARED, STORE):
        slug, n = f"{base}-{n}", n + 1
    return slug


def create(game, name):
    st = ensure(game)
    name = name.strip() or "New profile"
    slug = _slugify(name, {p["slug"] for p in st["profiles"]})
    st["profiles"].append(asdict(Profile(slug, name, "modded", time.time())))
    _save(game, st)
    return slug


def rename(game, slug, name):
    st = ensure(game)
    for p in st["profiles"]:
        if p["slug"] == slug:
            p["name"] = name.strip() or p["name"]
    _save(game, st)


def delete(game, slug, log=print):
    """Delete a modded profile and everything installed in it (shared requirements stay)."""
    p = get(game, slug)
    if not p or not p.editable:
        raise ProfileError("Only your own mod profiles can be deleted.")
    if active(game) == slug:
        activate(game, VANILLA, log)
    shutil.rmtree(store_dir(game, slug), ignore_errors=True)
    shutil.rmtree(scope_dir(game, slug), ignore_errors=True)
    st = ensure(game)
    st["profiles"] = [q for q in st["profiles"] if q["slug"] != slug]
    if st.get("launch") == slug:
        st["launch"] = "ask"
    _save(game, st)
    log(f"Deleted profile {p.name}")


# ---------------------------------------------------------------- switching

def _files_of(game, slug):
    from .installer import Manifest
    out = []
    for m in Manifest(game, slug).mods:
        out += m.files
    return out


def _move(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def _prune(folder, stop):
    d = folder
    while d != stop and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def _stash(game, slug, log):
    store = store_dir(game, slug)
    moved = 0
    for rel in _files_of(game, slug):
        src = game.folder / rel
        if src.is_file() or src.is_symlink():
            _move(src, store / "files" / rel)
            _prune(src.parent, game.folder)
            moved += 1
    if game.mods_folder.exists():
        if (store / "mods").exists():
            raise ProfileError(f"{store / 'mods'} already exists; not overwriting it.")
        _move(game.mods_folder, store / "mods")
    log(f"Stored {moved} file{'s' if moved != 1 else ''} of profile {slug}")


def _unstash(game, slug, log):
    store = store_dir(game, slug)
    files = store / "files"
    moved = 0
    if files.is_dir():
        for src in sorted(p for p in files.rglob("*") if p.is_file() or p.is_symlink()):
            rel = src.relative_to(files)
            dest = game.folder / rel
            if dest.exists():
                log(f"!! {rel} is already in the game folder; keeping the profile's copy in {files}")
                continue
            _move(src, dest)
            moved += 1
        for d in sorted((p for p in files.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(d.iterdir()):
                d.rmdir()
    if (store / "mods").exists():
        if game.mods_folder.exists():
            raise ProfileError("The game folder has a mods folder that isn't part of any profile. "
                               "Move it away, or install it into a profile first.")
        _move(store / "mods", game.mods_folder)
    _prune(store, game.folder)
    log(f"Restored {moved} file{'s' if moved != 1 else ''} of profile {slug}")


def activate(game, slug, log=print):
    """Make slug the profile whose files are in the game folder."""
    from .game import running_game_processes
    st = ensure(game)
    cur = st["active"]
    if cur == slug:
        return
    target = get(game, slug)
    if target is None:
        raise ProfileError(f"No profile called {slug}")
    if running_game_processes():
        raise ProfileError("Close GTA V before switching profiles.")
    cur_p = get(game, cur)
    if cur_p and cur_p.kind == "modded":
        _stash(game, cur, log)
    elif game.mods_folder.exists() and target.kind == "modded":
        raise ProfileError("The game folder has a mods folder that isn't part of any profile.")
    if target.kind == "modded":
        _unstash(game, slug, log)
    st["active"] = slug
    _save(game, st)
    log(f"Active profile: {target.name}")


def summary(game):
    """Profiles with a little detail, for the UI and the picker."""
    from .installer import Manifest
    act = active(game)
    out = []
    for p in profiles(game):
        mods = [m for m in Manifest(game, p.slug).mods if not m.source.startswith("requirement:")] if p.kind == "modded" else []
        out.append({"slug": p.slug, "name": p.name, "kind": p.kind, "active": p.slug == act,
                    "mods": len(mods), "notes": p.notes,
                    "titles": [m.title for m in sorted(mods, key=lambda m: m.installed)][:40]})
    order = {"vanilla": 0, "modded": 1, "vr": 2}
    return sorted(out, key=lambda x: (order[x["kind"]], x["name"].lower()))
