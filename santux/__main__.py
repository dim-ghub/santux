import os
import sys

COMMANDS = {"games", "search", "info", "reqs", "req", "install", "list", "profiles", "play", "uninstall"}


def _opened_files(args):
    """Paths (or file:// URIs) passed by the file manager or `santux FILE...`, else None."""
    if not args or args[0] in COMMANDS or args[0].startswith("-"):
        return None
    paths = [a[7:] if a.startswith("file://") else a for a in args]
    return paths if all(os.path.exists(p) for p in paths) else None


def main():
    args = sys.argv[1:]
    if args and args[0] == "launch":
        from .launcher import launch
        return launch(args[1:])
    if args and args[0] == "picker":
        from .qt import run_picker
        appid = args[args.index("--appid") + 1] if "--appid" in args else None
        return run_picker(appid)
    opened = _opened_files(args)
    if opened:
        from .qt import run
        return run(open_paths=[os.path.abspath(p) for p in opened])
    if args and not args[0].startswith("--gapplication"):
        from .cli import main as cli
        return cli(args)
    from .qt import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
