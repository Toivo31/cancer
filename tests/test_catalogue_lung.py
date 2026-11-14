"""Checks on the first real clinical catalogue, catalogue/lung-primary-care (WP-C2-1).

Covers: it loads without warnings, sizes are in the planned ranges, every output measures a variable, the seven
Finnish scenario conditions are representable, the sourced numbers of params/test_accuracy.yaml and
scenarios/finland_lung.yaml are carried with the same source id, no number lacks a source or is an unchecked
llm_draft, and scripts/catalogue_stats.py runs. All content is synthetic-world and still `status: draft`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from patient_engine.catalogue import load_catalogue

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / "catalogue" / "lung-primary-care"


@pytest.fixture(scope="module")
def cat():
    return load_catalogue(str(CAT))


@pytest.fixture(scope="module")
def raw():
    return {f: yaml.safe_load((CAT / f"{f}.yaml").read_text()) for f in ("catalogue", "conditions", "variables", "tests", "cooccurrence")}


@pytest.fixture(scope="module")
def accuracy():
    return yaml.safe_load((ROOT / "params" / "test_accuracy.yaml").read_text())


@pytest.fixture(scope="module")
def scenario():
    return yaml.safe_load((ROOT / "scenarios" / "finland_lung.yaml").read_text())


# ---------------------------------------------------------------- loads, sizes
def test_loads_without_errors_or_warnings(cat):
    assert len(cat.problems) == 0
    assert cat.status == "draft"          # a clinician has not read it
    assert cat.id == "lung_primary_care"


def test_counts_in_planned_ranges(cat):
    assert 8 <= len(cat.conditions) <= 12
    assert 25 <= len(cat.variables) <= 40
    assert 15 <= len(cat.tests) <= 20


def test_every_output_measures_a_variable_of_matching_type(cat):
    for t in cat.tests.values():
        assert t.outputs, t.id
        for o in t.outputs:
            assert o.measures in cat.variables, (t.id, o.id)
            assert cat.variables[o.measures].type == o.type or (o.type == "size_mm" and cat.variables[o.measures].type == "size_mm"), (t.id, o.id)


def test_prevalence_adds_up_to_one_at_every_smoking_level(cat):
    for level in (None, "never", "former", "current"):
        facts = {"smoking_status": level} if level else {}
        assert sum(c.prevalence.resolve(facts) for c in cat.conditions.values()) == pytest.approx(1.0, abs=1e-3), level


def test_process_steps_are_not_tests(cat):
    process = {"referral_letter", "gp_referral_letter", "referral_triage", "tumour_board", "treatment_booking", "gp_second_look",
               "symptoms_persist", "gp_represent", "specialist_visit", "nurse_assessment", "gp_assessment"}
    assert not process & set(cat.tests)


def test_expected_test_categories_present(cat):
    for tid in ("history", "examination", "blood_count", "chest_xray", "chest_ct", "low_dose_ct", "pet_ct", "spirometry",
                "bronchoscopy", "ebus_tbna", "ct_guided_biopsy", "sputum_cytology", "histology_report"):
        assert tid in cat.tests, tid


def test_cooccurrence_lung_cancer_with_pneumonia_and_copd(cat):
    pairs = {(c.primary, c.coexisting) for c in cat.cooccurrence}
    assert ("lung_cancer", "pneumonia") in pairs and ("lung_cancer", "copd_exacerbation") in pairs


# ---------------------------------------------------------------- the seven Finnish scenario conditions
SCENARIO_TO_CATALOGUE = {
    "lung_cancer_site": ["lung_cancer"],          # the two presentation variants become one condition
    "lung_cancer_nonspec": ["lung_cancer"],
    "pneumonia": ["pneumonia"],
    "copd_exacerbation": ["copd_exacerbation"],
    "benign_nodule": ["benign_nodule"],
    "other_benign": ["asthma", "heart_failure", "reflux_postinfectious_cough", "no_disease_found"],
    "self_limiting": ["viral_self_limiting"],
}


def test_scenario_conditions_are_representable(cat, scenario):
    ids = {c["id"] for c in scenario["conditions"]}
    assert ids == set(SCENARIO_TO_CATALOGUE)
    for sid, targets in SCENARIO_TO_CATALOGUE.items():
        assert targets and all(t in cat.conditions for t in targets), sid
    # the scenario's two cancer variants sum to 0.016: that is the high bound of the sourced lung cancer share
    scen_lc = sum(c["prevalence"] for c in scenario["conditions"] if c["id"].startswith("lung_cancer"))
    assert cat.conditions["lung_cancer"].prevalence.high == pytest.approx(scen_lc)


# ---------------------------------------------------------------- migration of sourced numbers (K2)
def out(cat, test, output):
    return cat.tests[test].output(output)


def test_chest_xray_migrated(cat, accuracy):
    o = out(cat, "chest_xray", "abnormal")
    a = accuracy["chest_xray"]
    assert o.sensitivity.source == a["sensitivity_symptomatic"]["source"] == "BRADLEY2021"
    assert o.sensitivity.params["value"] == a["sensitivity_symptomatic"]["value"]
    assert o.specificity.params["value"] == a["specificity_symptomatic"]["value"]
    assert o.specificity.source == "BRADLEY2021"
    # unspecified lesion size and condition give the carried base
    assert o.specificity.resolve({}) == a["specificity_symptomatic"]["value"]
    # the by-size assumption keeps the cancer average at the carried 0.754 (stage I median 20 mm, others median 30 mm)
    from statistics import NormalDist
    import math
    n = NormalDist()

    def cdf(x, med, p90):
        return n.cdf(math.log(x / med) / (math.log(p90 / med) / 1.2816))

    mix = [(0.17, 20, 35), (0.83, 30, 70)]
    bands = [(None, 10), (10, 20), (20, None)]
    mean = 0.0
    for (lo, hi), size in zip(bands, (5, 15, 40)):
        share = sum(w * ((cdf(hi, m, p) if hi else 1) - (cdf(lo, m, p) if lo else 0)) for w, m, p in mix)
        mean += share * o.sensitivity.resolve({"lesion_size_mm": size})
    assert mean == pytest.approx(a["sensitivity_symptomatic"]["value"], abs=0.005)
    assert o.sensitivity.high == pytest.approx(1 - a["miss_rate_hssib"]["value"])


def test_low_dose_ct_migrated(cat, accuracy):
    o = out(cat, "low_dose_ct", "suspicious_nodule")
    a = accuracy["low_dose_ct"]
    assert (o.sensitivity.params["value"], o.sensitivity.source) == (a["sensitivity_screening"]["value"], "HOREWEG2014")
    assert (o.specificity.params["value"], o.specificity.source) == (a["specificity_screening"]["value"], "HOREWEG2014")


def test_pet_ct_migrated_with_pet_ct_meta_analysis_as_low_bound(cat, accuracy):
    o = out(cat, "pet_ct", "fdg_avid")
    a = accuracy["pet_ct"]
    assert (o.sensitivity.params["value"], o.sensitivity.source) == (a["sensitivity_malignant_lesion"]["value"], "GOULD2001")
    assert (o.specificity.params["value"], o.specificity.source) == (a["specificity_malignant_lesion"]["value"], "GOULD2001")
    assert o.sensitivity.low == 0.89 and o.specificity.low == 0.70          # LI2018, the pooled value
    assert "LI2018" in o.sensitivity.note and "LI2018" in o.specificity.note
    assert "0.02" in cat.tests["pet_ct"].note and "STOKSTAD2019" in cat.tests["pet_ct"].note   # plan changed by PET-CT, no field for it


def test_bronchoscopy_sensitivity_by_location_and_size(cat, accuracy):
    s = out(cat, "bronchoscopy", "malignant_cells").sensitivity
    a = accuracy["bronchoscopy"]
    assert s.source == "RIVERA2013"
    assert s.resolve({"lesion_location": "central", "lesion_size_mm": 10}) == a["sensitivity_central_endobronchial"]["value"]
    assert s.resolve({"lesion_location": "peripheral", "lesion_size_mm": 30}) == a["sensitivity_peripheral_over_2cm"]["value"]
    assert s.resolve({"lesion_location": "peripheral", "lesion_size_mm": 12}) == a["sensitivity_peripheral_under_2cm"]["value"]
    assert cat.tests["bronchoscopy"].harm["pneumothorax"].params["value"] == a["complication_pneumothorax"]["value"]
    assert out(cat, "bronchoscopy", "malignant_cells").specificity.params["value"] == a["specificity"]["value"]


def test_needle_biopsy_migrated(cat, accuracy, scenario):
    t = cat.tests["ct_guided_biopsy"]
    o = t.output("malignant_cells")
    a = accuracy["transthoracic_needle_biopsy"]
    assert (o.sensitivity.params["value"], o.sensitivity.source) == (a["sensitivity"]["value"], "RIVERA2013")
    # the scenario never lets a non-cancer patient test positive on the needle: specificity 1.0
    assert scenario["tests"]["ttnb"]["p_positive"]["default"] == 0.0
    assert o.specificity.params["value"] == 1.0
    assert (t.nondiagnostic.params["value"], t.nondiagnostic.source) == (a["p_nondiagnostic"]["value"], "UZUN2017")
    assert t.nondiagnostic.resolve({"lesion_location": "central"}) == scenario["tests"]["ttnb"]["p_nondiagnostic"]["central"]
    assert (t.harm["pneumothorax"].params["value"], t.harm["pneumothorax"].source) == (a["pneumothorax_any"]["value"], "WIENER2011")
    assert t.harm["chest_tube"].params["value"] == a["pneumothorax_chest_tube"]["value"]
    # pooled-versus-carried: HUO2020 pooled values are the high bound, named in the note
    assert t.harm["pneumothorax"].high == 0.259 and "HUO2020" in t.harm["pneumothorax"].note


def test_mediastinal_staging_migrated(cat, accuracy):
    m = accuracy["mediastinal_staging"]
    ct = out(cat, "chest_ct", "nodes_enlarged")
    pet = out(cat, "pet_ct", "nodes_avid")
    eb = out(cat, "ebus_tbna", "nodes_malignant")
    assert (ct.sensitivity.params["value"], ct.specificity.params["value"]) == (m["ct_sensitivity"]["value"], m["ct_specificity"]["value"])
    assert (pet.sensitivity.params["value"], pet.specificity.params["value"]) == (m["pet_sensitivity"]["value"], m["pet_specificity"]["value"])
    assert eb.sensitivity.params["value"] == m["ebus_tbna_sensitivity"]["value"]
    assert eb.sensitivity.low == m["ebus_tbna_sensitivity_unselected"]["value"]           # carried 0.76 (ALMEIDA2012) as the low bound
    assert eb.specificity.params["value"] == m["ebus_tbna_specificity"]["value"]
    for o in (ct, pet, eb):
        assert o.sensitivity.source == "GELBERG2014"


def numbers_by_source(node, inherited=None, found=None):
    """Every (source, number-as-text) in the raw YAML where a number is `value`, `p`, `low`, `high`, or a median/p90, plus note text."""
    found = {"nums": set(), "notes": ""} if found is None else found
    if isinstance(node, dict):
        src = node.get("source", inherited)
        for k in ("value", "p", "low", "high", "median", "p90"):
            if isinstance(node.get(k), (int, float)) and src:
                found["nums"].add((src, float(node[k])))
        if isinstance(node.get("note"), str):
            found["notes"] += " " + node["note"]
        for k, v in node.items():
            numbers_by_source(v, src if k in ("by",) or isinstance(v, dict) else inherited, found)
    elif isinstance(node, list):
        for v in node:
            numbers_by_source(v, inherited, found)
    return found


# values in params/test_accuracy.yaml that have no leaf slot in the format; they live in a note under the same source id
NOTE_ONLY = {
    ("chest_xray", "negative_predictive_value"): "0.997",
    ("chest_xray", "miss_rate_hssib"): "0.20",
    ("low_dose_ct", "positive_predictive_value_screening"): "0.404",
    ("pet_ct", "treatment_plan_changed_by_pet_ct"): "0.02",
    ("mediastinal_staging", "ebus_tbna_npv"): "0.91",
    ("mediastinal_staging", "ebus_tbna_sensitivity_unselected"): "0.76",   # carried as the low bound of the EBUS sensitivity
    ("bronchoscopy", "radial_ebus_diagnostic_yield_peripheral"): "0.73",
}


def test_every_sourced_number_of_test_accuracy_is_carried(raw, accuracy):
    found = {"nums": set(), "notes": ""}
    for part in (raw["tests"], raw["variables"], raw["conditions"]):
        numbers_by_source(part, None, found)
    missing = []
    for group, entries in accuracy.items():
        for key, e in entries.items():
            if e["source"] == "assumption":
                continue
            if (group, key) in NOTE_ONLY:
                if e["source"] not in found["notes"] and e["source"] not in {s for s, _ in found["nums"]}:
                    missing.append((group, key, "source not mentioned"))
                if NOTE_ONLY[(group, key)] not in found["notes"]:
                    missing.append((group, key, "value not in a note"))
                continue
            if (e["source"], float(e["value"])) not in found["nums"]:
                missing.append((group, key, e["source"], e["value"]))
    assert not missing, missing


def test_scenario_sourced_test_values_are_carried(raw, scenario):
    found = {"nums": set(), "notes": ""}
    numbers_by_source(raw["tests"], None, found)
    t = scenario["tests"]
    assert ("BRADLEY2021", 0.754) in found["nums"]                       # chest X-ray note: sensitivity 0.754 (86/114)
    assert ("UZUN2017", 0.027) in found["nums"]
    assert ("PIRHA_PATH", 7.0) in found["nums"]                          # CT report within a week, bronchoscopy 3-5 d
    assert ("STOKSTAD2019", 2.5) in found["nums"] and ("STOKSTAD2019", 4.5) in found["nums"]
    assert t["pet_ct"]["report_days"]["median"] == 2.5 and t["ttnb"]["report_days"]["median"] == 4.5
    for tid, cost in (("chest_xray", 40), ("chest_ct", 250), ("bronchoscopy", 1200), ("ct_guided_biopsy", 900), ("pet_ct", 1500)):
        assert (t[{"ct_guided_biopsy": "ttnb"}.get(tid, tid)]["cost_eur"]) == cost


# ---------------------------------------------------------------- sources and honesty
def test_no_number_lacks_a_source_and_none_is_llm_draft(cat):
    for path, leaf in cat.leaves():
        assert leaf.source, path
        assert leaf.grade != "llm_draft", path
        if leaf.source == "assumption":
            assert leaf.note, f"assumption without reasoning: {path}"
            assert leaf.grade in (None, "assumption"), path


def test_notes_flag_numbers_read_through_a_summarising_tool(cat):
    registry = {s["id"] for s in yaml.safe_load((ROOT / "params" / "sources.yaml").read_text())}
    # sources that were already in params/ before the research notes (their numbers are in params/*.yaml)
    old = {"STOKSTAD2019", "IHE2026", "KHALIFE2025", "MATTILA2025", "YLE_MOT2025", "HELSINKI2025_NEWS", "BRADLEY2021", "BRADLEY2019", "HSSIB2021",
           "KOO2023", "SEWELL2020", "RIVERA2013", "SILVESTRI2013", "GELBERG2014", "ALMEIDA2012", "GOULD2001", "HOREWEG2014", "WIENER2011",
           "UZUN2017", "GLOBOCAN_FIN", "PIRHA_PATH"}
    for path, leaf in cat.leaves():
        if leaf.source != "assumption" and leaf.source in registry and leaf.source not in old:
            assert "re-check against the page" in (leaf.note or ""), path


def test_headline_numbers(cat):
    assert cat.conditions["lung_cancer"].prevalence.params["value"] == 0.013
    assert cat.conditions["lung_cancer"].prevalence.source == "BRADLEY2021"
    assert (cat.conditions["pneumonia"].prevalence.params["value"], cat.conditions["pneumonia"].prevalence.source) == (0.05, "VANVUGT2012")
    assert cat.variables["haemoptysis"].given["lung_cancer"].params["p"] == 0.202
    assert cat.variables["haemoptysis"].given["lung_cancer"].source == "ADES2014"


def test_sourced_value_wins_over_scenario_and_scenario_value_is_in_the_note(cat, scenario):
    by_id = {c["id"]: c for c in scenario["conditions"]}
    checks = {"pneumonia": ("pneumonia", "0.17"), "benign_nodule": ("benign_nodule", "0.03"), "copd_exacerbation": ("copd_exacerbation", "0.14")}
    for sid, (cid, text) in checks.items():
        assert str(by_id[sid]["prevalence"]) == text or float(text) == by_id[sid]["prevalence"]
        assert text in cat.conditions[cid].prevalence.note, cid
    assert "0.016" in cat.conditions["lung_cancer"].prevalence.note


# ---------------------------------------------------------------- the statistics script
def test_catalogue_stats_script_runs():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "catalogue_stats.py"), str(CAT)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "sourced" in r.stdout and "assumption" in r.stdout
    assert "Lung cancer share among presenters" in r.stdout and "BRADLEY2021" in r.stdout
