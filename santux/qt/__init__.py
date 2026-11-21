"""Qt Quick interface. Colours come from the system Qt palette; every control is our own QML."""
import json
import os
import sys
from pathlib import Path

QML_DIR = Path(__file__).parent / "qml"
DATA_DIR = Path(__file__).parent.parent / "data"
APP_NAME = "Santux"
ICON = DATA_DIR / "santux.svg"


def _brand(app):
    """Window icon and the bundled fonts: Material Symbols Rounded (icons) and Anton (the banner)."""
    from PySide6.QtGui import QFontDatabase, QIcon
    app.setWindowIcon(QIcon(str(ICON)))
    for f in ("MaterialSymbolsRounded.ttf", "Anton-Regular.ttf"):
        QFontDatabase.addApplicationFont(str(DATA_DIR / "fonts" / f))


def _socket_name():
    return f"santux-{os.getuid()}"


def _forward(paths):
    """Hand paths to a Santux window that's already open (it raises itself). True if one took them."""
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(_socket_name())
    if not s.waitForConnected(500):
        return False
    s.write(json.dumps(paths).encode())
    s.waitForBytesWritten(2000)
    s.disconnectFromServer()
    return True


def _listen(app, engine, backend):
    """Accept paths from later `santux FILE...` runs, so opening a .oiv reuses this window."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(app)
    QLocalServer.removeServer(_socket_name())        # a stale socket left by a crash
    if not server.listen(_socket_name()):
        return None

    def accept():
        sock = server.nextPendingConnection()
        buf = bytearray()
        sock.readyRead.connect(lambda: buf.extend(bytes(sock.readAll())))

        def done():
            buf.extend(bytes(sock.readAll()))
            try:
                paths = json.loads(buf.decode() or "[]")
            except ValueError:
                paths = []
            win = engine.rootObjects()[0]
            win.show(); win.raise_(); win.requestActivate()
            if paths:
                backend.openPaths(paths)
            sock.deleteLater()
        sock.disconnected.connect(done)
    server.newConnection.connect(accept)
    return server


def run(open_paths=None):
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")   # only used for scroll bars and popups
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from .backend import Backend
    from .providers import ThemeIcons, WebImages
    from .scheme import Scheme

    QCoreApplication.setOrganizationName("santux")
    QCoreApplication.setApplicationName(APP_NAME)
    QGuiApplication.setDesktopFileName("io.github.santux")
    app = QGuiApplication(sys.argv[:1])
    testing = bool(os.environ.get("SANTUX_SCREENSHOT"))
    if not testing and _forward(open_paths or []):
        return 0
    _brand(app)
    engine = QQmlApplicationEngine()
    backend = Backend()
    engine.addImageProvider("web", WebImages())
    engine.addImageProvider("icon", ThemeIcons())
    scheme = Scheme()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("scheme", scheme)
    engine.load(QML_DIR / "Main.qml")
    if not engine.rootObjects():
        return 1
    server = None if testing else _listen(app, engine, backend)
    app._keep = (engine, backend, scheme, server)
    _scrub_env()
    if open_paths:
        QTimer.singleShot(0, lambda: backend.openPaths(open_paths))
    _screenshot_and_quit(app, engine)
    return app.exec()


def _scrub_env():
    """Once Qt has started, drop the single binary's own variables from the environment, so
    programs Qt starts for us (xdg-open, the browser) don't load our bundled Qt plugins."""
    from .. import util
    if util.FROZEN:
        clean = util.child_env()
        os.environ.clear()
        os.environ.update(clean)


def _screenshot_and_quit(app, engine):
    """SANTUX_SCREENSHOT=file.png: save the window a few seconds after start (SANTUX_SCREENSHOT_DELAY ms,
    default 4000), then quit. For testing builds."""
    out = os.environ.get("SANTUX_SCREENSHOT")
    if not out:
        return
    from PySide6.QtCore import QTimer

    def grab():
        engine.rootObjects()[0].grabWindow().save(out)
        app.quit()
    QTimer.singleShot(int(os.environ.get("SANTUX_SCREENSHOT_DELAY", "4000")), grab)


def run_picker(appid=None):
    """Profile picker for `santux launch`. Prints the chosen profile slug on stdout."""
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    import subprocess
    from PySide6.QtCore import Property, QObject, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from .. import game as gamemod, gtavxr, profiles, util
    from .providers import ThemeIcons
    from .scheme import Scheme

    games = gamemod.find_games()
    game = next((g for g in games if str(g.appid) == str(appid)), games[0] if games else None)
    if game is None:
        return 1

    class Picker(QObject):
        changed = Signal()

        def __init__(self):
            super().__init__()
            self._list = profiles.summary(game)
            self.result = None

        @Property("QVariantList", notify=changed)
        def profiles(self):
            return self._list

        @Property(str, constant=True)
        def preselect(self):
            return profiles.active(game)

        @Property(bool, constant=True)
        def steamvr(self):
            return gtavxr.steamvr_running()

        @Slot(str, bool)
        def choose(self, slug, remember):
            if remember:
                profiles.set_launch_default(game, slug)
            self.result = slug
            QGuiApplication.quit()

        @Slot()
        def cancel(self):
            QGuiApplication.quit()

        @Slot()
        def openManager(self):
            subprocess.Popen(util.self_command(), start_new_session=True, env=util.child_env(itself=True))

    app = QGuiApplication(sys.argv[:1])
    QGuiApplication.setDesktopFileName("io.github.santux")
    _brand(app)
    engine = QQmlApplicationEngine()
    picker = Picker()
    engine.addImageProvider("icon", ThemeIcons())
    scheme = Scheme()
    engine.rootContext().setContextProperty("picker", picker)
    engine.rootContext().setContextProperty("scheme", scheme)
    engine.load(QML_DIR / "Picker.qml")
    if not engine.rootObjects():
        return 1
    _scrub_env()
    _screenshot_and_quit(app, engine)
    app.exec()
    if picker.result:
        print(picker.result, flush=True)
    return 0
