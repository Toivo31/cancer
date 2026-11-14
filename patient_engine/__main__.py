"""``python -m patient_engine <command>``.

Commands are discovered in ``patient_engine/commands/`` (see ``commands/__init__.py``); this file does not
change when a package adds one. Exit codes: 0 ok, 1 the command failed (message on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import sys

from .commands import register_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m patient_engine",
                                     description="Synthetic patients: libraries, cohorts, cards (synthetic data only).")
    sub = parser.add_subparsers(dest="command", metavar="command")
    register_all(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    try:
        rc = func(args)
    except (OSError, ValueError, KeyError, LookupError) as e:
        print(f"patient_engine {args.command}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return int(rc or 0)


if __name__ == "__main__":
    sys.exit(main())
