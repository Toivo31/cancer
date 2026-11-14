"""Review w7, finding B1: model-written report text carries the hidden error plan (invariant I1).

The G2 prompt tells the language model, per attempt and output, whether the result is ``correct``,
``false_alarm`` or ``miss`` (``patient_engine/authors.py::_plan_line``). The model then writes the report
knowing that. The values are correct by construction, but the free-text report often says so in words
("likely vascular overlap", "misread on preliminary frozen section"). The report reaches the decider through
``jev/record_context.py`` (``observations[].report``), so a decider that reads text can tell a false alarm
from a true positive better than the catalogue's test accuracy allows.

Fixed (branch w7/g2safe). The two tests below were written as strict xfails; they now guard the fix and were
rewritten to state the rule as built: a card's stored report reaches the decider only through
``RevealHandle.reveal``, which serves it when the card's results text is safe (template text, or result author
``g2@2`` and later, whose model never sees the hidden side) and otherwise rebuilds it from the values. The
review's original second test put the model text into a ``Record`` by hand, bypassing the handle; no simulation
path does that, so it now takes the report from the handle as the encounter loop does. The audit's
``report_wording`` check measures the leak in a library itself and must fail on the g2@1 Gemini libraries.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

from jev.record_context import context_from_record
from patient_engine.catalogue import load_catalogue
from patient_engine.record import Entry, Observation, Record
from patient_engine.card import card_from_json
from patient_engine.reference import report_text
from patient_engine.reveal import RevealHandle

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "catalogue" / "lung-primary-care"
LIBRARIES = [ROOT / "libraries" / "gemini_s2_30", ROOT / "libraries" / "gemini_trial"]

# Words a radiologist or lab uses to say "this positive is probably not real".
HEDGE = re.compile(r"\b(likely|mimic\w*|artefact|artifact|misread|possibly|non-specific|nonspecific|reactive|"
                   r"borderline|trace|transient\w*|technical|superimposition|overlap|cannot be (?:confirmed|excluded)|"
                   r"indeterminate|questionable|subtle|slight|mild\w*|marginal\w*|faint)\b", re.I)


_CAT = []


def _cat():
    if not _CAT:
        _CAT.append(load_catalogue(CATALOGUE))
    return _CAT[0]


def _cards():
    for lib in LIBRARIES:
        p = lib / "cards.jsonl.gz"
        if not p.exists():
            continue
        with gzip.open(p, "rt") as f:
            for line in f:
                yield json.loads(line)


def _positive_attempts():
    """(kind, test, attempt dict) for every ok attempt with at least one true binary output.
    kind is ``false_alarm`` when a true output is a planned false alarm, ``true_positive`` when all are correct."""
    for c in _cards():
        handle = RevealHandle(card_from_json(c), catalogue=_cat())
        for state, tests in c["hidden"]["error_plan"].items():
            for test, plans in tests.items():
                for k, plan in enumerate(plans):
                    a = dict(c["observations"][state][test][k])
                    a["model_report"] = a["report"]
                    a["report"] = handle.reveal(test, k, state).report       # what the decider receives
                    if a.get("status") != "ok":
                        continue
                    pos = [o for o, v in a["values"].items() if v is True]
                    if not pos:
                        continue
                    outs = plan.get("outputs", {})
                    if any(outs.get(o) == "false_alarm" for o in pos):
                        yield "false_alarm", test, a
                    elif all(outs.get(o) == "correct" for o in pos):
                        yield "true_positive", test, a


@pytest.fixture(scope="module")
def attempts():
    xs = list(_positive_attempts())
    if not xs:
        pytest.skip("no model-written library in libraries/")
    return xs


def test_report_wording_does_not_separate_false_alarms_from_true_positives(attempts):
    """The share of hedged reports reaching the decider should be about the same for false alarms and true
    positives (within 15 points). In the g2@1 cards' own text it is about 50% against 2%."""
    rate = {}
    for kind in ("false_alarm", "true_positive"):
        xs = [a for k, _, a in attempts if k == kind]
        rate[kind] = sum(1 for a in xs if HEDGE.search(a.get("report") or "")) / max(1, len(xs))
    gap = rate["false_alarm"] - rate["true_positive"]
    assert gap < 0.15, (f"hedged reports: false alarms {rate['false_alarm']:.0%}, true positives "
                        f"{rate['true_positive']:.0%}; the text tells the decider which positives are false (I1)")


