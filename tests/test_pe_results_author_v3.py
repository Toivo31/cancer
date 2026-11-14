"""Result author g2@3 (review w8 B1, decision D65): report wording per result pattern, written from one result's own
values only and shared by every card (the report bank). All offline with the reference fake."""

from __future__ import annotations

import json
import re
import threading

import pytest

from patient_engine import authors as A
from patient_engine.authors import (N_VARIANTS, Authors, ReportBank, fill_report, report_pattern, report_user)
from patient_engine.card import card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.library import load_library
from patient_engine.llm import FakeLLMClient
from patient_engine.pipeline import (_fake_g2v3, generate_card, generate_library_with_report, parse_bank_prompt,
                                     reference_fake_client)
from patient_engine.reveal import SAFE_RESULTS_PROMPTS, RevealHandle, results_text_is_safe
from patient_engine.skeleton import make_design, make_skeleton
from patient_engine.validate import has_errors, validate_card

LUNG = "catalogue/lung-primary-care"


@pytest.fixture(scope="module")
def lung():
    return load_catalogue(LUNG)


@pytest.fixture(scope="module")
def lib(lung, tmp_path_factory):
    """A 44-card fake g2@3 library, its report and the fake client's calls."""
    design = make_design(lung, {k: 4 for k in lung.conditions})
    fake = reference_fake_client(lung, design, 5)
    out = tmp_path_factory.mktemp("v3") / "L"
    manifest, rep = generate_library_with_report(lung, design, 5, fake, out_dir=out,
                                                 config=A_config(concurrency=8))
    return load_library(out, lung), rep, fake


def A_config(**kw):
    from patient_engine.pipeline import GenerationConfig
    return GenerationConfig(**kw)


def test_g2v3_is_the_default_and_the_only_safe_version():
    assert A.PROMPT_VERSIONS["results"] == "g2@3"
    assert SAFE_RESULTS_PROMPTS == {"g2@3"}


def test_bank_prompt_is_a_function_of_the_test_and_pattern_only(lung, lib):
    """Every attempt of every card whose result shows the same pattern sends byte-identical prompts; the prompt
    names no other test and nothing of the patient."""
    library, _, _ = lib
    seen: dict[tuple, str] = {}
    authors = Authors(lung)
    for c in library.cards:
        bg = c.background
        for st in c.states:
            for tid, atts in c.observations[st].items():
                test = lung.tests[tid]
                for a in atts:
                    pat = report_pattern(test, a.status, dict(a.values))
                    req = authors.bank_request(test, pat)
                    assert seen.setdefault((tid, pat), req["user"]) == req["user"]
                    assert c.id not in req["user"] and st not in req["user"].replace("status", "")
                    assert f"age {bg['age']}" not in req["user"] and "pack-years" not in req["user"]
                    assert re.findall(r"^Test: (\S+)$", req["user"], re.M) == [tid]          # one test
                    lines = re.findall(r"^- ([a-z0-9_]+): ", req["user"], re.M)
                    assert lines in ([], [o.id for o in test.outputs])                   # its own outputs only


def test_no_condition_or_number_in_any_bank_prompt(lung, lib):
    """No condition label or id outside a definitive test's own name, and no measured number (placeholders only)."""
    _, _, fake = lib
    names = {c.id: {c.label.lower(), c.id.replace("_", " ")} for c in lung.conditions.values() if c.cls != "healthy"}
    bank = [(s, u) for s, u in fake.calls if "RESULT OF ONE ATTEMPT" in u]
    assert bank
    for _, user in bank:
        tid, pat = parse_bank_prompt(lung, user)
        own = {o.measures[3:] for o in lung.tests[tid].outputs if o.measures.startswith("dx_")}
        result = user.split("RESULT OF ONE ATTEMPT")[1].lower().replace("_", " ")
        for cid, ns in names.items():
            if cid not in own:
                assert not any(n in result for n in ns), (tid, cid)
        assert not re.search(r":\s*\d", result), result


def test_one_bank_call_per_pattern_even_with_threads(lung, lib):
    library, rep, fake = lib
    pats = {(t, report_pattern(lung.tests[t], a.status, dict(a.values)))
            for c in library.cards for st in c.states for t, atts in c.observations[st].items() for a in atts}
    bank = [u for _, u in fake.calls if "RESULT OF ONE ATTEMPT" in u]
    assert len(bank) == len(set(bank)) == len(pats)
    assert rep.calls == len(library.cards) + len(pats) and rep.prompts["results"] == "g2@3"


