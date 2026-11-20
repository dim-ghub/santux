"""Launching GTA V through a profile.

Steam launch option:   santux launch %command%
                       santux launch --profile <slug> %command%   (also --vanilla, --vr, --ask)

Without a flag, the profile comes from a pending `santux play <profile>`, then from the
"launch" setting (a profile, or "ask" to show the picker).
"""
import json
import os
import subprocess
import sys
import time

from . import game as gamemod, profiles, util

NEXT = "next-launch.json"
SAVED_ENV = ("LD_PRELOAD", "LD_LIBRARY_PATH")


def _game_for(appid=None):
    games = gamemod.find_games()
    appid = appid or os.environ.get("SteamAppId") or os.environ.get("SteamGameId")
    if appid:
        g = next((g for g in games if str(g.appid) == str(appid)), None)
        if g:
            return g
    if not games:
        sys.exit("santux: no GTA V install found")
    return games[0]


def _pending(game):
    p = util.data_dir() / NEXT
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text())
    finally:
        p.unlink(missing_ok=True)
    if str(d.get("appid")) == str(game.appid) and time.time() - d.get("time", 0) < 600:
        return d.get("profile")
    return None


def _restore_steam_env(env):
    """The shell wrapper hides Steam's LD_PRELOAD/LD_LIBRARY_PATH from Python; the game gets them back.
    (The single binary needs no wrapper: util.child_env undoes its bootloader's changes.)"""
    for k in SAVED_ENV:
        v = env.pop("SANTUX_SAVED_" + k, None)
        if v is None:
            continue
        if v == "__unset__":
            env.pop(k, None)
        else:
            env[k] = v


def _ask(game):
    """Show the profile picker in a clean environment. Returns a profile slug, or None."""
    env = util.child_env(itself=True)
    for k in SAVED_ENV:
        env.pop(k, None)
    r = subprocess.run(util.self_command() + ["picker", "--appid", str(game.appid)],
                       stdout=subprocess.PIPE, text=True, env=env)
    choice = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return choice or None


def _override(env, dll_override, on):
    parts = [p for p in env.get("WINEDLLOVERRIDES", "").split(";") if p]
    name = dll_override.split("=")[0]
    parts = [p for p in parts if p.split("=")[0] != name]
    if on:
        parts.insert(0, dll_override)
    if parts:
        env["WINEDLLOVERRIDES"] = ";".join(parts)
    else:
        env.pop("WINEDLLOVERRIDES", None)


def launch(argv):
    choice, i = None, 0
    while i < len(argv) and argv[i].startswith("--"):
        a = argv[i]
        if a == "--profile" and i + 1 < len(argv):
            choice, i = argv[i + 1], i + 2
            continue
        if a.startswith("--profile="):
            choice = a.split("=", 1)[1]
        elif a == "--vanilla":
            choice = profiles.VANILLA
        elif a == "--vr":
            choice = profiles.VR
        elif a == "--ask":
            choice = "ask"
        elif a == "--":
            i += 1
            break
        i += 1
    cmd = argv[i:]
    if not cmd:
        sys.exit("usage: santux launch [--profile NAME | --vanilla | --vr | --ask] %command%")

    game = _game_for()
    profiles.ensure(game)
    choice = choice or _pending(game) or profiles.launch_default(game)
    if choice == "ask":
        choice = _ask(game)
        if not choice:
            print("santux: launch cancelled", file=sys.stderr)
            return 0
    prof = profiles.get(game, choice) or next((p for p in profiles.profiles(game) if p.name.lower() == choice.lower()), None)
    if prof is None:
        sys.exit(f"santux: no profile '{choice}'")

    profiles.activate(game, prof.slug, log=lambda l: print("santux:", l, file=sys.stderr))
    env = util.child_env()
    _restore_steam_env(env)
    if prof.kind == "vr":
        if not (game.folder / "GTAVXR.exe").is_file():
            sys.exit("santux: GTAVXR isn't set up. Open Santux → VR to set it up.")
        _override(env, game.dll_override, False)
        cmd = [a.replace("PlayGTAV.exe", "GTAVXR.exe") for a in cmd]
    else:
        _override(env, game.dll_override, prof.kind == "modded")
    print(f"santux: launching profile {prof.name}", file=sys.stderr)
    os.execvpe(cmd[0], cmd, env)


def play(profile, appid=None):
    """Launch GTA V from Steam with a given profile (works when the launch option is set)."""
    game = _game_for(appid)
    profiles.ensure(game)
    if profile not in (p.slug for p in profiles.profiles(game)):
        sys.exit(f"No profile '{profile}'. Profiles: " + ", ".join(p.slug for p in profiles.profiles(game)))
    (util.data_dir() / NEXT).write_text(json.dumps({"appid": game.appid, "profile": profile, "time": time.time()}))
    url = f"steam://rungameid/{game.appid}"
    for opener in (["steam", url], ["xdg-open", url]):
        try:
            subprocess.Popen(opener, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                             env=util.child_env())
            return 0
        except FileNotFoundError:
            continue
    sys.exit("Couldn't start Steam")
