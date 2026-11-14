"""Library audit (WP-W4-3, G4), fast tier: tolerances, refusals, the command, a small library. The 1 000-card baseline and skew tests are in test_pe_audit_1000.py."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from patient_engine.audit import AuditError, audit_library, load_tolerances
from patient_engine.catalogue import load_catalogue
from patient_engine.commands.design import scale_counts
from patient_engine.library import load_library, write_library
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
    path = tmp_path_factory.mktemp("audit_small") / "lib"
    cards = list(reference_cards(cat, make_design(cat, scale_counts(default_counts(cat), 110)), 1))
    write_library(cards, cat, path, {"generator": "reference"})
    return path, load_library(path, cat)


def test_small_library_runs_and_skips_thin_cells(built, cat, tol):
    report = audit_library(built[1], cat, tol)
    assert report["n_cards"] == len(built[1]) and report["format"] == "audit/1"
    assert any(c["n_skipped"] for c in report["checks"])           # too few cases is skipped, never passed
    assert report["passed"], report["failed_checks"]


def test_library_for_another_catalogue_is_refused(built, cat, tol):
    lib = built[1]
    other = dataclasses.replace(lib, manifest=dataclasses.replace(lib.manifest, catalogue_hash="0" * 64))
    with pytest.raises(AuditError):
        audit_library(other, cat, tol)


def test_presenting_complaint_that_is_not_a_symptom_fails(built, cat, tol):
    c = next(c for c in built[1].cards if c.primary_condition == "no_disease_found")
    false_sym = next(v for v, x in c.hidden.findings["all_active"].items()
                     if cat.variables[v].kind == "symptom" and x.value is not True)
    p = dataclasses.replace(c.presenting["all_active"], reported=(false_sym,))
    bad = dataclasses.replace(c, presenting={**c.presenting, "all_active": p})
    report = audit_library(dataclasses.replace(built[1], cards=tuple(bad if x.id == c.id else x for x in built[1].cards)), cat, tol)
    assert report["failed_checks"] == ["presenting"]


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
    assert main(["audit", str(built[0]), "--catalogue", str(CAT_DIR), "--tolerances", str(tmp_path / "x.yaml")]) == 2
