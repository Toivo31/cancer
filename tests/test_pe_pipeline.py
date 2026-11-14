"""Offline tests of the generation pipeline: everything runs on the reference-backed fake client."""

import json
import threading

import pytest

from patient_engine.authors import PROMPT_VERSIONS, Authors
from patient_engine.catalogue import load_catalogue
from patient_engine.library import load_library
from patient_engine.llm import Budget, LLMClient
from patient_engine.pipeline import (GenerationConfig, GenerationError, estimate_cost, generate_card,
                                     generate_library, generate_library_with_report, reference_fake_client)
from patient_engine.skeleton import make_design, make_skeleton
from patient_engine.validate import has_errors, validate_card
from tests.test_pe_llm import Stub

TINY = "catalogue/_examples/tiny"
LUNG = "catalogue/lung-primary-care"
KEY = "sk-test-SECRET-1234567890"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


@pytest.fixture(scope="module")
def lung():
    return load_catalogue(LUNG)


def tiny_design(tiny, n):
    counts = {c: 0 for c in tiny.conditions}
    keys = list(counts)
    for i in range(n):
        counts[keys[i % len(keys)]] += 1
    return make_design(tiny, counts)


def all_files_text(*roots):
    out = []
    for r in roots:
        for p in r.rglob("*"):
            if p.is_file():
                out.append(p.read_bytes())
    return out


# ---------------------------------------------------------------- end to end

def test_50_lung_cards_offline_all_valid_and_loadable(lung, tmp_path):
    design = make_design(lung, {k: 5 for k in lung.conditions})
    assert design.n == 5 * len(lung.conditions)
    fake = reference_fake_client(lung, design, 1)
    manifest, rep = generate_library_with_report(lung, design, 1, fake, out_dir=tmp_path / "L")
    lib = load_library(tmp_path / "L", lung)
    assert len(lib) == design.n and manifest.n_cards == design.n and not rep.partial
    assert rep.accepted == design.n and rep.discarded == 0 and rep.calls == design.n + sum(len(c.states) for c in lib.cards) and rep.repairs == {"0": design.n}
    assert any(len(c.states) > 1 for c in lib.cards)           # multi-state cards are written too
    for c in lib.cards:
        from patient_engine.card import card_to_json
        j = card_to_json(c)
        assert not has_errors(validate_card(j, lung))
        assert not [p for p in validate_card(j, lung) if p.code == "card_reveals_condition"]
        pv = c.provenance
        assert pv.generator == "llm" and pv.error_source == "guided" and pv.prompts == PROMPT_VERSIONS
        assert pv.validation["ok"] and pv.validation["repairs"] == 0
        assert c.hidden.error_plan is not None


def test_same_library_whatever_the_concurrency(tiny, tmp_path):
    design = tiny_design(tiny, 12)
    ids = []
    for conc in (1, 4):
        fake = reference_fake_client(tiny, design, 2)
        m = generate_library(tiny, design, 2, fake, out_dir=tmp_path / f"L{conc}",
                             config=GenerationConfig(concurrency=conc))
        ids.append(m.id)
    assert ids[0] == ids[1]


def test_plan_in_card_is_the_settled_plan_of_the_written_findings(tiny):
    from patient_engine.skeleton import plan_to_json, settle_error_plan
    design = tiny_design(tiny, 3)
    out = generate_card(Authors(tiny), make_skeleton(tiny, 1, design, 5), reference_fake_client(tiny, design, 5))
    card = out.card
    findings = {v: f["value"] for v, f in card["hidden"]["findings"]["all_active"].items()}
    sk = make_skeleton(tiny, 1, design, 5)
    assert card["hidden"]["error_plan"] == plan_to_json(settle_error_plan(tiny, sk, findings))


# ---------------------------------------------------------------- repair

def first_ok_binary(card_obs):
    for t, atts in card_obs.items():
        for a in atts:
            if a["status"] == "ok":
                for k, v in a["values"].items():
                    if isinstance(v, bool):
                        return a, k
    raise AssertionError("no binary output")


