"""Catalogue loader, validator and version hash (WP-C1-1, tickets T2-T4)."""

from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from patient_engine.catalogue import (CatalogueError, build_catalogue, load_catalogue, read_catalogue,
                                      validate_catalogue, version_hash)

ROOT = Path(__file__).resolve().parent.parent
TINY = ROOT / "catalogue" / "_examples" / "tiny"
BROKEN = ROOT / "catalogue" / "_examples" / "broken"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def _raw() -> dict:
    raw, problems = read_catalogue(TINY)
    assert not problems
    return copy.deepcopy(raw)


def _codes(raw) -> set[str]:
    return {p.code for p in validate_catalogue(raw) if p.severity == "error"}


def _find(entries, id_):
    return next(e for e in entries if e.get("id") == id_)


# ---------------------------------------------------------------- the tiny catalogue (acceptance)

def test_tiny_loads_without_problems(tiny):
    assert tiny.id == "tiny" and tiny.problems == ()
    assert len(tiny.version_hash) == 64


def test_tiny_has_what_acceptance_asks(tiny):
    classes = {c.cls for c in tiny.conditions.values()}
    assert len(tiny.conditions) >= 3 and {"cancer", "other_illness", "healthy"} <= classes
    cancer = next(c for c in tiny.conditions.values() if c.cls == "cancer")
    assert "stage" in cancer.attributes
    assert len(tiny.variables) >= 5
    types = {(v.kind, v.type) for v in tiny.variables.values()}
    assert ("symptom", "binary") in types and ("lab_true", "continuous") in types
    assert ("imaging_true", "size_mm") in types
    assert {"history", "blood_count", "chest_xray", "chest_ct"} <= set(tiny.tests)
    assert len(tiny.cooccurrence) >= 1


