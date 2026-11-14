"""The reference generator: a valid ``card/1`` card straight from the catalogue's numbers, no network.

    from patient_engine.catalogue import load_catalogue
    from patient_engine.skeleton import make_design, make_skeleton
    from patient_engine.reference import generate_reference

    cat = load_catalogue("catalogue/_examples/tiny")
    sk = make_skeleton(cat, 17, make_design(cat), seed=7)
    card = generate_reference(cat, sk)                 # deterministic in (catalogue, skeleton)

It is the baseline and the test-fixture generator. The language-model authors (WP-C1-5) replace the
"write" steps (findings, results, texts) and keep the skeleton and the settled error plan, so a model
library and a reference library of the same design differ only in who wrote the content.

Steps, all with keyed random numbers ``uniform(seed, index, *key)`` (see ``skeleton`` for the keys):

1. Findings. Every variable of ``catalogue.generation_order(primary)`` is drawn from
   ``given_for(condition).resolve(facts)`` with ``facts = {condition, background, attributes, findings so far}``.
   With a co-existing illness each active condition is drawn separately and the results are combined:
   * binary: present if any active condition with its own ``given`` entry draws true, or the ``default``
     entry (a background rate, drawn once, only when some active condition has no own entry) does;
     ``caused_by`` lists the conditions with an own entry that drew true, and is empty when only the
     background rate did;
   * categorical: the first active condition (primary first) with an own entry decides, else ``default``;
   * continuous and size: one value per own entry; with several, the one farthest from the ``default``
     distribution's median in units of its 10-90 spread wins (a pneumonia's high CRP beats a cancer's
     near-normal one; a cancer's low haemoglobin beats a pneumonia's normal one); no own entry: ``default``.
   A variable with ``only_if`` that does not hold is ``None`` with no cause.
2. The settled error plan (``skeleton.settle_attempt``) for every test and attempt, giving the result
   values and the plan stored in ``hidden.error_plan`` (``provenance.error_source == "guided"``).
3. Template texts: a report per attempt, the presenting complaint, one patient account and one GP
   note. They are short and say they are synthetic. Notes mention only what they reveal.

States (C8). A card has one state per combination of resolved ordinary illnesses (``skeleton.states``,
``patient_engine.states``). Findings, the presenting complaint, every test's attempts, the error plan and
two notes are written for each state; the keyed numbers include the state. In a resolved state the
findings caused only by a resolved illness are redrawn without it (``draw_findings``), the rest keep their
values, and test accuracy is resolved under the conditions still active.

Every test has ``max_attempts`` attempts. Attempt ``k`` of a test is a function of ``(seed, index, test,
k)`` only, so raising ``max_attempts`` never changes an earlier attempt (I3 in spirit).
Attempts of one test are independent given the patient (no persistence of a missed lesion across
repeats), as in ``pathway_sim.patients``.
"""

from __future__ import annotations

from typing import Iterator, Mapping, Sequence

from pathway_sim.dists import sample, uniform

from .card import (Attempt, Card, ConditionTruth, Finding, Hidden, Note, Presenting, Provenance, INITIAL_STATE,
                   Value)
from .catalogue import Catalogue, Leaf, Test, Variable
from .skeleton import (Design, Skeleton, active_conditions, common_facts, finding_values, holds, illness_ids,
                       make_skeleton, pick, settle_attempt)
from .states import resolved_in_state

#: share of true symptoms the patient mentions at first contact (at least one is always mentioned)
REPORT_SHARE = 0.75


# ============================================================================ findings

def _clamp_round(x: float, v: Variable) -> float:
    lo, hi = v.range
    if v.type == "size_mm" and lo is None:
        lo = 0.0
    if lo is not None:
        x = max(x, lo)
    if hi is not None:
        x = min(x, hi)
    return round(x, 1)


def _spread(default: Leaf, facts: Mapping, ) -> tuple[float, float]:
    spec = default.resolve(facts)
    lo, mid, hi = sample(spec, 0.1), sample(spec, 0.5), sample(spec, 0.9)
    return mid, (abs(hi - lo) or 1.0)


