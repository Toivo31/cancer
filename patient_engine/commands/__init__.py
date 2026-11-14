"""Command line commands of ``python -m patient_engine``.

Every module in this package that defines ``register(subparsers)`` adds commands; nothing else needs to be
edited to add one. A module registers a command like this::

    def register(subparsers):
        p = subparsers.add_parser("my-command", help="one line")
        p.add_argument("path")
        p.set_defaults(func=run)

    def run(args) -> int | None:          # return the exit code (None = 0)
        ...

Modules whose names start with an underscore are skipped. A module that fails to import or to register is
reported on stderr and the other commands keep working.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType
from typing import Iterator


def iter_command_modules() -> Iterator[tuple[str, ModuleType | Exception]]:
    """Yield ``(module name, module or the exception raised by importing it)`` in name order."""
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        try:
            yield info.name, importlib.import_module(f"{__name__}.{info.name}")
        except Exception as e:      # a broken command module must not take the others down
            yield info.name, e


def register_all(subparsers) -> list[str]:
    """Call ``register(subparsers)`` of every command module. Returns the problems found (also printed)."""
    problems: list[str] = []
    for name, mod in iter_command_modules():
        if isinstance(mod, Exception):
            problems.append(f"commands/{name}.py failed to import: {type(mod).__name__}: {mod}")
        elif hasattr(mod, "register"):
            try:
                mod.register(subparsers)
            except Exception as e:
                problems.append(f"commands/{name}.py failed to register: {type(e).__name__}: {e}")
    for p in problems:
        print(f"patient_engine: {p}", file=sys.stderr)
    return problems
