#!/usr/bin/env bash
# Build dist/santux, a single executable with Python, Qt, the QML interface and the fonts inside.
# The build tools and a self-contained Qt (PySide6 wheel) are installed into .venv on first run.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"
if [ ! -x .venv/bin/pyinstaller ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q -r packaging/requirements-build.txt
.venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/santux.spec
echo "Built $here/dist/santux ($(du -h dist/santux | cut -f1))"
