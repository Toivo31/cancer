"""Offline tests of the card authors G1 and G2 (prompts, schemas, routing). No model is called."""

import json
import re

import pytest

from patient_engine import authors as A
from patient_engine.authors import Authors, fill, load_prompt
from patient_engine.catalogue import load_catalogue
from patient_engine.pipeline import reference_fake_client
from patient_engine.problems import Problem
from patient_engine.skeleton import make_design, make_skeleton, settle_error_plan

LUNG = "catalogue/lung-primary-care"
TINY = "catalogue/_examples/tiny"


@pytest.fixture(scope="module")
def lung():
    return load_catalogue(LUNG)


@pytest.fixture(scope="module")
def setup(lung):
    design = make_design(lung, {k: 2 for k in lung.conditions})
    fake = reference_fake_client(lung, design, 3)
    authors = Authors(lung)
    sk = make_skeleton(lung, 4, design, 3)
    g1 = fake.complete_json(**authors.g1_request(sk), key="x")
    plan = settle_error_plan(lung, sk, authors.findings_of(g1))["all_active"]
    g2 = fake.complete_json(**authors.g2_request(sk, g1, plan), key="y")
    return authors, sk, g1, g2, plan, fake


def test_prompt_files_exist_for_every_version():
    for version in A.PROMPT_VERSIONS.values():
        for part in ("system", "user"):
            assert len(load_prompt(version, part)) > 200


def test_fill_rejects_missing_and_unused_placeholders():
    with pytest.raises(ValueError):
        fill("a $x b $y", x="1")
    with pytest.raises(ValueError):
        fill("a $x", x="1", z="2")
    assert fill("$$5 $x", x="1") == "$5 1"


def test_prompts_ask_for_english_synthetic_text_without_diagnosis():
    for v in A.PROMPT_VERSIONS.values():
        s = load_prompt(v, "system")
        assert "English" in s and "fictional" in s
        assert re.search(r"real (places|names)|No real|Do not name real", s)
        assert re.search(r"not name|without naming|leave the diagnosis out|without a diagnosis", s)


def test_g1_prompt_is_built_from_skeleton_and_catalogue(setup, lung):
    authors, sk, *_ = setup
    req = authors.g1_request(sk)
    assert sk.id in req["user"] and sk.brief in req["user"]
    assert lung.conditions[sk.primary].label in req["user"]
    for v in lung.variables:
        assert f"- {v} (" in req["user"]
    assert "reference" in req["user"]
    assert "synthetic report" not in req["user"].lower()    # no reference-generator text in a prompt


def test_g2_prompt_carries_findings_and_plan(setup, lung):
    authors, sk, g1, _, plan, _ = setup
    user = authors.g2_request(sk, g1, plan)["user"]
    for t in lung.tests.values():
        assert f"### {t.id}:" in user
        assert len(re.findall(rf"\n  attempt \d+: ", user.split(f"### {t.id}:")[1].split("###")[0])) == t.max_attempts
    for vid, f in g1["findings"].items():
        assert f"- {vid}: " in user
    assert "miss" in user or "false_alarm" in user or "correct" in user
    assert "synthetic report" not in user.lower()


def test_g2_prompt_changes_with_the_findings(setup, lung):
    authors, sk, g1, _, plan, _ = setup
    other = json.loads(json.dumps(g1))
    other["findings"]["cough"]["value"] = not other["findings"]["cough"]["value"]
    plan2 = settle_error_plan(lung, sk, authors.findings_of(other))["all_active"]
    assert authors.g2_request(sk, other, plan2)["user"] != authors.g2_request(sk, g1, plan)["user"]


def test_reference_answers_satisfy_the_author_schemas(setup):
    authors, _, g1, g2, *_ = setup
    assert authors.g1_problems(g1) == []
    assert authors.g2_problems(g2) == []


def test_g1_problems_flag_a_reported_symptom_that_is_not_true(setup, lung):
    authors, _, g1, *_ = setup
    bad = json.loads(json.dumps(g1))
    false_symptom = next(v for v, f in bad["findings"].items()
                         if lung.variables[v].kind == "symptom" and f["value"] is False)
    bad["presenting"]["reported"].append(false_symptom)
    probs = authors.g1_problems(bad)
    assert probs and "not a true symptom" in probs[0].message and probs[0].path.startswith("presenting.reported")


def test_schema_problems_for_missing_parts(setup):
    authors, _, g1, g2, *_ = setup
    assert authors.g1_problems({"findings": g1["findings"]})
    assert authors.g2_problems({"observations": {}})


def test_assemble_keeps_the_skeleton_and_plan(setup, lung):
    authors, sk, g1, g2, plan, _ = setup
    card = authors.assemble(sk, g1, g2, plan, {"library": None, "catalogue_id": lung.id, "catalogue_hash": "h",
                                               "generator": "llm", "model": "m", "prompts": {}, "error_source": "guided",
                                               "validation": {}})
    assert card["id"] == sk.id and card["background"] == sk.background
    assert card["hidden"]["conditions"][0]["id"] == sk.primary
    assert set(card["hidden"]["error_plan"]["all_active"]) == set(lung.tests)
    assert [n["kind"] for n in card["notes"]] == ["patient_account", "gp_note"]


def test_route_sends_problems_to_the_author_that_wrote_them():
    def p(path):
        return Problem("card_schema", "x", path)
    assert Authors.route(p("hidden.findings.all_active.cough.value")) == "g1"
    assert Authors.route(p("presenting.all_active.text")) == "g1"
    assert Authors.route(p("notes[0].text")) == "g1"
    assert Authors.route(p("observations.all_active.chest_xray[0].values.abnormal")) == "g2"
    assert Authors.route(p("notes[1].text")) == "g2"
    assert Authors.route(p(None)) == "g2"


def test_repair_user_contains_request_answer_and_problems(setup):
    authors, sk, g1, *_ = setup
    req = authors.g1_request(sk)
    text = authors.repair_user("g1", req["user"], g1, "- presenting: bad")
    assert req["user"] in text and "Your previous answer" in text and "- presenting: bad" in text
