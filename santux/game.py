"""Find GTA V installs in Steam libraries, and their Proton prefixes."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

EDITIONS = {
    271590: ("Legacy", "GTA5.exe"),
    3240220: ("Enhanced", "GTA5_Enhanced.exe"),
}

STEAM_ROOTS = [
    "~/.local/share/Steam",
    "~/.steam/steam",
    "~/.var/app/com.valvesoftware.Steam/.local/share/Steam",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
    "~/snap/steam/common/.local/share/Steam",
]


@dataclass
class Game:
    appid: int
    edition: str          # "Legacy" or "Enhanced"
    exe: str
    library: Path
    folder: Path          # where GTA5.exe is
    steam_root: Path
    flatpak_steam: bool

    @property
    def legacy(self):
        return self.edition == "Legacy"

    @property
    def compatdata(self) -> Path:
        return self.library / "steamapps/compatdata" / str(self.appid)

    @property
    def prefix(self) -> Path:
        return self.compatdata / "pfx"

    @property
    def has_prefix(self):
        return (self.prefix / "drive_c").is_dir()

    @property
    def proton_version(self):
        try:
            return (self.compatdata / "version").read_text().strip()
        except OSError:
            return None

    @property
    def version(self):
        return exe_version(self.folder / self.exe)

    @property
    def mods_folder(self) -> Path:
        return self.folder / "mods"

    @property
    def asi_loader(self):
        """The DLL name Script Hook V's ASI loader uses for this edition."""
        return "dinput8.dll" if self.legacy else "xinput1_4.dll"

    @property
    def dll_override(self):
        return self.asi_loader.removesuffix(".dll") + "=n,b"

    def winpath(self, p) -> str:
        return "Z:" + str(Path(p).resolve()).replace("/", "\\")


def exe_version(path: Path):
    """FileVersion from a PE's version resource, e.g. '1.0.3889.0'."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    m = re.search("FileVersion\0".encode("utf-16-le") + rb"(?:\x00\x00)*((?:[0-9.]\x00)+)", data)
    return m.group(1).decode("utf-16-le") if m else None


def build_number(version):
    """'1.0.3889.0' -> 3889"""
    try:
        return int(version.split(".")[2])
    except (AttributeError, IndexError, ValueError):
        return None


def _vdf_values(text, key):
    return re.findall(r'"%s"\s+"([^"]*)"' % re.escape(key), text)


def steam_roots():
    seen = set()
    for r in STEAM_ROOTS:
        p = Path(os.path.expanduser(r))
        if (p / "steamapps/libraryfolders.vdf").is_file():
            real = p.resolve()
            if real not in seen:
                seen.add(real)
                yield p


def steam_libraries():
    for root in steam_roots():
        text = (root / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        for lib in [Path(x.replace("\\\\", "\\")) for x in _vdf_values(text, "path")] or [root]:
            yield lib


def find_games():
    games = []
    for root in steam_roots():
        text = (root / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        libs = [Path(x.replace("\\\\", "\\")) for x in _vdf_values(text, "path")] or [root]
        for lib in libs:
            for appid, (edition, exe) in EDITIONS.items():
                acf = lib / "steamapps" / f"appmanifest_{appid}.acf"
                if not acf.is_file():
                    continue
                installdir = (_vdf_values(acf.read_text(errors="replace"), "installdir") or [None])[0]
                if not installdir:
                    continue
                folder = lib / "steamapps/common" / installdir
                if (folder / exe).is_file():
                    games.append(Game(appid, edition, exe, lib, folder, root, ".var/app" in str(root)))
    return games


def running_game_processes():
    """Names of GTA V processes currently running (from /proc)."""
    names = ("GTA5.exe", "GTA5_Enhanced.exe", "PlayGTAV.exe", "GTAVLauncher.exe")
    found = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")
        except OSError:
            continue
        base = cmd.replace("\\", "/").rsplit("/", 1)[-1]
        if base in names:
            found.add(base)
    return sorted(found)
