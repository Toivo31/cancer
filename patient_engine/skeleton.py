"""Card skeletons (G0), the library design and the error plan.

A skeleton is everything about one synthetic patient that is decided *before* anybody writes the
patient: the primary condition and its attributes, an optional co-existing illness, the visible
background, a one-phrase variation brief and the error plan (what each attempt of each test is
meant to do wrong, if anything). The reference generator (``patient_engine.reference``) and the
language-model authors (WP-C1-5) start from the same skeleton, so a library written by a model
and one written from the numbers share design, error rates and card ids.

    from patient_engine.catalogue import load_catalogue
    from patient_engine.skeleton import design_library, make_design, make_skeleton, settle_error_plan

    cat = load_catalogue("catalogue/_examples/tiny")
    skeletons = design_library(cat, counts=None, coexisting_rate=None, seed=7)    # default stratified design
    design = make_design(cat)                                    # the same design as an object
    sk = make_skeleton(cat, 17, design, seed=7)                  # card 17 of that design

Public API
    Skeleton, Design                         frozen dataclasses (``Skeleton.to_json`` / ``skeleton_from_json``)
    default_counts(catalogue)                at least 150 cards per condition, 300 for a cancer
    make_design(catalogue, counts, coexisting_rate)      stratified design (counts of cards per primary condition)
    proportional_design(n, coexisting_rate)              n cards, primary condition drawn by the catalogue's prevalence
    design_library(catalogue, counts, coexisting_rate, seed) -> list[Skeleton]
    make_skeleton(catalogue, index, design, seed) -> Skeleton
    settle_error_plan(catalogue, skeleton, findings) -> error plan for the card (``Hidden.error_plan`` shape)
    settle_attempt(...)                      one attempt: its planned outcomes and the values they imply
    design_table(skeletons) -> dict          counts by primary condition and by pair

Keyed random numbers (invariant I2). Every draw is ``pathway_sim.dists.uniform(seed, index, *key)``
with a key that names what is drawn (``("bg", ...)``, ``("var", state, variable, condition)``,
``("err", state, test, attempt, output)``, ...). A skeleton therefore never depends on how many other
skeletons exist. The one thing that does depend on the design is *which primary condition* card
``index`` gets in a stratified design: the strata are laid out and shuffled with keyed numbers
(``("design_shuffle",)``), so changing a count changes that assignment, but never a number inside a card.

The error plan, and why there are two of them
    The numbers a test is accurate by can depend on the patient's truth (sensitivity by lesion size,
    false alarms when a pneumonia is present), and the truth is written after the skeleton (by the
    model, or by the reference generator). So:

    * ``Skeleton.error_plan`` is the *nominal* plan: drawn at skeleton time with only the facts known
      then (condition, attributes, background). Leaves that read a finding use their base number.
    * ``settle_error_plan(catalogue, skeleton, findings)`` is the *settled* plan: the same keyed
      random numbers, now thresholded with every fact. This is the plan a card stores in
      ``hidden.error_plan`` and the one the result author must follow. Call it after the findings
      exist (G1) and before the results are written (G2).

    One keyed uniform ``u`` per (state, test, attempt, output) decides a binary output: with the
    sensitivity ``s`` and specificity ``c`` that apply, ``miss`` if ``u < 1 - s`` (only if the finding
    is true), ``false_alarm`` if ``u >= c`` (only if it is false), else ``correct``. A planned miss on a
    false finding is simply ``correct`` in the settled plan. Realised sensitivity and specificity are
    then exact in expectation because ``u`` is independent of the truth.
    Categorical: ``correct`` with the accuracy, else ``wrong`` (a different level, drawn uniformly
    among the others with a second keyed number). Continuous and size: the reported value is the truth
    plus ``error_sd * z`` with ``z = inv_cdf(u)``; the outcome is ``wrong`` when ``|z| >= 1.96`` (outside
    the stated error band), else ``correct``. A test with a ``nondiagnostic`` rate gives
    ``status: non_diagnostic`` (no values) for an attempt with probability that rate.
    With a co-existing illness the accuracy numbers are resolved under each active condition and the
    least favourable is used (lowest sensitivity, specificity and accuracy; largest error and
    non-diagnostic rate), so a pneumonia that raises false alarms or hides a lesion does so for the
    cancer patient too.

Standard library and ``pathway_sim`` only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from pathway_sim import expr as _expr
from pathway_sim.dists import sample, uniform

from .card import INITIAL_STATE, PlannedAttempt, Value
from .catalogue import Catalogue, Leaf, Test, TestOutput
from .population import get_model as _population_model
from .states import resolved_in_state, states_for

SKELETON_FORMAT = "skeleton/1"
OUTCOME_Z = 1.96                        # a measured value this many error SDs from the truth is `wrong`
MAX_BACKGROUND_TRIES = 200
DEFAULT_PER_CONDITION = 150
DEFAULT_PER_CANCER = 300

_N = NormalDist()

#: One short persona hint per skeleton (the variation brief). Neutral on purpose: no health, ethnicity,
#: religion or other sensitive trait; the language-model authors turn the phrase into a person.
PERSONAS = (
    "lives alone and tends to put off seeing a doctor",
    "busy carer for a relative, little time for appointments",
    "worries about health and asks many questions",
    "works shifts, hard to attend daytime appointments",
    "tends to play symptoms down",
    "retired, active, gives thorough and detailed answers",
    "recently moved to the area, no regular doctor yet",
    "works outdoors, notices changes late",
    "keeps a diary of symptoms and brings it along",
    "lives far from the health centre, travels by bus",
    "student-age caution: reads about symptoms online before visiting",
    "helps run a small family business, rarely takes time off",
)


# ============================================================================ types

@dataclass(frozen=True)
class Design:
    """The library design: how many cards of which primary condition.

    ``mode == "stratified"``: ``counts`` is ``((condition id, cards), ...)`` and ``n`` their sum.
    ``mode == "proportional"``: ``n`` cards whose primary condition is drawn with the catalogue's
    prevalence (given the card's background). ``coexisting_rate`` is None (use the catalogue's
    co-occurrence shares) or the share of cards of every primary that has co-occurrence entries that
    get a co-existing illness (which one: in proportion to the entries' shares)."""
    mode: str
    n: int
    counts: tuple[tuple[str, int], ...] = ()
    coexisting_rate: float | None = None

    def counts_dict(self) -> dict[str, int]:
        return dict(self.counts)


@dataclass(frozen=True)
class Skeleton:
    id: str
    index: int
    seed: int
    catalogue_id: str
    catalogue_hash: str
    primary: str
    attributes: dict[str, str]
    coexisting: str | None
    coexisting_attributes: dict[str, str]
    background: dict[str, Value]
    brief: str
    #: nominal error plan: state -> test id -> attempts (see the module docstring); ``None`` if not drawn
    error_plan: dict[str, dict[str, tuple[PlannedAttempt, ...]]] | None = None
    states: tuple[str, ...] = (INITIAL_STATE,)
    format: str = SKELETON_FORMAT

    @property
    def conditions(self) -> tuple[tuple[str, str, dict[str, str]], ...]:
        """Active conditions as ``(id, role, attributes)``, primary first."""
        out = [(self.primary, "primary", self.attributes)]
        if self.coexisting:
            out.append((self.coexisting, "coexisting", self.coexisting_attributes))
        return tuple(out)

    @property
    def condition_ids(self) -> tuple[str, ...]:
        return tuple(c for c, _, _ in self.conditions)

    def all_attributes(self) -> dict[str, str]:
        """Attributes of every active condition in one mapping (attribute names are unique in a catalogue)."""
        return {**self.coexisting_attributes, **self.attributes}

    def to_json(self) -> dict:
        return {
            "format": self.format, "id": self.id, "index": self.index, "seed": self.seed,
            "catalogue_id": self.catalogue_id, "catalogue_hash": self.catalogue_hash,
            "primary": self.primary, "attributes": dict(self.attributes),
            "coexisting": self.coexisting, "coexisting_attributes": dict(self.coexisting_attributes),
            "background": dict(self.background), "brief": self.brief, "states": list(self.states),
            "error_plan": None if self.error_plan is None else plan_to_json(self.error_plan),
        }


def plan_to_json(plan: Mapping[str, Mapping[str, Sequence[PlannedAttempt]]]) -> dict:
    return {s: {t: [{"status": p.status, "outputs": dict(p.outputs)} for p in ps] for t, ps in tp.items()}
            for s, tp in plan.items()}


def plan_from_json(d: Mapping[str, Any]) -> dict[str, dict[str, tuple[PlannedAttempt, ...]]]:
    return {s: {t: tuple(PlannedAttempt(p["status"], dict(p.get("outputs") or {})) for p in ps)
                for t, ps in tp.items()} for s, tp in d.items()}


def skeleton_from_json(d: Mapping[str, Any]) -> Skeleton:
    if d.get("format") != SKELETON_FORMAT:
        raise ValueError(f"not a {SKELETON_FORMAT} skeleton: format is {d.get('format')!r}")
    ep = d.get("error_plan")
    return Skeleton(
        id=d["id"], index=int(d["index"]), seed=int(d["seed"]), catalogue_id=d["catalogue_id"],
        catalogue_hash=d["catalogue_hash"], primary=d["primary"], attributes=dict(d.get("attributes") or {}),
        coexisting=d.get("coexisting"), coexisting_attributes=dict(d.get("coexisting_attributes") or {}),
        background=dict(d["background"]), brief=d["brief"], error_plan=None if ep is None else plan_from_json(ep),
        states=tuple(d.get("states") or (INITIAL_STATE,)), format=d["format"])


# ============================================================================ small helpers

def pick(weights: Mapping[str, float], u: float) -> str:
    """Inverse-CDF choice of a key from non-negative weights (normalised here)."""
    total = sum(weights.values())
    if total <= 0:
        keys = list(weights)
        return keys[min(int(u * len(keys)), len(keys) - 1)]
    acc = 0.0
    last = None
    for k, w in weights.items():
        last = k
        acc += w / total
        if u < acc:
            return k
    return last  # type: ignore[return-value]


def holds(expression: str | None, values: Mapping[str, Any]) -> bool:
    """Truth of a catalogue expression over ``values`` (None = always true)."""
    if expression is None:
        return True
    return bool(_expr.parse(expression).holds(values))


def finding_values(findings: Mapping[str, Any]) -> dict[str, Value]:
    """``{variable: value}`` from findings given as ``Finding`` objects or as plain values."""
    return {k: getattr(f, "value", f) for k, f in findings.items()}


def common_facts(skeleton: Skeleton, values: Mapping[str, Value] | None = None) -> dict[str, Any]:
    """Facts shared by all active conditions: background, attributes, and (when given) the non-null findings."""
    facts: dict[str, Any] = {**skeleton.background, **skeleton.all_attributes()}
    if values:
        facts.update({k: v for k, v in values.items() if v is not None})
    return facts


def illness_ids(catalogue: Catalogue, skeleton: "Skeleton") -> tuple[str, ...]:
    """The ordinary illnesses among the skeleton's conditions (class ``other_illness``): the ones that can
    resolve. A cancer never resolves by treatment (C8)."""
    return tuple(c for c in skeleton.condition_ids if catalogue.conditions[c].cls == "other_illness")


def active_conditions(catalogue: Catalogue, skeleton: "Skeleton", state: str) -> tuple[str, ...]:
    """Conditions still active in ``state``. When everything has resolved (a patient with an illness only)
    nothing is active and accuracy numbers resolve as for a patient without disease: under the catalogue's
    first ``healthy`` condition if it has one, else under a condition name that no ``by`` level matches."""
    resolved = resolved_in_state(state, illness_ids(catalogue, skeleton))
    active = tuple(c for c in skeleton.condition_ids if c not in resolved)
    if active:
        return active
    return (next((c for c, x in catalogue.conditions.items() if x.cls == "healthy"), "none"),)


def _resolve_worst(leaf: Leaf | None, conditions: Sequence[str], common: Mapping[str, Any], default: float,
                   worst: str) -> float:
    """``leaf`` resolved under each active condition; ``worst`` is ``min`` or ``max``."""
    if leaf is None:
        return default
    xs = [float(leaf.resolve({**common, "condition": c})) for c in conditions]
    return min(xs) if worst == "min" else max(xs)


def _truncated_normal(lo: float, hi: float, u: float) -> float:
    mu, sd = (lo + hi) / 2, (hi - lo) / 6 or 1.0
    a, b = _N.cdf((lo - mu) / sd), _N.cdf((hi - mu) / sd)
    return mu + sd * _N.inv_cdf(a + u * (b - a))


def _draw_background(catalogue: Catalogue, seed: int, index: int, k: int) -> dict[str, Value]:
    """One candidate background. With a population file (``populations/<catalogue id>.yaml``, see
    ``patient_engine/population.py``) age, sex, smoking status, pack-years and region follow it. Otherwise the
    default population model (``catalogue/1`` has none yet): a categorical
    field is uniform over its values, a binary one a fair coin, a continuous one a normal centred in its
    ``range`` (SD one sixth of the width) truncated to it (default range 0..100)."""
    bg: dict[str, Value] = {}
    model = _population_model(catalogue)
    if model is not None:        # populations/<catalogue id>.yaml: age, sex, smoking, pack-years, region
        bg = model.draw_background(seed, index, k, catalogue.background)
    for f in catalogue.background.values():
        if f.id in bg:
            continue
        u = uniform(seed, index, "bg", k, f.id)
        if f.type == "categorical":
            bg[f.id] = f.values[min(int(u * len(f.values)), len(f.values) - 1)]
        elif f.type == "binary":
            bg[f.id] = u < 0.5
        else:
            lo = 0.0 if f.range[0] is None else f.range[0]
            hi = 100.0 if f.range[1] is None else f.range[1]
            x = _truncated_normal(lo, hi, u)
            bg[f.id] = int(round(x)) if hi - lo >= 50 else round(x, 1)
    if model is None:
        _smoking_consistency(bg, catalogue, seed, index, k)
    return bg


# Pack-years given smoking status (assumption, not sourced): never-smokers have 0; former and current
# smokers draw from a log-normal with median 25 / 35 pack-years (geometric SD about 2), within the
# field's range. Without this, pack-years was drawn independently of smoking status (never-smokers
# with 150 pack-years; median about 100 across all cards).
_PACK_YEARS_MEDIAN = {"former": 25.0, "current": 35.0}
_PACK_YEARS_LOG_SD = 0.7


def _smoking_consistency(bg: dict, catalogue: Catalogue, seed: int, index: int, k: int) -> None:
    fields = catalogue.background
    if "pack_years" not in bg or "smoking_status" not in bg:
        return
    status = bg["smoking_status"]
    if status == "never":
        bg["pack_years"] = 0
        return
    median = _PACK_YEARS_MEDIAN.get(str(status))
    if median is None:
        return
    f = fields["pack_years"]
    lo = 0.0 if f.range[0] is None else f.range[0]
    hi = 100.0 if f.range[1] is None else f.range[1]
    u = min(max(uniform(seed, index, "bg", k, "pack_years_given_smoking"), 1e-9), 1 - 1e-9)
    x = math.exp(math.log(median) + _PACK_YEARS_LOG_SD * _N.inv_cdf(u))
    bg["pack_years"] = int(round(min(max(x, max(lo, 1.0)), hi)))


def _prevalence_shares(catalogue: Catalogue, bg: Mapping[str, Any]) -> dict[str, float]:
    """Weights of the conditions for a background: the catalogue's prevalence, and with a population model
    that prevalence carried by the age relative risks and renormalised (overall shares per smoking level stay)."""
    model = _population_model(catalogue)
    if model is not None and "age" in bg and "smoking_status" in bg:
        return model.condition_shares(bg)
    return {c: max(0.0, float(x.prevalence.resolve(bg))) for c, x in catalogue.conditions.items()}


def _leaf_bounds(leaf: Leaf) -> tuple[float, float]:
    """Smallest and largest number a ``value`` leaf can resolve to (base and every ``by`` level)."""
    nums = [float(leaf.params[leaf.kind])]

    def walk(by: Mapping | None) -> None:
        for levels in (by or {}).values():
            if not isinstance(levels, Mapping):
                continue
            for ov in levels.values():
                if isinstance(ov, Mapping):
                    if leaf.kind in ov:
                        nums.append(float(ov[leaf.kind]))
                    walk(ov.get("by"))
                elif isinstance(ov, (int, float)) and not isinstance(ov, bool):
                    nums.append(float(ov))
    walk(leaf.by)
    return min(nums), max(nums)


def _draw_primary_and_background(catalogue: Catalogue, design: Design, index: int, seed: int
                                 ) -> tuple[str, dict[str, Value]]:
    """The primary condition and a background that belong together (prevalence may read the background).

    Proportional: draw a background, then the condition with its resolved, normalised prevalences.
    Stratified: the condition is given; draw backgrounds until one is accepted with probability
    ``P(condition | background)`` over its upper bound (rejection sampling), so a condition's cards
    show the background mix the catalogue's prevalence implies (cancers skew to smokers)."""
    if design.mode == "proportional":
        bg = _draw_background(catalogue, seed, index, 0)
        shares = _prevalence_shares(catalogue, bg)
        return pick(shares, uniform(seed, index, "primary")), bg
    primary = _assignment(seed, design.counts)[index]
    leaf = catalogue.conditions[primary].prevalence
    model = _population_model(catalogue)
    if model is not None:
        top = model.top[primary]           # exact upper bound of P(condition | background)
    else:
        lows = sum(_leaf_bounds(x.prevalence)[0] for x in catalogue.conditions.values())
        top = min(1.0, _leaf_bounds(leaf)[1] / lows) if lows > 0 else 1.0
    bg: dict[str, Value] = {}
    for k in range(MAX_BACKGROUND_TRIES):
        bg = _draw_background(catalogue, seed, index, k)
        shares = _prevalence_shares(catalogue, bg)
        total = sum(shares.values())
        p = shares[primary] / total if total > 0 else 1.0 / len(shares)
        if top <= 0 or uniform(seed, index, "bg_accept", k) < p / top:
            break
    return primary, bg


@lru_cache(maxsize=16)
def _assignment(seed: int, counts: tuple[tuple[str, int], ...]) -> tuple[str, ...]:
    """The primary condition of every index of a stratified design: strata laid out in order, then
    shuffled (Fisher-Yates with keyed numbers) so any prefix of the library is already mixed."""
    items = [c for c, n in counts for _ in range(n)]
    for i in range(len(items) - 1, 0, -1):
        j = int(uniform(seed, i, "design_shuffle") * (i + 1))
        items[i], items[j] = items[j], items[i]
    return tuple(items)


def _check_attribute_dependencies(catalogue: Catalogue, condition: str) -> None:
    for a in catalogue.conditions[condition].attributes:
        reads = [d for d in catalogue.dependencies.get(f"attr:{condition}.{a}", ()) if d.startswith("var:")]
        if reads:
            raise ValueError(f"attribute {condition}.{a} reads variable(s) {sorted(reads)}; a skeleton draws "
                             "attributes before any finding exists, so it cannot be generated")


def _draw_attributes(catalogue: Catalogue, condition: str, bg: Mapping[str, Any], seed: int, index: int,
                     extra: Mapping[str, str] | None = None) -> dict[str, str]:
    _check_attribute_dependencies(catalogue, condition)
    cond = catalogue.conditions[condition]
    attrs: dict[str, str] = {}
    order = [n for n in catalogue.generation_order(condition) if n in cond.attributes]
    for name in order:
        facts = {**bg, **(extra or {}), **attrs, "condition": condition}
        weights = cond.attributes[name].resolve(facts)
        attrs[name] = pick(weights, uniform(seed, index, "attr", condition, name))
    return attrs


def _draw_coexisting(catalogue: Catalogue, primary: str, bg: Mapping[str, Any], attrs: Mapping[str, str],
                     rate: float | None, seed: int, index: int) -> str | None:
    pairs = [co for co in catalogue.cooccurring(primary) if co.coexisting != primary]
    if not pairs:
        return None
    facts = {**bg, **attrs, "condition": primary}
    shares = {co.coexisting: max(0.0, float(co.share.resolve(facts))) for co in pairs}
    p_any = min(1.0, sum(shares.values())) if rate is None else rate
    if uniform(seed, index, "coexisting") >= p_any:
        return None
    return pick(shares, uniform(seed, index, "coexisting_which"))


# ============================================================================ the error plan

def _err_u(seed: int, index: int, state: str, test: str, attempt: int, output: str) -> float:
    return uniform(seed, index, "err", state, test, attempt, output)


def _nd_u(seed: int, index: int, state: str, test: str, attempt: int) -> float:
    return uniform(seed, index, "nd", state, test, attempt)


def nondiagnostic_rate(test: Test, conditions: Sequence[str], common: Mapping[str, Any]) -> float:
    return _resolve_worst(test.nondiagnostic, conditions, common, 0.0, "max")


def _nominal_attempt(test: Test, k: int, conditions: Sequence[str], common: Mapping[str, Any], seed: int,
                     index: int, state: str) -> PlannedAttempt:
    if test.nondiagnostic is not None and \
            _nd_u(seed, index, state, test.id, k) < nondiagnostic_rate(test, conditions, common):
        return PlannedAttempt("non_diagnostic", {})
    outs: dict[str, str] = {}
    for o in test.outputs:
        u = _err_u(seed, index, state, test.id, k, o.id)
        if o.type == "binary":
            s = _resolve_worst(o.sensitivity, conditions, common, 1.0, "min")
            c = _resolve_worst(o.specificity, conditions, common, 1.0, "min")
            outs[o.id] = "miss" if u < 1 - s else "false_alarm" if u >= c else "correct"
        elif o.type == "categorical":
            a = _resolve_worst(o.accuracy, conditions, common, 1.0, "min")
            outs[o.id] = "correct" if u < a else "wrong"
        else:
            sd = _resolve_worst(o.error_sd, conditions, common, 0.0, "max")
            outs[o.id] = "wrong" if sd > 0 and abs(_N.inv_cdf(u)) >= OUTCOME_Z else "correct"
    return PlannedAttempt("ok", outs)


def nominal_error_plan(catalogue: Catalogue, skeleton: Skeleton) -> dict[str, dict[str, tuple[PlannedAttempt, ...]]]:
    """The plan from the facts known at skeleton time (condition, attributes, background), per state
    (accuracy numbers resolved under the conditions still active in that state)."""
    common = common_facts(skeleton)
    return {state: {t.id: tuple(_nominal_attempt(t, k, active_conditions(catalogue, skeleton, state), common,
                                                 skeleton.seed, skeleton.index, state)
                                for k in range(t.max_attempts))
                    for t in catalogue.tests.values()}
            for state in skeleton.states}


def _phantom_truth(catalogue: Catalogue, variable: str, skeleton: Skeleton, common: Mapping[str, Any],
                   state: str, key: tuple) -> Value:
    """A value for something a test reports although the patient has no such truth (the size of a lesion
    a false alarm "sees"): drawn from the variable's `default` entry (else the primary's) with a keyed number."""
    v = catalogue.variables[variable]
    leaf = v.given.get("default") or v.given_for(skeleton.primary)
    facts = {**common, "condition": skeleton.primary}
    u = uniform(skeleton.seed, skeleton.index, "phantom", state, *key)
    spec = leaf.resolve(facts)
    if v.type == "binary":
        return False
    if v.type == "categorical":
        return pick(spec, u)
    return _clamp(sample(spec, u), v.range, v.type)


def _clamp(x: float, rng: tuple[float | None, float | None], type_: str) -> float:
    lo, hi = rng
    if type_ == "size_mm" and lo is None:
        lo = 0.0
    if lo is not None:
        x = max(x, lo)
    if hi is not None:
        x = min(x, hi)
    return round(x, 1)


def settle_attempt(catalogue: Catalogue, test: Test, k: int, skeleton: Skeleton,
                   values: Mapping[str, Value], state: str = INITIAL_STATE
                   ) -> tuple[PlannedAttempt, dict[str, Value]]:
    """One attempt of one test given the patient's true ``values`` (variable id -> value).

    Returns ``(planned, reported)``: the settled plan of the attempt and the values it implies when
    followed literally (``{}`` if non-diagnostic; an output whose ``only_if`` is false is ``None``).
    The reference generator writes ``reported`` as the result; a language-model author is told
    ``planned`` and writes its own concrete result that fits it.

    ``k`` may be any whole number (not only below ``test.max_attempts``): attempt ``k`` depends on
    ``(seed, index, state, test, k)`` and the findings only, which is how the reveal handle draws fresh
    repeats. Accuracy numbers are resolved under the conditions still active in ``state``."""
    seed, index = skeleton.seed, skeleton.index
    conds = active_conditions(catalogue, skeleton, state)
    common = common_facts(skeleton, values)
    if test.nondiagnostic is not None and \
            _nd_u(seed, index, state, test.id, k) < nondiagnostic_rate(test, conds, common):
        return PlannedAttempt("non_diagnostic", {}), {}
    outcomes: dict[str, str] = {}
    reported: dict[str, Value] = {}
    for o in test.outputs:
        if not holds(o.only_if, reported):
            reported[o.id] = None
            outcomes[o.id] = "correct"
            continue
        truth = values.get(o.measures)
        u = _err_u(seed, index, state, test.id, k, o.id)
        if o.type == "binary":
            s = _resolve_worst(o.sensitivity, conds, common, 1.0, "min")
            c = _resolve_worst(o.specificity, conds, common, 1.0, "min")
            if bool(truth):
                miss = u < 1 - s
                outcomes[o.id], reported[o.id] = ("miss", False) if miss else ("correct", True)
            else:
                fa = u >= c
                outcomes[o.id], reported[o.id] = ("false_alarm", True) if fa else ("correct", False)
            continue
        if truth is None:
            if not o.only_if:
                # nothing exists and nothing the test itself reported says it does (review w8 M2: a non-cancer
                # patient's histology is null, not an invented cell type)
                reported[o.id] = None
                outcomes[o.id] = "correct"
                continue
            # reported although nothing exists, because this attempt's own result says it does (a false-alarm lesion's
            # size and location): invent one
            truth = _phantom_truth(catalogue, o.measures, skeleton, common, state, (test.id, k, o.id))
        if o.type == "categorical":
            a = _resolve_worst(o.accuracy, conds, common, 1.0, "min")
            levels = [x for x in (o.values or catalogue.variables[o.measures].values) if x != truth]
            if u < a or not levels:
                outcomes[o.id], reported[o.id] = "correct", truth
            else:
                u2 = uniform(seed, index, "err_level", state, test.id, k, o.id)
                outcomes[o.id], reported[o.id] = "wrong", levels[min(int(u2 * len(levels)), len(levels) - 1)]
        else:
            sd = _resolve_worst(o.error_sd, conds, common, 0.0, "max")
            z = _N.inv_cdf(u) if sd > 0 else 0.0
            x = float(truth) + sd * z
            outcomes[o.id] = "wrong" if abs(z) >= OUTCOME_Z else "correct"
            reported[o.id] = _clamp(x, catalogue.variables[o.measures].range, o.type)
    return PlannedAttempt("ok", outcomes), reported


def settle_error_plan(catalogue: Catalogue, skeleton: Skeleton, findings: Mapping[str, Any],
                      state: str = INITIAL_STATE) -> dict[str, dict[str, tuple[PlannedAttempt, ...]]]:
    """The settled error plan of one state for a patient whose true findings are ``findings`` (variable id
    -> ``Finding`` or plain value). Same shape as ``Hidden.error_plan`` for that state wrapped in ``{state: ...}``.
    See the module docstring: a planned miss on a false finding comes out as ``correct``."""
    values = finding_values(findings)
    return {state: {t.id: tuple(settle_attempt(catalogue, t, k, skeleton, values, state)[0]
                                for k in range(t.max_attempts))
                    for t in catalogue.tests.values()}}


# ============================================================================ designs and skeletons

def default_counts(catalogue: Catalogue) -> dict[str, int]:
    """A first stratified design: 150 cards per condition and 300 for each cancer."""
    return {c: DEFAULT_PER_CANCER if x.cls == "cancer" else DEFAULT_PER_CONDITION
            for c, x in catalogue.conditions.items()}


def _check_rate(rate: float | None) -> float | None:
    if rate is not None and not 0.0 <= float(rate) <= 1.0:
        raise ValueError(f"coexisting_rate must be between 0 and 1, got {rate!r}")
    return None if rate is None else float(rate)


def make_design(catalogue: Catalogue, counts: Mapping[str, int] | None = None,
                coexisting_rate: float | None = None) -> Design:
    """A stratified design. ``counts`` maps primary condition ids to numbers of cards (default
    ``default_counts``); conditions left out get no cards."""
    counts = dict(default_counts(catalogue) if counts is None else counts)
    unknown = [c for c in counts if c not in catalogue.conditions]
    if unknown:
        raise ValueError(f"counts name unknown condition(s) {unknown}; the catalogue has {list(catalogue.conditions)}")
    if any(int(n) < 0 for n in counts.values()):
        raise ValueError("counts must not be negative")
    items = tuple((c, int(n)) for c, n in counts.items() if int(n) > 0)
    if not items:
        raise ValueError("the design has no cards")
    return Design("stratified", sum(n for _, n in items), items, _check_rate(coexisting_rate))


def proportional_design(n: int, coexisting_rate: float | None = None) -> Design:
    """``n`` cards whose primary condition follows the catalogue's prevalence."""
    if n < 1:
        raise ValueError("n must be at least 1")
    return Design("proportional", int(n), (), _check_rate(coexisting_rate))


def make_skeleton(catalogue: Catalogue, index: int, design: Design, seed: int, *, plan: bool = True) -> Skeleton:
    """Card ``index`` of ``design``. Depends only on ``(catalogue, design, seed, index)``; the numbers
    inside it never depend on how many other skeletons exist. ``plan=False`` leaves out the nominal
    error plan (``error_plan`` is None), which is faster when only the design is wanted."""
    if not 0 <= index < design.n:
        raise IndexError(f"index {index} is outside the design (0..{design.n - 1})")
    primary, bg = _draw_primary_and_background(catalogue, design, index, seed)
    attrs = _draw_attributes(catalogue, primary, bg, seed, index)
    co = _draw_coexisting(catalogue, primary, bg, attrs, design.coexisting_rate, seed, index)
    co_attrs = _draw_attributes(catalogue, co, bg, seed, index, extra=attrs) if co else {}
    brief = PERSONAS[min(int(uniform(seed, index, "brief") * len(PERSONAS)), len(PERSONAS) - 1)]
    sk = Skeleton(id=f"{catalogue.id}.s{seed}:{index:06d}", index=index, seed=seed, catalogue_id=catalogue.id,
                  catalogue_hash=catalogue.version_hash, primary=primary, attributes=attrs, coexisting=co,
                  coexisting_attributes=co_attrs, background=bg, brief=brief)
    sk = Skeleton(**{**sk.__dict__, "states": states_for(illness_ids(catalogue, sk))})
    if plan:
        sk = Skeleton(**{**sk.__dict__, "error_plan": nominal_error_plan(catalogue, sk)})
    return sk


def design_library(catalogue: Catalogue, counts: Mapping[str, int] | None = None,
                   coexisting_rate: float | None = None, seed: int = 0) -> list[Skeleton]:
    """All skeletons of a stratified design (``counts`` default: ``default_counts``)."""
    design = make_design(catalogue, counts, coexisting_rate)
    return [make_skeleton(catalogue, i, design, seed) for i in range(design.n)]


def design_table(skeletons: Sequence[Skeleton]) -> dict[str, Any]:
    """Counts by primary condition, by (primary, coexisting) pair and in total."""
    by_primary: dict[str, int] = {}
    pairs: dict[str, int] = {}
    for s in skeletons:
        by_primary[s.primary] = by_primary.get(s.primary, 0) + 1
        if s.coexisting:
            key = f"{s.primary}+{s.coexisting}"
            pairs[key] = pairs.get(key, 0) + 1
    return {"n": len(skeletons), "by_primary": dict(sorted(by_primary.items())),
            "pairs": dict(sorted(pairs.items())), "with_coexisting": sum(pairs.values())}
