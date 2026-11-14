"""Library audit on 1 000 reference cards (WP-W4-3, G4): baseline passes, skewed libraries fail exactly the check they skew.

Listed in tests/slow_tests.txt (about 1 minute)."""

from __future__ import annotations

import dataclasses
import json
import random
import time
from pathlib import Path

import pytest

from patient_engine.audit import AuditError, audit_library, load_tolerances, render_markdown, write_audit
from patient_engine.catalogue import load_catalogue
from patient_engine.commands.design import scale_counts
from patient_engine.library import Library, load_library, write_library
from patient_engine.reference import reference_cards
from patient_engine.skeleton import default_counts, make_design

ROOT = Path(__file__).resolve().parents[1]
CAT_DIR = ROOT / "catalogue" / "lung-primary-care"


@pytest.fixture(scope="module")
def cat():
    return load_catalogue(CAT_DIR)


@pytest.fixture(scope="module")
def tol():
    return load_tolerances(CAT_DIR / "audit_tolerances.yaml")


@pytest.fixture(scope="module")
def built(cat, tmp_path_factory):
    path = tmp_path_factory.mktemp("audit") / "lib"
    cards = list(reference_cards(cat, make_design(cat, scale_counts(default_counts(cat), 1000)), 1))
    write_library(cards, cat, path, {"generator": "reference"})
    return path, load_library(path, cat)


@pytest.fixture(scope="module")
def baseline(built, cat, tol):
    t0 = time.monotonic()
    report = audit_library(built[1], cat, tol)
    return report, time.monotonic() - t0


def _with_cards(lib: Library, cards) -> Library:
    return dataclasses.replace(lib, cards=tuple(cards))


def _flip_test(lib: Library, test: str, output: str, share: float, seed: int = 5) -> Library:
    rng = random.Random(seed)
    out = []
    for c in lib.cards:
        obs = {}
        for s, tests in c.observations.items():
            atts = []
            for a in tests[test] if test in tests else ():
                if a.status == "ok" and isinstance(a.values.get(output), bool) and rng.random() < share:
                    a = dataclasses.replace(a, values={**a.values, output: not a.values[output]})
                atts.append(a)
            obs[s] = {**tests, test: tuple(atts)} if test in tests else dict(tests)
        out.append(dataclasses.replace(c, observations=obs))
    return _with_cards(lib, out)


def test_reference_library_of_1000_passes_in_time(baseline):
    report, seconds = baseline
    assert report["passed"], report["failed_checks"]
    assert report["failed_checks"] == []
    assert report["n_cards"] == 1000
    assert seconds < 30
    ids = {c["id"] for c in report["checks"]}
    assert {"state_consistency", "presenting", "diversity", "leak", "non_diagnostic", "accuracy.chest_xray",
            "findings.lung_cancer"} <= ids
    assert sum(c["n_cells"] for c in report["checks"]) > 300
    assert set(report["states"]) > {"all_active"} and any(s != "all_active" for s in report["states"])


def test_every_cell_has_numbers_and_an_interval(baseline):
    for c in baseline[0]["checks"]:
        for x in c["cells"]:
            assert x["status"] in ("pass", "skipped", "fail")
            if x["status"] == "pass" and x["kind"] != "share":
                assert x["lo"] <= x["expected"] <= x["hi"]


def test_skewed_test_fails_exactly_that_check(built, cat, tol):
    skewed = _flip_test(built[1], "chest_xray", "abnormal", 0.30)
    report = audit_library(skewed, cat, tol)
    assert report["failed_checks"] == ["accuracy.chest_xray"]
    cells = [x for c in report["checks"] if c["id"] == "accuracy.chest_xray" for x in c["cells"] if x["status"] == "fail"]
    assert cells and all(x["id"].startswith("chest_xray.abnormal.") for x in cells)


def test_skewed_findings_fail_the_findings_check_only(built, cat, tol):
    out = []
    rng = random.Random(2)
    for c in built[1].cards:
        f = c.hidden.findings
        if c.primary_condition == "pneumonia" and len(c.hidden.conditions) == 1 and rng.random() < 0.6:
            st = {s: {**fs, "fever": dataclasses.replace(fs["fever"], value=False, caused_by=())} for s, fs in f.items()}
            c = dataclasses.replace(c, hidden=dataclasses.replace(c.hidden, findings=st))
        out.append(c)
    report = audit_library(_with_cards(built[1], out), cat, tol)
    assert "findings.pneumonia" in report["failed_checks"]
    assert not any(i.startswith("findings.") and i != "findings.pneumonia" for i in report["failed_checks"])


