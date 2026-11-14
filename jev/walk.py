"""Walk one synthetic patient through the encounter loop, one decision at a time (demo and test tool).

    python -m decision_api.server                                   # terminal 1: the owner's proxy (no key: the hosted gateway, checkpoint 2350)
    python -m jev.walk                                               # terminal 2: a random patient (blind for you too); you review each proposal
    python -m jev.walk --pick random --pick-seed 7                   # the same random patient again
    python -m jev.walk --pick cancer                                 # you choose the kind: NOT blind for the person
    python -m jev.walk --pick pneumonia --auto-accept --max-calls 20 # unattended, accepts every proposal
    python -m jev.walk --pick cancer --auto-accept --jev mock        # no model, no key: a local mock of the API

At each decision it prints the record so far, the offered actions with the model's scores and its proposal
(and the decision tables' numbers with ``--placeholder``), then waits: Enter accepts the proposal, or type an
action id or its number. The chosen action is what the simulator does (the model proposes, a person decides).
The patient's hidden truth is shown only after the walk ends. The walk is saved as JSON.

Who is blind: the model always is (it sees the record only). The person at the keyboard is blind only with
``--pick random`` (the default) and ``--library`` with a patient the person did not choose by condition.
``--pick cancer|pneumonia|worried_well`` tells the person the condition before the walk: use it for rehearsal,
not for a "person decides" demo.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

from patient_engine.card import CohortSpec
from patient_engine.cohort import Cohort
from patient_engine.record_text import render

from .birch import (BirchBackend, BirchError, BirchPolicy, DEFAULT_CACHE_DIR, DEFAULT_MAX_CALLS, DEFAULT_URL,
                    GATEWAY_MIN_INTERVAL, parse_spec, pinned_backend)
from .birch_mock import MockProxy

RANDOM_PICK = "random"
PICKS = {"cancer": "lung_cancer", "pneumonia": "pneumonia", "worried_well": "worried_well"}
WORLD = "scenarios/finland_encounter.yaml"
LIBRARY_SEED, LIBRARY_CARDS = 1, 3
ROOT = Path(__file__).resolve().parents[1]


def library_for(world, condition: str, cache: Path):
    """A small library holding only ``condition`` cards (a few seconds; stored under ``cache``)."""
    from patient_engine.library import load_library, write_library
    from patient_engine.reference import reference_cards
    from patient_engine.skeleton import Design
    d = cache / f"{world.catalogue.version_hash[:10]}-{condition}-{LIBRARY_SEED}-{LIBRARY_CARDS}"
    if not d.exists():
        design = Design(mode="stratified", n=LIBRARY_CARDS, counts=((condition, LIBRARY_CARDS),))
        write_library(list(reference_cards(world.catalogue, design, LIBRARY_SEED)), world.catalogue, d,
                      meta={"created": "1970-01-01T00:00:00Z"})
    return load_library(d, world.catalogue)


def one_patient_cohort(lib, index: int, seed: int) -> Cohort:
    card = lib.cards[index]
    cond = card.primary_condition
    return Cohort(spec=CohortSpec(library_id=lib.id, prevalence={cond: 1.0}, n=1, seed=seed),
                  arrivals={"rate_per_day": 44}, library_id=lib.id, card_index=(index,), condition=(cond,),
                  arrival=(0.0,), library=lib)


def resolve_pick(pick: str | None, pick_seed: int | None, patient) -> tuple[str, int | None, int | None, int | None]:
    """``(kind, patient index or None, pick seed or None, pick seed used)``. ``random`` draws the kind and the card
    from ``random.Random(seed)`` (a fresh seed when none is given), so the same seed gives the same patient."""
    if pick != RANDOM_PICK:
        return pick, (int(patient) if patient is not None else None), None, None
    seed = pick_seed if pick_seed is not None else random.SystemRandom().randrange(1, 10 ** 6)
    rng = random.Random(seed)
    kind = rng.choice(sorted(PICKS))
    ix = int(patient) if patient is not None else rng.randrange(LIBRARY_CARDS)
    return kind, ix, seed, seed


class StepPolicy:
    """Wraps an engine policy: shows each decision and lets a person choose (or auto-accepts the proposal)."""

    def __init__(self, inner, world, table=None, auto_accept=False, input_fn=input, out=print):
        self.inner, self.world, self.table = inner, world, table
        self.auto, self.input, self.out = auto_accept, input_fn, out
        self.steps: list[dict] = []
        self.backend_name = getattr(inner, "backend_name", type(inner).__name__)
        self.model_id = getattr(inner, "model_id", None)
        self.decision_mode = "argmax"

    def run_summary(self) -> dict:
        fn = getattr(self.inner, "run_summary", None)
        return fn() if callable(fn) else {}

    def choose(self, view, options):
        return self.choose_with_note(view, options)[0]

    def _label(self, aid: str) -> str:
        a = self.world.care.actions.get(aid)
        return a.label if a is not None and a.label else aid.replace("_", " ")

    def choose_with_note(self, view, options):
        o = self.out
        o(f"\n{'=' * 78}\nDecision: {view.node}, day {view.t_now:g}\n{'-' * 78}\nRecord so far:")
        for line in render(view.record, self.world.catalogue, self.world.care):
            o("  " + line)
        try:
            probs, note, assess = _call(self.inner, view, options)          # a model error stops the walk, loudly
        except BirchError as e:
            o(f"\nSTOPPED: {e}")
            raise
        table = None
        if self.table is not None:
            table = self.table.choose_with_note(view, options)[0]
        proposed = max(options, key=lambda a: (probs[a], -options.index(a)))
        expl = getattr(self.inner, "last_explanation", None)
        o(f"\nOffered actions (scores are relative to this list, not probabilities of disease)"
          + ("; second column: placeholder decision table" if table else "") + ":")
        for i, a in enumerate(sorted(options, key=lambda a: -probs[a]), 1):
            mark = "  <- proposed" if a == proposed else ""
            tcol = f"  table {table[a]:5.1%}" if table else ""
            o(f"  {i:2d}. {probs[a]:6.1%}{tcol}  {a:<30} {self._label(a)}{mark}")
        if expl:
            o(f"  ({expl})")
        order = sorted(options, key=lambda a: -probs[a])
        chosen = proposed
        if not self.auto:
            while True:
                raw = self.input("Enter = accept the proposal, or type an action id or number: ").strip()
                if not raw:
                    break
                if raw.isdigit() and 1 <= int(raw) <= len(order):
                    chosen = order[int(raw) - 1]
                    break
                if raw in options:
                    chosen = raw
                    break
                o(f"  not one of the offered actions: {raw!r}")
        overridden = chosen != proposed
        o(f"-> {'person chose' if overridden else 'accepted'}: {chosen} ({self._label(chosen)})")
        self.steps.append({"decision_point": view.node, "t_days": view.t_now,
                           "record": render(view.record, self.world.catalogue, self.world.care),
                           "probs": {a: round(probs[a], 6) for a in options}, "table": table, "proposed": proposed,
                           "chosen": chosen, "overridden": overridden, "explanation": expl,
                           "cached": getattr(getattr(self.inner, "backend", None), "last_cached", None),
                           **_identity(getattr(self.inner, "backend", None))})
        who = "Reviewer overrode the proposal" if overridden else "Reviewer accepted the proposal"
        text = f"{who} ({proposed}); chosen: {chosen}. " + (note or "")
        return {a: float(a == chosen) for a in options}, text.strip(), assess or {"plan": "{action}"}


def _identity(be) -> dict:
    """The answering model's identity and latency as the response states them (step, weight hash), for the saved walk."""
    r = getattr(be, "last_response", None)
    if not isinstance(r, dict):
        return {}
    return {"backend": r.get("backend"), "latency_ms": r.get("latency_ms")}