def test_every_report_is_a_bank_wording_with_its_numbers(lung, lib):
    library, _, fake = lib
    variants: dict[tuple, list[str]] = {}
    for s, u in list(fake.calls):
        if "RESULT OF ONE ATTEMPT" in u:
            tid, pat = parse_bank_prompt(lung, u)
            variants[(tid, pat)] = _fake_g2v3(lung, u)["variants"]
    for c in library.cards:
        assert results_text_is_safe(c.provenance) and c.provenance.prompts["results"] == "g2@3"
        assert not has_errors(validate_card(card_to_json(c), lung))
        for st in c.states:
            for tid, atts in c.observations[st].items():
                test = lung.tests[tid]
                for a in atts:
                    opts = [fill_report(v, test, dict(a.values))
                            for v in variants[(tid, report_pattern(test, a.status, dict(a.values)))]]
                    assert a.report in opts


def test_reveal_serves_the_stored_g2v3_report(lung, lib):
    library, _, _ = lib
    c = library.cards[0]
    h = RevealHandle(c, catalogue=lung)
    assert h.reveal("chest_xray", 0).report == c.observations["all_active"]["chest_xray"][0].report


def test_gp_note_repeats_first_contact_reports(lung, lib):
    library, _, _ = lib
    for c in library.cards:
        for n in c.notes:
            if n.kind != "gp_note":
                continue
            assert set(n.mentions) <= {"history", "examination", "chest_xray"}
            for t in n.mentions:
                assert c.observations[n.state][t][0].report in n.text


def test_variant_choice_does_not_depend_on_the_plan(lung):
    """The wording picked for an attempt is keyed on (seed, index, state, test, attempt): the same skeleton gives
    the same reports, and the pick is spread over the variants."""
    design = make_design(lung, {k: 2 for k in lung.conditions})
    fake = reference_fake_client(lung, design, 3)
    authors = Authors(lung)
    sk = make_skeleton(lung, 0, design, 3)
    a = generate_card(authors, sk, fake).card
    b = generate_card(Authors(lung), sk, reference_fake_client(lung, design, 3)).card
    assert a["observations"] == b["observations"]
    picks = [int(m.group(1)) for atts in a["observations"]["all_active"].values() for x in atts
             for m in [re.search(r"wording (\d)", x["report"])] if m]
    assert len(set(picks)) >= 3


def test_fill_report_writes_numbers_with_units(lung):
    ct = lung.tests["chest_ct"]
    vals = {"lesion_seen": True, "suspicious_for_malignancy": False, "nodes_enlarged": False, "size_mm": 14.0,
            "location": "peripheral"}
    pat = report_pattern(ct, "ok", vals)
    assert ("size_mm", "{size_mm}") in pat and ("location", "peripheral") in pat
    assert fill_report("A {size_mm} peripheral nodule.", ct, vals) == "A 14 mm peripheral nodule."
    assert "{size_mm}" in report_user(ct, pat) and "14" not in report_user(ct, pat)


# ---------------------------------------------------------------- the bank checks and repairs

def _answer(*texts):
    return {"variants": list(texts)}


def test_bank_problems_catch_names_placeholders_contradictions_and_repeats(lung):
    authors = Authors(lung)
    xr = lung.tests["chest_xray"]
    pat = report_pattern(xr, "ok", {"abnormal": True, "consolidation": False})
    good = _answer("Abnormal chest film; no consolidation.", "The radiograph is abnormal, without consolidation.",
                   "Abnormal appearances, no consolidation seen.", "Chest X-ray abnormal. No consolidation.")
    assert authors.bank_problems(xr, pat, good) == []
    bad = _answer("Abnormal film suggesting a tumour; no consolidation.", "Abnormal; consolidation is seen.",
                  "Abnormal chest film; no consolidation.", "Abnormal film, {size_mm}, no consolidation.")
    codes = {p.path: p.code for p in authors.bank_problems(xr, pat, bad)}
    assert codes == {"variants[0]": "card_reveals_condition", "variants[1]": "card_report_contradiction",
                     "variants[3]": "card_schema"}
    repeat = _answer(*good["variants"][:3], good["variants"][0].upper())
    assert [(p.path, p.code) for p in authors.bank_problems(xr, pat, repeat)] == [("variants[3]", "card_schema")]
    assert authors.bank_good(xr, pat, bad) == ("Abnormal chest film; no consolidation.",)
    ct = lung.tests["chest_ct"]
    pat = report_pattern(ct, "ok", {"lesion_seen": True, "suspicious_for_malignancy": True, "nodes_enlarged": False,
                                    "size_mm": 9.0, "location": "central"})
    probs = authors.bank_problems(ct, pat, _answer(*(["A central lesion suspicious for malignancy, no enlarged nodes."] * 4)))
    assert {p.code for p in probs} == {"card_schema"}                                     # missing {size_mm}
    unit = [f"A central {{size_mm}} mm lesion suspicious for malignancy, no enlarged nodes ({i})." for i in range(N_VARIANTS)]
    assert all("leave the unit out" in p.message for p in authors.bank_problems(ct, pat, _answer(*unit)))