def break_g2_once(role, cid, ans, user):
    """Contradict the plan on the first answer of G2 only (a repair prompt contains 'failed validation')."""
    if role == "g2" and "failed validation" not in user:
        a, k = first_ok_binary(ans["observations"])
        a["values"][k] = not a["values"][k]
    return ans


def test_broken_g2_then_fixed_records_one_repair(tiny):
    design = tiny_design(tiny, 3)
    fake = reference_fake_client(tiny, design, 1, transform=break_g2_once)
    out = generate_card(Authors(tiny, "g2@1"), make_skeleton(tiny, 0, design, 1), fake)   # g2@1: G2 writes values
    assert out.status == "accepted" and out.repairs == 1
    assert out.card["provenance"]["validation"]["repairs"] == 1
    assert len(fake.calls) == 3
    repair_user = fake.calls[2][1]
    assert "failed validation" in repair_user and "Your previous answer" in repair_user and "card_plan_mismatch" not in repair_user
    assert not has_errors(validate_card(out.card, tiny))


def test_broken_g1_repair_asks_g2_again_with_the_new_findings(tiny):
    design = tiny_design(tiny, 3)

    def break_g1(role, cid, ans, user):
        if role == "g1" and "failed validation" not in user:
            blk = ans["states"]["all_active"]
            false_symptoms = [v for v, f in blk["findings"].items()
                              if tiny.variables[v].kind == "symptom" and f["value"] is False]
            blk["presenting"]["reported"].append(false_symptoms[0])
        return ans

    fake = reference_fake_client(tiny, design, 1, transform=break_g1)
    out = generate_card(Authors(tiny), make_skeleton(tiny, 0, design, 1), fake)
    assert out.status == "accepted" and out.repairs == 1
    roles = ["g1" if "patient author" in s else "g2" for s, _ in fake.calls]
    assert roles[:2] == ["g1", "g1"] and set(roles[2:]) == {"g2"}      # the broken G1 never reaches G2


def always_break_g2_for(card_index):
    def f(role, cid, ans, user):
        if role == "g2" and cid.endswith(f":{card_index:06d}"):
            a, k = first_ok_binary(ans["observations"])
            a["values"][k] = not a["values"][k]
        return ans
    return f


def test_three_broken_answers_discard_the_card_and_log_it(tiny, tmp_path):
    design = tiny_design(tiny, 4)
    fake = reference_fake_client(tiny, design, 1, transform=always_break_g2_for(2))
    manifest, rep = generate_library_with_report(tiny, design, 1, fake, out_dir=tmp_path / "L",
                                                 config=GenerationConfig(concurrency=1), results_prompt="g2@1")
    assert rep.accepted == 3 and rep.discarded == 1 and not rep.partial
    lines = [json.loads(l) for l in (tmp_path / "L.work" / "discarded.jsonl").read_text().splitlines()]
    assert len(lines) == 1 and lines[0]["card_id"].endswith(":000002") and lines[0]["repairs"] == 2
    assert any("card_plan_mismatch" in p for p in lines[0]["problems"])
    assert not any(c.id.endswith(":000002") for c in load_library(tmp_path / "L").cards)
    states = {c.id: len(c.states) for c in load_library(tmp_path / "L").cards}
    bad_states = len(make_skeleton(tiny, 2, design, 1).states)
    assert rep.calls == sum(1 + n for n in states.values()) + 1 + 3 * bad_states   # G1 once, every G2 state asked 3 times


def test_all_cards_discarded_raises_and_writes_report(tiny, tmp_path):
    design = tiny_design(tiny, 2)
    fake = reference_fake_client(tiny, design, 1, transform=lambda r, c, a, u: (break_g2_once(r, c, a, "") if r == "g2" else a))
    with pytest.raises(GenerationError):
        generate_library(tiny, design, 1, fake, out_dir=tmp_path / "L", results_prompt="g2@1")
    assert not (tmp_path / "L").exists()
    assert json.loads((tmp_path / "L.work" / "generation_report.json").read_text())["accepted"] == 0


