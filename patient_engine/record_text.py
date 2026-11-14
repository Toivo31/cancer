"""A record (``record/1``) as readable lines, one per entry, for the demo and for people reading a run.

Reads a ``Record`` only (revealed side). With a catalogue, variable and test ids become their labels;
``care`` (optional, a ``patient_engine.care.Care``) does the same for action ids.
"""

from __future__ import annotations

from .record import Entry, Record

_ROLE = {"nurse": "Nurse", "gp": "GP", "specialist": "Specialist"}


def _day(t: float) -> str:
    return f"Day {int(t)}" if abs(t - round(t)) < 1e-9 else f"Day {t:.1f}"


def _words(s: str) -> str:
    return s.replace("_", " ")


def _var(catalogue, vid: str) -> str:
    v = getattr(catalogue, "variables", {}).get(vid) if catalogue is not None else None
    return (v.label if v is not None and v.label else _words(vid))


def _test(catalogue, tid: str) -> str:
    t = getattr(catalogue, "tests", {}).get(tid) if catalogue is not None else None
    return (t.label if t is not None and t.label else _words(tid))


def _action(catalogue, care, aid: str) -> str:
    a = getattr(care, "actions", {}).get(aid) if care is not None else None
    if a is not None and getattr(a, "label", ""):
        return a.label
    t = getattr(catalogue, "tests", {}).get(aid) if catalogue is not None else None
    return t.label if t is not None else _words(aid)


def _found(catalogue, found) -> str:
    parts = []
    for k, v in found.items():
        name = _var(catalogue, k)
        if v is True:
            parts.append(name)
        elif v is False:
            parts.append(f"no {name}")
        elif v is not None:
            parts.append(f"{name} {v}")
    return ", ".join(parts)


#: words in output ids written as clinicians write them
_ACRONYMS = {"fdg": "FDG", "hb": "Hb", "crp": "CRP", "alp": "ALP", "ldh": "LDH", "bnp": "BNP", "fev1": "FEV1",
             "pct": "", "mets": "metastases"}


def _output_name(oid: str) -> str:
    """An output's own label: its id in words (``suspicious_for_malignancy`` -> "suspicious for malignancy").
    Not the label of the variable it measures: a CT that is suspicious for malignancy did not show malignant
    tissue (review w7 M3); the noisy output must not be named as the truth it estimates."""
    return " ".join(x for x in (_ACRONYMS.get(w, w) for w in oid.split("_")) if x)


def _values(catalogue, test: str, values) -> str:
    t = getattr(catalogue, "tests", {}).get(test) if catalogue is not None else None
    parts = []
    for k, v in values.items():
        if v is None:
            continue
        name, unit = _output_name(k), ""
        if t is not None:
            try:
                out = t.output(k)
                unit = f" {out.unit}" if out.unit else ""
            except StopIteration:
                pass
        if v is True:
            parts.append(name)
        elif v is False:
            parts.append(f"no {name}")
        else:
            parts.append(f"{name} {v}{unit}")
    return ", ".join(parts)


def _assessment_line(e: Entry) -> str:
    who = _ROLE.get(e.role or "", e.role or "")
    a = dict(e.assessment)
    segs = [_day(e.t_days), f"{who} assessment" if who else "assessment"]
    if a.get("working_diagnosis"):
        segs.append(f"working diagnosis: {a['working_diagnosis']}")
    if a.get("differential"):
        segs.append("differential: " + ", ".join(map(str, a["differential"])))
    if a.get("plan"):
        segs.append(f"plan: {a['plan']}")
    if a.get("confidence") is not None:
        segs.append(f"confidence {a['confidence']}")
    if e.note:
        segs.append(f"note: {e.note}")
    return " · ".join(segs).replace(" · working", " · working", 1)


def _line(e: Entry, catalogue, care) -> str:
    if e.kind == "assessment":
        return _assessment_line(e)
    who = _ROLE.get(e.role or "", e.role or "")
    head = _day(e.t_days)
    if e.kind == "result":
        bits = []
        for o in e.observations:
            if o.status != "ok":
                bits.append(f"{_test(catalogue, o.test)}: not diagnostic, needs repeating")
            else:
                vals = _values(catalogue, o.test, o.values)
                bits.append(f"{_test(catalogue, o.test)}: {vals}" if vals else _test(catalogue, o.test))
        return f"{head} · result · " + "; ".join(bits)
    segs = [head]
    if e.kind == "encounter":
        segs.append(who or "visit")
    else:
        segs.append(e.kind if not who else f"{e.kind} ({who})")
    said = _found(catalogue, e.found) if e.found else ", ".join(_var(catalogue, r) for r in e.reported)
    if said:
        segs.append(said)
    for o in e.observations:                                  # hospital steps carry results on the entry
        vals = _values(catalogue, o.test, o.values)
        segs.append(f"{_test(catalogue, o.test)}: {vals}" if vals else _test(catalogue, o.test))
    if e.action:
        verb = "ordered " if care is not None and getattr(care, "actions", {}).get(e.action) is not None \
            and care.actions[e.action].kind == "order" else ""
        segs.append(verb + _action(catalogue, care, e.action))
    if e.note:
        segs.append(f"note: {e.note}")
    return " · ".join(segs)


def render(record: Record, catalogue=None, care=None) -> list[str]:
    """One short readable line per entry, in record order."""
    return [_line(e, catalogue, care) for e in record.entries]
