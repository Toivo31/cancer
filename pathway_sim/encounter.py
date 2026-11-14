"""Primary care as an encounter loop (component C8, decisions D44-D49), then the hospital flowchart.

::

    world = load_world("scenarios/finland_encounter.yaml")
    log   = run_encounter(world, n=2000, seed=1)            # EncounterLog (a RunLog with records)
    print(format_outcomes(outcomes(log, world)))

How a patient moves (docs/encounter_loop.md has the long version):

1. **Arrival.** First contact with a nurse or a GP (``behaviour.first_contact``), booked on the role's
   resource (a ``server`` of the shared world, so nurse, GP, lab, X-ray and the hospital queues are real
   queues in one event loop).
2. **Encounter.** Every test in the role's ``gathers`` is done (its next attempt is revealed; only the
   role's outputs reach the record). The policy is asked at decision point ``<role>_encounter`` with a
   ``PatientView`` whose ``record`` holds the record so far plus this encounter (``action`` still None).
   It sees nothing else about the patient (I1). The action is drawn from its probabilities with the keyed
   number ``uniform(seed, patient, "enc", n)`` (n = the patient's encounter count).
3. **Act.** ``order`` books the test, its result arrives as a ``result`` entry and opens a review encounter
   with the ordering role; ``treat`` starts a treatment (hidden side: each true condition it resolves ends
   with p after days), review after ``review_days``; ``book`` / ``follow_up`` schedule an encounter;
   ``refer`` hands the patient to the hospital flowchart at its referral node; ``discharge`` closes the
   episode, and the patient returns while symptoms persist (``return_if_persisting``, ``give_up_per_episode``).
4. **Ends** at treatment start (hospital), leaving (no persisting symptoms, or did not return) or the
   horizon (``undiagnosed_at_horizon``). A hospital discharge sends the patient back to primary care as a
   discharge with advice.

Hidden side: this module reads the card (``Cohort.card(i)``) to apply treatment effects, natural course and
persisting symptoms. The decision side receives only the ``Record`` (``PatientView.record``).
Results: attempt k of a test is ``RevealHandle.reveal(test, k, state)``: a pure function of the card (I3).
Until multi-state cards and fresh attempts beyond ``max_attempts`` exist (WP-C8-2), a request the handle
refuses falls back to the last stored attempt of the first state, with binary outputs whose finding is
caused only by resolved conditions read as absent (counted as ``fallback_reveals``).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import statistics
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from patient_engine.card import INITIAL_STATE, CohortSpec
from patient_engine.care import Care, load_care
from patient_engine.catalogue import Catalogue, load_catalogue
from patient_engine.cohort import Cohort, draw_cohort
from patient_engine.library import Library, load_library, write_library
from patient_engine.record import Entry, Observation, Record
from patient_engine.reference import report_text
from patient_engine.reveal import RevealError, RevealHandle
from patient_engine.skeleton import Design

from .dists import sample, uniform
from .engine import PatientRun, RunLog, Simulation, mark_critical
from .expr import Expr, parse as parse_expr
from .patients import MAX_ATTEMPTS, Patient, p_positive
from .policy import PatientView, choose_with_note
from .scenario import Flowchart, Scenario, load_scenario, parse_flowchart, validate_flowchart

WORLD_FORMAT = "encounter_world/1"
POLICY_FORMAT = "encounter_policy/1"
REASONS = ("first", "booked", "result", "treatment", "follow_up")

try:                                       # WP-C8-2: multi-state cards
    from patient_engine.states import next_state as _next_state  # type: ignore
except ImportError:                        # pragma: no cover - until WP-C8-2 merges
    _next_state = None


# ============================================================================ record names (decision side)

_DOTTED = re.compile(r"(?<![A-Za-z0-9_'\"])([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)")
_QUOTED = re.compile(r"('[^']*'|\"[^\"]*\")")


def undot(source: str) -> str:
    """``found.cough`` -> ``found__cough`` outside quoted text (``pathway_sim.expr`` has no attribute access)."""
    parts = _QUOTED.split(source)
    return "".join(p if i % 2 else _DOTTED.sub(lambda m: m.group(1).replace(".", "__"), p) for i, p in enumerate(parts))


def compile_when(source: str) -> Expr:
    """A table condition: dotted record names allowed (see ``record_names``)."""
    return parse_expr(undot(source))


class RecordNames(dict):
    """Names a table condition reads; ``attempts.<test>`` defaults to 0, anything else unknown to None."""

    def get(self, key, default=None):
        if key in self:
            return self[key]
        if key.startswith("attempts__") or key == "treatments":
            return 0
        return default


def record_names(record: Record, dotted: bool = False) -> RecordNames:
    """The names an encounter decision table may read, built from the ``Record`` alone (I1).

    The decision being made is the record's last mechanical ``encounter`` entry (its ``action`` is None while
    the policy is asked). Names (with ``dotted=False`` the dots are ``__``): background fields; ``found.<output>``;
    ``reported.<variable>`` (this episode); ``last.<test>.<output>``, ``last.<test>.positive``,
    ``last.<test>.days`` (latest ``ok`` result); ``attempts.<test>``; ``treated.<treatment>``, ``treatments``
    (this episode); ``episode``, ``encounters``, ``encounters_total``, ``role_encounters``, ``role``, ``reason``,
    ``last_action``, ``t``, ``t_episode``. Format: ``scenarios/finland_encounter_policy.yaml``."""
    sep = "." if dotted else "__"
    env = RecordNames()
    env.update(record.background)
    ents = record.mechanical()
    cur = ents[-1] if ents else None
    now = cur.t_days if cur else 0.0
    episode = cur.episode if cur else 1
    ep = [e for e in ents if e.episode == episode]
    encs = [e for e in ep if e.kind == "encounter"]
    role = cur.role if cur is not None and cur.kind == "encounter" else None
    env.update(episode=episode, encounters=len(encs), role=role,
               encounters_total=sum(1 for e in ents if e.kind == "encounter"),
               role_encounters=sum(1 for e in encs if e.role == role),
               t=now, t_episode=now - (ep[0].t_days if ep else now))
    for k, v in record.latest_found().items():
        env[f"found{sep}{k}"] = v
    for e in ep:
        for v in e.reported:
            env[f"reported{sep}{v}"] = True
    for t, o in record.observations():
        env[f"attempts{sep}{o.test}"] = env.get(f"attempts{sep}{o.test}", 0) + 1
        if o.status == "ok":
            for out, val in o.values.items():
                env[f"last{sep}{o.test}{sep}{out}"] = val
            env[f"last{sep}{o.test}{sep}positive"] = o.positive
            env[f"last{sep}{o.test}{sep}days"] = round(now - t, 3)
    n_treat = 0
    for e in ep:
        if e.kind == "treatment" and e.action:
            env[f"treated{sep}{e.action}"] = True
            n_treat += 1
    env["treatments"] = n_treat
    # why this encounter happens, from the entries since the previous encounter of the episode
    before = ep[:-1] if cur is not None and cur.kind == "encounter" else ep
    prev_enc = next((e for e in reversed(before) if e.kind == "encounter"), None)
    reason, last_action = "first", None
    if prev_enc is not None:
        last_action = prev_enc.action
        after = before[before.index(prev_enc) + 1:]
        kinds = {e.kind for e in after}
        if "result" in kinds:
            reason = "result"
        elif "treatment" in kinds:
            reason = "treatment"
        elif prev_enc.role == role:
            reason = "follow_up"
        else:
            reason = "booked"
    env["reason"], env["last_action"] = reason, last_action
    return env


# ============================================================================ decision tables

class PolicyTableError(ValueError):
    pass


def _row(where: str, row) -> dict[str, float]:
    if not isinstance(row, dict) or not row:
        raise PolicyTableError(f"{where}: probabilities must be an object like {{action: 0.5, ...}}")
    out = {}
    for k, v in row.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise PolicyTableError(f"{where}: probability for {k!r} must be a number >= 0")
        out[str(k)] = float(v)
    if sum(out.values()) <= 0:
        raise PolicyTableError(f"{where}: probabilities are all zero")
    return out


class EncounterTablePolicy:
    """Decision tables (``encounter_policy/1``) for ``<role>_encounter`` points, reading ``view.record`` only.

    First rule whose ``when`` holds and that puts mass on an offered action wins, else ``default``; the row is
    restricted to the offered actions and renormalised; nothing usable gives uniform probabilities and a
    ``missing_probabilities`` warning. ``choose_with_note`` adds a template assessment (D49): the rule's
    ``working_diagnosis`` when it has one and ``plan: {action}`` (the engine fills in the chosen action)."""

    backend_name = "table"
    model_id = POLICY_FORMAT
    decision_mode = "sample"

    def __init__(self, points: dict):
        self.points: dict[str, dict] = {}
        self.warnings: dict[str, int] = {}
        for pt, spec in (points or {}).items():
            if not isinstance(spec, dict):
                raise PolicyTableError(f"{pt}: expected an object with `default` and optional `rules`")
            rules = []
            for i, r in enumerate(spec.get("rules") or []):
                where = f"{pt}/rules[{i}]"
                if not isinstance(r, dict) or "when" not in r or "probs" not in r:
                    raise PolicyTableError(f"{where}: a rule needs `when` and `probs`")
                try:
                    cond = compile_when(str(r["when"]))
                except ValueError as e:
                    raise PolicyTableError(f"{where}: bad condition {r['when']!r}: {e}") from None
                rules.append({"when": str(r["when"]), "code": cond, "probs": _row(where, r["probs"]),
                              "working_diagnosis": r.get("working_diagnosis")})
            default = _row(f"{pt}/default", spec["default"]) if spec.get("default") else None
            self.points[pt] = {"default": default, "rules": rules,
                               "working_diagnosis": spec.get("working_diagnosis")}

    @classmethod
    def from_file(cls, path: str | Path) -> "EncounterTablePolicy":
        raw = yaml.safe_load(Path(path).read_text()) or {}
        if raw.get("format") != POLICY_FORMAT:
            raise PolicyTableError(f"{path}: `format` must be {POLICY_FORMAT}")
        return cls(raw.get("points") or {})

    def problems(self, care: Care) -> list[str]:
        """Rows naming actions the role does not offer, points for unknown roles, rows not summing to 1."""
        out = []
        for pt, spec in self.points.items():
            role = pt[: -len("_encounter")] if pt.endswith("_encounter") else None
            if role not in care.roles:
                out.append(f"{pt}: no role {role!r} in the care model")
                continue
            offered = set(care.roles[role].actions)
            rows = ([("default", spec["default"])] if spec["default"] else []) + \
                   [(f"rule {r['when']!r}", r["probs"]) for r in spec["rules"]]
            for label, row in rows:
                bad = sorted(set(row) - offered)
                if bad:
                    out.append(f"{pt}/{label}: actions {bad} are not offered to {role}")
                if abs(sum(row.values()) - 1) > 1e-6:
                    out.append(f"{pt}/{label}: probabilities sum to {sum(row.values()):.4g}, not 1")
        return out

    @staticmethod
    def _restrict(row: dict, offered: list[str]) -> dict[str, float] | None:
        total = sum(row.get(o, 0.0) for o in offered)
        return None if total <= 0 else {o: row.get(o, 0.0) / total for o in offered}

    def _warn(self, pt: str) -> None:
        k = f"missing_probabilities:{pt}"
        self.warnings[k] = self.warnings.get(k, 0) + 1

    def choose_with_note(self, view: PatientView, options: list[str]):
        spec = self.points.get(view.node)
        if spec is None:
            self._warn(view.node)
            return {o: 1 / len(options) for o in options}, None, None
        env = record_names(view.record) if view.record is not None else RecordNames()
        for r in spec["rules"]:
            if r["code"].holds(env):
                row = self._restrict(r["probs"], options)
                if row is not None:
                    a = {"plan": "{action}"}
                    if r["working_diagnosis"]:
                        a["working_diagnosis"] = r["working_diagnosis"]
                    return row, f"Table rule: {r['when']}.", a
        if spec["default"] is not None:
            row = self._restrict(spec["default"], options)
            if row is not None:
                a = {"plan": "{action}"}
                if spec["working_diagnosis"]:
                    a["working_diagnosis"] = spec["working_diagnosis"]
                return row, "Table default.", a
        self._warn(view.node)
        return {o: 1 / len(options) for o in options}, None, None

    def choose(self, view: PatientView, options: list[str]) -> dict[str, float]:
        return self.choose_with_note(view, options)[0]

    def run_summary(self) -> dict:
        return {"warnings": dict(self.warnings)} if self.warnings else {}


# ============================================================================ the world

@dataclass
class EncounterWorld:
    id: str
    raw: dict
    path: Path
    catalogue: Catalogue
    care: Care
    care_path: Path
    policy: EncounterTablePolicy
    scenario: Scenario                     # hospital scenario with the merged resources
    flowchart: Flowchart                   # hospital sub-flowchart (entry node and downstream)
    target_days: float

    @property
    def hospital(self) -> dict:
        return self.raw.get("hospital") or {}

    @property
    def encounters(self) -> dict:
        return self.raw.get("encounters") or {}

    def leaf_value(self, spec, default: float) -> float:
        if spec is None:
            return default
        if isinstance(spec, (int, float)):
            return float(spec)
        return float(spec.get("value", spec.get("p", default)))

    def prevalence(self) -> dict[str, float]:
        p = self.raw.get("prevalence", "catalogue")
        if isinstance(p, dict):
            return {k: float(v) for k, v in p.items()}
        return {c: float(cd.prevalence.resolve()) for c, cd in self.catalogue.conditions.items()}


def hospital_subflowchart(fc: Flowchart, entry: str, new_id: str = "encounter") -> Flowchart:
    """``entry`` and every node downstream of it; dependencies on dropped nodes are removed and the entry
    node loses its guard (the referral itself is the condition)."""
    if entry not in fc.nodes:
        raise ValueError(f"flowchart {fc.id} has no node {entry!r}")
    children: dict[str, set[str]] = {x: set() for x in fc.nodes}
    for n in fc.nodes.values():
        for d in list(n.after) + list(n.after_any) + list(n.after_optional):
            children[d].add(n.id)
        if n.kind == "choice":
            for o in n.options:
                children[n.id].add(o)
    keep, stack = set(), [entry]
    while stack:
        x = stack.pop()
        if x not in keep:
            keep.add(x)
            stack.extend(children[x])
    d = fc.to_dict()
    nodes = []
    for nd in d["nodes"]:
        if nd["id"] not in keep:
            continue
        nd = dict(nd)
        for k in ("after", "after_any", "after_optional"):
            if k in nd:
                nd[k] = [x for x in nd[k] if x in keep]
                if not nd[k]:
                    del nd[k]
        if nd["id"] == entry:
            nd.pop("when", None)
            for k in ("after", "after_any", "after_optional"):
                nd.pop(k, None)
        nodes.append(nd)
    d["nodes"] = nodes
    d["policy"] = {k: v for k, v in (d.get("policy") or {}).items() if k in keep}
    d["description"] = f"hospital part of {fc.id} from {entry}"
    return parse_flowchart(new_id, d)


def load_world(path: str | Path) -> EncounterWorld:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    if raw.get("format") != WORLD_FORMAT:
        raise ValueError(f"{path}: `format` must be {WORLD_FORMAT}")
    base = path.parent
    cat = load_catalogue(base / raw["catalogue"])
    care_dir = base / raw.get("care", raw["catalogue"])
    if not (care_dir / "care.yaml").exists() and raw.get("care_fallback"):
        care_dir = base / raw["care_fallback"]
    care = load_care(care_dir, cat)
    if care is None:
        raise ValueError(f"{path}: no care.yaml in {care_dir}")
    policy = EncounterTablePolicy.from_file(base / raw["policy"])
    probs = policy.problems(care)
    if probs:
        raise PolicyTableError("; ".join(probs[:5]))
    hosp = raw.get("hospital") or {}
    sc = copy.deepcopy(load_scenario(base / hosp["scenario"]))
    res = dict(sc.resources)
    extra = dict(raw.get("resources") or {})
    rf = raw.get("resources_file")
    if rf and (base / rf).exists():
        fr = yaml.safe_load((base / rf).read_text()) or {}
        extra.update(fr.get("resources", fr) or {})
    for rid, spec in extra.items():
        if isinstance(spec, dict) and ("type" in spec or "capacity_per_day" in spec):
            res[rid] = {**res.get(rid, {}), **spec}
    sc.resources = res
    fc = hospital_subflowchart(sc.flowcharts[hosp.get("flowchart", "baseline")], hosp.get("entry", "referral_in"))
    validate_flowchart(sc, fc)
    sc.flowcharts = {**sc.flowcharts, fc.id: fc}
    return EncounterWorld(id=raw.get("id", path.stem), raw=raw, path=path, catalogue=cat, care=care,
                          care_path=care_dir, policy=policy, scenario=sc, flowchart=fc,
                          target_days=float(raw.get("target_days", sc.target_days)))


def is_world_file(path: str | Path) -> bool:
    try:
        with open(path) as f:
            head = f.read(4000)
    except OSError:
        return False
    return re.search(rf"^format:\s*['\"]?{re.escape(WORLD_FORMAT)}", head, re.M) is not None


# ============================================================================ library and cohort

_LIBRARIES: dict[str, Library] = {}


def world_library(world: EncounterWorld) -> Library:
    """The world's card library: a stored one (``library: {path}``) or reference cards generated per primary
    condition (``library: {per_condition, seed}``), written once to a temporary directory per process."""
    spec = world.raw.get("library") or {}
    if spec.get("path"):
        return load_library(world.path.parent / spec["path"], world.catalogue)
    per, seed = int(spec.get("per_condition", 60)), int(spec.get("seed", 1))
    key = f"{world.catalogue.version_hash}|{per}|{seed}"
    if key not in _LIBRARIES:
        from patient_engine.reference import reference_cards
        design = Design(mode="stratified", n=per * len(world.catalogue.conditions),
                        counts=tuple((c, per) for c in world.catalogue.conditions))
        cards = list(reference_cards(world.catalogue, design, seed))
        d = Path(tempfile.mkdtemp(prefix="enc_lib_"))
        write_library(cards, world.catalogue, d, meta={"created": "1970-01-01T00:00:00Z"})
        _LIBRARIES[key] = load_library(d, world.catalogue)
    return _LIBRARIES[key]


def world_cohort(world: EncounterWorld, n: int, seed: int) -> Cohort:
    lib = world_library(world)
    prev = {c: v for c, v in world.prevalence().items() if c in lib.by_condition and v > 0}
    arr = {k: v for k, v in (world.raw.get("arrivals") or {"rate_per_day": 44}).items()
           if k in ("rate_per_day", "spread_days")}
    return draw_cohort(lib, CohortSpec(library_id=lib.id, prevalence=prev, n=n, seed=seed), arr)


def _pick(weights: dict, u: float) -> str:
    total, acc = sum(weights.values()), 0.0
    for k, w in weights.items():
        acc += w / total
        if u < acc:
            return k
    return list(weights)[-1]


def hospital_patient(world: EncounterWorld, cohort: Cohort, i: int, seed: int) -> Patient:
    """The flowchart engine's ``Patient`` for cohort patient ``i`` (hidden side): the catalogue condition
    mapped to the hospital scenario's, attributes and pre-drawn results for hospital steps that do not read
    the card (as ``pathway_sim.patients``, same keys)."""
    sc, hosp = world.scenario, world.hospital
    card = cohort.card(i)
    cat_cond = card.primary_condition
    cmap = hosp.get("condition_map") or {}
    cond = cmap.get(cat_cond, hosp.get("default_condition", sc.conditions[-1]["id"]))
    reported = set(card.presenting[INITIAL_STATE].reported)
    if cond == "lung_cancer_nonspec" and "haemoptysis" in reported and any(c["id"] == "lung_cancer_site" for c in sc.conditions):
        cond = "lung_cancer_site"
    group = "site_specific" if "haemoptysis" in reported else "non_specific"
    attrs = {}
    for name, spec in sc.attributes.items():
        lvl = next((c.attributes.get(name) for c in card.hidden.conditions if name in c.attributes), None)
        attrs[name] = lvl if lvl is not None else _pick(spec["values"], uniform(seed, i, "attr", name))
    results = {}
    for tid, test in sc.tests.items():
        p = p_positive(test, cond, {**attrs, "group": group})
        nd = test.get("p_nondiagnostic", 0.0) or 0.0
        if isinstance(nd, dict):
            nd = nd.get({**attrs, "group": group}.get(nd["by"]), nd.get("default", 0.0))
        results[tid] = [None if uniform(seed, i, "nd", tid, k) < float(nd) else uniform(seed, i, "res", tid, k) < p
                        for k in range(MAX_ATTEMPTS)]
    is_cancer = world.catalogue.conditions[cat_cond].cls == "cancer"
    age = int(card.background.get("age") or 0)
    return Patient(i, cond, is_cancer, group, age, cohort.arrival[i], attrs, results)


# ============================================================================ per-patient state

@dataclass
class EncounterRun(PatientRun):
    record: Record | None = None
    primary_condition: str = ""                 # hidden, for scoring
    conditions: tuple = ()                      # hidden, for scoring
    phase: str = "primary"                      # primary | hospital | done
    episode: int = 1
    enc_total: int = 0
    enc_in_episode: int = 0
    attempts: dict = field(default_factory=dict)            # catalogue test -> attempts done
    resolve_at: dict = field(default_factory=dict)          # hidden: condition -> day it resolves
    pending: dict = field(default_factory=dict)             # (test, attempt) -> (role, encounter, observation)
    hosp_obs: dict = field(default_factory=dict)            # hospital test -> list of card observations
    t_referral: float | None = None
    referrals: int = 0
    hospital_discharges: int = 0
    by_role: dict = field(default_factory=dict)
    tests_ordered: list = field(default_factory=list)
    cost: dict = field(default_factory=lambda: {"visits": 0.0, "tests": 0.0, "hospital": 0.0})
    treatments: list = field(default_factory=list)          # {"id", "t", "matched"}
    seen: list = field(default_factory=list)                # hidden: (test, attempt, state, values) served
    fallback_reveals: int = 0

    def to_dict(self) -> dict:
        d = super().to_dict()
        a = self.patient.arrival
        d.update({
            "primary_condition": self.primary_condition, "conditions": list(self.conditions),
            "episodes": self.episode, "encounters_by_role": dict(self.by_role),
            "t_referral": None if self.t_referral is None else round(self.t_referral - a, 4),
            "referrals": self.referrals, "hospital_discharges": self.hospital_discharges,
            "tests_ordered": list(self.tests_ordered), "cost_eur": {k: round(v, 2) for k, v in self.cost.items()},
            "treatments": list(self.treatments), "fallback_reveals": self.fallback_reveals,
            "record": self.record.to_json() if self.record is not None else None,
        })
        return d


@dataclass
class EncounterLog(RunLog):
    world: str = ""
    library_id: str = ""
    cohort_fingerprint: str = ""
    distinct_cards: int = 0

    def to_dict(self, include_patients: bool = True) -> dict:
        d = super().to_dict(include_patients)
        d.update(world=self.world, library_id=self.library_id, cohort_fingerprint=self.cohort_fingerprint,
                 distinct_cards=self.distinct_cards)
        return d


# ============================================================================ the simulation

class EncounterSimulation(Simulation):
    def __init__(self, world: EncounterWorld, cohort: Cohort, policy=None, seed: int = 0):
        self.world, self.cohort = world, cohort
        self.cat, self.care = world.catalogue, world.care
        self.enc_policy = policy if policy is not None else world.policy
        patients = [hospital_patient(world, cohort, i, seed) for i in range(cohort.n)]
        super().__init__(world.scenario, world.flowchart, patients, None, seed)
        b = self.care.behaviour
        self.first_contact = b["first_contact"].resolve()
        self.p_return = float(b["return_if_persisting"].resolve())
        self.return_delay = b["return_delay_days"].params
        self.p_give_up = float(b["give_up_per_episode"].resolve()) if "give_up_per_episode" in b else 0.0
        self.horizon = float(b["horizon_days"].resolve())
        enc = world.encounters
        self.review_urgent = enc.get("review_urgency", "urgent") == "urgent"
        self.no_advice = world.leaf_value(enc.get("no_advice_return_factor"), 1.0)
        self.cost_scale = world.leaf_value(enc.get("cost_scale"), 1.0)
        self.visit_cost = {r: world.leaf_value(v, 0.0) for r, v in (enc.get("visit_cost_eur") or {}).items()}
        self.natural = world.raw.get("natural_course") or {}
        self.symptoms = [v for v, x in self.cat.variables.items() if x.kind == "symptom"]
        self.backend = getattr(self.enc_policy, "backend_name", type(self.enc_policy).__name__)

    # ------------------------------------------------------------------ helpers (hidden side)
    def new_run(self, p: Patient) -> EncounterRun:
        card = self.cohort.card(p.id)
        return EncounterRun(p, primary_condition=card.primary_condition,
                            conditions=tuple(c.id for c in card.hidden.conditions))

    def card(self, pr):
        return self.cohort.card(pr.patient.id)

    def handle(self, pr) -> RevealHandle:
        return self.cohort.handle(pr.patient.id)

    def u(self, pr, *key) -> float:
        return uniform(self.seed, pr.patient.id, *key)

    def end_of_horizon(self, pr) -> float:
        return pr.patient.arrival + self.horizon

    def resolved(self, pr, t: float) -> set[str]:
        return {c for c, tr in pr.resolve_at.items() if tr <= t}

    def state(self, pr, t: float) -> str:
        res = self.resolved(pr, t) - {"unexplained"}
        if not res:
            return INITIAL_STATE
        card = self.card(pr)
        if _next_state is not None:
            try:
                return _next_state(card, res)
            except Exception:              # pragma: no cover - signature drift until WP-C8-2 merges
                pass
        active = [c.id for c in card.hidden.conditions]
        if set(active) <= res:
            return "all_resolved"
        if len(res) == 1:
            return f"{next(iter(res))}_resolved"
        return "all_resolved"

    def persisting(self, pr, t: float) -> set[str]:
        """Symptom variables still present at ``t`` (hidden side): a finding persists unless every condition
        causing it has resolved; findings with no cause persist until ``unexplained`` resolves."""
        res = self.resolved(pr, t)
        out = set()
        for v, f in self.card(pr).hidden.findings[INITIAL_STATE].items():
            if v not in self.symptoms or not f.value:
                continue
            if f.caused_by:
                if not set(f.caused_by) <= res:
                    out.add(v)
            elif "unexplained" not in res:
                out.add(v)
        return out

    def reveal(self, pr, test_id: str, k: int, t: float) -> tuple[str, dict, str, bool | None]:
        """``(status, values, report, positive)`` of attempt ``k`` (0-based) of ``test_id`` at time ``t``."""
        state = self.state(pr, t)
        test = self.cat.tests[test_id]
        h = self.handle(pr)
        try:
            ro = h.reveal(test_id, k, state)
            status, values, report = ro.status, dict(ro.values), ro.report
        except RevealError:
            pr.fallback_reveals += 1
            ro = h.reveal(test_id, min(k, h.max_attempts(test_id) - 1), INITIAL_STATE)
            status, values = ro.status, dict(ro.values)
            res = self.resolved(pr, t) - {"unexplained"}
            if res and status == "ok":
                findings = self.card(pr).hidden.findings[INITIAL_STATE]
                for o in test.outputs:
                    f = findings.get(o.measures)
                    if o.type == "binary" and f is not None and f.caused_by and set(f.caused_by) <= res:
                        values[o.id] = False
            report = report_text(test, status, values) if values != dict(ro.values) else ro.report
        positive = test.is_positive(values) if status == "ok" else None
        pr.seen.append((test_id, k, state, tuple(sorted(values.items()))))
        return status, values, report, positive

    def next_attempt(self, pr, test_id: str) -> int:
        k = pr.attempts.get(test_id, 0)
        pr.attempts[test_id] = k + 1
        return k

    def rel(self, pr, t: float) -> float:
        return t - pr.patient.arrival

    def label(self, action_id: str) -> str:
        a = self.care.actions.get(action_id)
        return (a.label or a.id) if a else action_id

    def finish(self, pr, outcome: str, t: float) -> None:
        pr.outcome, pr.t_exit, pr.phase = outcome, t, "done"

    def book(self, pr, role: str, t_ready: float, urgent: bool) -> None:
        rid = self.care.roles[role].resource
        t = self.servers[rid].book(t_ready, urgent) if rid in self.servers else t_ready
        if t > self.end_of_horizon(pr):
            self.finish(pr, "undiagnosed_at_horizon", self.end_of_horizon(pr))
            return
        self.push(t, "enc", pr.patient.id, role)

    # ------------------------------------------------------------------ engine hooks
    def on_arrive(self, pr, t: float) -> None:
        card = self.card(pr)
        pr.record = Record(self.handle(pr).card_id, dict(card.background))
        for c in [c.id for c in card.hidden.conditions] + ["unexplained"]:
            nc = self.natural.get(c)
            if nc and self.u(pr, "natural", c) < float(nc.get("p", 0)):
                pr.resolve_at[c] = t + max(0.0, sample(nc.get("days"), self.u(pr, "natural_days", c)))
        self.start_episode(pr, t)

    def start_episode(self, pr, t: float) -> None:
        role = _pick(self.first_contact, self.u(pr, "first_contact", pr.episode))
        if role not in self.care.roles:
            role = next(iter(self.care.roles))
        self.book(pr, role, t, False)

    def on_event(self, pr, kind: str, node: str, attempt: int, t: float) -> None:
        if pr.phase != "primary":
            return
        if kind == "enc":
            self.encounter(pr, node, t)
        elif kind == "enc_result":
            self.result_arrives(pr, node, attempt, t)
        elif kind == "enc_return":
            pr.episode += 1
            pr.enc_in_episode = 0
            pr.record.append(Entry(self.rel(pr, t), pr.episode, "return", note="Patient returns: symptoms persist."))
            self.start_episode(pr, t)

    # ------------------------------------------------------------------ encounter
    def encounter(self, pr, role_id: str, t: float) -> None:
        role = self.care.roles[role_id]
        pr.enc_total += 1
        pr.enc_in_episode += 1
        pr.by_role[role_id] = pr.by_role.get(role_id, 0) + 1
        pr.cost["visits"] += self.visit_cost.get(role_id, 0.0)
        present = self.persisting(pr, t)
        try:
            reported = tuple(v for v in self.handle(pr).visible(self.state(pr, t)).presenting.reported if v in present)
        except RevealError:
            reported = tuple(v for v in self.card(pr).presenting[INITIAL_STATE].reported if v in present)
        found, obs = {}, []
        for g in role.gathers:
            test = self.cat.tests[g.test]
            k = self.next_attempt(pr, g.test)
            status, values, _, _ = self.reveal(pr, g.test, k, t)
            sub = {o: values.get(o) for o in g.outputs} if status == "ok" else {}
            if status == "ok":
                found.update(sub)
            pos = test.is_positive(sub) if status == "ok" else None
            obs.append(Observation(g.test, k + 1, status, sub, report_text(test, status, sub), pos))
        rel = self.rel(pr, t)
        options = list(role.actions)
        draft = Entry(rel, pr.episode, "encounter", encounter=pr.enc_in_episode, role=role_id, reported=reported,
                      found=found, observations=tuple(obs))
        view_record = Record(pr.record.patient_id, dict(pr.record.background), list(pr.record.entries) + [draft])
        view = PatientView(pr.patient.id, "", int(pr.record.background.get("age") or 0), rel, f"{role_id}_encounter",
                           record=view_record, offered=options)
        probs, note, assessment = choose_with_note(self.enc_policy, view, options)
        action = self.draw(pr, options, probs)
        lab = self.label(action)
        pr.record.append(Entry(rel, pr.episode, "encounter", encounter=pr.enc_in_episode, role=role_id,
                               reported=reported, found=found, observations=tuple(obs), action=action,
                               note=self.encounter_note(role_id, found, lab)))
        if note or assessment:
            note = (note or "").replace("{action}", lab)
            assessment = {k: (v.replace("{action}", lab) if isinstance(v, str) else v)
                          for k, v in (assessment or {}).items()}
            pr.record.add_assessment(rel, f"{role_id}_encounter/{self.backend}", note, assessment,
                                     role=role_id, encounter=pr.enc_in_episode)
        pr.choices.append({"node": f"{role_id}_encounter", "t": round(rel, 4), "chosen": action, "offered": options,
                           "probs": {k: round(float(v), 4) for k, v in probs.items()}, "mode": "sample",
                           "backend": self.backend, "model": getattr(self.enc_policy, "model_id", None)})
        self.act(pr, role_id, action, t)

    def draw(self, pr, options: list[str], probs: dict) -> str:
        w = [max(0.0, float(probs.get(o, 0.0))) for o in options]
        total = sum(w)
        if total <= 0:
            return options[0]
        u, acc, last = self.u(pr, "enc", pr.enc_total), 0.0, options[0]
        for o, x in zip(options, w):
            if x <= 0:
                continue
            last = o
            acc += x / total
            if u < acc:
                return o
        return last

    @staticmethod
    def encounter_note(role: str, found: dict, label: str) -> str:
        pos = [k.replace("_", " ") for k, v in found.items() if v is True]
        neg = [k.replace("_", " ") for k, v in found.items() if v is False]
        bits = []
        if pos:
            bits.append(", ".join(pos[:5]) + ".")
        if neg and len(neg) <= 4:
            bits.append("No " + ", ".join(neg) + ".")
        elif not pos:
            bits.append("Nothing found on questioning.")
        return f"{role.upper()}: " + " ".join(bits) + f" Plan: {label}."

    # ------------------------------------------------------------------ actions
    def act(self, pr, role: str, action_id: str, t: float) -> None:
        a = self.care.actions[action_id]
        rel = self.rel(pr, t)
        if a.kind == "order":
            self.order_test(pr, role, a.test, t)
        elif a.kind == "treat":
            tr = self.care.treatments[a.treatment]
            pr.record.append(Entry(rel, pr.episode, "treatment", encounter=pr.enc_in_episode, role=role,
                                   action=tr.id, note=f"{tr.label} started."))
            n_given = sum(1 for x in pr.treatments if x["id"] == tr.id)
            matched = False
            for c in pr.conditions:
                if c not in tr.resolves:
                    continue
                matched = True
                pl, dl = tr.resolves[c]
                if self.u(pr, "treat", tr.id, c, n_given) < float(pl.resolve()):
                    tr_t = t + max(0.0, sample(dl.params, self.u(pr, "treat_days", tr.id, c, n_given)))
                    pr.resolve_at[c] = min(pr.resolve_at.get(c, math.inf), tr_t)
            pr.treatments.append({"id": tr.id, "t": round(rel, 3), "matched": matched})
            days = sample(a.review_days.params, 0.5) if a.review_days else 14.0
            self.book(pr, role, t + days, self.review_urgent)
        elif a.kind == "book":
            self.book(pr, a.role, t, a.urgency == "urgent")
        elif a.kind == "follow_up":
            days = sample(a.days.params, 0.5) if a.days else 14.0
            self.book(pr, role, t + days, self.review_urgent)
        elif a.kind == "refer":
            pr.record.append(Entry(rel, pr.episode, "referral", encounter=pr.enc_in_episode, role=role,
                                   action=action_id, note=f"{self.label(action_id)} sent."))
            self.refer(pr, t, a.urgency == "urgent")
        elif a.kind == "discharge":
            self.discharge(pr, t, a.advice, role=role, action=action_id)

    def order_test(self, pr, role: str, test_id: str, t: float) -> None:
        test = self.cat.tests[test_id]
        k = self.next_attempt(pr, test_id)
        rid = test.resource_kind
        if rid in self.servers:
            t_start = self.servers[rid].book(t, False)
        else:
            t_start = t
        svc = test.timing.get("service_days")
        rep = test.timing.get("report_days")
        t_end = t_start + (sample(svc.params, self.u(pr, "svc", test_id, k)) if svc else 0.0)
        t_res = t_end + (sample(rep.params, self.u(pr, "rep", test_id, k)) if rep else 0.0)
        pr.tests_ordered.append(test_id)
        if test.cost_eur is not None:
            pr.cost["tests"] += float(test.cost_eur.resolve()) * self.cost_scale
        if t_res > self.end_of_horizon(pr):
            self.finish(pr, "undiagnosed_at_horizon", self.end_of_horizon(pr))
            return
        status, values, report, positive = self.reveal(pr, test_id, k, t_end)
        pr.pending[(test_id, k)] = (role, pr.enc_in_episode, Observation(test_id, k + 1, status, values, report, positive))
        self.push(t_res, "enc_result", pr.patient.id, test_id, k)

    def result_arrives(self, pr, test_id: str, k: int, t: float) -> None:
        role, enc, ob = pr.pending.pop((test_id, k))
        lab = self.cat.tests[test_id].label
        reading = {True: "positive", False: "negative", None: "no reading"}[ob.positive] if ob.status == "ok" else "non-diagnostic"
        pr.record.append(Entry(self.rel(pr, t), pr.episode, "result", encounter=enc, role=role,
                               observations=(ob,), note=f"{lab}: {reading}."))
        self.book(pr, role, t, self.review_urgent)

    def discharge(self, pr, t: float, advice: bool, role: str | None = None, action: str | None = None) -> None:
        rel = self.rel(pr, t)
        pr.record.append(Entry(rel, pr.episode, "discharge", encounter=pr.enc_in_episode if role else None, role=role,
                               action=action, note="Discharged" + (" with advice to return if it persists." if advice else ".")))
        gave_up = self.u(pr, "give_up", pr.episode) < self.p_give_up
        t_ret = t + max(0.5, sample(self.return_delay, self.u(pr, "return_delay", pr.episode)))
        persisting = bool(self.persisting(pr, t_ret))
        p = self.p_return * (1.0 if advice else self.no_advice)
        if persisting and not gave_up and self.u(pr, "return", pr.episode) < p:
            if t_ret > self.end_of_horizon(pr):
                self.finish(pr, "undiagnosed_at_horizon", self.end_of_horizon(pr))
            else:
                self.push(t_ret, "enc_return", pr.patient.id)
            return
        self.finish(pr, "left_with_symptoms" if persisting else "left_resolved", t)

    # ------------------------------------------------------------------ hand-over to the hospital
    def refer(self, pr, t: float, urgent: bool) -> None:
        if pr.t_referral is None:
            pr.t_referral = t
        pr.referrals += 1
        for hosp_test, cat_test in (self.world.hospital.get("card_tests") or {}).items():
            k0 = pr.attempts.get(cat_test, 0)
            obs = [self.reveal(pr, cat_test, k0 + j, t) for j in range(MAX_ATTEMPTS)]
            pr.hosp_obs[hosp_test] = (cat_test, k0, obs)
            pr.patient.results[hosp_test] = [o[3] if o[0] == "ok" else None for o in obs]
        for nid in self.fc.nodes:
            pr.status[nid] = "pending"
            pr.result.pop(nid, None)
            pr.t_done.pop(nid, None)
            pr.cause.pop(nid, None)
        pr.priority = bool(urgent and self.world.hospital.get("urgent_referral_priority", False))
        pr.phase = "hospital"
        self.advance(pr, t)

    def on_done(self, pr, nid: str, attempt: int, t: float) -> None:
        if pr.phase != "hospital":
            return
        n = self.fc.nodes[nid]
        res_list = pr.patient.results.get(n.test) or [True]
        r = res_list[min(attempt, len(res_list) - 1)]
        test = self.tests[n.test]
        if test.get("cost_eur"):
            pr.cost["hospital"] += float(test["cost_eur"])
        if n.test in pr.hosp_obs:
            cat_test, k0, obs = pr.hosp_obs[n.test]
            status, values, report, positive = obs[min(attempt, len(obs) - 1)]
            ob = Observation(cat_test, k0 + attempt + 1, status, values, report, positive)
            pr.attempts[cat_test] = max(pr.attempts.get(cat_test, 0), k0 + attempt + 1)
        else:
            ob = Observation(n.test, attempt + 1, "ok" if r is not None else "non_diagnostic",
                             {"result": r} if r is not None else {}, n.label or n.test, r)
        pr.record.append(Entry(self.rel(pr, t), pr.episode, "hospital", observations=(ob,), action=nid,
                               note=f"{n.label or nid}: " + ("positive" if r else "negative" if r is False else "non-diagnostic") + "."))
        super().on_done(pr, nid, attempt, t)

    def exit(self, pr, nid: str, t: float) -> None:
        if pr.phase != "hospital":
            return
        n = self.fc.nodes[nid]
        if n.outcome == "treatment":
            pr.record.append(Entry(self.rel(pr, t), pr.episode, "hospital", action=nid, note=f"{n.label or nid}."))
            super().exit(pr, nid, t)
            pr.phase = "done"
            return
        pr.status[nid], pr.t_done[nid] = "done", t
        pr.hospital_discharges += 1
        pr.phase, pr.priority = "primary", False
        self.discharge(pr, t, True, action=nid)

    # ------------------------------------------------------------------ run
    def run(self) -> EncounterLog:
        log = super().run()
        for pr in log.patients:
            if pr.outcome is None:                 # cannot happen: every path ends; kept as a guard
                pr.outcome = "stuck"
        if log.patients:                           # utilisation over the arrival window (no warm-up cut here)
            t0 = min(p.patient.arrival for p in log.patients)
            t1 = max(p.patient.arrival for p in log.patients)
            for rid, s in self.servers.items():
                log.resources[rid] = s.summary(t0, t1)
        return EncounterLog(**log.__dict__, world=self.world.id, library_id=self.cohort.library_id,
                            cohort_fingerprint=self.cohort.fingerprint(), distinct_cards=self.cohort.distinct_cards)


def run_encounter(world: EncounterWorld, n: int, seed: int, policy=None, cohort: Cohort | None = None,
                  progress=None) -> EncounterLog:
    """Run ``n`` patients of ``world`` through the encounter loop and the hospital part. Deterministic in
    (world, n, seed, policy) (I2). ``policy`` defaults to the world's decision tables."""
    cohort = cohort if cohort is not None else world_cohort(world, n, seed)
    sim = EncounterSimulation(world, cohort, policy, seed)
    sim.progress = progress
    log = sim.run()
    log.target_days = world.target_days
    for pr in log.patients:
        mark_critical(pr, world.flowchart)
    return log


