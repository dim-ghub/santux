# PyInstaller spec for the single-file Santux binary. Build with ./build.sh.
import os
from pathlib import Path

ROOT = Path(SPECPATH).parent

# QML modules the interface imports; the rest of Qt's QML tree (WebEngine, 3D, ...) is left out.
QML_KEEP = ("QtQuick", "QtQml", "QtCore", "builtins.qmltypes", "jsroot.qmltypes")
QML_DROP = ("QtQuick3D", "QtQuick/VirtualKeyboard", "QtQuick/Scene2D", "QtQuick/Scene3D", "QtQuick/Timeline",
            "QtQuick/Particles", "QtQuick/Pdf", "QtQuick/Controls/Fusion", "QtQuick/Controls/Imagine",
            "QtQuick/Controls/Material", "QtQuick/Controls/Universal", "QtQuick/Controls/FluentWinUI3",
            "QtQuick/Controls/macOS", "QtQuick/Controls/Windows", "QtQuick/Controls/iOS")

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "santux" / "qt" / "qml"), "santux/qt/qml"),
           (str(ROOT / "santux" / "data"), "santux/data")],
    hiddenimports=["PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtSvg", "santux.cli", "santux.launcher", "santux.qt"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore",
              "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
              "PySide6.QtPdf", "PySide6.QtQuick3D", "PySide6.QtWidgets"],
)


# Libraries nothing in the interface loads: other Controls styles, and the GTK platform theme,
# which would pull in the build machine's GTK (it isn't portable; Qt falls back to its own theme).
LIB_DROP = ("WebEngine", "Qt3D", "Quick3D", "QtPdf", "Multimedia", "QuickControls2Imagine",
            "QuickControls2FluentWinUI3", "QuickControls2Material", "QuickControls2Universal",
            "LabsStyleKit", "libqgtk3", "libgtk-", "libgdk-", "libglycin", "libatk", "libpango",
            "libcairo", "libharfbuzz-gobject")


def keep(entry):
    path = entry[0].replace(os.sep, "/")
    if path.startswith("santux/"):
        return True
    if path.startswith("PySide6/") and "/qml/" in path:
        tail = path.split("/qml/", 1)[1]
        return tail.startswith(QML_KEEP) and not tail.startswith(QML_DROP)
    return not any(s in path for s in LIB_DROP)


a.datas = [e for e in a.datas if keep(e)]
a.binaries = [e for e in a.binaries if keep(e)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="santux",
    strip=True,
    upx=False,
    console=True,
    runtime_tmpdir=None,
)
