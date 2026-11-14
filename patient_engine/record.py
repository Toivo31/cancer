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

``kind``: ``encounter`` (a visit: findings, decision, note), ``result`` (a test result arrives),
``treatment`` (a treatment started; ``action`` names it), ``referral`` (handed to the hospital),
``hospital`` (a hospital step's revealed result), ``discharge`` (episode closed), ``return`` (the patient
comes back; a new episode starts). What happens to the hidden truth (a pneumonia resolving) is never an
entry; it shows only through later findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

RECORD_FORMAT = "record/1"
ENTRY_KINDS = ("encounter", "result", "treatment", "referral", "hospital", "discharge", "return")

Value = Any   # bool | int | float | str | None, as on a card


@dataclass(frozen=True)
class Observation:
    """One revealed test result: the same fields as ``card.RevealedObservation`` minus the state."""
    test: str
    attempt: int
    status: str                               # ok | non_diagnostic
    values: Mapping[str, Value] = field(default_factory=dict)
    report: str = ""

    def to_json(self) -> dict:
        return {"test": self.test, "attempt": self.attempt, "status": self.status,
                "values": dict(self.values), "report": self.report}


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
        self.entries.append(entry)

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

    def actions(self) -> list[str]:
        return [e.action for e in self.entries if e.action]

    def to_json(self) -> dict:
        return {"format": RECORD_FORMAT, "patient_id": self.patient_id, "background": dict(self.background),
                "entries": [e.to_json() for e in self.entries]}


#: Every type the revealed side may hold from this module (the I1 test walks these).
RECORD_TYPES = (Observation, Entry, Record)
