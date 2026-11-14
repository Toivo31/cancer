"""A patient record (``record/1``) as the JEV request context.

``context_from_record(record, role=..., now_days=...)`` is the one place where a :class:`Record`
becomes request JSON. It reads the record and nothing else (invariant I1): no card, no condition, no
hidden field can reach it, because a ``Record`` holds none. Field meanings are in
``docs/platform/jev-card-context.md``.
"""

from __future__ import annotations

from typing import Any

from patient_engine.record import Record

CARD_FORMAT = "card/1"


def _positive(catalogue, test: str, status: str, values: dict) -> bool | None:
    """The yes/no reading of a result (``positive_when``); None when unknown, not ok or no rule."""
    if catalogue is None or status != "ok":
        return None
    t = getattr(catalogue, "tests", {}).get(test)
    if t is None:
        return None
    try:
        r = t.is_positive(values)
    except Exception:               # a rule that cannot be evaluated on these values is "unknown"
        return None
    return None if r is None else bool(r)


def context_from_record(record: Record, *, role: str | None, now_days: float, catalogue: Any = None) -> dict:
    """Request ``context`` for ``record`` at time ``now_days`` for a decision by ``role``.

    ``catalogue`` (optional) only turns results into the yes/no ``history[].result`` via the test's
    ``positive_when``; without it ``result`` is null.
    """
    entries = list(record.entries)
    episode = record.episode
    in_ep = [e for e in entries if e.episode == episode]

    observations, history = [], []
    for e in entries:
        for o in e.observations:
            observations.append({"test": o.test, "attempt": o.attempt, "status": o.status,
                                 "values": dict(o.values), "report": o.report, "t_days": round(float(e.t_days), 3)})
            history.append({"step": o.test, "test": o.test, "result": _positive(catalogue, o.test, o.status, dict(o.values)),
                            "t_days": round(float(e.t_days), 3)})

    notes = [{"id": f"n{i + 1}", "kind": f"{e.role or e.kind}_note", "text": e.note, "t_days": round(float(e.t_days), 3)}
             for i, e in enumerate(entries) if e.note]

    # what the patient reported when this episode began: its first entry that lists anything
    reported = next((list(e.reported) for e in in_ep if e.reported), [])

    bg = dict(record.background)
    age = bg.get("age")
    return {
        "age": age, "t_days": float(now_days), "fast_track": False, "attributes": {},
        "history": history,
        "card_format": CARD_FORMAT, "patient_id": record.patient_id, "background": bg,
        "episode": episode, "role": role,
        "encounters_so_far": sum(1 for e in entries if e.kind == "encounter"),
        "presenting": {"reported": reported},
        "found": record.latest_found(),
        "observations": observations, "notes": notes,
        "actions": record.actions(),
    }
