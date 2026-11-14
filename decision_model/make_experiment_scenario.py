"""Builds scenarios/experiments/stokstad_method_availability.yaml from the calibrated Stokstad scenario.

    python -m decision_model.make_experiment_scenario

An EXPERIMENT for open question 12 (does comparing options matter?), not a calibrated pathway.
Changes to scenarios/generated/stokstad_calibrated.yaml (`optimal` flowchart), all assumptions:

* Sampling-method choice ``method`` (right after the tumour board) has three options:
  bronchoscopy, radial EBUS (new test) and CT-guided needle biopsy, each with a chance of not
  being on offer (``availability``). No ``sample_plan`` / ``after_bronch`` mixes.
* A non-diagnostic bronchoscopy falls back to a needle biopsy (``ttnb_rescue``).
* Yields by location (non-diagnostic rates) are set so that bronchoscopy suits central lesions, needle
  biopsy suits peripheral ones and EBUS is a middle option; central lesions are 50 %.
* Flowchart ``availability``: needle biopsy wait is a published-style delay. The value of an option
  does not depend on the other options offered.
* Flowchart ``rescue_queue``: needle biopsy is booked on a capacity-limited list (``ttnb_list``)
  shared with other biopsy referrals (a second patient group that only uses that list), so its lead
  varies. The value of bronchoscopy then depends on the needle-biopsy queue (its rescue), i.e. on a
  feature of ANOTHER option on offer: the comparison-dependent case.
  Each other referral books a block of OTHER_SESSIONS sessions at once (bursty, policy-independent
  demand), so the needle-biopsy lead varies widely (roughly 1 to 35 days).
* Poisson arrivals with a warm-up, so queue load does not depend on the number of patients drawn.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"
OUT = ROOT / "scenarios" / "experiments" / "stokstad_method_availability.yaml"

LUNG, OTHER = "lung_cancer_stage_i_ii", "other_biopsy_referral"
LUNG_RATE, OTHER_RATE, OTHER_SESSIONS = 1.0, 0.025, 20   # per day; sessions booked per other referral
LUNG_SHARE = LUNG_RATE / (LUNG_RATE + OTHER_RATE)
RATE_PER_DAY = LUNG_RATE + OTHER_RATE
SAMPLING = ["method", "bronch1", "ebus1", "ttnb1", "ttnb_rescue"]
NOTE = "experiment assumption (decision_model/make_experiment_scenario.py), not sourced"


def build() -> dict:
    src = yaml.safe_load(SRC.read_text())
    sc = {k: copy.deepcopy(src[k]) for k in ("clock_start", "target_days", "age")}
    sc.update({
        "id": "stokstad_method_availability",
        "description": ("EXPERIMENT (open question 12), built from stokstad_calibrated.yaml: three sampling methods "
                        "with varying availability; in flowchart rescue_queue the needle-biopsy list is "
                        "capacity-limited and is the rescue after a non-diagnostic bronchoscopy. "
                        "Yields and capacities are assumptions. See decision_model/make_experiment_scenario.py."),
        "default_n": 3000, "warmup_days": 90,
        "arrivals": {"rate_per_day": RATE_PER_DAY, "note": NOTE},
        "conditions": [{**src["conditions"][0], "prevalence": LUNG_SHARE},
                       {"id": OTHER, "cancer": False, "prevalence": round(1 - LUNG_SHARE, 6),
                        "note": "other CT-guided biopsy referrals sharing the needle-biopsy list; " + NOTE}],
        "groups": [{"id": "lung_referral", "share_by_condition": {LUNG: 1.0, OTHER: 0.0}},
                   {"id": "other_biopsy"}],
    })
    attrs = copy.deepcopy(src["attributes"])
    attrs["location"] = {"values": {"central": 0.5, "peripheral": 0.5}, "source": "assumption", "note": NOTE}
    sc["attributes"] = attrs
    res = copy.deepcopy(src["resources"])
    res["ttnb_list"] = {"type": "server", "capacity_per_day": 2, "weekdays_only": True, "min_lead_days": 1,
                        "source": "assumption", "note": "CT-guided biopsy list shared with other referrals; " + NOTE}
    sc["resources"] = res
    tests = copy.deepcopy(src["tests"])
    report = copy.deepcopy(tests["ttnb"]["report_days"])
    tests["bronchoscopy"]["p_nondiagnostic"] = {"by": "location", "central": 0.4, "peripheral": 0.75}
    tests["bronchoscopy"]["note"] = "non-diagnostic rates: " + NOTE
    tests["ttnb"] = {**tests["ttnb"], "resource": "ttnb_list",
                     "p_nondiagnostic": {"by": "location", "central": 0.45, "peripheral": 0.1},
                     "note": "booked on ttnb_list (server) in rescue_queue; delay wait in availability; " + NOTE}
    tests["radial_ebus"] = {"confirms_diagnosis": True, "resource": "waits", "stage": "diagnosis", "invasive": True,
                            "cost_eur": 1500, "wait": {"dist": "lognormal", "median": 8, "p90": 13},
                            "service_days": 0.1, "report_days": report,
                            "p_positive": {LUNG: 1.0},
                            "p_nondiagnostic": {"by": "location", "central": 0.25, "peripheral": 0.3},
                            "source": "assumption", "note": "radial EBUS / navigation bronchoscopy; " + NOTE}
    tests["ttnb_other"] = {"kind": "test", "resource": "ttnb_list", "stage": "diagnosis", "service_days": 0.1,
                           "source": "assumption", "note": "biopsy for the other referral group; " + NOTE}
    sc["tests"] = tests

    opt = src["flowcharts"]["optimal"]
    keep = ["ct", "visit", "ct_redo", "pet_on_time", "pet_triage", "pet_early_route", "pet_early", "pet_scan",
            "workup", "pet", "ex_test", "exercise", "mdt", "book_surgery", "book_rt"]
    by_id = {n["id"]: copy.deepcopy(n) for n in opt["nodes"]}
    nodes = [by_id[k] for k in keep]
    nodes[0]["when"] = "group == 'lung_referral'"
    nodes += [
        {"id": "method", "kind": "choice", "after": ["mdt"], "options": ["bronch1", "ebus1", "ttnb1"],
         "label": "Choose sampling method"},
        {"id": "bronch1", "test": "bronchoscopy", "retry": {"max": 0, "on": "nondiagnostic", "fallback": "ttnb_rescue"},
         "label": "Bronchoscopy (needle biopsy if non-diagnostic)"},
        {"id": "ebus1", "test": "radial_ebus", "label": "Radial EBUS"},
        {"id": "ttnb1", "test": "ttnb", "label": "Needle biopsy"},
        {"id": "ttnb_rescue", "test": "ttnb", "after": ["bronch1"], "when": "False",
         "label": "Needle biopsy after a non-diagnostic bronchoscopy (runs only as the fallback)"},
        {"id": "sampling_done", "after_optional": list(SAMPLING), "label": "Sampling finished"},
        {"id": "diagnosis", "kind": "milestone", "milestone": "diagnosis", "after": ["sampling_done"],
         "label": "Diagnostic workup complete"},
        by_id["treat"],
    ]
    nodes += [{"id": f"other_bx{k}", "test": "ttnb_other", "when": "group == 'other_biopsy'",
               "label": f"Other referral: biopsy session {k + 1}"} for k in range(OTHER_SESSIONS)]
    nodes.append({"id": "other_exit", "kind": "exit", "outcome": "discharged",
                  "after": [f"other_bx{k}" for k in range(OTHER_SESSIONS)], "label": "Other referral done"})
    policy = {"pet_on_time": copy.deepcopy(opt["policy"]["pet_on_time"]),
              "method": {"rules": [{"when": "location == 'central'", "choose": "bronch1"},
                                   {"when": "location == 'peripheral'", "choose": "ttnb1"}],
                         "default": "ebus1", "source": "assumption",
                         "note": "hand-written: central -> bronchoscopy, peripheral -> needle biopsy, else EBUS"}}
    delay_ttnb = {"resource": "waits", "wait": {"dist": "lognormal", "median": 8, "p90": 13}}

    def fc(desc, availability, test_overrides):
        ns = copy.deepcopy(nodes)
        next(n for n in ns if n["id"] == "method")["availability"] = availability
        d = {"description": desc, "policy": copy.deepcopy(policy), "nodes": ns}
        d["test_overrides"] = {**copy.deepcopy(opt.get("test_overrides", {})), **test_overrides}
        return d

    sc["flowcharts"] = {
        "availability": fc("Three sampling methods with varying availability; needle-biopsy wait is a delay "
                           "(option values do not depend on the other options)",
                           {"bronch1": {"p_available": 0.7}, "ebus1": {"p_available": 0.6}, "ttnb1": {"p_available": 0.6}},
                           {"ttnb": delay_ttnb}),
        "rescue_queue": fc("Needle biopsy booked on a shared capacity-limited list; it is also the rescue after a "
                           "non-diagnostic bronchoscopy, so bronchoscopy's value depends on the needle-biopsy queue",
                           {"bronch1": {"p_available": 0.8}, "ebus1": {"p_available": 0.6}}, {}),
    }
    return sc


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = "# GENERATED by `python -m decision_model.make_experiment_scenario`; edit that file, not this one.\n"
    OUT.write_text(header + yaml.safe_dump(build(), sort_keys=False, width=110))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
