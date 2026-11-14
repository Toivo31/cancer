"""The patient card (``card/1``) and the library and cohort shapes (``library/1``, ``cohort/1``).

A card is one synthetic patient: what is visible about them, what is hidden, and the result every
test of the catalogue would give, per state and attempt. JSON shape (field order as written)::

    {"format": "card/1", "id": "L_9c1e:000217",
     "background": {"age": 67, "sex": "f", "smoking_status": "former", ...},   # catalogue `background`
     "states": ["all_active"],                                   # first state = state at first contact
     "presenting": {"all_active": {"reported": ["cough_3wk"], "text": "Cough for a month."}},
     "hidden": {
        "conditions": [{"id": "lung_cancer", "role": "primary", "attributes": {"stage": "II", ...}}],
        "findings": {"all_active": {"cough_3wk": {"value": true, "caused_by": ["lung_cancer"]}, ...}},
        "error_plan": null | {"all_active": {"chest_xray": [{"status": "ok", "outputs": {"abnormal": "miss"}}]}}},
     "observations": {"all_active": {"chest_xray": [
        {"status": "ok", "values": {"abnormal": false, "consolidation": false}, "report": "No focal lesion."}]}},
     "notes": [{"id": "n1", "kind": "patient_account", "state": "all_active", "text": "...",
                "mentions": ["cough_3wk", "chest_xray.abnormal"]}],
     "provenance": {"library": null, "catalogue_id": "tiny", "catalogue_hash": "…", "generator": "reference",
                    "model": null, "prompts": {}, "error_source": "guided", "validation": {}}}

Visibility (invariant I1). ``Card`` holds everything and is hidden-side. Code on the revealed side
(the simulation's decision layer, guards, the optimiser, notes shown before their facts) gets only
the revealed types below: ``PublicView``, ``RevealedObservation``, ``RevealedNote`` and
``Presenting``. None of them has a field that can hold a condition, a finding or a cause; the test
``tests/test_pe_contract.py::test_i1_*`` fails if one is added. Building a ``PublicView`` from a card
(the reveal handle) is WP-C1-6's job.

Keys. Variable ids, test ids, output ids, condition ids and attribute names come from the
catalogue (``catalogue/README.md``). A note's ``mentions`` names what the note may reveal: a
variable id (a finding), a test id (the whole result) or ``<test id>.<output id>``.

Standard library only. The dataclasses are frozen; mappings inside them are plain dicts (treat them
as read-only). ``card_from_json`` / ``card_to_json`` round-trip exactly (``card_to_json(card_from_json(x)) == x``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Union

CARD_FORMAT = "card/1"
LIBRARY_FORMAT = "library/1"
COHORT_FORMAT = "cohort/1"

#: The state every card has; the Sunday slice uses only this one (decision D40 adds more later).
INITIAL_STATE = "all_active"

#: A value on a card: an output of a test, a finding, a background field. ``None`` = not applicable
#: (for example the size of a lesion that is not there).
Value = Union[bool, int, float, str, None]

ROLES = ("primary", "coexisting")
STATUSES = ("ok", "non_diagnostic")
NOTE_KINDS = ("patient_account", "nurse_note", "gp_note", "referral_letter", "other")
GENERATORS = ("reference", "llm")
ERROR_SOURCES = ("guided", "free")
#: Planned outcome of one output of one attempt in ``guided`` mode. ``wrong`` = a categorical or
#: measured output reported differently from the truth beyond its stated error.
OUTCOMES = ("correct", "miss", "false_alarm", "wrong")

#: Field names that belong to the hidden section. No revealed-side type may have a field with one of
#: these names (checked by the I1 test).
HIDDEN_FIELD_NAMES = frozenset({"hidden", "conditions", "findings", "caused_by", "error_plan", "truth"})


# ============================================================================ hidden side

@dataclass(frozen=True)
class ConditionTruth:
    """One condition the patient truly has. Exactly one has ``role == "primary"``."""
    id: str
    role: Literal["primary", "coexisting"]
    attributes: dict[str, str] = field(default_factory=dict)     # attribute name -> level (catalogue)


@dataclass(frozen=True)
class Finding:
    """The true value of one hidden variable in one state, with the conditions that cause it.
    ``caused_by`` is empty when no condition explains it (a smoker's cough without disease)."""
    value: Value
    caused_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlannedAttempt:
    """``guided`` mode: what the engine decided this attempt should be before the model wrote it."""
    status: Literal["ok", "non_diagnostic"]
    outputs: dict[str, str] = field(default_factory=dict)        # output id -> one of OUTCOMES


@dataclass(frozen=True)
class Hidden:
    conditions: tuple[ConditionTruth, ...]
    findings: dict[str, dict[str, Finding]]                      # state -> variable id -> finding
    error_plan: dict[str, dict[str, tuple[PlannedAttempt, ...]]] | None = None   # state -> test -> attempts

    @property
    def primary(self) -> ConditionTruth:
        return next(c for c in self.conditions if c.role == "primary")


@dataclass(frozen=True)
class Attempt:
    """The result one attempt of one test gives in one state. ``values`` has every output of the
    test when ``status == "ok"`` (an output may be ``None`` when its ``only_if`` is false) and is
    empty when ``status == "non_diagnostic"``."""
    status: Literal["ok", "non_diagnostic"]
    values: dict[str, Value]
    report: str


@dataclass(frozen=True)
class Note:
    """Readable text tied to the facts it may reveal (``mentions``). Shown only after every
    mentioned fact is revealed; then it becomes a ``RevealedNote`` (no ``mentions``)."""
    id: str
    kind: str                                                    # one of NOTE_KINDS
    state: str
    text: str
    mentions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Provenance:
    library: str | None                                          # library id, None before it is stored
    catalogue_id: str
    catalogue_hash: str
    generator: str                                               # one of GENERATORS
    model: str | None = None
    prompts: dict[str, str] = field(default_factory=dict)        # role -> prompt version, e.g. {"patient": "g1@1"}
    error_source: str | None = None                              # one of ERROR_SOURCES
    validation: dict[str, Any] = field(default_factory=dict)     # validator summary, e.g. {"ok": true, "repairs": 0}


# ============================================================================ revealed side (I1)

@dataclass(frozen=True)
class Presenting:
    """What the patient reports at first contact in a state: variable ids they mention, and the
    complaint in their words. Visible from first contact."""
    reported: tuple[str, ...] = ()
    text: str | None = None


@dataclass(frozen=True)
class RevealedObservation:
    """One revealed (test, attempt) in a state. Carries the test's outputs and report only."""
    test: str
    attempt: int                                                 # 0-based
    state: str
    status: Literal["ok", "non_diagnostic"]
    values: dict[str, Value]
    report: str


@dataclass(frozen=True)
class RevealedNote:
    id: str
    kind: str
    text: str


@dataclass(frozen=True)
class PublicView:
    """Everything the revealed side may know about a patient at one moment."""
    card_id: str
    state: str
    background: dict[str, Value]
    presenting: Presenting
    observations: tuple[RevealedObservation, ...] = ()
    notes: tuple[RevealedNote, ...] = ()


#: Every type the revealed side may hold. The I1 test walks these.
PUBLIC_TYPES = (PublicView, RevealedObservation, RevealedNote, Presenting)


# ============================================================================ the card

@dataclass(frozen=True)
class Card:
    id: str
    background: dict[str, Value]
    states: tuple[str, ...]
    presenting: dict[str, Presenting]                            # state -> presenting
    hidden: Hidden
    observations: dict[str, dict[str, tuple[Attempt, ...]]]      # state -> test id -> attempts
    notes: tuple[Note, ...]
    provenance: Provenance
    format: str = CARD_FORMAT

    @property
    def primary_condition(self) -> str:
        return self.hidden.primary.id

    def attempt(self, test: str, attempt: int = 0, state: str | None = None) -> Attempt:
        return self.observations[state or self.states[0]][test][attempt]


# ============================================================================ JSON

def _attempt_to_json(a: Attempt) -> dict:
    return {"status": a.status, "values": dict(a.values), "report": a.report}


def _planned_to_json(p: PlannedAttempt) -> dict:
    return {"status": p.status, "outputs": dict(p.outputs)}


def card_to_json(card: Card) -> dict:
    """The card as a JSON-ready dict (lists, not tuples). Inverse of ``card_from_json``."""
    h = card.hidden
    hidden: dict[str, Any] = {
        "conditions": [{"id": c.id, "role": c.role, "attributes": dict(c.attributes)} for c in h.conditions],
        "findings": {s: {v: {"value": f.value, "caused_by": list(f.caused_by)} for v, f in fs.items()}
                     for s, fs in h.findings.items()},
        "error_plan": None if h.error_plan is None else
        {s: {t: [_planned_to_json(p) for p in ps] for t, ps in tp.items()} for s, tp in h.error_plan.items()},
    }
    return {
        "format": card.format,
        "id": card.id,
        "background": dict(card.background),
        "states": list(card.states),
        "presenting": {s: {"reported": list(p.reported), "text": p.text} for s, p in card.presenting.items()},
        "hidden": hidden,
        "observations": {s: {t: [_attempt_to_json(a) for a in atts] for t, atts in ts.items()}
                         for s, ts in card.observations.items()},
        "notes": [{"id": n.id, "kind": n.kind, "state": n.state, "text": n.text, "mentions": list(n.mentions)}
                  for n in card.notes],
        "provenance": {
            "library": card.provenance.library, "catalogue_id": card.provenance.catalogue_id,
            "catalogue_hash": card.provenance.catalogue_hash, "generator": card.provenance.generator,
            "model": card.provenance.model, "prompts": dict(card.provenance.prompts),
            "error_source": card.provenance.error_source, "validation": dict(card.provenance.validation),
        },
    }


def card_from_json(d: Mapping[str, Any]) -> Card:
    """Build a ``Card`` from its JSON dict. Checks the shape only as far as it needs to build the
    types (raises ``KeyError``/``TypeError``/``ValueError``); check a card against its catalogue with
    ``card_schema_problems`` first."""
    if d.get("format") != CARD_FORMAT:
        raise ValueError(f"not a {CARD_FORMAT} card: format is {d.get('format')!r}")
    h = d["hidden"]
    ep = h.get("error_plan")
    hidden = Hidden(
        conditions=tuple(ConditionTruth(c["id"], c["role"], dict(c.get("attributes") or {})) for c in h["conditions"]),
        findings={s: {v: Finding(f["value"], tuple(f.get("caused_by") or ())) for v, f in fs.items()}
                  for s, fs in h["findings"].items()},
        error_plan=None if ep is None else
        {s: {t: tuple(PlannedAttempt(p["status"], dict(p.get("outputs") or {})) for p in ps) for t, ps in tp.items()}
         for s, tp in ep.items()},
    )
    p = d["provenance"]
    return Card(
        id=d["id"],
        background=dict(d["background"]),
        states=tuple(d["states"]),
        presenting={s: Presenting(tuple(x.get("reported") or ()), x.get("text")) for s, x in d["presenting"].items()},
        hidden=hidden,
        observations={s: {t: tuple(Attempt(a["status"], dict(a["values"]), a["report"]) for a in atts)
                          for t, atts in ts.items()} for s, ts in d["observations"].items()},
        notes=tuple(Note(n["id"], n["kind"], n["state"], n["text"], tuple(n.get("mentions") or ()))
                    for n in d.get("notes") or ()),
        provenance=Provenance(
            library=p.get("library"), catalogue_id=p["catalogue_id"], catalogue_hash=p["catalogue_hash"],
            generator=p["generator"], model=p.get("model"), prompts=dict(p.get("prompts") or {}),
            error_source=p.get("error_source"), validation=dict(p.get("validation") or {}),
        ),
        format=d["format"],
    )


def card_schema(catalogue) -> dict:
    """JSON Schema (draft 2020-12) of a complete card for ``catalogue``. See ``patient_engine.schema``."""
    from .schema import card_schema as _card_schema
    return _card_schema(catalogue)


def card_schema_problems(data: Any, catalogue) -> list:
    """Schema problems of a card dict against ``card_schema(catalogue)`` (list of ``Problem``;
    empty = valid). Semantic checks (findings consistent with conditions, misses that do not show
    the finding) are the card validator's job (WP-C1-4)."""
    from .schema import card_schema as _card_schema, schema_problems
    return schema_problems(data, _card_schema(catalogue))


# ============================================================================ library/1, cohort/1 (shapes only)

@dataclass(frozen=True)
class LibraryManifest:
    """``library/1`` manifest: an immutable, stored set of validated cards. ``id`` is a content hash
    of the cards (computed by the store, WP-C1-6). Storage layout is WP-C1-6's."""
    id: str
    catalogue_id: str
    catalogue_hash: str
    generator: str                                               # one of GENERATORS
    model: str | None
    prompts: dict[str, str]                                      # role -> prompt version
    error_source: str | None                                     # one of ERROR_SOURCES
    card_count_by_condition: dict[str, int]                      # primary condition id -> number of cards
    created: str                                                 # ISO 8601 UTC, e.g. "2026-11-14T15:00:00Z"
    format: str = LIBRARY_FORMAT

    @property
    def n_cards(self) -> int:
        return sum(self.card_count_by_condition.values())

    def to_json(self) -> dict:
        return {"format": self.format, "id": self.id, "catalogue_id": self.catalogue_id,
                "catalogue_hash": self.catalogue_hash, "generator": self.generator, "model": self.model,
                "prompts": dict(self.prompts), "error_source": self.error_source,
                "card_count_by_condition": dict(self.card_count_by_condition), "created": self.created}

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "LibraryManifest":
        if d.get("format") != LIBRARY_FORMAT:
            raise ValueError(f"not a {LIBRARY_FORMAT} manifest: format is {d.get('format')!r}")
        return cls(id=d["id"], catalogue_id=d["catalogue_id"], catalogue_hash=d["catalogue_hash"],
                   generator=d["generator"], model=d.get("model"), prompts=dict(d.get("prompts") or {}),
                   error_source=d.get("error_source"),
                   card_count_by_condition={k: int(v) for k, v in d["card_count_by_condition"].items()},
                   created=d["created"], format=d["format"])


@dataclass(frozen=True)
class CohortSpec:
    """``cohort/1``: a simulation cohort drawn from a library, reproducible without a model.
    ``prevalence`` maps primary condition id -> share (normalised by the assembler)."""
    library_id: str
    prevalence: dict[str, float]
    n: int
    seed: int
    format: str = COHORT_FORMAT

    def to_json(self) -> dict:
        return {"format": self.format, "library_id": self.library_id, "prevalence": dict(self.prevalence),
                "n": self.n, "seed": self.seed}

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "CohortSpec":
        if d.get("format") != COHORT_FORMAT:
            raise ValueError(f"not a {COHORT_FORMAT} spec: format is {d.get('format')!r}")
        return cls(library_id=d["library_id"], prevalence={k: float(v) for k, v in d["prevalence"].items()},
                   n=int(d["n"]), seed=int(d["seed"]), format=d["format"])
