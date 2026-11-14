"""Review w8: defects in the g2@2 result author and the patient-author leak rule, and their fixes.

Recorded as strict xfails by the review (docs/review_w8_fixes.md, B1, M1, M2); fixed on w8/g2blind (decision D60):
B1 by the result author g2@3, whose prompt for a report holds that one result's own values only; M1 by the
synonyms of ``validate.CONDITION_TERMS`` and no exemption for the patient's own words; M2 in ``settle_attempt``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patient_engine.authors import Authors, report_pattern, results_user
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
    """g2@2's prompt of the first state (kept for comparison: the review's finding)."""
    st = card["states"][0]
    obs = {t: [{"status": a["status"], "values": a["values"]} for a in atts]
           for t, atts in card["observations"][st].items()}
    return results_user(CAT, card["background"], card["presenting"][st]["reported"], obs, Authors(CAT).gp_tests)


def _g2v3_prompts(card: dict) -> dict[tuple[str, int], str]:
    """(test, attempt) -> the g2@3 prompt that wrote that attempt's report (every state)."""
    authors = Authors(CAT)
    out = {}
    for st in card["states"]:
        for tid, atts in card["observations"][st].items():
            for k, a in enumerate(atts):
                pat = report_pattern(CAT.tests[tid], a["status"], a["values"])
                out[(tid, k)] = authors.bank_request(CAT.tests[tid], pat)["user"]
    return out


def test_g2v2_prompt_still_carries_the_definitive_result():
    """The review's finding stands for g2@2, which is why it left ``SAFE_RESULTS_PROMPTS``."""
    text = _prompt(_card("lung_cancer"))
    assert "lung_cancer_confirmed" in text and "malignant_cells" in text


def test_g2_prompt_does_not_carry_a_definitive_result():
    """g2@3: no report's prompt holds a definitive test's result, except that definitive test's own report."""
    for (tid, _), text in _g2v3_prompts(_card("lung_cancer")).items():
        if tid != "dx_lung_cancer_histology":
            assert "lung_cancer_confirmed" not in text and "definitive for lung cancer" not in text, tid


def test_g2_prompt_for_the_chest_xray_does_not_include_tissue_results():
    prompts = _g2v3_prompts(_card("lung_cancer"))
    for k in range(3):
        text = prompts[("chest_xray", k)]
        assert "malignant_cells" not in text and "histology" not in text
        assert all(t not in text for t in CAT.tests if t != "chest_xray")       # no other test at all


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


def test_patient_account_naming_lung_cancer_is_flagged():
    card = _card("lung_cancer")
    st = card["states"][0]
    own = [v for v, f in card["hidden"]["findings"][st].items()
           if f["value"] not in (None, False) and f["caused_by"] == ["lung_cancer"]]
    assert own, "fixture: a finding caused by the cancer alone"
    card = _with_account(card, "I have been coughing for weeks and I am frightened it is lung cancer.")
    next(n for n in card["notes"] if n["kind"] == "patient_account")["mentions"] = own[:1]
    assert _flags(card)


@pytest.mark.parametrize("condition,text", [
    ("lung_cancer", "My GP said the shadow could be a tumour and I keep thinking about cancer."),
    ("copd_exacerbation", "My COPD has been worse since the cold weather and the inhaler is not helping."),
    ("tuberculosis", "A cousin had TB last year and I have been sweating at night."),
])
def test_patient_account_naming_a_synonym_is_flagged(condition, text):
    card = _with_account(_card(condition), text)
    next(n for n in card["notes"] if n["kind"] == "patient_account")["mentions"] = []
    assert _flags(card)


def test_histology_of_a_cancer_patient_is_still_reported():
    card = _card("lung_cancer")
    vals = [a["values"].get("histology") for a in card["observations"][card["states"][0]]["histology_report"]
            if a["status"] == "ok"]
    assert any(v is not None for v in vals)


def test_gp_note_naming_a_result_it_mentions_is_still_allowed():
    """The exemption stays for a clinician's note that states a revealing result (rule 8 as before)."""
    card = _card("lung_cancer")
    st = card["states"][0]
    own = [v for v, f in card["hidden"]["findings"][st].items()
           if f["value"] not in (None, False) and f["caused_by"] == ["lung_cancer"]]
    gp = next(n for n in card["notes"] if n["kind"] == "gp_note" and n["state"] == st)
    gp["text"], gp["mentions"] = "Findings in keeping with lung cancer; referred.", own[:1]
    assert not [p for p in _flags(card) if p.path.startswith("notes[") and card["notes"][int(p.path[6])]["kind"] == "gp_note"]


def test_no_output_or_label_of_the_catalogue_names_a_condition_outside_its_definitive_test():
    """The synonyms never flag a report that only describes its values ("recurrent chest infection", "malignant
    cells", "suspicious for malignancy" stay allowed)."""
    from patient_engine.validate import condition_pattern
    for c in CAT.conditions.values():
        if c.cls == "healthy":
            continue
        rx = condition_pattern(c)
        for t in CAT.tests.values():
            if any(o.measures == f"dx_{c.id}" for o in t.outputs):
                continue
            words = [t.label.lower(), *(o.id.replace("_", " ") for o in t.outputs),
                     *(str(v).replace("_", " ") for o in t.outputs
                       for v in (o.values or CAT.variables[o.measures].values or ()))]
            for w in words:
                assert not rx.search(w), (c.id, t.id, w)
        for v in CAT.variables.values():
            if v.kind == "symptom":
                assert not rx.search(v.label.lower()), (c.id, v.id)
