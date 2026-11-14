"""Review w8: open defects in the g2@2 result author and the patient-author leak rule.

Every test here states the rule as it should hold and is a strict xfail today, so the gate stays green while the
defect is recorded; when a fix lands the xfail turns into an unexpected pass and must be removed.
See docs/review_w8_fixes.md (B1, M1, M2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patient_engine.authors import Authors, results_user
from patient_engine.card import card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.reference import generate_reference
from patient_engine.skeleton import make_design, make_skeleton
from patient_engine.validate import validate_card

ROOT = Path(__file__).resolve().parents[1]
CAT = load_catalogue(ROOT / "catalogue" / "lung-primary-care")


def _card(condition: str, index: int = 0, seed: int = 31) -> dict:
    design = make_design(CAT, {condition: index + 1})
    return card_to_json(generate_reference(CAT, make_skeleton(CAT, index, design, seed)))


def _prompt(card: dict) -> str:
    st = card["states"][0]
    obs = {t: [{"status": a["status"], "values": a["values"]} for a in atts]
           for t, atts in card["observations"][st].items()}
    return results_user(CAT, card["background"], card["presenting"][st]["reported"], obs, Authors(CAT).gp_tests)


@pytest.mark.xfail(strict=True, reason="review w8 B1: the g2@2 prompt holds every test's values, including the "
                                       "definitive tests whose output ids name the diagnosis")
def test_g2_prompt_does_not_carry_a_definitive_result():
    text = _prompt(_card("lung_cancer"))
    assert "lung_cancer_confirmed" not in text and "definitive for lung cancer" not in text


@pytest.mark.xfail(strict=True, reason="review w8 B1: the model writing one report sees the other attempts and the "
                                       "other tests (tissue sampling) of the same patient, which a reader of that "
                                       "report does not have")
def test_g2_prompt_for_the_chest_xray_does_not_include_tissue_results():
    text = _prompt(_card("lung_cancer"))
    assert "malignant_cells" not in text


@pytest.mark.xfail(strict=True, reason="review w8 M2: a test without only_if whose variable is null reports an "
                                       "invented value (histology of a cancer for a patient without one), "
                                       "planned 'correct'")
def test_histology_of_a_non_cancer_patient_is_null():
    card = _card("viral_self_limiting")
    vals = [a["values"].get("histology") for a in card["observations"][card["states"][0]]["histology_report"]
            if a["status"] == "ok"]
    assert vals and all(v is None for v in vals)


def _with_account(card: dict, text: str) -> dict:
    notes = card["notes"]
    acc = next(n for n in notes if n["kind"] == "patient_account" and n["state"] == card["states"][0])
    acc["text"] = text
    return card


def _flags(card: dict) -> list:
    return [p for p in validate_card(card, CAT) if p.code == "card_reveals_condition"]


@pytest.mark.xfail(strict=True, reason="review w8 M1: rule 8 exempts a text whose mentions include a finding caused "
                                       "by the primary alone, so a cancer patient's account may name 'lung cancer'")
def test_patient_account_naming_lung_cancer_is_flagged():
    card = _card("lung_cancer")
    st = card["states"][0]
    own = [v for v, f in card["hidden"]["findings"][st].items()
           if f["value"] not in (None, False) and f["caused_by"] == ["lung_cancer"]]
    assert own, "fixture: a finding caused by the cancer alone"
    card = _with_account(card, "I have been coughing for weeks and I am frightened it is lung cancer.")
    next(n for n in card["notes"] if n["kind"] == "patient_account")["mentions"] = own[:1]
    assert _flags(card)


@pytest.mark.xfail(strict=True, reason="review w8 M1: rule 8 matches only the condition's label and id, not "
                                       "'cancer', 'tumour', 'COPD' or 'TB'")
@pytest.mark.parametrize("condition,text", [
    ("lung_cancer", "My GP said the shadow could be a tumour and I keep thinking about cancer."),
    ("copd_exacerbation", "My COPD has been worse since the cold weather and the inhaler is not helping."),
    ("tuberculosis", "A cousin had TB last year and I have been sweating at night."),
])
def test_patient_account_naming_a_synonym_is_flagged(condition, text):
    card = _with_account(_card(condition), text)
    next(n for n in card["notes"] if n["kind"] == "patient_account")["mentions"] = []
    assert _flags(card)
