"""The QObject that QML talks to. Long work runs in threads and reports back through signals."""
import threading
import traceback
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from .. import actions, deps, game as gamemod, gta5mods, gtavxr, installer, launcher, profiles, util

GROUPS = [
    ("Proton prefix", "Runtimes installed into GTA V's own Wine prefix.", ["vcrun2022", "dotnet48"]),
    ("Script loaders", "What lets the game load mods at all.", ["scripthookv", "launchoption", "rageopenv", "shvdn"]),
    ("Stability", "Raise the game's limits so bigger mod setups don't crash.", ["gameconfig", "heapadjuster", "packfilelimit"]),
]


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


class Backend(QObject):
    gamesChanged = Signal()
    gameChanged = Signal()
    busyChanged = Signal()

    searchFinished = Signal(int, "QVariantList", bool)       # request id, results, more pages
    searchFailed = Signal(int, str)
    detailsLoaded = Signal(str, "QVariantMap")               # url, details
    detailsFailed = Signal(str, str)

    taskStarted = Signal(str)                                # title
    taskLog = Signal(str)
    taskStatus = Signal(str)
    taskProgress = Signal(float)                             # 0..1, or -1 for indeterminate
    taskFinished = Signal(bool, str)                         # ok, message
    planReady = Signal("QVariantMap")
    toast = Signal(str)
    stateChanged = Signal()                                  # installed mods / requirements changed

    def __init__(self):
        super().__init__()
        self._games = gamemod.find_games()
        self._game = self._games[0] if self._games else None
        self._busy = False
        self._plan = None
        self._req_id = 0
        self._cancel = threading.Event()

    # ------------------------------------------------------------ game
    @Property("QVariantList", notify=gamesChanged)
    def games(self):
        return [f"GTA V {g.edition}" for g in self._games]

    @Property(bool, notify=gamesChanged)
    def hasGame(self):
        return self._game is not None

    @Property(int, notify=gameChanged)
    def gameIndex(self):
        return self._games.index(self._game) if self._game else -1

    @Slot(int)
    def selectGame(self, i):
        if 0 <= i < len(self._games):
            self._game = self._games[i]
            self.gameChanged.emit()
            self.stateChanged.emit()

    @Property("QVariantMap", notify=gameChanged)
    def gameInfo(self):
        g = self._game
        if not g:
            return {}
        return {
            "edition": g.edition, "version": g.version or "unknown", "folder": str(g.folder),
            "prefix": str(g.prefix) if g.has_prefix else "", "proton": g.proton_version or "unknown",
            "steam": "Flatpak" if g.flatpak_steam else str(g.steam_root),
            "launchOptions": deps.launch_options(g) or "", "legacy": g.legacy,
            "dataDir": str(util.data_dir()),
        }

    @Slot(result=bool)
    def gameRunning(self):
        return bool(gamemod.running_game_processes())

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    # ------------------------------------------------------------ helpers
    @Slot(str)
    def openUrl(self, url):
        QDesktopServices.openUrl(QUrl(url))

    @Slot(str)
    def openPath(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot()
    def launchGame(self):
        if self._game:
            QDesktopServices.openUrl(QUrl(f"steam://rungameid/{self._game.appid}"))

    @Slot(str)
    def copy(self, text):
        QGuiApplication.clipboard().setText(text)

    @Slot(result="QVariantList")
    def categories(self):
        return [{"key": k, "label": v} for k, v in gta5mods.CATEGORIES.items()]

    @Slot(result="QVariantList")
    def sorts(self):
        return [{"key": k, "label": v} for k, v in gta5mods.SORTS.items()]

    def _thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ------------------------------------------------------------ browsing
    @Slot(str, str, str, int, result=int)
    def search(self, query, category, sort, page):
        self._req_id += 1
        rid = self._req_id
        if not query and not sort:
            sort = "most-downloaded"

        def work():
            try:
                res, more = gta5mods.search(query, category, sort, page)
                out = [{"url": m.url, "title": m.title, "image": m.image, "version": m.version,
                        "author": m.author, "downloads": m.downloads, "likes": m.likes,
                        "rating": m.rating, "categories": " · ".join(m.categories)} for m in res]
                self.searchFinished.emit(rid, out, more)
            except Exception as e:
                self.searchFailed.emit(rid, str(e))
        self._thread(work)
        return rid

    @Slot(str)
    def loadDetails(self, url):
        def work():
            try:
                d = gta5mods.details(url)
                best = actions.default_file(d, self._game) if self._game else None
                files = [{"label": f.label, "current": f.current, "size": f.size, "date": f.date,
                          "downloads": f.downloads, "verified": bool(f.sha256), "index": i,
                          "recommended": f is best} for i, f in enumerate(d.files)]
                self._details_cache[url] = d
                self.detailsLoaded.emit(url, {
                    "url": d.url, "title": d.title, "version": d.version, "author": d.author,
                    "description": d.description, "images": d.images, "files": files,
                    "downloads": d.downloads, "updated": d.updated,
                    "installed": bool(self._game and installer.Manifest(self._game).find(d.url)),
                })
            except Exception as e:
                self.detailsFailed.emit(url, str(e))
        self._thread(work)

    _details_cache = {}

    # ------------------------------------------------------------ tasks
    taskQuiet = Signal(bool)

    def _run_task(self, title, fn, on_done=None, success="Done.", quiet=False):
        """Run fn(log, status, progress) in a thread, reporting through task signals."""
        if self._busy:
            self.toast.emit("Something is already running.")
            return
        self._busy = True
        self._cancel.clear()
        self.busyChanged.emit()
        self.taskQuiet.emit(quiet)
        self.taskStarted.emit(title)

        def log(line):
            self.taskLog.emit(str(line))

        def work():
            ok, msg = True, success
            try:
                result = fn(log, self.taskStatus.emit, self.taskProgress.emit)
                if on_done:
                    on_done(result)
            except Exception as e:
                ok, msg = False, str(e) or e.__class__.__name__
                log("".join(traceback.format_exception(e)).rstrip())
            self._busy = False
            self.busyChanged.emit()
            self.taskFinished.emit(ok, msg)
            self.stateChanged.emit()
        self._thread(work)

    @Slot()
    def cancelTask(self):
        self._cancel.set()

    @Slot(str, int)
    def installFromSite(self, url, index):
        d = self._details_cache.get(url)
        if not d or not self._game:
            return
        f = d.files[index]
        game = self._game

        def work(log, status, progress):
            def prog(done, total):
                progress(done / total if total else -1)
                status(f"Downloading… {util.human_size(done)}" + (f" of {util.human_size(total)}" if total else ""))
            archive = actions.download_mod_file(d, f, progress=prog, log=log, cancel=self._cancel)
            progress(-1)
            status("Unpacking…")
            return actions.prepare(archive, game, key=d.slug, title=d.title)

        self._run_task(f"Getting {d.title}", work,
                       on_done=lambda plan: self._offer_plan(plan, d.title, f.label, d.url, d.author),
                       success="Ready to install.")

    @Slot(str)
    def installLocal(self, path):
        self.openPaths([path])

    @Slot("QVariantList")
    def openPaths(self, paths):
        """Files or folders opened from the file manager, the command line or the app: one archive,
        .oiv package or folder, or several files (the parts of a multi-part mod) as one plan."""
        if not self._game:
            return
        ps = [Path(QUrl(p).toLocalFile() if str(p).startswith("file:") else str(p)) for p in paths]
        ps = [p for p in ps if p.exists()]
        if not ps:
            self.toast.emit("Nothing to open.")
            return
        game = self._game
        title = actions.package_title(ps)

        def work(log, status, progress):
            status("Unpacking…" if any(p.suffix.lower() in actions.ARCHIVES for p in ps) else "Reading…")
            if len(ps) == 1:
                return actions.prepare(ps[0], game, title=title)
            return actions.prepare_many(ps, game, title)

        source = str(ps[0]) if len(ps) == 1 else ""
        self._run_task(f"Opening {ps[0].name if len(ps) == 1 else title}", work,
                       on_done=lambda plan: self._offer_plan(plan, title, "", source),
                       success="Ready to install.")

    def _offer_plan(self, plan, title, version, source, author=""):
        game = self._game
        self._plan = (plan, title, version, source, author)
        skipped = plan.skipped
        if len(skipped) > 12:
            groups = Counter("/".join(p.split("/")[:2]) for p, _ in skipped)
            skipped_rows = [f"{g}/ — {_plural(n, 'file')}" for g, n in groups.most_common()]
        else:
            skipped_rows = [f"{p} — {why}" for p, why in skipped]
        missing = actions.missing_for_plan(game, plan)
        self.planReady.emit({
            "title": title, "version": version, "edition": game.edition,
            "oivs": [{"name": installer.oiv_name(p), "path": p.relative_to(plan.root).as_posix(),
                      "checked": p in plan.chosen_oivs} for p in plan.oivs],
            "addons": [pack for _, pack in plan.addons],
            "copies": [dest for _, dest in plan.copies],
            "skipped": skipped_rows, "skippedCount": len(skipped),
            "missing": [r.name for r in missing],
            "root": str(plan.root),
            "empty": plan.empty and not plan.oivs,
        })

    @Slot("QVariantList", bool)
    def commitPlan(self, order, install_reqs):
        """order: indexes into the plan's .oiv list, in the order to install them (unticked ones left out)."""
        if not self._plan:
            return
        plan, title, version, source, author = self._plan
        self._plan = None
        oivs = [plan.oivs[int(i)] for i in order] if plan.oivs else []
        game = self._game
        reqs = actions.missing_for_plan(game, plan) if install_reqs else []

        def work(log, status, progress):
            done = set()
            for r in reqs:
                status(f"Installing {r.name}…")
                actions.install_requirement(game, r, log, done)
            status(f"Installing {title}…")
            mod = installer.install(game, plan, title, version, source, author, oivs=oivs, log=log)
            for n in mod.notes:
                log("Note: " + n)
        self._run_task(f"Installing {title}", work, success=f"{title} is installed.")

    @Slot()
    def discardPlan(self):
        self._plan = None

    # ------------------------------------------------------------ installed
    @Slot(result="QVariantList")
    def installedMods(self):
        if not self._game:
            return []
        out = []
        for m in sorted(installer.Manifest(self._game).mods, key=lambda m: -m.installed):
            if m.source.startswith("requirement:"):
                continue
            pk = [p["name"] if isinstance(p, dict) else p for p in m.packages]
            bits = [m.version, _plural(len(m.files), "file") if m.files else "",
                    _plural(len(pk), "package") if pk else ""]
            out.append({"id": m.id, "title": m.title, "summary": "  ·  ".join(b for b in bits if b),
                        "disabled": m.disabled,
                        "files": m.files[:300], "packages": pk, "notes": m.notes,
                        "source": m.source, "web": m.source.startswith("http")})
        return out

    @Slot(str, str)
    def uninstall(self, mod_id, title):
        game = self._game
        self._run_task(f"Uninstalling {title}", lambda log, st, pr: installer.uninstall(game, mod_id, log=log),
                       success=f"{title} was removed.")

    @Slot()
    def rebuildMods(self):
        game = self._game
        self._run_task("Rebuilding the mods folder", lambda log, st, pr: installer.rebuild(game, None, log),
                       success="The mods folder was rebuilt from the original game files.")

    @Slot()
    def resetMods(self):
        game = self._game
        self._run_task("Resetting the mods folder", lambda log, st, pr: installer.reset_mods_folder(game, log),
                       success="The mods folder was deleted.")

    # ------------------------------------------------------------ requirements
    @Slot(result="QVariantList")
    def requirementGroups(self):
        game = self._game
        if not game:
            return []
        out = []
        for title, desc, ids in GROUPS:
            rows = []
            for rid in ids:
                r = deps.BY_ID[rid]
                if not r.applies(game):
                    continue
                st = r.status(game)
                rows.append({"id": rid, "name": r.name, "description": r.description, "state": st.state,
                             "detail": st.detail,
                             "action": {"missing": "Install", "update": "Update", "info": "Set"}.get(st.state, "Reinstall"),
                             "copyText": r.wanted(game) if rid == "launchoption" else ""})
            out.append({"title": title, "description": desc, "rows": rows})
        return out

    @Slot(str)
    def installRequirement(self, rid):
        game, r = self._game, deps.BY_ID[rid]
        self._run_task(r.name, lambda log, st, pr: actions.install_requirement(game, r, log),
                       success=f"{r.name} is set up.")

    @Slot()
    def installAllMissing(self):
        game = self._game

        def work(log, status, progress):
            done = set()
            todo = [r for r in deps.for_game(game) if r.recommended and r.status(game).state in (deps.MISSING, deps.UPDATE)]
            if not todo:
                log("Everything is already installed.")
            for r in todo:
                if r.id in done:
                    continue
                status(f"Installing {r.name}…")
                try:
                    actions.install_requirement(game, r, log, done)
                except Exception as e:
                    log(f"!! {r.name} failed: {e}")
                    if r.id in ("dotnet48", "vcrun2022", "scripthookv"):
                        raise
        self._run_task("Installing requirements", work, success="Finished. Check the log for anything that needs your attention.")

    @Slot()
    def preparePrefix(self):
        game = self._game

        def work(log, status, progress):
            if not game.has_prefix:
                raise installer.InstallError("Launch GTA V from Steam once so Proton creates the prefix.")
            for rid in ("vcrun2022", "dotnet48"):
                r = deps.BY_ID[rid]
                if r.status(game).state == deps.OK:
                    log(f"{r.name}: already installed")
                    continue
                status(f"Installing {r.name}… (this takes a while)")
                r.install(game, log)
        self._run_task("Preparing the prefix", work, success="The prefix is ready.")

    # ------------------------------------------------------------ profiles
    @Slot(result="QVariantList")
    def profiles(self):
        return profiles.summary(self._game) if self._game else []

    @Slot(result="QVariantMap")
    def activeProfile(self):
        p = profiles.active_profile(self._game) if self._game else None
        return {"slug": p.slug, "name": p.name, "kind": p.kind, "editable": p.editable} if p else {}

    @Slot(result=str)
    def launchDefault(self):
        return profiles.launch_default(self._game) if self._game else "ask"

    @Slot(str)
    def setLaunchDefault(self, value):
        profiles.set_launch_default(self._game, value)
        self.stateChanged.emit()

    @Slot(str, result=str)
    def createProfile(self, name):
        slug = profiles.create(self._game, name)
        self.stateChanged.emit()
        return slug

    @Slot(str, str)
    def renameProfile(self, slug, name):
        profiles.rename(self._game, slug, name)
        self.stateChanged.emit()

    @Slot(str)
    def deleteProfile(self, slug):
        game = self._game
        self._run_task("Deleting profile", lambda log, st, pr: profiles.delete(game, slug, log), success="Profile deleted.")

    @Slot(str)
    def switchProfile(self, slug):
        game = self._game
        self._run_task("Switching profile", lambda log, st, pr: profiles.activate(game, slug, log),
                       success="Switched.", quiet=True)

    @Slot(str)
    def play(self, slug):
        """Start GTA V from Steam with this profile."""
        try:
            launcher.play(slug, self._game.appid)
            self.toast.emit("Starting GTA V through Steam…")
        except SystemExit as e:
            self.toast.emit(str(e))

    @Slot(result="QVariantList")
    def unmanagedFiles(self):
        return installer.unmanaged_files(self._game) if self._game else []

    @Slot("QVariantList", str)
    def adoptFiles(self, rels, title):
        game = self._game
        self._run_task("Adding existing files", lambda log, st, pr: installer.adopt(game, list(rels), title or "Existing files", log=log),
                       success="They're now part of this profile.")

    # ------------------------------------------------------------ VR
    @Slot(result="QVariantList")
    def vrStatus(self):
        return gtavxr.status(self._game) if self._game else []

    @Slot(result=bool)
    def steamvrRunning(self):
        return gtavxr.steamvr_running()

    @Slot(str)
    def vrStep(self, step):
        game = self._game
        names = {s["id"]: s["name"] for s in gtavxr.status(game)}
        self._run_task(names.get(step, step), lambda log, st, pr: gtavxr.run_step(game, step, log))

    @Slot()
    def vrSetupAll(self):
        game = self._game
        self._run_task("Setting up GTAVXR", lambda log, st, pr: gtavxr.setup_all(game, log),
                       success="Done. If the Suite still needs installing, use Open Suite.")

    @Slot(str, str, bool)
    def setModEnabled(self, mod_id, title, enabled):
        game = self._game
        self._run_task(("Enabling " if enabled else "Disabling ") + title,
                       lambda log, st, pr: installer.set_enabled(game, mod_id, enabled, log),
                       success=f"{title} is {'on' if enabled else 'off'}.", quiet=True)

    adultChanged = Signal()

    @Property(bool, notify=adultChanged)
    def showAdult(self):
        return bool(util.settings().get("show_adult", False))

    @Slot(bool)
    def setShowAdult(self, show):
        util.set_setting("show_adult", bool(show))
        self.adultChanged.emit()