def _call(policy, view, options):
    fn = getattr(policy, "choose_with_note", None)
    if fn is not None:
        return fn(view, options)
    return policy.choose(view, options), None, None


def walk(args, out=print, input_fn=input) -> dict:
    from pathway_sim.encounter import load_world, run_encounter
    world = load_world(ROOT / args.world if not Path(args.world).exists() else args.world)
    if args.library:
        from patient_engine.library import load_library
        lib = load_library(args.library, world.catalogue)
        ix = int(args.patient) if str(args.patient).isdigit() else next(i for i, c in enumerate(lib.cards) if c.id == args.patient)
    else:
        kind, ix, pick_seed, _ = resolve_pick(args.pick, getattr(args, "pick_seed", None), args.patient)
        ix = ix or 0
        lib = library_for(world, PICKS[kind], Path(args.work_dir) / "walk_library")
    if args.library:
        pick_seed = None
    cohort = one_patient_cohort(lib, ix, args.seed)
    table = world.policy if args.placeholder else None
    mock = None
    try:
        if args.jev == "table":
            inner = world.policy
        else:
            url = DEFAULT_URL
            allow_non_model = False
            cache = Path(args.cache_dir)
            if args.jev == "mock":
                mock = MockProxy().__enter__()
                url, allow_non_model, cache = mock.url, True, Path(args.work_dir) / "jev_cache_mock"
            elif parse_spec(args.jev):
                url = parse_spec(args.jev)
            kw = dict(max_calls=args.max_calls, cache_dir=cache, include_assessments=args.include_assessments,
                      concurrency=args.concurrency, forbidden_values=frozenset(world.catalogue.conditions))
            if mock is not None:                       # the mock is not the model: no identity pin, no pacing
                be = BirchBackend(url, allow_non_model=True, **kw)
            else:                                      # the owner's bridge: step 2350 and its weight hash, or refused
                be = pinned_backend(url=url, min_interval=getattr(args, "min_interval", GATEWAY_MIN_INTERVAL), **kw)
            inner = BirchPolicy(be, mode="argmax", catalogue=world.catalogue, care=world.care)
        step = StepPolicy(inner, world, table, args.auto_accept, input_fn, out)
        if pick_seed is not None:
            out(f"Random patient, pick seed {pick_seed} (repeat with --pick random --pick-seed {pick_seed}); the kind is not shown until the end.")
        elif args.pick in PICKS:
            out(f"Note: --pick {args.pick} tells you the condition up front, so you are not blind; the model is. "
                "Use --pick random for a blind walk.")
        out(f"Walking patient {ix} of {lib.id[:12]} (hidden truth withheld until the end); decider: {args.jev}"
            + ("; auto-accept" if args.auto_accept else ""))
        try:
            log = run_encounter(world, 1, args.seed, policy=step, cohort=cohort)
        except BirchError as e:                    # keep what was decided before the stop (a live smoke's evidence)
            p = Path(args.work_dir) / "walks" / f"walk_stopped_{args.pick or 'card'}{'' if pick_seed is None else pick_seed}_{ix}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"format": "jev_walk/1", "decider": args.jev, "outcome": None, "stopped": str(e),
                                     "steps": step.steps, "model_calls": step.run_summary()}, indent=1))
            out(f"Saved the walk up to the stop: {p}")
            raise
    finally:
        if mock is not None:
            mock.__exit__()
    pr = log.patients[0]
    record_lines = render(pr.record, world.catalogue, world.care)
    summary = step.run_summary()
    out(f"\n{'=' * 78}\nOutcome: {pr.outcome}")
    out(f"  referral at day {None if pr.t_referral is None else round(pr.t_referral - pr.patient.arrival, 1)}, "
        f"tests {pr.tests_ordered}, treatments {[t['id'] for t in pr.treatments]}")
    out(f"  hidden truth (not shown to the decider): {pr.primary_condition}")
    out("Full record:")
    for line in record_lines:
        out("  " + line)
    if summary:
        out("Model calls: " + json.dumps(summary))
    result = {"format": "jev_walk/1", "decider": args.jev, "outcome": pr.outcome, "steps": step.steps,
              "record": pr.record.to_json(), "record_text": record_lines, "model_calls": summary,
              "hidden_block_scoring_only": {"primary_condition": pr.primary_condition, "library": lib.id, "patient": ix,
                                            "pick": args.pick, "pick_seed": pick_seed}}
    p = Path(args.out) if args.out else Path(args.work_dir) / "walks" / f"walk_{args.pick or 'card'}{'' if pick_seed is None else pick_seed}_{ix}_{args.jev.replace(':', '_').replace('/', '_')}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=1))
    out(f"Saved {p}")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m jev.walk", description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--pick", choices=sorted(PICKS) + [RANDOM_PICK],
                   help="random (default): a seeded random kind and card, so the person is blind too; the seed is printed. "
                        "cancer, pneumonia, worried_well: you choose the kind, so you know it before the walk (the model still does not): not blind for the person")
    ap.add_argument("--pick-seed", type=int, default=None, help="seed for --pick random (default: a fresh one, printed); the same seed gives the same patient")
    g.add_argument("--library", help="a patient library directory (with --patient)")
    ap.add_argument("--patient", default=None, help="card index or card id in the library (default 0)")
    ap.add_argument("--jev", default="birch", help="birch (proxy on 127.0.0.1:8771), birch+http://host:port, mock "
                    "(local mock, no model), table (the placeholder decision tables, no model)")
    ap.add_argument("--placeholder", action="store_true", help="also show the placeholder decision table's numbers")
    ap.add_argument("--auto-accept", action="store_true", help="accept every proposal without asking")
    ap.add_argument("--include-assessments", action="store_true", help="send earlier assessment entries as evidence too")
    ap.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS, help="hard limit on model calls (default %(default)s)")
    ap.add_argument("--concurrency", type=int, default=1, help="model calls in flight, 1 to 4 (default 1; a walk asks one at a time)")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="answer cache, one directory per checkpoint (default %(default)s)")
    ap.add_argument("--min-interval", type=float, default=GATEWAY_MIN_INTERVAL,
                    help="seconds between live model calls (default %(default)s: the hosted gateway takes 6 a minute; 30 keeps a long run under 120 an hour)")
    ap.add_argument("--work-dir", default="runs", help="libraries, mock cache and saved walks go here")
    ap.add_argument("--world", default=WORLD)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", help="where to save the walk (JSON)")
    a = ap.parse_args(argv)
    if a.pick is None and not a.library:
        if a.patient is not None:
            ap.error("--patient needs --library (or --pick)")
        a.pick = RANDOM_PICK
    try:
        walk(a)
    except (BirchError, EOFError, KeyboardInterrupt) as e:
        print(f"walk ended: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
