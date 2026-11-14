"""Patient author g1@2 (G1 skew fix): the engine draws the findings, the model writes the voice around them.

Root cause on the Gemini g1@1 libraries: one independent call per patient writes each finding at its most likely
value (every asthma card wheezes, labs sit just below their median), so audit ``findings.*`` failed for every
condition. g1@2 takes the findings from ``reference.draw_findings`` and gives the model no channel to change them.
What only a real model run can show: the quality of the texts and whether they stay consistent with the findings.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from patient_engine import authors as A
from patient_engine.audit import audit_library, load_tolerances
from patient_engine.authors import Authors
from patient_engine.card import card_from_json, card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.library import load_library
from patient_engine.pipeline import generate_card, generate_library_with_report, reference_fake_client
from patient_engine.reference import draw_findings, generate_reference
from patient_engine.skeleton import holds, make_design, make_skeleton
from pathway_sim.dists import sample

ROOT = Path(__file__).resolve().parents[1]
LUNG = ROOT / "catalogue" / "lung-primary-care"
HIDDEN_KINDS = ("lab_true", "imaging_true", "function_true", "tissue_true")


@pytest.fixture(scope="module")
def lung():
    return load_catalogue(LUNG)


@pytest.fixture(scope="module")
def design(lung):
    return make_design(lung, {k: 3 for k in lung.conditions})


def stereotyped_voice(role, cid, ans, user):
    """A model that writes every patient the same way: it reports only the first symptom it was given and copies
    one text. With g1@1 such a model also wrote the findings; with g1@2 it cannot reach them."""
    if role == "g1":
        for blk in ans["states"].values():
            blk["presenting"]["reported"] = blk["presenting"]["reported"][:1]
            blk["presenting"]["text"] = "I have had this for a few weeks and it is not going away."
            blk["account"] = {"text": "It started a while ago. I am worried and want it checked.", "mentions": []}
    return ans


def test_g1v2_is_the_default_and_g1v1_stays_selectable(lung):
    assert A.PROMPT_VERSIONS["patient"] == "g1@2"
    assert Authors(lung).prompt_versions == {"patient": "g1@2", "results": "g2@2"}
    assert Authors(lung, patient_prompt="g1@1").prompt_versions["patient"] == "g1@1"
    with pytest.raises(ValueError):
        Authors(lung, patient_prompt="g1@9")


def test_prompt_shows_symptoms_and_signs_only(lung, design):
    """The patient author sees the patient's symptoms and signs; measured, imaging and tissue truths and the
    catalogue's reference numbers stay with the engine (the account cannot hint at what its author never saw)."""
    authors = Authors(lung)
    hidden_ids = [v for v, x in lung.variables.items() if x.kind in HIDDEN_KINDS]
    for i in range(design.n):
        sk = make_skeleton(lung, i, design, 5)
        req = authors.g1_request(sk)
        for vid in hidden_ids:
            assert vid not in req["user"], (sk.id, vid)
        assert "reference" not in req["user"] and "%" not in req["user"]
        assert "findings" not in json.dumps(req["schema"])
        prof = authors.profile(sk)
        for st in sk.states:
            for vid, f in prof[st].items():
                if lung.variables[vid].kind == "symptom" and f.value is True:
                    assert f"{vid} (" in req["user"]


def test_findings_are_the_engines_whatever_the_model_writes(lung, design):
    """Same skeleton: the accepted card's findings in every state equal the reference generator's draw."""
    authors = Authors(lung)
    fake = reference_fake_client(lung, design, 5, transform=stereotyped_voice)
    for i in range(0, design.n, 3):
        sk = make_skeleton(lung, i, design, 5)
        out = generate_card(authors, sk, fake)
        assert out.status == "accepted", out.problems
        ref = card_to_json(generate_reference(lung, make_skeleton(lung, i, design, 5, plan=False)))
        assert out.card["hidden"]["findings"] == ref["hidden"]["findings"]
        assert out.card["provenance"]["prompts"]["patient"] == "g1@2"
        for st in sk.states:
            assert out.card["hidden"]["findings"][st] == {
                k: {"value": f.value, "caused_by": list(f.caused_by)} for k, f in draw_findings(lung, sk, st).items()}


def test_an_answer_that_writes_findings_is_refused_and_repaired(lung, design):
    def add_findings(role, cid, ans, user):
        if role == "g1" and "failed validation" not in user:
            for blk in ans["states"].values():
                blk["findings"] = {"cough": {"value": True, "caused_by": []}}
        return ans
    sk = make_skeleton(lung, 0, design, 5)
    fake = reference_fake_client(lung, design, 5, transform=add_findings)
    out = generate_card(Authors(lung), sk, fake)
    assert out.status == "accepted" and out.repairs == 1
    assert out.card["hidden"]["findings"]["all_active"] == {
        k: {"value": f.value, "caused_by": list(f.caused_by)} for k, f in draw_findings(lung, sk).items()}