# ============================================================================ outcomes (scoring side)

def _band(age) -> str:
    a = int(age or 0)
    return "<50" if a < 50 else "50-64" if a < 65 else "65-74" if a < 75 else "75+"


def _median(xs):
    return round(statistics.median(xs), 1) if xs else None


def _summary(prs: list, target: float) -> dict:
    n = len(prs)
    if not n:
        return {"n": 0}
    cancer = [p for p in prs if p.patient.cancer]
    rel = lambda p, x: None if x is None else x - p.patient.arrival
    treated = [p for p in cancer if p.outcome == "treatment"]
    tt = [rel(p, p.t_treatment) for p in treated]
    out = {
        "n": n, "cancers": len(cancer),
        "cancer_treated_share": round(len(treated) / len(cancer), 3) if cancer else None,
        "cancer_within_target_share": round(sum(1 for x in tt if x <= target) / len(cancer), 3) if cancer else None,
        "cancer_median_days_to_referral": _median([rel(p, p.t_referral) for p in cancer if p.t_referral is not None]),
        "cancer_median_days_to_diagnosis": _median([rel(p, p.t_diagnosis) for p in cancer if p.t_diagnosis is not None]),
        "cancer_median_days_to_treatment": _median(tt),
        "cancer_undiagnosed_at_horizon": sum(1 for p in cancer if p.outcome == "undiagnosed_at_horizon"),
        "cancer_left_with_symptoms": sum(1 for p in cancer if p.outcome == "left_with_symptoms"),
        "nurse_encounters_per_patient": round(sum(p.by_role.get("nurse", 0) for p in prs) / n, 2),
        "gp_encounters_per_patient": round(sum(p.by_role.get("gp", 0) for p in prs) / n, 2),
        "episodes_per_patient": round(sum(p.episode for p in prs) / n, 2),
        "tests_per_patient": round(sum(len(p.tests_ordered) for p in prs) / n, 2),
        "cost_per_patient_eur": round(sum(sum(p.cost.values()) for p in prs) / n, 1),
        "referral_share": round(sum(1 for p in prs if p.referrals) / n, 3),
        "noncancer_referred": sum(1 for p in prs if p.referrals and not p.patient.cancer),
        "treatments_per_patient": round(sum(len(p.treatments) for p in prs) / n, 2),
        "treatments_matching_share": (round(sum(t["matched"] for p in prs for t in p.treatments)
                                            / max(1, sum(len(p.treatments) for p in prs)), 3)),
        "undiagnosed_at_horizon": sum(1 for p in prs if p.outcome == "undiagnosed_at_horizon"),
        "outcomes": {},
    }
    for p in prs:
        out["outcomes"][p.outcome] = out["outcomes"].get(p.outcome, 0) + 1
    return out


