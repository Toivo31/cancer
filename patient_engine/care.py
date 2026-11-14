"""Care model (``care/1``): who does what in primary care, what treatments do, how patients behave.

An optional file ``care.yaml`` next to a catalogue's other files (decision D44, encounter loop).
It is medical-practice content, so every number is a leaf object with a ``source`` (an id in
``params/sources.yaml`` or ``assumption``), like the rest of the catalogue. Load it with
``load_care(catalogue_dir, catalogue)``; it raises ``CareError`` with a list of problems.

Shape (see ``catalogue/_examples/tiny/care.yaml`` for a complete small example)::

    format: care/1
    roles:                                   # one entry per role that holds encounters
      - id: nurse
        resource: nurse                      # world resource giving the appointment slot
        gathers:                             # done at every encounter of this role, revealed at once
          - {test: history, outputs: [cough_3wk, fever]}   # outputs omitted = all outputs of the test
        actions: [advice_return, book_gp_routine, book_gp_urgent]
    actions:                                 # the options a role's decision node offers
      - {id: order_chest_xray, kind: order, test: chest_xray}
      - {id: treat_antibiotics, kind: treat, treatment: antibiotics, review_days: {value: 14, source: assumption}}
      - {id: book_gp_routine, kind: book, role: gp, urgency: routine}
      - {id: follow_up, kind: follow_up, days: {value: 14, source: assumption}}
      - {id: refer_urgent, kind: refer, urgency: urgent}
      - {id: advice_return, kind: discharge, advice: true}
      - {id: discharge, kind: discharge}
    treatments:
      - id: antibiotics
        resolves: {pneumonia: {p: {value: 0.9, source: assumption}, days: {dist: lognormal, median: 7, p90: 14, source: assumption}}}
    behaviour:
      first_contact: {values: {nurse: 0.5, gp: 0.5}, source: KHALIFE2025}
      return_if_persisting: {p: 0.7, source: assumption}     # after a discharge, while any symptom persists
      return_delay_days: {dist: lognormal, median: 21, p90: 60, source: assumption}
      give_up_per_episode: {p: 0.05, source: assumption}       # chance a patient stops coming back after an episode
      horizon_days: {value: 365, source: assumption}

Action kinds: ``order`` (a test; its result arrives after the test's report time and opens a review
encounter with the ordering role; ordering a test already done gives its next attempt), ``treat`` (start
a treatment; a review encounter after ``review_days``), ``book`` (an encounter with another role),
``follow_up`` (an encounter with the same role after ``days``), ``refer`` (hand over to the hospital
flowchart), ``discharge`` (episode ends; ``advice: true`` means the patient was told to come back if it
persists, which the behaviour model uses).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .catalogue import Catalogue, Leaf
from .problems import Problem

CARE_FORMAT = "care/1"
CARE_FILE = "care.yaml"
ACTION_KINDS = ("order", "treat", "book", "follow_up", "refer", "discharge")
URGENCIES = ("routine", "urgent")


class CareError(ValueError):
    def __init__(self, problems: list[Problem]):
        self.problems = problems
        super().__init__("; ".join(f"{p.path}: {p.message}" for p in problems[:5]))


@dataclass(frozen=True)
class Gather:
    test: str
    outputs: tuple[str, ...]          # the outputs this role sees from the test (all when the yaml omits them)


@dataclass(frozen=True)
class Role:
    id: str
    label: str
    resource: str | None
    gathers: tuple[Gather, ...]
    actions: tuple[str, ...]


@dataclass(frozen=True)
class Action:
    id: str
    kind: str
    label: str = ""
    test: str | None = None
    treatment: str | None = None
    role: str | None = None           # book: which role
    urgency: str | None = None        # book, refer
    days: Leaf | None = None          # follow_up
    review_days: Leaf | None = None   # treat
    advice: bool = False              # discharge with "come back if it persists"


@dataclass(frozen=True)
class Treatment:
    id: str
    label: str
    resolves: dict[str, tuple[Leaf, Leaf]]   # condition id -> (probability it resolves, days until it does)


@dataclass(frozen=True)
class Care:
    roles: dict[str, Role]
    actions: dict[str, Action]
    treatments: dict[str, Treatment]
    behaviour: dict[str, Leaf]
    problems: list[Problem] = field(default_factory=list)

    def role_actions(self, role: str) -> list[Action]:
        return [self.actions[a] for a in self.roles[role].actions]


class _Reader:
    def __init__(self, cat: Catalogue, sources: set[str] | None):
        self.cat, self.sources, self.problems = cat, sources, []

    def add(self, code: str, msg: str, path: str) -> None:
        self.problems.append(Problem(code=code if code in _codes() else "bad_type", message=msg, path=path, file=CARE_FILE))

    def leaf(self, obj: Any, path: str, kind_hint: str | None = None) -> Leaf | None:
        if not isinstance(obj, dict):
            self.add("bad_type", "a number must be an object with a `source`", path)
            return None
        src = obj.get("source")
        if not isinstance(src, str):
            self.add("missing_source", "every number needs `source` (an id or `assumption`)", path)
            return None
        if self.sources is not None and src != "assumption" and src not in self.sources:
            self.add("unknown_source", f"source {src!r} is not in params/sources.yaml", path)
        kind = next((k for k in ("p", "value", "values", "dist") if k in obj), None)
        if kind is None:
            self.add("bad_type", "a number needs `p`, `value`, `values` or `dist`", path)
            return None
        params = {k: v for k, v in obj.items() if k not in ("source", "grade", "note", "low", "high", "by")}
        if kind == "p" and not (isinstance(obj["p"], (int, float)) and 0 <= obj["p"] <= 1):
            self.add("probability_out_of_range", "`p` must be in 0..1", path)
        return Leaf(kind=kind, params=params, source=src, grade=obj.get("grade"), note=obj.get("note"),
                    low=obj.get("low"), high=obj.get("high"), by=obj.get("by"))


def _codes() -> set[str]:
    from .problems import CODES
    return set(CODES)


def load_care(path: str | Path, catalogue: Catalogue, sources: set[str] | None = None) -> Care | None:
    """Read ``<path>/care.yaml`` (``path`` = the catalogue folder). Returns ``None`` when the file is
    absent. Raises ``CareError`` on any error-severity problem."""
    f = Path(path) / CARE_FILE
    if not f.exists():
        return None
    raw = yaml.safe_load(f.read_text()) or {}
    r = _Reader(catalogue, sources)
    if raw.get("format") != CARE_FORMAT:
        r.add("bad_type", f"`format` must be {CARE_FORMAT}", "format")

    actions: dict[str, Action] = {}
    for i, a in enumerate(raw.get("actions") or []):
        p = f"actions[{i}]"
        kind = a.get("kind")
        if kind not in ACTION_KINDS:
            r.add("bad_type", f"kind must be one of {', '.join(ACTION_KINDS)}", f"{p}.kind")
            continue
        if kind == "order" and a.get("test") not in catalogue.tests:
            r.add("unknown_reference", f"test {a.get('test')!r} is not in the catalogue", f"{p}.test")
        if a.get("urgency") is not None and a["urgency"] not in URGENCIES:
            r.add("bad_type", f"urgency must be one of {', '.join(URGENCIES)}", f"{p}.urgency")
        actions[a["id"]] = Action(
            id=a["id"], kind=kind, label=a.get("label", ""), test=a.get("test"), treatment=a.get("treatment"),
            role=a.get("role"), urgency=a.get("urgency"),
            days=r.leaf(a["days"], f"{p}.days") if "days" in a else None,
            review_days=r.leaf(a["review_days"], f"{p}.review_days") if "review_days" in a else None,
            advice=bool(a.get("advice", False)))

    treatments: dict[str, Treatment] = {}
    for i, t in enumerate(raw.get("treatments") or []):
        p = f"treatments[{i}]"
        res: dict[str, tuple[Leaf, Leaf]] = {}
        for cid, spec in (t.get("resolves") or {}).items():
            if cid not in catalogue.conditions:
                r.add("unknown_reference", f"condition {cid!r} is not in the catalogue", f"{p}.resolves.{cid}")
                continue
            pl, dl = r.leaf(spec.get("p"), f"{p}.resolves.{cid}.p"), r.leaf(spec.get("days"), f"{p}.resolves.{cid}.days")
            if pl and dl:
                res[cid] = (pl, dl)
        treatments[t["id"]] = Treatment(id=t["id"], label=t.get("label", t["id"]), resolves=res)

    roles: dict[str, Role] = {}
    for i, ro in enumerate(raw.get("roles") or []):
        p = f"roles[{i}]"
        gathers = []
        for j, g in enumerate(ro.get("gathers") or []):
            test = catalogue.tests.get(g.get("test"))
            if test is None:
                r.add("unknown_reference", f"test {g.get('test')!r} is not in the catalogue", f"{p}.gathers[{j}].test")
                continue
            outs = tuple(g.get("outputs") or test.output_ids)
            for o in outs:
                if o not in test.output_ids:
                    r.add("unknown_reference", f"test {test.id} has no output {o!r}", f"{p}.gathers[{j}].outputs")
            gathers.append(Gather(test.id, outs))
        for a in ro.get("actions") or []:
            if a not in actions:
                r.add("unknown_reference", f"action {a!r} is not defined under `actions`", f"{p}.actions")
        roles[ro["id"]] = Role(id=ro["id"], label=ro.get("label", ro["id"]), resource=ro.get("resource"),
                               gathers=tuple(gathers), actions=tuple(ro.get("actions") or ()))

    for a in actions.values():
        if a.kind == "book" and a.role not in roles:
            r.add("unknown_reference", f"action {a.id} books role {a.role!r}, which is not defined", "actions")
        if a.kind == "treat" and a.treatment not in treatments:
            r.add("unknown_reference", f"action {a.id} uses treatment {a.treatment!r}, which is not defined", "actions")

    behaviour = {}
    for k, v in (raw.get("behaviour") or {}).items():
        lf = r.leaf(v, f"behaviour.{k}")
        if lf:
            behaviour[k] = lf
    for k in ("first_contact", "return_if_persisting", "return_delay_days", "horizon_days"):
        if k not in behaviour:
            r.add("bad_type", f"behaviour.{k} is required", f"behaviour.{k}")

    errors = [p for p in r.problems if p.severity == "error"]
    if errors:
        raise CareError(errors)
    return Care(roles=roles, actions=actions, treatments=treatments, behaviour=behaviour, problems=r.problems)