def test_outcome_command_prints_hash_and_test_count():
    out = subprocess.run([sys.executable, "-c",
                          "from patient_engine.catalogue import load_catalogue; "
                          "c = load_catalogue('catalogue/_examples/tiny'); print(c.version_hash, len(c.tests))"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    h, n = out.stdout.split()
    assert len(h) == 64 and n == "4"


def test_sources_used_counts_sources_and_assumptions(tiny):
    used = tiny.sources_used()
    assert used["BRADLEY2021"] == 2
    assert used["assumption"] > 10
    assert sum(used.values()) >= len(list(tiny.leaves()))


def test_typed_objects(tiny):
    ct = tiny.tests["chest_ct"]
    assert ct.output_ids == ("nodule_seen", "size_mm", "location")
    assert ct.max_attempts == 2 and tiny.tests["history"].max_attempts == 3
    assert ct.output("size_mm").unit == "mm" and ct.output("size_mm").only_if == "nodule_seen"
    assert ct.output("location").values == ("central", "peripheral")
    assert tiny.variables["lesion_size_mm"].only_if == "lung_lesion"
    assert tiny.tests["chest_ct"].requires == ("history",)
    assert tiny.states()[0] == "all_active" and "pneumonia_resolved" in tiny.states()


def test_positive_when_reads_outputs(tiny):
    bc = tiny.tests["blood_count"]
    assert bc.is_positive({"crp": 60.0, "hb": 130.0}) is True
    assert bc.is_positive({"crp": 5.0, "hb": 130.0}) is False
    assert tiny.tests["chest_ct"].is_positive({"nodule_seen": True, "size_mm": 12.0, "location": "central"}) is True


# ---------------------------------------------------------------- `by:` resolution

def test_by_replaces_a_probability(tiny):
    cough = tiny.variables["cough_3wk"].given_for("lung_cancer")
    assert cough.resolve({"stage": "IV"}) == 0.75
    assert cough.resolve({"stage": "I"}) == 0.6
    assert cough.resolve({}) == 0.6
    assert tiny.variables["cough_3wk"].given_for("healthy").resolve({}) == 0.05      # default


def test_by_on_background_and_condition(tiny):
    prev = tiny.conditions["lung_cancer"].prevalence
    assert prev.resolve({"smoking_status": "never"}) == 0.004
    spec = tiny.tests["chest_xray"].output("abnormal").specificity
    assert spec.resolve({"condition": "pneumonia"}) == 0.8
    assert spec.resolve({"condition": "healthy"}) == 0.902


def test_by_numeric_bands(tiny):
    sens = tiny.tests["chest_xray"].output("abnormal").sensitivity
    assert sens.resolve({"lesion_size_mm": 9.99}) == 0.4
    assert sens.resolve({"lesion_size_mm": 10.0}) == 0.8
    assert sens.resolve({"lesion_size_mm": None}) == 0.754


def test_by_partial_override_of_a_distribution_and_categorical(tiny):
    size = tiny.variables["lesion_size_mm"].given_for("lung_cancer")
    assert size.resolve({"stage": "I"}) == {"dist": "lognormal", "median": 18, "p90": 28}
    assert size.resolve({"stage": "IV"})["median"] == 30
    loc = tiny.variables["lesion_location"].given_for("lung_cancer")
    assert loc.resolve({"location": "central"}) == {"central": 1.0, "peripheral": 0.0}


def test_resolved_distribution_feeds_the_simulator_sampler(tiny):
    from pathway_sim.dists import sample
    spec = tiny.variables["crp_true"].given_for("pneumonia").resolve({})
    assert sample(spec, 0.5) == pytest.approx(80.0)


# ---------------------------------------------------------------- one test per required problem kind

def test_problem_unknown_source():
    raw = _raw()
    _find(raw["variables"], "fever")["given"]["default"]["source"] = "NOT_A_SOURCE_2099"
    probs = [p for p in validate_catalogue(raw) if p.code == "unknown_source"]
    assert len(probs) == 1
    assert probs[0].path == "variables.fever.given.default.source" and probs[0].file == "variables.yaml"


def test_problem_number_without_source():
    raw = _raw()
    _find(raw["conditions"], "pneumonia")["prevalence"] = 0.25              # bare number
    del _find(raw["tests"], "chest_xray")["cost_eur"]["source"]             # object without source
    probs = [p for p in validate_catalogue(raw) if p.code == "missing_source"]
    assert {p.path for p in probs} == {"conditions.pneumonia.prevalence", "tests.chest_xray.cost_eur"}


def test_problem_by_cycle():
    raw = _raw()
    _find(raw["variables"], "fever")["given"]["default"]["by"] = {"cough_3wk": {True: 0.2}}
    _find(raw["variables"], "cough_3wk")["given"]["default"]["by"] = {"fever": {True: 0.3}}
    probs = [p for p in validate_catalogue(raw) if p.code == "by_cycle"]
    assert len(probs) == 1
    assert "variables.fever" in probs[0].message and "variables.cough_3wk" in probs[0].message


def test_problem_by_cycle_through_only_if():
    raw = _raw()
    _find(raw["variables"], "lung_lesion")["given"]["default"]["by"] = {"lesion_size_mm": {"10..": 0.5}}
    assert "by_cycle" in _codes(raw)                     # lesion_size_mm exists only_if lung_lesion


def test_problem_prevalence_reading_a_variable_is_a_cycle():
    raw = _raw()
    _find(raw["conditions"], "pneumonia")["prevalence"]["by"] = {"fever": {True: 0.9}}
    assert "by_cycle" in _codes(raw)


def test_problem_output_measures_unknown_variable():
    raw = _raw()
    _find(_find(raw["tests"], "chest_ct")["outputs"], "nodule_seen")["measures"] = "lung_lesoin"
    probs = [p for p in validate_catalogue(raw) if p.code == "unknown_variable"]
    assert len(probs) == 1 and probs[0].hint == "Did you mean 'lung_lesion'?"


def test_problem_probability_out_of_range():
    raw = _raw()
    _find(_find(raw["tests"], "history")["outputs"], "fever")["sensitivity"]["value"] = 1.2
    _find(raw["variables"], "fever")["given"]["pneumonia"]["p"] = -0.1
    probs = [p for p in validate_catalogue(raw) if p.code == "probability_out_of_range"]
    assert {p.path for p in probs} == {"tests.history.outputs.fever.sensitivity.value",
                                        "variables.fever.given.pneumonia.p"}


def test_problem_probability_out_of_range_inside_by():
    raw = _raw()
    _find(raw["variables"], "cough_3wk")["given"]["lung_cancer"]["by"]["stage"]["IV"] = 7.5
    assert "probability_out_of_range" in _codes(raw)


def test_problem_unknown_condition_in_given():
    raw = _raw()
    g = _find(raw["variables"], "fever")["given"]
    g["pneumonai"] = g.pop("pneumonia")
    probs = [p for p in validate_catalogue(raw) if p.code == "unknown_condition"]
    assert len(probs) == 1 and probs[0].path == "variables.fever.given.pneumonai"
    assert probs[0].hint == "Did you mean 'pneumonia'?"


def test_broken_example_reports_each_mistake():
    with pytest.raises(CatalogueError) as ei:
        load_catalogue(BROKEN)
    codes = [p.code for p in ei.value.problems]
    for code in ("unknown_source", "missing_source", "by_cycle", "unknown_variable",
                 "probability_out_of_range", "unknown_condition"):
        assert codes.count(code) == 1, (code, codes)
    assert "6 error(s)" in str(ei.value)


# ---------------------------------------------------------------- further checks

def test_problem_missing_given_without_default():
    raw = _raw()
    del _find(raw["variables"], "fever")["given"]["default"]
    assert "missing_given" in _codes(raw)


def test_problem_type_mismatch():
    raw = _raw()
    _find(_find(raw["tests"], "chest_ct")["outputs"], "size_mm")["measures"] = "lung_lesion"
    assert "type_mismatch" in _codes(raw)


def test_problem_bad_expression():
    raw = _raw()
    _find(raw["tests"], "chest_xray")["positive_when"] = "abnormal or nodule_seen"     # not an output here
    raw2 = _raw()
    _find(raw2["tests"], "chest_xray")["positive_when"] = "__import__('os')"
    assert "bad_expression" in _codes(raw) and "bad_expression" in _codes(raw2)


def test_problem_unknown_reference_and_level():
    raw = _raw()
    _find(raw["variables"], "fever")["given"]["pneumonia"]["by"] = {"stge": {"IV": 0.9}}
    raw2 = _raw()
    _find(raw2["variables"], "cough_3wk")["given"]["lung_cancer"]["by"]["stage"]["V"] = 0.9
    assert "unknown_reference" in _codes(raw) and "unknown_level" in _codes(raw2)


def test_problem_overlapping_bands():
    raw = _raw()
    out = _find(_find(raw["tests"], "chest_xray")["outputs"], "abnormal")
    out["sensitivity"]["by"]["lesion_size_mm"] = {"..12": 0.4, "10..": 0.8}
    assert "bad_band" in _codes(raw)


def test_problem_categorical_shares_must_sum_to_one():
    raw = _raw()
    _find(raw["conditions"], "lung_cancer")["attributes"]["stage"]["values"]["IV"] = 0.5
    assert "values_do_not_sum_to_one" in _codes(raw)


def test_problem_bad_distribution():
    raw = _raw()
    _find(raw["variables"], "crp_true")["given"]["default"] = {"dist": "lognormal", "median": 3, "source": "assumption"}
    raw2 = _raw()
    _find(raw2["variables"], "crp_true")["given"]["default"] = {"dist": "gamma", "shape": 2, "source": "assumption"}
    assert "bad_distribution" in _codes(raw) and "bad_distribution" in _codes(raw2)


def test_problem_ambiguous_name():
    raw = _raw()
    raw["catalogue"]["background"].append({"id": "fever", "type": "binary"})
    assert "ambiguous_name" in _codes(raw)


def test_problem_bad_cooccurrence():
    raw = _raw()
    raw["cooccurrence"][0]["coexisting"] = "healthy"
    raw2 = _raw()
    raw2["cooccurrence"].append(copy.deepcopy(raw2["cooccurrence"][0]))
    raw3 = _raw()                                        # shares of one primary above 1
    raw3["conditions"].append({"id": "bronchitis", "label": "Bronchitis", "class": "other_illness",
                               "prevalence": {"value": 0.0, "source": "assumption"}})
    raw3["cooccurrence"][0]["share"]["value"] = 0.6
    raw3["cooccurrence"].append({"primary": "lung_cancer", "coexisting": "bronchitis",
                                 "share": {"value": 0.6, "source": "assumption"}})
    assert "bad_cooccurrence" in _codes(raw)
    assert "duplicate_id" in _codes(raw2)
    assert _codes(raw3) == {"bad_cooccurrence"}


def test_warnings_do_not_block_loading():
    raw = _raw()
    del _find(raw["tests"], "history")["positive_when"]
    _find(raw["conditions"], "healthy")["prevalence"]["value"] = 0.5
    cat = build_catalogue(raw)
    assert {p.code for p in cat.problems} == {"no_positive_when", "prevalence_sum"}


def test_missing_required_file(tmp_path):
    shutil.copytree(TINY, tmp_path / "c")
    (tmp_path / "c" / "tests.yaml").unlink()
    with pytest.raises(CatalogueError) as ei:
        load_catalogue(tmp_path / "c")
    assert [p.code for p in ei.value.problems] == ["file_missing"]


def test_validate_does_not_modify_raw():
    raw = _raw()
    before = copy.deepcopy(raw)
    validate_catalogue(raw)
    assert raw == before


def test_explicit_source_registry():
    raw = _raw()
    assert "unknown_source" in _codes_with(raw, sources={"SOMETHING_ELSE"})
    assert "unknown_source" not in _codes_with(raw, sources={"BRADLEY2021"})


def _codes_with(raw, sources):
    return {p.code for p in validate_catalogue(raw, sources=sources)}


# ---------------------------------------------------------------- version hash (T4)

def test_hash_is_stable_across_loads(tiny):
    assert load_catalogue(TINY).version_hash == tiny.version_hash


def test_hash_ignores_order_of_entries_and_keys(tmp_path, tiny):
    dst = tmp_path / "c"
    shutil.copytree(TINY, dst)
    for name in ("conditions.yaml", "variables.yaml", "tests.yaml"):
        data = yaml.safe_load((dst / name).read_text())
        data = [dict(reversed(list(e.items()))) for e in reversed(data)]
        for e in data:
            if "outputs" in e:
                e["outputs"] = list(reversed(e["outputs"]))
        (dst / name).write_text(yaml.safe_dump(data, sort_keys=False))
    cat = yaml.safe_load((dst / "catalogue.yaml").read_text())
    cat["background"] = list(reversed(cat["background"]))
    (dst / "catalogue.yaml").write_text(yaml.safe_dump(dict(reversed(list(cat.items()))), sort_keys=False))
    again = load_catalogue(dst)
    assert again.version_hash == tiny.version_hash
    assert list(again.conditions) != list(tiny.conditions)        # the files really were reordered


def test_hash_treats_1_and_1_0_alike():
    raw = _raw()
    raw2 = _raw()
    _find(raw2["variables"], "lung_lesion")["given"]["lung_cancer"]["p"] = 1
    assert version_hash(raw) == version_hash(raw2)


def test_hash_changes_with_one_number(tmp_path, tiny):
    dst = tmp_path / "c"
    shutil.copytree(TINY, dst)
    text = (dst / "tests.yaml").read_text()
    assert text.count("value: 0.902") == 1
    (dst / "tests.yaml").write_text(text.replace("value: 0.902", "value: 0.903"))
    assert load_catalogue(dst).version_hash != tiny.version_hash


def test_hash_changes_with_a_source_or_note():
    raw, raw2, raw3 = _raw(), _raw(), _raw()
    _find(raw2["variables"], "fever")["given"]["default"]["source"] = "BRADLEY2021"
    _find(raw3["variables"], "fever")["given"]["default"]["note"] = "changed"
    assert len({version_hash(raw), version_hash(raw2), version_hash(raw3)}) == 3


# ---------------------------------------------------------------- generation order (for the skeleton and reference generator)

def test_generation_order_puts_dependencies_first(tiny):
    order = tiny.generation_order("lung_cancer")
    assert set(order) == {"stage", "location", *tiny.variables}
    for before, after in (("stage", "cough_3wk"), ("lung_lesion", "lesion_size_mm"), ("location", "lesion_location"),
                          ("lung_lesion", "lesion_location")):
        assert order.index(before) < order.index(after)
    assert "stage" not in tiny.generation_order("healthy")


def test_generation_order_follows_by_on_variables():
    raw = _raw()
    _find(raw["variables"], "cough_3wk")["given"]["default"]["by"] = {"consolidation": {True: 0.5}}
    cat = build_catalogue(raw)
    order = cat.generation_order("pneumonia")
    assert order.index("consolidation") < order.index("cough_3wk")
