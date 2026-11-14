"""Result author g2@2 (review w7 B1): the engine decides every value, the model writes only wording from public
inputs. Offline: the reference-backed fake answers; no model is called."""

import dataclasses
import inspect
import json
import re

import pytest

from patient_engine import authors as A
from patient_engine.authors import PUBLIC_BACKGROUND, Authors, results_user
from patient_engine.card import card_from_json, card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.library import load_library
from patient_engine.pipeline import (generate_card, generate_library_with_report, parse_results_prompt,
                                     reference_fake_client)
from patient_engine.problems import Problem
from patient_engine.reference import generate_reference
from patient_engine.reveal import SAFE_RESULTS_PROMPTS, RevealHandle, results_text_is_safe
from patient_engine.skeleton import make_design, make_skeleton, settle_error_plan
from patient_engine.validate import has_errors, validate_card

LUNG = "catalogue/lung-primary-care"
TINY = "catalogue/_examples/tiny"
CATALOGUE_V1_HASH = "2bcb9c78b2e0"


@pytest.fixture(scope="module")
def lung():
    return load_catalogue(LUNG)


@pytest.fixture(scope="module")
def design(lung):
    return make_design(lung, {k: 3 for k in lung.conditions})


@pytest.fixture(scope="module")
def requests(lung, design):
    """(skeleton, state, g1 answer, plan, request) for every state of 33 cards."""
    fake = reference_fake_client(lung, design, 7)
    authors = Authors(lung)
    out = []
    for i in range(design.n):
        sk = make_skeleton(lung, i, design, 7)
        g1 = fake.complete_json(**authors.g1_request(sk), key=str(i))
        for st in sk.states:
            plan = settle_error_plan(lung, sk, authors.findings_of(g1, st), st)[st]
            out.append((sk, st, g1, plan, authors.g2_request(sk, g1, plan, st)))
    return authors, fake, out


def test_catalogue_is_still_the_locked_v1(lung):
    assert lung.version_hash.startswith(CATALOGUE_V1_HASH)


def test_g2v2_is_the_default_and_the_only_safe_version():
    assert A.PROMPT_VERSIONS["results"] == "g2@2"
    assert "g2@2" in SAFE_RESULTS_PROMPTS and "g2@1" not in SAFE_RESULTS_PROMPTS
    with pytest.raises(ValueError):
        Authors(load_catalogue(TINY), "g2@9")


def test_the_prompt_is_a_function_of_public_inputs_only(lung, requests, monkeypatch):
    """By construction: the user prompt is ``results_user(catalogue, public background, reported symptoms, values,
    gp tests)``, and nothing else reaches it. Changing every hidden input (conditions, persona, card id, region,
    state name, findings, causes) while keeping the reported values gives the same prompt, byte for byte."""
    assert list(inspect.signature(results_user).parameters) == ["cat", "background", "reported", "observations", "gp_tests"]
    authors, _, reqs = requests
    sk, st, g1, plan, req = next(r for r in reqs if r[0].coexisting and r[1] != "all_active")
    obs = authors.g2_values(sk, g1, plan, st)
    assert req["user"] == results_user(lung, sk.background, g1["states"][st]["presenting"]["reported"], obs,
                                       authors.gp_tests)
    # every hidden input changed, the engine's values pinned
    monkeypatch.setattr(Authors, "g2_values", lambda self, *a, **k: json.loads(json.dumps(obs)))
    other = next(c for c in lung.conditions if c not in (sk.primary, sk.coexisting))
    sk2 = dataclasses.replace(sk, id="other:000999", primary=other, coexisting=None, attributes={},
                              coexisting_attributes={}, brief="a completely different persona",
                              background={**sk.background, "region": "elsewhere"}, states=("all_active", "x_resolved"))
    g1b = json.loads(json.dumps(g1))
    blk = g1b["states"][st]
    for f in blk["findings"].values():
        f["caused_by"] = [other] if f["value"] else []
        if isinstance(f["value"], bool) and f["value"] is False:
            f["value"] = None
    g1b["states"]["x_resolved"] = blk
    assert authors.g2_request(sk2, g1b, plan, "x_resolved")["user"] == req["user"]
    assert authors.g2_request(sk2, g1b, plan, "x_resolved")["system"] == req["system"]


