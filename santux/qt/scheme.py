"""Material 3 colour roles for the UI.

Sources, newest first:
- KiiteShell:    $XDG_STATE_HOME/kiite/user/generated/colors.json   (snake_case roles, "#RRGGBB")
- caelestia-cli: $XDG_STATE_HOME/caelestia/scheme.json, "colours"   (camelCase roles, "rrggbb")
Without either, a scheme generated from the GTA V palette (schemecolor.com/grand-theft-auto-gta-v):
Grassfield #47761E as primary, Caramel Yellow #FED985 as secondary, Beside Blue #61B5CB as tertiary,
built with Material Color Utilities' content scheme. Files are watched and reloaded when they change.
"""
import json
import os
import re
from pathlib import Path

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPalette

GTA_DARK = {
    "primary": "#A0D672", "on_primary": "#1A3700", "primary_container": "#47761E", "on_primary_container": "#C4FC93",
    "secondary": "#DEC48C", "on_secondary": "#3E2E04", "secondary_container": "#59471B", "on_secondary_container": "#CFB67F",
    "tertiary": "#94D0E1", "on_tertiary": "#003640", "tertiary_container": "#357281", "on_tertiary_container": "#C8F2FF",
    "error": "#FFB4AB", "on_error": "#690005", "error_container": "#93000A", "on_error_container": "#FFDAD6",
    "background": "#11140E", "on_background": "#E1E4D8", "surface": "#11140E", "on_surface": "#E1E4D8",
    "surface_variant": "#42493B", "on_surface_variant": "#C2C9B7", "outline": "#8C9382", "outline_variant": "#42493B",
    "shadow": "#000000", "scrim": "#000000", "inverse_surface": "#E1E4D8", "inverse_on_surface": "#2E312A",
    "inverse_primary": "#3C6A12", "surface_dim": "#11140E", "surface_bright": "#373A32",
    "surface_container_lowest": "#0C0F09", "surface_container_low": "#191D16", "surface_container": "#1D211A",
    "surface_container_high": "#282B24", "surface_container_highest": "#33362E",
}
GTA_LIGHT = {
    "primary": "#305D02", "on_primary": "#FFFFFF", "primary_container": "#47761E", "on_primary_container": "#C4FC93",
    "secondary": "#6F5C2E", "on_secondary": "#FFFFFF", "secondary_container": "#FBE0A6", "on_secondary_container": "#766233",
    "tertiary": "#165968", "on_tertiary": "#FFFFFF", "tertiary_container": "#357281", "on_tertiary_container": "#C8F2FF",
    "error": "#BA1A1A", "on_error": "#FFFFFF", "error_container": "#FFDAD6", "on_error_container": "#93000A",
    "background": "#F8FAEF", "on_background": "#191D16", "surface": "#F8FAEF", "on_surface": "#191D16",
    "surface_variant": "#DEE5D2", "on_surface_variant": "#42493B", "outline": "#73796A", "outline_variant": "#C2C9B7",
    "shadow": "#000000", "scrim": "#000000", "inverse_surface": "#2E312A", "inverse_on_surface": "#F0F2E6",
    "inverse_primary": "#A0D672", "surface_dim": "#D9DBD0", "surface_bright": "#F8FAEF",
    "surface_container_lowest": "#FFFFFF", "surface_container_low": "#F3F5E9", "surface_container": "#EDEFE3",
    "surface_container_high": "#E7E9DE", "surface_container_highest": "#E1E4D8",
}
ROLES = list(GTA_DARK)


def _state_home():
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")


def sources():
    s = _state_home()
    return {"KiiteShell": s / "kiite/user/generated/colors.json", "caelestia": s / "caelestia/scheme.json"}


def _snake(k):
    return re.sub(r"(?<!^)([A-Z])", r"_\1", k).lower()


def _hex(v):
    v = str(v).strip()
    if not v.startswith("#"):
        v = "#" + v
    return v.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", v) else None


def _read(name, path):
    data = json.loads(path.read_text())
    if name == "caelestia":
        data = data.get("colours", {})
    out = {}
    for k, v in data.items():
        k = _snake(k)
        h = _hex(v)
        if k in GTA_DARK and h:
            out[k] = h
    return out if {"primary", "surface", "on_surface"} <= out.keys() else None


def _dark_palette():
    app = QGuiApplication.instance()
    if not app:
        return True
    return app.palette().color(QPalette.Window).lightness() < 128


def load():
    """(source name, roles). The newest readable shell scheme wins; else the GTA V scheme.
    SANTUX_SCHEME=gta|kiite|caelestia forces one."""
    force = os.environ.get("SANTUX_SCHEME", "").lower()
    if force == "gta":
        return "GTA V", dict(GTA_DARK if _dark_palette() else GTA_LIGHT)
    found = []
    for name, path in sources().items():
        if force and not name.lower().startswith(force[:4]):
            continue
        try:
            if path.is_file():
                roles = _read(name, path)
                if roles:
                    found.append((path.stat().st_mtime, name, roles))
        except (OSError, ValueError):
            continue
    if found:
        _, name, roles = max(found, key=lambda t: t[0])
        base = GTA_DARK if _lum(roles["surface"]) < 0.5 else GTA_LIGHT
        return name, {**base, **roles}
    return "GTA V", dict(GTA_DARK if _dark_palette() else GTA_LIGHT)


def _lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _camel(k):
    return re.sub(r"_(\w)", lambda m: m.group(1).upper(), k)


class Scheme(QObject):
    """Exposed to QML as `scheme`: `colors` (camelCase M3 roles) and `source`."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._watch = QFileSystemWatcher(self)
        self._debounce = QTimer(self, singleShot=True, interval=150)
        self._debounce.timeout.connect(self.reload)
        self._watch.fileChanged.connect(lambda _: self._debounce.start())
        self._watch.directoryChanged.connect(lambda _: self._debounce.start())
        self._name, self._roles = "GTA V", {}
        self.reload()

    def _rewatch(self):
        for p in sources().values():
            for target in (p, p.parent):
                if target.exists() and str(target) not in self._watch.files() + self._watch.directories():
                    self._watch.addPath(str(target))

    def reload(self):
        name, roles = load()
        if (name, roles) != (self._name, self._roles):
            self._name, self._roles = name, roles
            self.changed.emit()
        self._rewatch()

    @Property("QVariantMap", notify=changed)
    def colors(self):
        return {_camel(k): v for k, v in self._roles.items()}

    @Property(str, notify=changed)
    def source(self):
        return self._name