# ---------------------------------------------------------------- I1

def test_a_note_that_names_the_diagnosis_is_repaired(tiny, lung):
    design = tiny_design(tiny, 3)

    def leak(role, cid, ans, user):
        if role == "g2" and "failed validation" not in user:
            ans["gp_note"]["text"] = f"GP note: this is {leak.label}."
            ans["gp_note"]["mentions"] = []
        return ans

    sk = next(s for s in (make_skeleton(tiny, i, design, 1) for i in range(design.n))
              if tiny.conditions[s.primary].cls != "healthy")
    leak.label = tiny.conditions[sk.primary].label
    fake = reference_fake_client(tiny, design, 1, transform=leak)
    out = generate_card(Authors(tiny, "g2@1"), sk, fake)
    assert out.status == "accepted" and out.repairs == 1
    assert "names the hidden primary condition" in fake.calls[2][1]


def test_condition_label_absent_from_notes_of_fake_cards_without_revealing_fact(lung, tmp_path):
    design = make_design(lung, {k: 3 for k in lung.conditions})
    fake = reference_fake_client(lung, design, 4)
    generate_library(lung, design, 4, fake, out_dir=tmp_path / "L")
    from patient_engine.card import card_to_json
    for c in load_library(tmp_path / "L").cards:
        probs = validate_card(card_to_json(c), lung)
        assert not [p for p in probs if p.code == "card_reveals_condition"]


# ---------------------------------------------------------------- budget, resume

def test_budget_stops_cleanly_with_a_partial_library_and_resume_finishes(tiny, tmp_path):
    design = tiny_design(tiny, 8)
    work = tmp_path / "w"
    cfg = GenerationConfig(concurrency=1)
    fake = reference_fake_client(tiny, design, 1, cache_dir=work / "cache")
    manifest, rep = generate_library_with_report(tiny, design, 1, fake, budget=Budget(max_calls=5),
                                                 out_dir=tmp_path / "L", work_dir=work, config=cfg)
    assert rep.partial and rep.stop_reason == "budget" and 1 <= rep.accepted <= 3 and rep.accepted + rep.not_completed == 8
    assert len(load_library(tmp_path / "L")) == rep.accepted
    saved = json.loads((work / "generation_report.json").read_text())
    assert saved["partial"] is True and saved["library_id"] == manifest.id

    with pytest.raises(GenerationError):                      # not silently replaced
        generate_library(tiny, design, 1, reference_fake_client(tiny, design, 1, cache_dir=work / "cache"),
                         out_dir=tmp_path / "L", work_dir=work)
    fake2 = reference_fake_client(tiny, design, 1, cache_dir=work / "cache")
    m2, rep2 = generate_library_with_report(tiny, design, 1, fake2, out_dir=tmp_path / "L", work_dir=work,
                                            config=cfg, resume=True)
    assert not rep2.partial and rep2.accepted == 8
    total = sum(1 + len(make_skeleton(tiny, i, design, 1).states) for i in range(8))
    assert len(fake2.calls) == total - 5                       # the 5 answered before the stop are cached
    assert len(load_library(tmp_path / "L")) == 8
    with pytest.raises(GenerationError):                       # a complete library is never replaced
        generate_library(tiny, design, 1, fake2, out_dir=tmp_path / "L", work_dir=work, resume=True)


def test_budget_with_concurrency_never_loses_a_finished_card(tiny, tmp_path):
    design = tiny_design(tiny, 12)
    fake = reference_fake_client(tiny, design, 1)
    manifest, rep = generate_library_with_report(tiny, design, 1, fake, budget=Budget(max_calls=7),
                                                 out_dir=tmp_path / "L", config=GenerationConfig(concurrency=4))
    assert rep.partial and 1 <= rep.accepted <= 3
    assert len(load_library(tmp_path / "L")) == rep.accepted


# ---------------------------------------------------------------- key, cost, CLI

def reference_schema(authors, user):
    return {"properties": {"states": {}}}