def test_no_hidden_word_in_any_g2v2_prompt(lung, requests):
    authors, _, reqs = requests
    out_ids = {o.id for t in lung.tests.values() for o in t.outputs}
    hidden_vars = [v for v in lung.variables if v not in out_ids and lung.variables[v].kind != "symptom"]
    for sk, st, g1, plan, req in reqs:
        text = (req["system"] + req["user"]).lower()
        assert sk.id.lower() not in text and sk.brief.lower() not in text
        assert str(sk.background.get("region", "\0")).lower() not in text.split("patient")[1].split("results")[0]
        for word in ("false_alarm", "false alarm", "miss", "correct", "plan", "hidden", "truth", "caused"):
            assert not re.search(rf"\b{word}\b", req["user"].lower()), (word, st)
        # test names and output ids are the catalogue's, the same for every patient (a definitive test names
        # what it tests for); everything else may not name a condition
        rest = "\n".join(l for l in req["user"].splitlines() if not l.startswith("### "))
        for o in sorted(out_ids, key=len, reverse=True):
            rest = re.sub(rf"\b{o}\b", "", rest)
        for c in lung.conditions.values():
            assert not re.search(rf"\b{re.escape(c.id)}\b", rest), c.id
            assert c.label.lower() not in rest.lower(), c.label
        assert not any(s in req["user"] for s in sk.states if s != "all_active")
        for v in hidden_vars:
            assert not re.search(rf"\b{v}\b", req["user"]), v


def test_the_prompt_shows_exactly_the_engine_values(lung, requests):
    authors, _, reqs = requests
    for sk, st, g1, plan, req in reqs[:20]:
        obs = authors.g2_values(sk, g1, plan, st)
        back = parse_results_prompt(lung, req["user"])
        assert set(back) == set(lung.tests)
        for tid, atts in obs.items():
            assert [a["status"] for a in back[tid]] == [a["status"] for a in atts]
            for a, b in zip(atts, back[tid]):
                assert b["values"] == {k: v for k, v in a["values"].items() if v is not None}


def test_engine_values_equal_the_reference_generator(lung, design):
    """Same skeleton, same findings: g2@2 values are the reference generator's (``settle_attempt``)."""
    fake = reference_fake_client(lung, design, 7)
    authors = Authors(lung)
    for i in (0, 5, 17):
        sk = make_skeleton(lung, i, design, 7)
        ref = card_to_json(generate_reference(lung, make_skeleton(lung, i, design, 7, plan=False)))
        out = generate_card(authors, sk, fake)
        assert out.status == "accepted"
        for st in sk.states:
            for tid, atts in ref["observations"][st].items():
                assert [(a["status"], a["values"]) for a in out.card["observations"][st][tid]] == \
                       [(a["status"], a["values"]) for a in atts]


def test_schema_is_short_reports_and_a_gp_note(lung, requests):
    authors, fake, reqs = requests
    sch = reqs[0][4]["schema"]
    assert set(sch["properties"]) == {"reports", "gp_note"}
    assert len(json.dumps(sch)) < len(json.dumps(authors.g2_schema)) / 3
    ans = fake.complete_json(**reqs[0][4], key="z")
    assert authors.g2_problems(ans) == []
    assert all(len(v) == lung.tests[t].max_attempts for t, v in ans["reports"].items())


def test_name_check_is_condition_blind(lung, requests):
    authors, fake, reqs = requests
    ans = fake.complete_json(**reqs[0][4], key="z")
    bad = json.loads(json.dumps(ans))
    bad["reports"]["chest_xray"][0] = "Right lower lobe consolidation in keeping with pneumonia."
    bad["reports"]["dx_pneumonia_chest_xray"][0] = "Film read for pneumonia: pneumonia confirmed."   # definitive: allowed
    bad["gp_note"]["text"] = "Probably asthma; spirometry arranged."
    probs = authors.g2_problems(bad)
    assert {p.path for p in probs} == {"reports.chest_xray[0]", "gp_note.text"}
    assert all("pneumonia" not in p.message and "asthma" not in p.message for p in probs)


