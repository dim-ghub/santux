import sys


def main():
    args = sys.argv[1:]
    if args and args[0] == "launch":
        from .launcher import launch
        return launch(args[1:])
    if args and args[0] == "picker":
        from .qt import run_picker
        appid = args[args.index("--appid") + 1] if "--appid" in args else None
        return run_picker(appid)
    if args and not args[0].startswith("--gapplication"):
        from .cli import main as cli
        return cli(args)
    from .qt import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