def _draw_one(catalogue: Catalogue, skeleton: Skeleton, name: str, v: Variable, active: Sequence[str],
              values: Mapping[str, Value], state: str, *, background_only: bool = False) -> Finding:
    """One variable drawn under the conditions in ``active`` (keyed numbers include ``state``).
    ``background_only``: a binary finding draws only its background rate, never its own causes (used when a
    resolved illness's finding is redrawn: no new symptom may appear because a state changed)."""
    seed, index = skeleton.seed, skeleton.index
    common = common_facts(skeleton, values)
    own = [(c, v.given[c]) for c in active if c in v.given]
    default = v.given.get("default")
    lacks_own = len(own) < len(active) and default is not None

    def u(who: str) -> float:
        return uniform(seed, index, "var", state, name, who)

    if v.type == "binary":
        causes = [] if background_only else [c for c, lf in own if u(c) < lf.resolve({**common, "condition": c})]
        base = lacks_own and u("default") < default.resolve({**common, "condition": skeleton.primary})
        return Finding(bool(causes) or bool(base), tuple(causes))
    if v.type == "categorical":
        if own:
            c, lf = own[0]
            return Finding(pick(lf.resolve({**common, "condition": c}), u(c)), (c,))
        lf = default or v.given_for(skeleton.primary)           # nothing active has an entry: the resolved illness's
        return Finding(pick(lf.resolve({**common, "condition": skeleton.primary}), u("default")), ())
    if own:
        cands = [(sample(lf.resolve({**common, "condition": c}), u(c)), c) for c, lf in own]
        if len(cands) > 1 and default is not None:
            mid, spread = _spread(default, {**common, "condition": skeleton.primary})
            cands.sort(key=lambda t: -abs(t[0] - mid) / spread)
        x, c = cands[0]
        return Finding(_clamp_round(x, v), (c,))
    lf = default or v.given_for(skeleton.primary)
    x = sample(lf.resolve({**common, "condition": skeleton.primary}), u("default"))
    return Finding(_clamp_round(x, v), ())


def draw_findings(catalogue: Catalogue, skeleton: Skeleton, state: str = INITIAL_STATE) -> dict[str, Finding]:
    """The patient's true value of every variable in ``state``, with the conditions that cause it.

    ``all_active`` is drawn as in the module docstring. A resolved state (``<illness>_resolved``,
    ``all_resolved``) starts from the ``all_active`` findings and changes only what the resolved illness
    explained (C8 rule 3):

    * a finding with no cause, or with a cause that is still active, keeps its value (``caused_by`` loses the
      resolved conditions);
    * a finding caused only by resolved conditions is redrawn under the conditions still active, with keyed
      numbers that include the state: a binary one is then true only by the background rate (a symptom never
      appears because the state changed), a categorical or measured one takes the remaining conditions'
      entry or the ``default`` (CRP falls back to normal);
    * a finding whose ``only_if`` stops holding becomes ``None``; one whose ``only_if`` starts holding is drawn."""
    seed, index = skeleton.seed, skeleton.index
    if state == INITIAL_STATE:
        active = skeleton.condition_ids
        base: Mapping[str, Finding] | None = None
    else:
        base = draw_findings(catalogue, skeleton, INITIAL_STATE)
        resolved = resolved_in_state(state, illness_ids(catalogue, skeleton))
        active = tuple(c for c in skeleton.condition_ids if c not in resolved)
    values: dict[str, Value] = {}
    findings: dict[str, Finding] = {}
    for name in catalogue.generation_order(skeleton.primary):
        v = catalogue.variables.get(name)
        if v is None:                                           # an attribute: drawn in the skeleton
            continue
        if not holds(v.only_if, values):
            values[name] = None
            findings[name] = Finding(None, ())
            continue
        if base is None:
            f = _draw_one(catalogue, skeleton, name, v, active, values, state)
        else:
            b = base[name]
            gone = tuple(c for c in b.caused_by if c not in active)
            if b.value is not None and not (b.caused_by and len(gone) == len(b.caused_by)):
                f = Finding(b.value, tuple(c for c in b.caused_by if c in active))
            else:
                f = _draw_one(catalogue, skeleton, name, v, active, values, state, background_only=True)
        values[name] = f.value
        findings[name] = f
    return findings


# ============================================================================ texts

def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:]


def _show(value: Value, unit: str | None = None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, float):
        return f"{value:g}" + (f" {unit}" if unit else "")
    return str(value)


def report_text(test: Test, status: str, values: Mapping[str, Value]) -> str:
    """A short template report, marked synthetic."""
    if status == "non_diagnostic":
        return f"{test.label} (synthetic report): no usable result (non-diagnostic); repeat if still indicated."
    def part(o):
        name, v = o.id.replace('_', ' '), values[o.id]
        if isinstance(v, bool):                     # "no nodule seen" reads as a negation; "nodule seen no" did not
            return name if v else f"no {name}"
        return f"{name} {_show(v, o.unit)}"
    parts = [part(o) for o in test.outputs if values.get(o.id) is not None]
    return f"{test.label} (synthetic report): " + "; ".join(parts) + "."