def test_presenting_complaint_that_is_not_a_symptom_fails(built, cat, tol):
    c = next(c for c in built[1].cards if c.primary_condition == "no_disease_found")
    false_sym = next(v for v, x in c.hidden.findings["all_active"].items()
                     if cat.variables[v].kind == "symptom" and x.value is not True)
    p = dataclasses.replace(c.presenting["all_active"], reported=(false_sym,))
    bad = dataclasses.replace(c, presenting={**c.presenting, "all_active": p})
    report = audit_library(_with_cards(built[1], [bad if x.id == c.id else x for x in built[1].cards]), cat, tol)
    assert report["failed_checks"] == ["presenting"]


def test_duplicates_fail_diversity(built, cat, tol):
    base = list(built[1].cards)
    cards = [dataclasses.replace(base[0], id=f"dup:{i}") for i in range(30)] + base[30:]
    report = audit_library(_with_cards(built[1], cards), cat, tol)
    assert "diversity" in report["failed_checks"]


def test_leak_check_counts_flagged_notes(built, cat, tol):
    c = next(c for c in built[1].cards if c.primary_condition == "lung_cancer" and len(c.hidden.conditions) == 1)
    n = dataclasses.replace(c.notes[0], text="Synthetic note: this patient has lung cancer.", mentions=())
    leaky = dataclasses.replace(c, notes=(n, *c.notes[1:]))
    tight = json.loads(json.dumps(tol))
    tight["checks"]["leak"]["max_share"] = 0.0
    report = audit_library(_with_cards(built[1], [leaky if x.id == c.id else x for x in built[1].cards]), cat, tight)
    assert report["failed_checks"] == ["leak"]


def test_resolved_state_violation_fails_consistency(built, cat, tol):
    c = next(c for c in built[1].cards if len(c.states) > 1 and c.primary_condition == "lung_cancer")
    res = c.states[1]
    f = dict(c.hidden.findings[res])
    victim = next(v for v, x in c.hidden.findings["all_active"].items() if x.value is False and cat.variables[v].type == "binary")
    f[victim] = dataclasses.replace(f[victim], value=True, caused_by=())
    bad = dataclasses.replace(c, hidden=dataclasses.replace(c.hidden, findings={**c.hidden.findings, res: f}))
    report = audit_library(_with_cards(built[1], [bad if x.id == c.id else x for x in built[1].cards]), cat, tol)
    assert report["failed_checks"] == ["state_consistency"]


def test_library_for_another_catalogue_is_refused(built, cat, tol):
    lib = built[1]
    other = dataclasses.replace(lib, manifest=dataclasses.replace(lib.manifest, catalogue_hash="0" * 64))
    with pytest.raises(AuditError):
        audit_library(other, cat, tol)


def test_tolerances_file_needs_reasons_and_numbers(tmp_path):
    raw = (CAT_DIR / "audit_tolerances.yaml").read_text()
    load_tolerances(CAT_DIR / "audit_tolerances.yaml")
    bad = tmp_path / "t.yaml"
    bad.write_text(raw.replace("    max_share: 0.02\n    reason:", "    reason:", 1))
    with pytest.raises(AuditError):
        load_tolerances(bad)
    with pytest.raises(AuditError):
        load_tolerances(tmp_path / "missing.yaml")
    assert load_tolerances(None)["checks"]["leak"]["max_share"] > 0


def test_cli_writes_reports_and_sets_exit_code(built, cat, tmp_path, capsys):
    from patient_engine.__main__ import main
    out = tmp_path / "rep"
    code = main(["audit", str(built[0]), "--catalogue", str(CAT_DIR), "--out", str(out)])
    text = capsys.readouterr().out
    assert code == 0 and "PASS" in text and "accuracy.chest_xray" in text
    rep = json.loads((out / "audit.json").read_text())
    assert rep["passed"] and rep["library_id"] == built[1].id
    assert (out / "audit.md").read_text().startswith("# Library audit: PASS")
    assert main(["audit", str(tmp_path / "nope"), "--catalogue", str(CAT_DIR)]) == 2


def test_markdown_lists_failed_cells(built, cat, tol):
    report = audit_library(_flip_test(built[1], "chest_xray", "abnormal", 0.3), cat, tol)
    md = render_markdown(report)
    assert md.startswith("# Library audit: FAIL") and "Failed cells" in md and "chest_xray.abnormal" in md