def test_g2v2_repair_text_names_no_condition_no_state_no_card(lung):
    authors = Authors(lung)
    probs = [Problem("card_reveals_condition", "the text names the hidden primary condition (Pneumonia (radiograph-confirmed))",
                     "observations.pneumonia_resolved.chest_xray[1].report", "rephrase"),
             Problem("card_plan_mismatch", "lesion_seen is planned miss", "observations.all_active.chest_ct[0].values"),
             Problem("card_report_contradiction", "the report says abnormal is absent, but chest_xray.abnormal is true",
                     "observations.pneumonia_resolved.chest_xray[0].report", "make the report agree with the values"),
             Problem("card_reveals_condition", "the text names the hidden primary condition (Lung cancer)", "notes[3].text")]
    text = authors.repair_text("g2", "lung_primary_care.s1:000004", probs)
    low = text.lower()
    for word in ("pneumonia", "lung cancer", "resolved", "miss", "planned", "000004", "observations."):
        assert word not in low, word
    assert "reports.chest_xray[1]" in text and "reports.chest_xray[0]" in text and "gp_note.text" in text
    assert "abnormal is absent" in text


def test_a_named_diagnosis_is_repaired_without_telling_the_model_anything_hidden(lung, design):
    sk = next(s for s in (make_skeleton(lung, i, design, 7) for i in range(design.n)) if s.primary == "lung_cancer")
    seen = []

    def leak(role, cid, ans, user):
        if role == "g2" and "failed validation" not in user:
            ans["reports"]["chest_ct"][0] = "Spiculated mass, appearances of lung cancer."
        seen.append(user)
        return ans

    fake = reference_fake_client(lung, design, 7, transform=leak)
    out = generate_card(Authors(lung), sk, fake)
    assert out.status == "accepted" and out.repairs == 1
    repair = fake.calls[-1][1].split("Your previous answer")[1].split("}\n\n", 1)[1]
    assert "reports.chest_ct[0]" in repair and "lung cancer" not in repair.lower() and sk.id not in fake.calls[-1][1]
    assert out.card["provenance"]["prompts"]["results"] == "g2@2"


def test_library_end_to_end_records_g2v2_and_reveal_serves_its_reports(lung, tmp_path):
    design = make_design(lung, {k: 2 for k in lung.conditions})
    manifest, rep = generate_library_with_report(lung, design, 3, reference_fake_client(lung, design, 3),
                                                 out_dir=tmp_path / "L")
    assert rep.accepted == design.n and manifest.prompts["results"] == "g2@2" and rep.prompts["results"] == "g2@2"
    lib = load_library(tmp_path / "L", lung)
    for c in lib.cards:
        assert results_text_is_safe(c.provenance)
        assert not has_errors(validate_card(card_to_json(c), lung))
        h = RevealHandle(c, catalogue=lung)
        assert h.reveal("chest_xray", 0).report == c.observations["all_active"]["chest_xray"][0].report


def test_estimate_is_smaller_than_g2v1(lung):
    from patient_engine.pipeline import estimate_cost
    design = make_design(lung, {k: 2 for k in lung.conditions})
    new, old = estimate_cost(lung, design, 1, sample=4), estimate_cost(lung, design, 1, sample=4, results_prompt="g2@1")
    assert new["calls_per_card"] == old["calls_per_card"]
    assert new["input_tokens_per_card"] < old["input_tokens_per_card"]


def test_audit_report_wording_skips_small_and_passes_template_libraries(lung, tmp_path):
    from patient_engine.audit import audit_library, load_tolerances
    tol = load_tolerances(f"{LUNG}/audit_tolerances.yaml")        # the locked file has no entry: built-in default
    assert tol["checks"]["report_wording"]["pp"] == 15.0
    design = make_design(lung, {k: 1 for k in lung.conditions})
    generate_library_with_report(lung, design, 3, reference_fake_client(lung, design, 3), out_dir=tmp_path / "S")
    rep = audit_library(load_library(tmp_path / "S", lung), lung, tol)
    chk = next(c for c in rep["checks"] if c["id"] == "report_wording")
    assert chk["status"] == "pass"                                     # template text: no gap, no excess
    tiny = load_catalogue(TINY)
    d2 = make_design(tiny, {"lung_cancer": 1, "pneumonia": 1})
    generate_library_with_report(tiny, d2, 3, reference_fake_client(tiny, d2, 3), out_dir=tmp_path / "T")
    rep2 = audit_library(load_library(tmp_path / "T", tiny), tiny, None)
    assert next(c for c in rep2["checks"] if c["id"] == "report_wording")["status"] == "skipped"