def _presenting(catalogue: Catalogue, skeleton: Skeleton, findings: Mapping[str, Finding], state: str
                ) -> Presenting:
    symptoms = [vid for vid, v in catalogue.variables.items() if v.kind == "symptom" and findings[vid].value is True]
    reported = [vid for vid in symptoms
                if uniform(skeleton.seed, skeleton.index, "reports", state, vid) < REPORT_SHARE]
    if symptoms and not reported:
        reported = [symptoms[0]]
    if not reported:
        return Presenting((), "Synthetic patient with no particular complaint; attends for a check-up.")
    labels = "; ".join(_lower_first(catalogue.variables[v].label) for v in reported)
    return Presenting(tuple(reported), f"Synthetic complaint: {labels}.")


def _notes(catalogue: Catalogue, skeleton: Skeleton, presenting: Presenting, observations: Mapping[str, tuple],
           state: str, first_id: int = 1) -> tuple[Note, ...]:
    bg = ", ".join(f"{k} {_show(v)}" for k, v in skeleton.background.items())
    account = Note(f"n{first_id}", "patient_account", state,
                   f"Synthetic patient account ({skeleton.brief}). Background: {bg}. {presenting.text}",
                   presenting.reported)
    imaging = [t for t in catalogue.tests.values() if t.category == "imaging"]
    t = (imaging or list(catalogue.tests.values()))[0]
    gp = Note(f"n{first_id + 1}", "gp_note", state, f"Synthetic GP note. {observations[t.id][0].report}", (t.id,))
    return (account, gp)


# ============================================================================ the card

def generate_reference(catalogue: Catalogue, skeleton: Skeleton, seed: int | None = None) -> Card:
    """The reference card for ``skeleton``. ``seed`` defaults to the skeleton's own; passing another
    one raises, because the skeleton's keyed numbers (and its card id) belong to its seed."""
    if seed is not None and seed != skeleton.seed:
        raise ValueError(f"seed {seed} differs from the skeleton's seed {skeleton.seed}")
    if skeleton.catalogue_id != catalogue.id:
        raise ValueError(f"skeleton is for catalogue {skeleton.catalogue_id!r}, not {catalogue.id!r}")
    plan: dict[str, dict[str, tuple]] = {}
    obs: dict[str, dict[str, tuple[Attempt, ...]]] = {}
    all_findings: dict[str, dict[str, Finding]] = {}
    presenting: dict[str, Presenting] = {}
    for state in skeleton.states:
        findings = draw_findings(catalogue, skeleton, state)
        values = finding_values(findings)
        splan: dict[str, tuple] = {}
        sobs: dict[str, tuple[Attempt, ...]] = {}
        for t in catalogue.tests.values():
            planned, attempts = [], []
            for k in range(t.max_attempts):
                p, reported = settle_attempt(catalogue, t, k, skeleton, values, state)
                planned.append(p)
                attempts.append(Attempt(p.status, reported, report_text(t, p.status, reported)))
            splan[t.id], sobs[t.id] = tuple(planned), tuple(attempts)
        all_findings[state], plan[state], obs[state] = findings, splan, sobs
        presenting[state] = _presenting(catalogue, skeleton, findings, state)
    conditions = tuple(ConditionTruth(c, role, dict(a)) for c, role, a in skeleton.conditions)
    notes: list[Note] = []
    for i, state in enumerate(skeleton.states):
        notes.extend(_notes(catalogue, skeleton, presenting[state], obs[state], state, 2 * i + 1))
    return Card(
        id=skeleton.id,
        background=dict(skeleton.background),
        states=skeleton.states,
        presenting=presenting,
        hidden=Hidden(conditions=conditions, findings=all_findings, error_plan=plan),
        observations=obs,
        notes=tuple(notes),
        provenance=Provenance(library=None, catalogue_id=catalogue.id, catalogue_hash=catalogue.version_hash,
                              generator="reference", model=None, prompts={}, error_source="guided",
                              validation={}),
    )


def reference_cards(catalogue: Catalogue, design: Design, seed: int) -> Iterator[Card]:
    """Cards ``0..design.n-1`` of ``design``, one at a time (nothing is kept)."""
    for i in range(design.n):
        yield generate_reference(catalogue, make_skeleton(catalogue, i, design, seed, plan=False))