GROUPS = {"age": lambda p: _band(p.record.background.get("age")),
          "sex": lambda p: p.record.background.get("sex"),
          "smoking": lambda p: p.record.background.get("smoking_status"),
          "region": lambda p: p.record.background.get("region")}


def outcomes(log: EncounterLog, warmup_days: float = 0.0) -> dict:
    """Overall and per patient group (age band, sex, smoking, region) summaries; patients arriving before
    ``warmup_days`` are left out."""
    prs = [p for p in log.patients if p.patient.arrival >= warmup_days]
    out = {"overall": _summary(prs, log.target_days), "by_group": {}}
    for g, key in GROUPS.items():
        vals: dict[str, list] = {}
        for p in prs:
            vals.setdefault(str(key(p)), []).append(p)
        out["by_group"][g] = {k: _summary(v, log.target_days) for k, v in sorted(vals.items())}
    out["fallback_reveals"] = sum(p.fallback_reveals for p in prs)
    return out


def format_outcomes(o: dict, target: float = 90) -> str:
    ov = o["overall"]
    lines = [
        f"patients {ov['n']}, cancers {ov['cancers']}: treated {ov['cancer_treated_share']}, within {target:g} d "
        f"{ov['cancer_within_target_share']}; median days to referral {ov['cancer_median_days_to_referral']}, "
        f"diagnosis {ov['cancer_median_days_to_diagnosis']}, treatment {ov['cancer_median_days_to_treatment']}",
        f"cancers undiagnosed at horizon {ov['cancer_undiagnosed_at_horizon']}, left with symptoms {ov['cancer_left_with_symptoms']}",
        f"per patient: nurse {ov['nurse_encounters_per_patient']}, GP {ov['gp_encounters_per_patient']}, episodes "
        f"{ov['episodes_per_patient']}, tests {ov['tests_per_patient']}, cost {ov['cost_per_patient_eur']} EUR, "
        f"treatments {ov['treatments_per_patient']} ({ov['treatments_matching_share']} matching the truth)",
        f"referred {ov['referral_share']} (non-cancer referred {ov['noncancer_referred']}); "
        f"undiagnosed at horizon (all) {ov['undiagnosed_at_horizon']}",
        "outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(ov["outcomes"].items())),
        "",
        f"{'group':<20}{'n':>6}{'cancers':>8}{'treated':>9}{'<=target':>9}{'med tx d':>9}{'GP/pt':>7}{'tests/pt':>9}{'EUR/pt':>8}",
    ]
    for g, rows in o["by_group"].items():
        for k, s in rows.items():
            if not s.get("n"):
                continue
            f = lambda x: "-" if x is None else f"{x:g}"
            lines.append(f"{g + ' ' + k:<20}{s['n']:>6}{s['cancers']:>8}{f(s['cancer_treated_share']):>9}"
                         f"{f(s['cancer_within_target_share']):>9}{f(s['cancer_median_days_to_treatment']):>9}"
                         f"{s['gp_encounters_per_patient']:>7}{s['tests_per_patient']:>9}{s['cost_per_patient_eur']:>8}")
    if o.get("fallback_reveals"):
        lines.append(f"\nnote: {o['fallback_reveals']} reveals used the single-state fallback (multi-state cards: WP-C8-2)")
    return "\n".join(lines)


# ============================================================================ CLI

def cli_run(a) -> None:
    """``python -m pathway_sim run <world.yaml> --flowchart encounter --n N --seed S [--out F]``."""
    import time
    t0 = time.time()
    world = load_world(a.scenario)
    n = a.n or int(world.raw.get("default_n", 2000))
    log = run_encounter(world, n, a.seed)
    o = outcomes(log)
    print(f"{world.id}: library {log.library_id} ({log.distinct_cards} distinct cards), care {world.care_path}, "
          f"policy {getattr(world.policy, 'model_id', '')}; {time.time() - t0:.1f} s")
    print(format_outcomes(o, world.target_days))
    util = {k: v.get("utilisation") for k, v in log.resources.items() if v.get("utilisation") is not None}
    if util:
        print("utilisation:", ", ".join(f"{k} {v:.0%}" for k, v in util.items()))
    w = world.policy.run_summary()
    if w:
        print("policy warnings:", w)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"run": log.to_dict(), "outcomes": o}))
        print("wrote", a.out)
