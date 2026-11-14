"""Commands on libraries and cohorts: ``library-info``, ``cohort``, ``show``.

::

    python -m patient_engine library-info PATH [--json]
    python -m patient_engine cohort PATH --n 1000 --seed 1 [--prevalence a=0.2,b=0.8 | --spec spec.json]
                                    [--rate-per-day R | --spread-days D] [--catalogue DIR] [--json]
    python -m patient_engine show PATH CARD [--reveal TEST[:ATTEMPT] ...] [--state S] [--hidden] [--json]

``PATH`` is a library directory (``manifest.json`` + ``cards.jsonl.gz``); ``CARD`` is a card id or ``#N`` (position).
``show`` goes through ``RevealHandle``: without ``--hidden`` it prints exactly what the revealed side may see.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

from ..card import INITIAL_STATE, CohortSpec, card_to_json
from ..cohort import CohortError, draw_cohort
from ..library import library_sources, load_library
from ..reveal import RevealHandle


def register(subparsers) -> None:
    p = subparsers.add_parser("library-info", help="verify a library and print its manifest and card counts")
    p.add_argument("path")
    p.add_argument("--json", action="store_true", help="print the manifest as JSON")
    p.set_defaults(func=_library_info)

    p = subparsers.add_parser("cohort", help="draw a cohort from a library and print its marginals")
    p.add_argument("path")
    p.add_argument("--spec", help="a cohort/1 spec JSON file (replaces --n, --seed and --prevalence)")
    p.add_argument("--n", type=int, default=1000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--prevalence", help="condition=share,... (default: the library's own mix)")
    p.add_argument("--rate-per-day", type=float, help="Poisson arrivals per day (default: spread over 365 days)")
    p.add_argument("--spread-days", type=float, help="arrival days drawn uniformly over this many days")
    p.add_argument("--catalogue", help="catalogue directory: adds test positive shares and array size")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cohort)

    p = subparsers.add_parser("show", help="print one card: the public view, or everything with --hidden")
    p.add_argument("path")
    p.add_argument("card", help="card id, or #N for the N-th card (0-based)")
    p.add_argument("--state", default=INITIAL_STATE)
    p.add_argument("--reveal", action="append", default=[], metavar="TEST[:ATTEMPT]",
                   help="also reveal this test attempt (attempt defaults to 0); repeatable")
    p.add_argument("--hidden", action="store_true", help="print the whole card including hidden truth")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_show)


def _catalogue(path: str | None):
    if not path:
        return None
    from ..catalogue import load_catalogue
    return load_catalogue(path)


def _out(text: str = "") -> None:
    print(text)


def _library_info(args) -> int:
    lib = load_library(args.path)
    m = lib.manifest
    sources = library_sources(args.path)
    if args.json:
        _out(json.dumps(m.to_json() | ({"sources": sources} if sources else {}), indent=2, sort_keys=True))
        return 0
    _out(f"library {m.id}  (verified: file hash and content hash match)")
    _out(f"  catalogue   {m.catalogue_id}  {m.catalogue_hash[:12]}")
    _out(f"  generator   {m.generator}  model={m.model}  error_source={m.error_source}")
    _out(f"  prompts     {m.prompts or '-'}")
    _out(f"  created     {m.created}")
    _out(f"  cards       {m.n_cards}")
    for cond, k in m.card_count_by_condition.items():
        _out(f"    {cond:<28}{k:>7}")
    if sources:
        _out(f"  merged from {len(sources)} libraries:")
        for s in sources:
            _out(f"    {s['id']}  {s['n_cards']:>5} cards  {s['generator']}  model={s['model']}  "
                 f"error_source={s['error_source']}  prompts={s['prompts'] or '-'}  created {s['created']}")
    return 0


def _parse_prevalence(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in text.split(","):
        key, sep, val = part.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"prevalence must look like a=0.2,b=0.8, got {text!r}")
        out[key.strip()] = float(val)
    return out


def _cohort(args) -> int:
    cat = _catalogue(args.catalogue)
    lib = load_library(args.path, cat)
    if args.spec:
        spec = CohortSpec.from_json(json.loads(Path(args.spec).read_text()))
    else:
        prev = _parse_prevalence(args.prevalence) if args.prevalence else \
            {c: float(k) for c, k in lib.manifest.card_count_by_condition.items()}
        spec = CohortSpec(library_id=lib.id, prevalence=prev, n=args.n, seed=args.seed)
    if args.rate_per_day is not None and args.spread_days is not None:
        raise ValueError("give --rate-per-day or --spread-days, not both")
    arrivals = ({"rate_per_day": args.rate_per_day} if args.rate_per_day is not None
                else {"spread_days": args.spread_days} if args.spread_days is not None else None)
    try:
        cohort = draw_cohort(lib, spec, arrivals)
    except CohortError as e:
        print(f"patient_engine cohort: {e}", file=sys.stderr)
        return 1
    total = sum(spec.prevalence.values())
    counts = cohort.condition_counts()
    rows = []
    for cond in sorted(set(spec.prevalence) | set(counts)):
        target = spec.prevalence.get(cond, 0.0) / total
        got = counts.get(cond, 0) / cohort.n if cohort.n else 0.0
        rows.append({"condition": cond, "target": target, "observed": got, "n": counts.get(cond, 0),
                     "cards_in_library": len(lib.by_condition.get(cond, ()))})
    arr = cohort.arrival
    summary = {"library": lib.id, "n": cohort.n, "seed": spec.seed, "arrivals": dict(cohort.arrivals),
               "distinct_cards": cohort.distinct_cards, "fingerprint": cohort.fingerprint(),
               "arrival_days": {"min": min(arr, default=0.0), "mean": sum(arr) / len(arr) if arr else 0.0,
                                "max": max(arr, default=0.0)},
               "conditions": rows}
    if cat is not None:
        a = cohort.to_arrays(cat)
        shares = {}
        for ti, t in enumerate(a.tests):
            vals = [a.code(p, ti, 0) for p in range(a.n)]
            ok = [v for v in vals if v in (0, 1)]
            shares[t] = {"positive_first_attempt": (sum(ok) / len(ok)) if ok else None,
                         "non_diagnostic_first_attempt": (sum(v == 2 for v in vals) / len(vals)) if vals else None}
        summary["tests"] = shares
        summary["array_bytes"] = a.nbytes
    if args.json:
        _out(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    _out(f"cohort from library {lib.id}: n={cohort.n} seed={spec.seed} arrivals={dict(cohort.arrivals)}")
    _out(f"  distinct cards {cohort.distinct_cards}   fingerprint {summary['fingerprint']}")
    _out(f"  arrival day    min {summary['arrival_days']['min']:.2f}  mean {summary['arrival_days']['mean']:.2f}  "
         f"max {summary['arrival_days']['max']:.2f}")
    _out(f"  {'condition':<28}{'target':>9}{'observed':>10}{'n':>8}{'cards':>7}")
    for r in rows:
        _out(f"  {r['condition']:<28}{r['target']:>9.4f}{r['observed']:>10.4f}{r['n']:>8}{r['cards_in_library']:>7}")
    if cat is not None:
        _out(f"  compact arrays {summary['array_bytes']:,} bytes; first attempt, positive share of readable results:")
        for t, s in summary["tests"].items():
            pos = "-" if s["positive_first_attempt"] is None else f"{s['positive_first_attempt']:.3f}"
            _out(f"    {t:<26} positive {pos:>6}   non-diagnostic {s['non_diagnostic_first_attempt']:.3f}")
    return 0


def _find_card(lib, ref: str):
    if ref.startswith("#"):
        return lib.cards[int(ref[1:])]
    return lib.card(ref)


def _to_plain(obj):
    return dataclasses.asdict(obj) if dataclasses.is_dataclass(obj) else obj


def _show(args) -> int:
    lib = load_library(args.path)
    card = _find_card(lib, args.card)
    if args.hidden:
        _out(json.dumps(card_to_json(card), indent=2, ensure_ascii=False))
        return 0
    revealed = []
    for item in args.reveal:
        test, _, att = item.partition(":")
        revealed.append((test, int(att) if att else 0))
    view = RevealHandle(card, public_id=card.id).visible(args.state, revealed)
    if args.json:
        _out(json.dumps(_to_plain(view), indent=2, ensure_ascii=False))
        return 0
    _out(f"patient {view.card_id}  state={view.state}")
    _out("  background  " + ", ".join(f"{k}={v}" for k, v in view.background.items()))
    _out(f"  reported    {', '.join(view.presenting.reported) or '-'}")
    _out(f"  in words    {view.presenting.text or '-'}")
    for o in view.observations:
        vals = ", ".join(f"{k}={v}" for k, v in o.values.items()) or "-"
        _out(f"  {o.test}[{o.attempt}] {o.status}: {vals}")
        _out(f"      {o.report}")
    for n in view.notes:
        _out(f"  note {n.id} ({n.kind}): {n.text}")
    return 0