def test_reported_symptom_must_be_present_in_the_engines_findings(lung, design):
    """The g1@2 check of ``presenting.reported`` reads the engine's findings; the repair echoes the author's own
    answer (no findings in it)."""
    authors = Authors(lung)
    sk = next(s for s in (make_skeleton(lung, i, design, 5) for i in range(design.n))
              if any(f.value is False and lung.variables[v].kind == "symptom"
                     for v, f in draw_findings(lung, s).items()))
    absent = next(v for v, f in draw_findings(lung, sk).items() if lung.variables[v].kind == "symptom" and f.value is False)

    def report_absent(role, cid, ans, user):
        if role == "g1" and "failed validation" not in user:
            ans["states"]["all_active"]["presenting"]["reported"].append(absent)
        return ans
    fake = reference_fake_client(lung, design, 5, transform=report_absent)
    out = generate_card(authors, sk, fake)
    assert out.status == "accepted" and out.repairs == 1
    repair = [u for s, u in fake.calls if "patient author" in s][1]
    previous = repair.split("Your previous answer:\n", 1)[1].split("\n", 1)[0]
    assert '"findings"' not in previous and absent in previous


def test_g1v1_answers_still_flow_through_g1_accept(lung, design):
    authors = Authors(lung, patient_prompt="g1@1")
    fake = reference_fake_client(lung, design, 5)
    sk = make_skeleton(lung, 2, design, 5)
    raw = fake.complete_json(**authors.g1_request(sk), key="x")
    g1, probs = authors.g1_accept(sk, raw)
    assert probs == [] and g1 is raw
    assert generate_card(authors, sk, fake).status == "accepted"


def _mode_author(lib, cat, q=0.45):
    """The failure mechanism of g1@1 as an author: each finding at its most likely value (binary true when its
    chance is at least 50%, the most likely level, a measured value at quantile ``q``), all_active of
    single-illness cards."""
    cards = []
    for c in lib.cards:
        d = card_to_json(c)
        if len(d["hidden"]["conditions"]) == 1:
            p = d["hidden"]["conditions"][0]["id"]
            facts, vals = {**d["background"], **d["hidden"]["conditions"][0]["attributes"]}, {}
            for vid in cat.generation_order(p):
                v = cat.variables.get(vid)
                if v is None:
                    continue
                if not holds(v.only_if, vals):
                    vals[vid] = None
                else:
                    spec = v.given_for(p).resolve({**facts, **{k: x for k, x in vals.items() if x is not None},
                                                   "condition": p})
                    vals[vid] = (float(spec) >= 0.5 if v.type == "binary" else max(spec, key=spec.get)
                                 if v.type == "categorical" else round(sample(spec, q), 2))
                d["hidden"]["findings"]["all_active"][vid] = {
                    "value": vals[vid], "caused_by": [p] if vals[vid] not in (None, False) and p in v.given else []}
        cards.append(card_from_json(d))
    return dataclasses.replace(lib, cards=tuple(cards))


def test_g1v2_library_passes_the_findings_audit_and_a_mode_author_fails_it(lung, tmp_path):
    """Offline proof of the mechanical part: 330 cards through the whole pipeline with a model that writes every
    patient alike pass every ``findings.*`` check; the same cards with the findings rewritten at their most likely
    values (what one call per patient does) fail them, with the cells seen on the Gemini g1@1 libraries."""
    design = make_design(lung, {k: 30 for k in lung.conditions}, 0.0)
    fake = reference_fake_client(lung, design, 3, transform=stereotyped_voice)
    generate_library_with_report(lung, design, 3, fake, out_dir=tmp_path / "L")
    lib = load_library(tmp_path / "L", lung)
    assert lib.manifest.prompts["patient"] == "g1@2"
    tol = load_tolerances(LUNG / "audit_tolerances.yaml")
    ok = {c["id"]: c for c in audit_library(lib, lung, tol)["checks"]}
    assert all(c["status"] == "pass" for k, c in ok.items() if k.startswith("findings.")), \
        [(k, c["summary"]) for k, c in ok.items() if k.startswith("findings.") and c["status"] != "pass"]
    bad = {c["id"]: c for c in audit_library(_mode_author(lib, lung), lung, tol)["checks"]}
    failed = {x["id"] for k, c in bad.items() if k.startswith("findings.") for x in c["cells"] if x["status"] == "fail"}
    assert {"pneumonia.fever", "tuberculosis.weight_loss", "tuberculosis.fever"} <= failed
    assert all(f"{c}.calcium_true<median" in failed for c in lung.conditions if f"findings.{c}" in bad)
