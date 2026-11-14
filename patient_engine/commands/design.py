"""``python -m patient_engine design``: lay out a library design and write its skeletons.

    python -m patient_engine design --catalogue catalogue/_examples/tiny --seed 7
    python -m patient_engine design --catalogue PATH --seed 7 --n 1000 --coexisting-rate 0.2 --out skeletons.jsonl
    python -m patient_engine design --catalogue PATH --seed 7 --counts lung_cancer=400,pneumonia=200
    python -m patient_engine design --catalogue PATH --seed 7 --n 5000 --proportional

Prints the design table (cards by primary condition and by pair) and writes one skeleton per line
(JSON lines, ``skeleton/1``) to ``--out`` (default ``skeletons_<catalogue id>_s<seed>.jsonl`` in the
current folder; ``--out -`` writes nothing).

Without ``--n`` the counts are the default stratified design (150 per condition, 300 per cancer). With
``--n N`` the default counts are scaled to N cards in total. ``--counts`` sets the counts itself.
``--proportional`` draws the primary condition of N cards by the catalogue's prevalence instead.

``register(subparsers)`` is the hook ``patient_engine/__main__.py`` calls; the handler is stored as
``args.func`` and returns the exit code. ``run_design`` is the function behind it (no argparse).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..catalogue import CatalogueError, Catalogue, load_catalogue
from ..skeleton import (Design, Skeleton, default_counts, design_table, make_design, make_skeleton,
                        proportional_design)


def scale_counts(counts: Mapping[str, int], n: int) -> dict[str, int]:
    """``counts`` scaled to sum to exactly ``n`` (largest remainder; every condition keeps at least 1 card
    when ``n`` allows)."""
    total = sum(counts.values())
    raw = {c: n * x / total for c, x in counts.items()}
    out = {c: int(v) for c, v in raw.items()}
    for c in sorted(raw, key=lambda c: raw[c] - out[c], reverse=True)[: n - sum(out.values())]:
        out[c] += 1
    return out


def parse_counts(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in text.split(","):
        if part.strip():
            k, _, v = part.partition("=")
            out[k.strip()] = int(v)
    return out


def run_design(catalogue: Catalogue, seed: int, n: int | None = None, counts: Mapping[str, int] | None = None,
               coexisting_rate: float | None = None, proportional: bool = False) -> tuple[Design, list[Skeleton]]:
    """The design and its skeletons (the function the command wraps)."""
    if proportional:
        if n is None:
            raise ValueError("--proportional needs --n")
        design = proportional_design(n, coexisting_rate)
    else:
        base = dict(counts) if counts else default_counts(catalogue)
        if n is not None and not counts:
            base = scale_counts(base, n)
        design = make_design(catalogue, base, coexisting_rate)
    return design, [make_skeleton(catalogue, i, design, seed) for i in range(design.n)]


def format_table(catalogue: Catalogue, design: Design, skeletons: Sequence[Skeleton]) -> str:
    t = design_table(skeletons)
    lines = [f"design: {design.mode}, {t['n']} cards, catalogue {catalogue.id} (hash {catalogue.version_hash[:12]})",
             "", f"{'primary condition':<28}{'cards':>7}{'share':>8}"]
    for c, k in t["by_primary"].items():
        lines.append(f"{c:<28}{k:>7}{k / t['n']:>8.1%}")
    lines += ["", f"{'co-existing pair':<40}{'cards':>7}"]
    for p, k in t["pairs"].items():
        lines.append(f"{p:<40}{k:>7}")
    if not t["pairs"]:
        lines.append("(none)")
    lines.append(f"{'total with a co-existing illness':<40}{t['with_coexisting']:>7}")
    return "\n".join(lines)


def write_skeletons(skeletons: Sequence[Skeleton], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for s in skeletons:
            f.write(json.dumps(s.to_json(), sort_keys=False) + "\n")


def _handler(args: Any) -> int:
    try:
        catalogue = load_catalogue(args.catalogue)
        design, skeletons = run_design(
            catalogue, args.seed, args.n, parse_counts(args.counts) if args.counts else None,
            args.coexisting_rate, args.proportional)
    except (CatalogueError, ValueError, KeyError) as e:
        print(f"design: {e}", file=sys.stderr)
        return 2
    print(format_table(catalogue, design, skeletons))
    if args.out != "-":
        out = args.out or f"skeletons_{catalogue.id}_s{args.seed}.jsonl"
        write_skeletons(skeletons, out)
        print(f"\nwrote {len(skeletons)} skeletons to {out}")
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("design", help="lay out a library design and write its skeletons (JSON lines)",
                              description=__doc__.split("\n\n")[0])
    p.add_argument("--catalogue", required=True, help="catalogue folder")
    p.add_argument("--seed", type=int, default=0, help="seed for every keyed random number (default 0)")
    p.add_argument("--n", type=int, help="total cards (scales the default counts; with --proportional the card count)")
    p.add_argument("--counts", help="cards per primary condition, e.g. lung_cancer=400,pneumonia=200")
    p.add_argument("--coexisting-rate", type=float, help="share of cards (of primaries with co-occurrence entries) "
                   "that get a co-existing illness; default: the catalogue's shares")
    p.add_argument("--proportional", action="store_true", help="draw primary conditions by the catalogue's prevalence")
    p.add_argument("--out", help="skeleton file (default skeletons_<catalogue>_s<seed>.jsonl; '-' = do not write)")
    p.set_defaults(func=_handler)
