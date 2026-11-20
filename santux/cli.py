"""Command-line interface: santux <command> ..."""
import argparse
import sys
from pathlib import Path

from . import actions, deps, game as gamemod, gta5mods, installer, profiles


def pick_game(edition):
    games = gamemod.find_games()
    if edition:
        games = [g for g in games if g.edition.lower() == edition.lower()]
    if not games:
        sys.exit("No GTA V install found in your Steam libraries.")
    return games[0]


def main(argv):
    ap = argparse.ArgumentParser(prog="santux")
    ap.add_argument("--edition", choices=["legacy", "enhanced"], help="which GTA V install to use")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("games", help="show detected GTA V installs")
    s = sub.add_parser("search", help="search gta5-mods.com")
    s.add_argument("query", nargs="*")
    s.add_argument("--category", default="all", choices=list(gta5mods.CATEGORIES))
    s.add_argument("--sort", default="", choices=list(gta5mods.SORTS))
    s.add_argument("--page", type=int, default=1)
    i = sub.add_parser("info", help="show a mod page")
    i.add_argument("url")
    sub.add_parser("reqs", help="show requirement status")
    r = sub.add_parser("req", help="install a requirement (and what it needs)")
    r.add_argument("id", choices=list(deps.BY_ID))
    n = sub.add_parser("install", help="install from a gta5-mods.com URL or a local archive/folder")
    n.add_argument("source")
    n.add_argument("--version", help="version label to download (default: current)")
    n.add_argument("--oiv", action="append", help="install only .oiv files whose path contains this (repeatable)")
    n.add_argument("--dry-run", action="store_true")
    sub.add_parser("list", help="list installed mods (active profile and shared requirements)")
    pr = sub.add_parser("profiles", help="list profiles, or switch/create/delete with --use/--new/--delete")
    pr.add_argument("--use", metavar="SLUG")
    pr.add_argument("--new", metavar="NAME")
    pr.add_argument("--delete", metavar="SLUG")
    pr.add_argument("--launch-default", metavar="SLUG|ask")
    pl = sub.add_parser("play", help="start GTA V from Steam with a profile (needs the launch option)")
    pl.add_argument("profile")
    u = sub.add_parser("uninstall", help="uninstall a mod by id (see list)")
    u.add_argument("id")
    a = ap.parse_args(argv)

    if a.cmd == "games":
        for g in gamemod.find_games():
            print(f"{g.edition:8} {g.version or '?':14} {g.folder}\n         prefix: {g.prefix} "
                  f"({'ok' if g.has_prefix else 'missing'}), Proton {g.proton_version}")
        return
    if a.cmd == "search":
        res, more = gta5mods.search(" ".join(a.query), a.category, a.sort, a.page)
        for m in res:
            print(f"{m.title}  [{m.version}] by {m.author}  ↓{m.downloads} ★{m.rating}\n    {m.url}")
        if more:
            print(f"(more: --page {a.page + 1})")
        return
    if a.cmd == "info":
        d = gta5mods.details(a.url)
        print(f"{d.title} {d.version} by {d.author}, ↓{d.downloads}, updated {d.updated}\n")
        print(d.description[:2000], "\n")
        for f in d.files:
            print(f"  {f.label:28} {f.size:10} {f.date:18} {'current' if f.current else ''}")
        return

    g = pick_game(a.edition)
    if a.cmd == "reqs":
        for r in deps.for_game(g):
            st = r.status(g)
            print(f"  {st.state:8} {r.name:34} {st.detail}")
    elif a.cmd == "req":
        actions.install_requirement(g, deps.BY_ID[a.id])
    elif a.cmd == "list":
        for scope, label in ((profiles.SHARED, "shared"), (profiles.active(g), profiles.active_profile(g).name)):
            for m in installer.Manifest(g, scope).mods:
                print(f"  [{label}] {m.id}  {m.title} {m.version}  ({len(m.files)} files, {len(m.packages)} packages)")
    elif a.cmd == "profiles":
        if a.new:
            print("created", profiles.create(g, a.new))
        if a.delete:
            profiles.delete(g, a.delete)
        if a.use:
            profiles.activate(g, a.use)
        if a.launch_default:
            profiles.set_launch_default(g, a.launch_default)
        print(f"launch default: {profiles.launch_default(g)}")
        for p in profiles.summary(g):
            print(f"  {'*' if p['active'] else ' '} {p['slug']:14} {p['name']:24} {p['kind']:8} {p['mods']} mods")
    elif a.cmd == "play":
        from .launcher import play
        return play(a.profile, g.appid)
    elif a.cmd == "uninstall":
        installer.uninstall(g, a.id)
    elif a.cmd == "install":
        src = a.source
        title, version = Path(src).stem, ""
        if src.startswith("http"):
            d = gta5mods.details(src)
            f = next((x for x in d.files if x.label == a.version), None) if a.version else \
                actions.default_file(d, g)
            if not d.files:
                sys.exit(f"No downloadable files found on {src}")
            if not f:
                sys.exit(f"No version {a.version}; have: " + ", ".join(x.label for x in d.files))
            print(f"{d.title}: file {f.label}")
            archive = actions.download_mod_file(d, f)
            title, version, key = d.title, f.label, d.slug
        else:
            archive, key = Path(src), None
        plan = actions.prepare(archive, g, key, title)
        oivs = plan.chosen_oivs
        if a.oiv:
            oivs = [p for p in plan.oivs if any(s.lower() in str(p.relative_to(plan.root)).lower() for s in a.oiv)]
        print("Packages found:")
        for p in plan.oivs:
            print(f"  [{'x' if p in oivs else ' '}] {p.relative_to(plan.root)}")
        for rpf, pack in plan.addons:
            print(f"  add-on DLC: {pack}")
        for s, d_ in plan.copies:
            print(f"  copy {d_}")
        for s, why in plan.skipped:
            print(f"  skip {s}: {why}")
        missing = actions.missing_for_plan(g, plan)
        if missing:
            print("Missing requirements: " + ", ".join(r.name for r in missing))
        if a.dry_run:
            return
        if not (oivs or plan.addons or plan.copies):
            sys.exit(f"Nothing to install automatically. Files are in {plan.root}")
        installer.install(g, plan, title, version, src, oivs=oivs)
        print("Installed.")