def test_definitive_test_may_name_what_it_tests_for(lung):
    authors = Authors(lung)
    t = lung.tests["dx_lung_cancer_histology"]
    pat = report_pattern(t, "ok", {"lung_cancer_confirmed": True})
    texts = [f"Histology confirms lung cancer (sample {i})." for i in range(N_VARIANTS)]
    assert authors.bank_problems(t, pat, _answer(*texts)) == []


def test_bank_repairs_with_its_own_answer_only_then_falls_back(lung):
    authors = Authors(lung)
    xr = lung.tests["chest_xray"]
    pat = report_pattern(xr, "ok", {"abnormal": True, "consolidation": True})
    users = []

    def leaky_once(system, user, schema):
        users.append(user)
        if "failed validation" in user:
            return _answer(*(f"Abnormal film with consolidation, zone {i}." for i in range(N_VARIANTS)))
        return _answer(*(f"Consolidation in keeping with pneumonia, view {i}; abnormal." for i in range(N_VARIANTS)))

    bank = ReportBank(authors, FakeLLMClient(leaky_once))
    texts = bank.texts(xr, pat)
    assert len(texts) == N_VARIANTS and all("pneumonia" not in t for t in texts) and bank.repaired == 1
    assert "names a diagnosis" in users[1] and "lung" not in users[1].split("---")[1].lower()
    assert bank.texts(xr, pat) is texts and len(users) == 2                                # memoised

    always = ReportBank(authors, FakeLLMClient(lambda s, u, sc: _answer(*(["Tumour seen; abnormal; consolidation."] * N_VARIANTS))))
    fb = always.texts(xr, pat)
    assert always.fallbacks == [("chest_xray", pat)] and len(fb) == 1 and "tumour" not in fb[0].lower()


def test_bank_is_thread_safe_one_call_per_pattern(lung):
    authors = Authors(lung)
    xr = lung.tests["chest_xray"]
    pat = report_pattern(xr, "ok", {"abnormal": False, "consolidation": False})
    n = []
    lock = threading.Lock()

    def slow(system, user, schema):
        with lock:
            n.append(1)
        return _answer(*(f"Normal chest film, no consolidation ({i})." for i in range(N_VARIANTS)))

    bank = ReportBank(authors, FakeLLMClient(slow))
    ts = [threading.Thread(target=bank.texts, args=(xr, pat)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(n) == 1


def test_estimate_counts_bank_calls_once(lung):
    from patient_engine.pipeline import estimate_cost
    design = make_design(lung, {k: 20 for k in lung.conditions})
    e = estimate_cost(lung, design, 1, sample=4)
    assert e["bank_calls_in_sample"] > 0 and e["total_calls"] == design.n + e["bank_calls_in_sample"]


def test_cli_shared_results_cache_asks_each_pattern_once_across_runs(tmp_path):
    """generate_gemini.sh runs five seeds with one ``--results-cache-dir``: a later run finds the bank answered."""
    from patient_engine.__main__ import main
    tiny = "catalogue/_examples/tiny"
    bank = tmp_path / "bank"
    args = ["generate", "--catalogue", tiny, "--n", "10", "--fake", "--results-cache-dir", str(bank)]
    assert main([*args, "--seed", "1", "--out", str(tmp_path / "A")]) == 0
    first = sum(1 for _ in bank.glob("*.json"))
    assert first > 0 and sum(1 for _ in (tmp_path / "A.work" / "cache").glob("*.json")) == 10      # G1 answers only
    assert main([*args, "--seed", "2", "--out", str(tmp_path / "B")]) == 0
    log = [json.loads(l) for l in (tmp_path / "B.work" / "cache" / "calls.jsonl").read_text().splitlines()]
    bank_log = [r for r in log if r["key"].startswith("bank:")]
    assert bank_log and sum(r["outcome"] == "cache_hit" for r in bank_log) >= len(bank_log) // 2
    assert main([*args, "--seed", "3", "--out", str(tmp_path / "C"), "--results-prompt", "g2@2"]) == 0
    assert load_library(tmp_path / "C").manifest.prompts["results"] == "g2@2"
