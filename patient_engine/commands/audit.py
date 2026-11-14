"""``python -m patient_engine audit``: audit a library against its catalogue (G4).

::

    python -m patient_engine audit LIBRARY --catalogue catalogue/lung-primary-care [--tolerances FILE] [--out DIR] [--json]

Writes ``audit.json`` and ``audit.md`` into the library directory (or ``--out``) and prints pass or fail per
check. Tolerances default to ``<catalogue>/audit_tolerances.yaml``. Exit code 0 when every check passes, 1 when
one fails, 2 on a usage or data error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..audit import AuditError, TOLERANCES_FILE, audit_library, load_tolerances, write_audit
from ..catalogue import CatalogueError, load_catalogue
from ..library import LibraryError, load_library


def register(subparsers) -> None:
    p = subparsers.add_parser("audit", help="audit a library of cards against the catalogue's reference numbers",
                              description=__doc__.split("\n\n")[0])
    p.add_argument("library")
    p.add_argument("--catalogue", required=True)
    p.add_argument("--tolerances", help=f"tolerances file (default: <catalogue>/{TOLERANCES_FILE})")
    p.add_argument("--out", help="directory for audit.json and audit.md (default: the library directory)")
    p.add_argument("--json", action="store_true", help="print the report as JSON instead of the summary")
    p.set_defaults(func=run)


def run(args) -> int:
    try:
        cat = load_catalogue(args.catalogue)
        tpath = Path(args.tolerances) if args.tolerances else Path(args.catalogue) / TOLERANCES_FILE
        tol = load_tolerances(tpath)
        lib = load_library(args.library, cat)
        report = audit_library(lib, cat, tol)
        out = args.out or lib.path
        write_audit(report, out)
    except (CatalogueError, LibraryError, AuditError, OSError) as e:
        print(f"audit: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"audit of library {report['library_id']} ({report['n_cards']} cards) against {report['catalogue_id']}")
        for c in report["checks"]:
            print(f"  {c['status'].upper():7} {c['id']:44} {c['summary']}")
        print(f"{'PASS' if report['passed'] else 'FAIL'}: {len(report['failed_checks'])} failed check(s) of "
              f"{len(report['checks'])}; {report['seconds']} s; written to {out}")
    return 0 if report["passed"] else 1
