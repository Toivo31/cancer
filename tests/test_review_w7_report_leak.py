"""Review w7, finding B1: model-written report text carries the hidden error plan (invariant I1).

The G2 prompt tells the language model, per attempt and output, whether the result is ``correct``,
``false_alarm`` or ``miss`` (``patient_engine/authors.py::_plan_line``). The model then writes the report
knowing that. The values are correct by construction, but the free-text report often says so in words
("likely vascular overlap", "misread on preliminary frozen section"). The report reaches the decider through
``jev/record_context.py`` (``observations[].report``), so a decider that reads text can tell a false alarm
from a true positive better than the catalogue's test accuracy allows.

These tests fail on the current tree (marked xfail strict, so the suite stays green until the fix). They pass once reports reaching the decider are
rebuilt from the values (as the encounter loop already does for gathered outputs), or the report is left
out of the request context.
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
from patient_engine.reference import report_text

#: Each test shows an open finding, so it fails today. strict: once the finding is fixed the test passes,
#: the run reports XPASS as a failure, and the marker must be removed (the test then guards the fix).
pytestmark = pytest.mark.xfail(strict=True, reason="review w7 B1: open finding; remove this marker when fixed")

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "catalogue" / "lung-primary-care"
LIBRARIES = [ROOT / "libraries" / "gemini_s2_30", ROOT / "libraries" / "gemini_trial"]

# Words a radiologist or lab uses to say "this positive is probably not real".
HEDGE = re.compile(r"\b(likely|mimic\w*|artefact|artifact|misread|possibly|non-specific|nonspecific|reactive|"
                   r"borderline|trace|transient\w*|technical|superimposition|overlap|cannot be (?:confirmed|excluded)|"
                   r"indeterminate|questionable|subtle|slight|mild\w*|marginal\w*|faint)\b", re.I)


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
        for state, tests in c["hidden"]["error_plan"].items():
            for test, plans in tests.items():
                for k, plan in enumerate(plans):
                    a = c["observations"][state][test][k]
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
    """The share of hedged reports should be about the same for false alarms and true positives (within
    15 points). On the current libraries it is about 50% against 2%."""
    rate = {}
    for kind in ("false_alarm", "true_positive"):
        xs = [a for k, _, a in attempts if k == kind]
        rate[kind] = sum(1 for a in xs if HEDGE.search(a.get("report") or "")) / max(1, len(xs))
    gap = rate["false_alarm"] - rate["true_positive"]
    assert gap < 0.15, (f"hedged reports: false alarms {rate['false_alarm']:.0%}, true positives "
                        f"{rate['true_positive']:.0%}; the text tells the decider which positives are false (I1)")


def test_request_context_report_is_derived_from_values_only(attempts):
    """End to end: a model-written false-alarm report put into a Record (as the encounter loop does for an
    ordered test) reaches the JEV request context verbatim. It should be a rendering of the values only."""
    cat = load_catalogue(CATALOGUE)
    kind, test_id, a = next((k, t, a) for k, t, a in attempts
                            if k == "false_alarm" and t not in ("history", "examination", "vitals")
                            and HEDGE.search(a.get("report") or ""))
    test = cat.tests[test_id]
    ob = Observation(test_id, 1, a["status"], dict(a["values"]), a["report"], test.is_positive(a["values"]))
    rec = Record("P000001", {"age": 60, "sex": "f"})
    rec.append(Entry(0.0, 1, "encounter", encounter=1, role="gp", action="order_" + test_id))
    rec.append(Entry(3.0, 1, "result", encounter=1, role="gp", observations=(ob,)))
    ctx = context_from_record(rec, role="gp", now_days=3.0, catalogue=cat)
    sent = ctx["observations"][0]["report"]
    assert sent == report_text(test, a["status"], a["values"]), (
        f"report sent to the decider is the model's own text, not a rendering of the values: {sent!r}")
