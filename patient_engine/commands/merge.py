"""``merge``: combine libraries made for the same catalogue into one new library.

::

    python -m patient_engine merge LIB LIB [LIB ...] --out DIR [--catalogue DIR] [--json]

Refuses libraries for different catalogues and card ids that occur twice. The result is deterministic:
the same libraries give the same library id on any machine, in any order. ``library-info`` on the result
lists the libraries it came from. See ``patient_engine.library.merge_libraries``.
"""

from __future__ import annotations

import json

from ..library import load_library, merge_libraries


def register(subparsers) -> None:
    p = subparsers.add_parser("merge", help="combine libraries for one catalogue into a new library")
    p.add_argument("libraries", nargs="+", metavar="LIB", help="two or more library directories")
    p.add_argument("--out", required=True, help="directory for the new library (must not hold a different one)")
    p.add_argument("--catalogue", help="catalogue directory: also check every card against it")
    p.add_argument("--json", action="store_true", help="print the new manifest as JSON")
    p.set_defaults(func=_merge)


def _merge(args) -> int:
    cat = None
    if args.catalogue:
        from ..catalogue import load_catalogue
        cat = load_catalogue(args.catalogue)
    manifest = merge_libraries([load_library(p, cat) for p in args.libraries], args.out, cat)   # LibraryError -> exit 1
    if args.json:
        print(json.dumps(manifest.to_json(), indent=2, sort_keys=True))
    else:
        print(f"merged {len(args.libraries)} libraries into {args.out}: {manifest.id}, {manifest.n_cards} cards")
    return 0