def reference_stub(tiny, design, seed):
    fake = reference_fake_client(tiny, design, seed)
    authors = Authors(tiny)

    def echo(body):
        system, user = body["messages"][0]["content"], body["messages"][-1]["content"]
        schema = reference_schema(authors, user) if "patient author" in system else authors.results_schema
        return fake._fn(system, user, schema)
    return echo


def test_no_api_key_in_files_logs_or_exceptions(tiny, tmp_path, stub_factory_fixture=None):
    design = tiny_design(tiny, 3)
    stub = Stub(echo=reference_stub(tiny, design, 1))
    try:
        client = LLMClient(stub.url, "m", KEY, cache_dir=tmp_path / "L.work" / "cache")
        generate_library(tiny, design, 1, client, out_dir=tmp_path / "L")
        assert len(load_library(tmp_path / "L")) == 3
        assert all(KEY.encode() not in b for b in all_files_text(tmp_path))
        assert KEY not in repr(client)
    finally:
        stub.close()
    bad = Stub(script=[401] * 20)                      # a leaky server that echoes the Authorization header
    try:
        client = LLMClient(bad.url, "m", KEY, cache_dir=tmp_path / "M.work" / "cache")
        with pytest.raises(GenerationError) as e:
            generate_library(tiny, design, 1, client, out_dir=tmp_path / "M")
        assert KEY not in str(e.value)
        assert all(KEY.encode() not in b for b in all_files_text(tmp_path))
    finally:
        bad.close()


def test_estimate_cost_counts_one_g1_call_and_one_g2_call_per_state(lung):
    design = make_design(lung, {k: 3 for k in lung.conditions})
    e = estimate_cost(lung, design, 1, sample=2)
    assert 2 <= e["calls_per_card"] <= 5 and e["input_tokens_per_card"] > 1000 and e["total_calls"] == round(design.n * e["calls_per_card"])


def test_cli_fake_and_partial_exit_code(tmp_path, capsys):
    from patient_engine.__main__ import main
    out = tmp_path / "L"
    assert main(["generate", "--catalogue", TINY, "--n", "10", "--seed", "1", "--out", str(out), "--fake"]) == 0
    assert len(load_library(out)) == 10
    out2 = tmp_path / "L2"
    rc = main(["generate", "--catalogue", TINY, "--n", "10", "--seed", "1", "--out", str(out2), "--fake",
               "--max-calls", "5", "--concurrency", "1"])
    assert rc == 3 and "PARTIAL" in capsys.readouterr().err
    assert main(["generate", "--catalogue", TINY, "--n", "10", "--out", str(out2), "--fake"]) == 1   # taken
    assert main(["generate", "--catalogue", TINY, "--n", "4", "--out", str(tmp_path / "E"), "--estimate"]) == 0


def test_cli_without_endpoint_says_so_without_traceback(tmp_path, monkeypatch, capsys):
    from patient_engine.__main__ import main
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert main(["generate", "--catalogue", TINY, "--n", "4", "--out", str(tmp_path / "L")]) == 1
    assert "LLM_BASE_URL" in capsys.readouterr().err


def test_a_broken_resolved_state_repairs_only_that_states_g2(lung):
    design = make_design(lung, {k: 6 for k in lung.conditions})
    sk = next(k for k in (make_skeleton(lung, i, design, 1) for i in range(design.n)) if len(k.states) > 1)
    later = sk.states[1]

    def break_later_once(role, cid, ans, user):
        if role == "g2" and f"State: {later} " in user and "failed validation" not in user:
            a, k = first_ok_binary(ans["observations"])
            a["values"][k] = not a["values"][k]
        return ans

    fake = reference_fake_client(lung, design, 1, transform=break_later_once)
    out = generate_card(Authors(lung, "g2@1"), sk, fake)
    assert out.status == "accepted" and out.repairs == 1
    assert len(fake.calls) == 1 + len(sk.states) + 1
    assert f"State: {later} " in fake.calls[-1][1] and "failed validation" in fake.calls[-1][1]
