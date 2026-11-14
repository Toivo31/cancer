"""The patient record (``record/1``): what clinicians have found out and done, as a log.

Revealed side (invariant I1). A record holds only what an encounter or a test has revealed, what was
decided and the clinician's note. It never holds a condition, a cause, an error plan or an unrevealed
result. Decision policies and the JEV request builder read a ``Record`` and nothing else about a patient.
The test ``tests/test_pe_record.py`` fails if a hidden field name appears in these types.

One entry per event, appended in time order::

    {"format": "record/1", "patient_id": "c_5f2a91e0", "background": {...},
     "entries": [
       {"t_days": 0.0, "episode": 1, "encounter": 1, "role": "nurse", "kind": "encounter",
        "reported": ["cough_3wk"], "found": {"cough_3wk": true, "fever": false},
        "observations": [], "action": "book_gp_routine", "note": "Cough 4 wk, no fever. GP booked."},
       {"t_days": 9.0, "episode": 1, "encounter": 2, "role": "gp", "kind": "encounter", "reported": [...],
        "found": {...}, "observations": [], "action": "order_chest_xray", "note": "..."},
       {"t_days": 11.5, "episode": 1, "encounter": 2, "role": "gp", "kind": "result",
        "observations": [{"test": "chest_xray", "attempt": 1, "status": "ok",
                          "values": {"abnormal": false, "consolidation": true}, "report": "..."}]},
       ...]}

Two layers (decision D49):

* **Mechanical log** (``author`` = ``"engine"``): written by the simulator, never edited. ``kind``:
  ``encounter`` (a visit: what was gathered, which action was chosen), ``result`` (a test result
  arrives; each observation carries ``positive``: the catalogue's ``positive_when`` reading, true,
  false or None for non-diagnostic), ``treatment``, ``referral``, ``hospital`` (a hospital step and its
  result), ``discharge``, ``return`` (a new episode starts). Its ``note`` is a short template line.
* **Clinical assessments** (``kind`` = ``assessment``, ``author`` = the decision point and backend,
  e.g. ``"gp_encounter/jev"``): the decider's own words, appended right after its decision: free text
  in ``note`` (at most ``MAX_NOTE_CHARS``) and an optional structured ``assessment``
  (``working_diagnosis``, ``differential``, ``plan``, ``confidence``). This is how the JEV's enriched
  context becomes part of the record that later decisions read. Assessments are interpretation, not
  facts: they never change or hide a mechanical entry, and readers must treat the mechanical log as
  authoritative.

What happens to the hidden truth (a pneumonia resolving) is never an entry; it shows only through
later findings. Because deciders see only the record, nothing they write can leak hidden data (I1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

RECORD_FORMAT = "record/1"
ENTRY_KINDS = ("encounter", "result", "treatment", "referral", "hospital", "discharge", "return", "assessment")
MAX_NOTE_CHARS = 2000
ASSESSMENT_KEYS = ("working_diagnosis", "differential", "plan", "confidence")

Value = Any   # bool | int | float | str | None, as on a card


@dataclass(frozen=True)
class Observation:
    """One revealed test result: the same fields as ``card.RevealedObservation`` minus the state."""
    test: str
    attempt: int
    status: str                               # ok | non_diagnostic
    values: Mapping[str, Value] = field(default_factory=dict)
    report: str = ""
    positive: bool | None = None              # mechanical reading of the catalogue's positive_when

    def to_json(self) -> dict:
        return {"test": self.test, "attempt": self.attempt, "status": self.status,
                "values": dict(self.values), "report": self.report, "positive": self.positive}


@dataclass(frozen=True)
class Entry:
    t_days: float
    episode: int
    kind: str
    encounter: int | None = None
    role: str | None = None                   # nurse | gp | specialist | None (hospital steps, returns)
    reported: tuple[str, ...] = ()            # variable ids the patient mentioned at this encounter
    found: Mapping[str, Value] = field(default_factory=dict)   # variable id -> value revealed by asking/examining
    observations: tuple[Observation, ...] = ()
    action: str | None = None                 # action id chosen (catalogue care.yaml), or a hospital step id
    note: str = ""
    author: str = "engine"                    # "engine" for the mechanical log; "<decision point>/<backend>" for assessments
    assessment: Mapping[str, Value] = field(default_factory=dict)   # kind "assessment" only

    def to_json(self) -> dict:
        d: dict = {"t_days": round(float(self.t_days), 3), "episode": self.episode, "kind": self.kind}
        if self.encounter is not None:
            d["encounter"] = self.encounter
        if self.role is not None:
            d["role"] = self.role
        if self.reported:
            d["reported"] = list(self.reported)
        if self.found:
            d["found"] = dict(self.found)
        if self.observations:
            d["observations"] = [o.to_json() for o in self.observations]
        if self.action is not None:
            d["action"] = self.action
        if self.note:
            d["note"] = self.note
        d["author"] = self.author
        if self.assessment:
            d["assessment"] = dict(self.assessment)
        return d


@dataclass
class Record:
    """Append-only. ``patient_id`` is the opaque id from the reveal handle, never a library card id."""
    patient_id: str
    background: Mapping[str, Value]
    entries: list[Entry] = field(default_factory=list)

    def append(self, entry: Entry) -> None:
        if entry.kind not in ENTRY_KINDS:
            raise ValueError(f"unknown record entry kind {entry.kind!r}")
        if self.entries and entry.t_days < self.entries[-1].t_days - 1e-9:
            raise ValueError("record entries must be appended in time order")
        if entry.kind == "assessment":
            if entry.author == "engine":
                raise ValueError("an assessment needs the decider as author")
            bad = set(entry.assessment) - set(ASSESSMENT_KEYS)
            if bad:
                raise ValueError(f"unknown assessment keys {sorted(bad)}")
            if len(entry.note) > MAX_NOTE_CHARS:
                entry = Entry(**{**entry.__dict__, "note": entry.note[:MAX_NOTE_CHARS - 1] + "…"})
        elif entry.author != "engine" or entry.assessment:
            raise ValueError("only assessment entries are authored by a decider")
        self.entries.append(entry)

    def add_assessment(self, t_days: float, author: str, note: str = "", assessment: Mapping | None = None,
                       role: str | None = None, encounter: int | None = None) -> None:
        """Append the decider's own words after its decision (the JEV's enriched context)."""
        if not note and not assessment:
            return
        self.append(Entry(t_days, self.episode, "assessment", encounter=encounter, role=role, note=note or "",
                          author=author, assessment=dict(assessment or {})))

    # ------------------------------------------------------------------ reading helpers
    @property
    def episode(self) -> int:
        return self.entries[-1].episode if self.entries else 1

    def latest_found(self) -> dict[str, Value]:
        """Latest revealed value of each variable (later encounters overwrite earlier ones)."""
        out: dict[str, Value] = {}
        for e in self.entries:
            out.update(e.found)
        return out

    def observations(self, test: str | None = None) -> list[tuple[float, Observation]]:
        return [(e.t_days, o) for e in self.entries for o in e.observations if test is None or o.test == test]

    def attempts_done(self, test: str) -> int:
        return sum(1 for _, o in self.observations(test))

    def mechanical(self) -> list[Entry]:
        return [e for e in self.entries if e.author == "engine"]

    def assessments(self) -> list[Entry]:
        return [e for e in self.entries if e.kind == "assessment"]

    def actions(self) -> list[str]:
        return [e.action for e in self.entries if e.action]

    def to_json(self) -> dict:
        return {"format": RECORD_FORMAT, "patient_id": self.patient_id, "background": dict(self.background),
                "entries": [e.to_json() for e in self.entries]}


#: Every type the revealed side may hold from this module (the I1 test walks these).
RECORD_TYPES = (Observation, Entry, Record)
