#!/usr/bin/env bash
# Add santux to ~/.local/bin and the app menu. ./install.sh --uninstall removes both.
# Installs the single binary from ./build.sh (dist/santux) when there is one; otherwise links
# bin/santux, which runs this checkout with the system's Python and PySide6.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
share="${XDG_DATA_HOME:-$HOME/.local/share}"
bin="$HOME/.local/bin/santux"
desktop="$share/applications/io.github.santux.desktop"
icon="$share/icons/hicolor/scalable/apps/io.github.santux.svg"
mime="$share/mime/packages/io.github.santux.xml"
# .oiv has no standard MIME type; it's a zip with OpenIV's package layout.
OIV_TYPE=application/x-openiv-package
ARCHIVE_TYPES="application/zip;application/x-7z-compressed;application/vnd.rar;application/x-rar;"

refresh() {
    update-mime-database "$share/mime" 2>/dev/null || true
    update-desktop-database "$share/applications" 2>/dev/null || true
    gtk-update-icon-cache -q "$share/icons/hicolor" 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$bin" "$desktop" "$icon" "$mime"
    refresh
    echo "Removed $bin and $desktop. Your mods and data in $share/santux are kept."
    exit 0
fi

missing=()
if [ ! -x "$here/dist/santux" ]; then
    python3 -c 'import PySide6.QtQuick' 2>/dev/null || missing+=("PySide6 (Qt 6 for Python)")
    python3 -c 'import lxml, cryptography, numpy' 2>/dev/null || missing+=("python lxml, cryptography and numpy")
fi
command -v 7z >/dev/null || command -v bsdtar >/dev/null || missing+=("7-Zip (7z) or bsdtar, for .7z/.rar archives")
command -v protontricks >/dev/null || flatpak info com.github.Matoking.protontricks >/dev/null 2>&1 || missing+=("protontricks")
if [ ${#missing[@]} -gt 0 ]; then
    echo "Missing dependencies:"; printf '  - %s\n' "${missing[@]}"
    echo "Install them with your package manager (see README.md), then re-run."
fi

mkdir -p "$(dirname "$bin")" "$(dirname "$desktop")" "$(dirname "$icon")" "$(dirname "$mime")"
rm -f "$bin"
if [ -x "$here/dist/santux" ]; then
    install -m 755 "$here/dist/santux" "$bin"
    what="the single binary"
else
    chmod +x "$here/bin/santux"
    ln -s "$here/bin/santux" "$bin"
    what="a link to this checkout"
fi
cp "$here/santux/data/santux.svg" "$icon"
# Listing archive types can make Santux their default; remember the current ones to put back.
declare -A before
for t in ${ARCHIVE_TYPES//;/ }; do before[$t]=$(xdg-mime query default "$t" 2>/dev/null || true); done
cat > "$mime" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="$OIV_TYPE">
    <comment>OpenIV package</comment>
    <sub-class-of type="application/zip"/>
    <glob pattern="*.oiv"/>
    <icon name="io.github.santux"/>
  </mime-type>
</mime-info>
EOF
# Santux opens .oiv files, and shows up under "Open With" for mod archives.
cat > "$desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Santux
GenericName=GTA V Mod Loader
Comment=Find, install and manage GTA V mods on Linux
Exec=$bin %F
Icon=io.github.santux
Terminal=false
Categories=Game;Utility;
MimeType=$OIV_TYPE;$ARCHIVE_TYPES
StartupWMClass=io.github.santux
EOF
refresh
xdg-mime default io.github.santux.desktop "$OIV_TYPE" 2>/dev/null || true
for t in "${!before[@]}"; do
    old=${before[$t]}
    if [ -n "$old" ] && [ "$old" != io.github.santux.desktop ] \
            && [ "$(xdg-mime query default "$t" 2>/dev/null)" = io.github.santux.desktop ]; then
        xdg-mime default "$old" "$t" 2>/dev/null || true
    fi
done
echo "Installed $what as $bin. Run 'santux' or find Santux in your app menu; .oiv files open in Santux."