def test_the_g2v1_text_itself_still_separates_them(attempts):
    """Sanity: the libraries do carry the leak (so the test above shows the gate, not an empty sample)."""
    fa = [a for k, _, a in attempts if k == "false_alarm"]
    tp = [a for k, _, a in attempts if k == "true_positive"]
    rate = lambda xs: sum(1 for a in xs if HEDGE.search(a["model_report"])) / max(1, len(xs))
    assert rate(fa) - rate(tp) > 0.3


def test_request_context_report_is_derived_from_values_only(attempts):
    """End to end: a g2@1 false-alarm result, taken from the card through the reveal handle (as the encounter
    loop does for ordered and hospital tests) and put into a Record, reaches the JEV request context as a
    rendering of its values, not as the model's text."""
    cat = load_catalogue(CATALOGUE)
    kind, test_id, a = next((k, t, a) for k, t, a in attempts
                            if k == "false_alarm" and t not in ("history", "examination", "vitals")
                            and HEDGE.search(a["model_report"]))
    test = cat.tests[test_id]
    ob = Observation(test_id, 1, a["status"], dict(a["values"]), a["report"], test.is_positive(a["values"]))
    rec = Record("P000001", {"age": 60, "sex": "f"})
    rec.append(Entry(0.0, 1, "encounter", encounter=1, role="gp", action="order_" + test_id))
    rec.append(Entry(3.0, 1, "result", encounter=1, role="gp", observations=(ob,)))
    ctx = context_from_record(rec, role="gp", now_days=3.0, catalogue=cat)
    sent = ctx["observations"][0]["report"]
    assert sent == report_text(test, a["status"], a["values"]), (
        f"report sent to the decider is the model's own text, not a rendering of the values: {sent!r}")
    assert sent != a["model_report"]


def test_safe_cards_keep_their_own_report():
    """The gate passes the stored text of a card whose results prompt is safe (g2@2) or that is template text."""
    from patient_engine.reveal import results_text_is_safe
    for c in _cards():
        card = card_from_json(c)
        assert not results_text_is_safe(card.provenance)                  # the Gemini libraries are g2@1
        safe = card_from_json({**c, "provenance": {**c["provenance"], "prompts": {"patient": "g1@1", "results": "g2@2"}}})
        h = RevealHandle(safe, catalogue=_cat())
        assert h.reveal("chest_xray", 0).report == c["observations"]["all_active"]["chest_xray"][0]["report"]
        break


def test_audit_report_wording_fails_on_the_g2v1_gemini_library():
    """The audit's leak measure: fails on libraries/gemini_s2_30 (g2@1) with the review's numbers."""
    from patient_engine.audit import audit_library, load_tolerances
    from patient_engine.library import load_library
    lib_dir = ROOT / "libraries" / "gemini_s2_30"
    if not (lib_dir / "cards.jsonl.gz").exists():
        pytest.skip("libraries/gemini_s2_30 is not in this checkout")
    cat = _cat()
    rep = audit_library(load_library(lib_dir, cat), cat, load_tolerances(CATALOGUE / "audit_tolerances.yaml"))
    chk = next(c for c in rep["checks"] if c["id"] == "report_wording")
    assert chk["status"] == "fail" and "report_wording" in rep["failed_checks"]
    pos = next(x for x in chk["cells"] if x["id"] == "report_wording.positive")
    assert pos["status"] == "fail" and pos["hedge_wrong"] > 0.4 and pos["hedge_right"] < 0.05
