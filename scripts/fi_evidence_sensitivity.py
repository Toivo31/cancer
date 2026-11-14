"""Does the Finnish conclusion survive if the other evidence is right?

Builds alternative Finnish worlds from docs/evidence_research.md section 1, writes each as a scenario under
scenarios/experiments/finland_evidence_<world>.yaml, and re-evaluates today's pathway, the optimiser's suggested
pathway (runs/opt_fi_noft.json) and the four hand-written pathways on held-out cohorts, with common random numbers
(same patients, same per-patient random draws, in every world and for every pathway).

    python scripts/fi_evidence_sensitivity.py                 # about 12-20 min on one core
    python scripts/fi_evidence_sensitivity.py --worlds A,L67  # a subset
    python scripts/fi_evidence_sensitivity.py --quick         # 2 cohorts, for a smoke test

Writes docs/review_checks/fi_evidence_worlds.json (how each world was built and calibrated) and
docs/review_checks/fi_evidence_results.json (all results). Does not touch scenarios/finland_lung.yaml, params/,
the engine or the optimiser. Synthetic data only.

Worlds (what changes; everything else is the scenario as it is):
  A     the scenario as it is (control; must reproduce the pitch numbers on seeds 301 and 302)
  N37   treatment-slot booking lead recalibrated so tissue diagnosis -> treatment is exactly 37 d (the scenario's own
        stated target; as it stands it gives about 32 d)
  L67   same lead recalibrated to 67 d: the midpoint of the lung-specific Finnish medians (65 non-surgical, 69 surgical)
  L92   stress: 92 d, the upper quartile of the surgical group in that study
  X1    chest X-ray from the primary-care meta-analysis: sensitivity 0.81, specificity 0.68
  X2    chest X-ray, NSCLC in the Leeds cohort: sensitivity 0.76, specificity 0.95
  P     PET-CT instead of stand-alone PET: sensitivity 0.89, specificity 0.70
  ALT   L67 + X2 + P together (every lung-specific or more recent figure at once)
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics as st
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from optimiser.search import Config, guardrails, mean_metrics  # noqa: E402
from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate  # noqa: E402
from pathway_sim.scenario import parse_flowchart, scenario_from_dict, validate_flowchart  # noqa: E402

BASE = ROOT / "scenarios" / "finland_lung.yaml"
EXP = ROOT / "scenarios" / "experiments"
OUT = ROOT / "docs" / "review_checks"

CAL_SEEDS = (901, 902)           # calibration cohorts, never used for reporting
HELD_SEEDS = (301, 302, 303, 304)  # 301 and 302 are the headline's held-out cohorts
RANK_SEEDS = (301, 302, 303)      # the four hand-written pathways are run on these only (cost)
N = 18800                        # default_n of the scenario: 60 d warm-up + one measured year (n=2000 is all warm-up)
SUGGESTED_RUN = ROOT / "runs" / "opt_fi_noft.json"
OTHERS = ("direct_ct", "bundled_workup", "fast_track_nonspecific", "baseline_plus_capacity")

TARGETS_DIAG_TO_TREAT = {"N37": 37.0, "L67": 67.0, "L92": 92.0}
CXR = {"X1": (0.81, 0.68), "X2": (0.76, 0.95)}
PET = (0.89, 0.70)


# ---------------------------------------------------------------- building worlds
def non_cancer_weights(raw: dict) -> dict:
    return {c["id"]: c["prevalence"] for c in raw["conditions"] if not c.get("cancer")}


def weighted_fp(p_pos: dict, w: dict) -> float:
    tot = sum(w.values())
    return sum(p_pos[k] * v for k, v in w.items()) / tot


def set_accuracy(raw: dict, test_ids: list[str], sens: float, spec: float) -> dict:
    """Set cancer sensitivity and scale every non-cancer false-positive rate by one factor so that the
    prevalence-weighted specificity over the non-cancer conditions equals ``spec`` (rates capped at 0.97)."""
    w = non_cancer_weights(raw)
    info = {}
    for tid in test_ids:
        pp = raw["tests"][tid]["p_positive"]
        fp_before = weighted_fp(pp, w)
        lo, hi = 0.0, 50.0
        for _ in range(60):     # bisection on the scale factor (the cap makes it non-linear)
            k = (lo + hi) / 2
            fp = sum(min(0.97, pp[c] * k) * v for c, v in w.items()) / sum(w.values())
            lo, hi = (k, hi) if fp < 1 - spec else (lo, k)
        for c in w:
            pp[c] = round(min(0.97, pp[c] * k), 4)
        for c in ("lung_cancer_site", "lung_cancer_nonspec"):
            pp[c] = sens
        info[tid] = {"specificity_before": round(1 - fp_before, 3), "specificity_after": round(1 - weighted_fp(pp, w), 3),
                     "sensitivity_after": sens, "fp_scale": round(k, 3)}
    return info


def set_treatment_lead(raw: dict, lead: float) -> None:
    ts = raw["resources"]["treatment_slot"]
    ts["urgent_lead_days"] = lead - (ts["min_lead_days"] - ts["urgent_lead_days"])   # keep the fast lane's 4-day advantage
    ts["min_lead_days"] = lead


def build_raw(base_raw: dict, world: str, lead: float | None, notes: dict) -> dict:
    raw = copy.deepcopy(base_raw)
    raw["id"] = f"finland_evidence_{world}"
    info = {}
    if lead is not None:
        set_treatment_lead(raw, lead)
        info["treatment_slot.min_lead_days"] = round(lead, 2)
    if world in ("X1", "X2") or world == "ALT":
        sens, spec = CXR["X1" if world == "X1" else "X2"]
        info["chest_xray"] = set_accuracy(raw, ["chest_xray"], sens, spec)
    if world in ("P", "ALT"):
        info["pet_ct"] = set_accuracy(raw, ["pet_ct", "pet_ct_fast"], *PET)
    raw["description"] = (f"EXPERIMENT (scripts/fi_evidence_sensitivity.py): alternative-evidence world '{world}' built from "
                          f"scenarios/finland_lung.yaml. {notes['what']} Everything else is unchanged; not recalibrated unless "
                          f"stated. Synthetic. Do not use as the Finnish scenario. Original description follows. ") + str(base_raw.get("description", ""))
    info["what"] = notes["what"]
    raw["_evidence_world"] = info
    return raw


def write_world(raw: dict, world: str) -> Path:
    EXP.mkdir(parents=True, exist_ok=True)
    p = EXP / f"finland_evidence_{world.lower()}.yaml"
    head = ("# GENERATED by scripts/fi_evidence_sensitivity.py; edit that file, not this one.\n"
            "# Alternative-evidence world (docs/evidence_sensitivity.md). Not the Finnish scenario.\n")
    p.write_text(head + yaml.safe_dump(raw, sort_keys=False, width=140))
    return p


# ---------------------------------------------------------------- measuring
def intervals(run) -> dict:
    """Per treated cancer (measured year): days between milestones."""
    out = {"first_contact_to_treatment": [], "diagnosis_to_treatment": [], "referral_to_treatment": [], "specialist_visit_to_treatment": []}
    for pr in run.patients:
        if not pr.patient.cancer or pr.t_treatment is None or pr.patient.arrival < run.warmup_days:
            continue
        a = pr.patient.arrival
        out["first_contact_to_treatment"].append(pr.t_treatment - a)
        if pr.t_diagnosis is not None:
            out["diagnosis_to_treatment"].append(pr.t_treatment - pr.t_diagnosis)
        for key, node in (("referral_to_treatment", "referral_in"), ("specialist_visit_to_treatment", "spec_visit")):
            t = pr.t_done.get(node)
            if t is not None:
                out[key].append(pr.t_treatment - t)
    return out


def run_set(sc, fc, cohorts, targets) -> dict:
    """Run ``fc`` on each cohort; metrics at each target in ``targets`` (days)."""
    per = {t: [] for t in targets}
    iv: dict[str, list] = {}
    for seed, pts in cohorts:
        run = simulate(sc, fc, pts, seed=seed)
        for t in targets:
            run.target_days = float(t)
            per[t].append(compute_metrics(run, sc))
        for k, v in intervals(run).items():
            iv.setdefault(k, []).extend(v)
    return {"per_cohort": per, "mean": {t: mean_metrics(per[t]) for t in targets},
            "interval_median": {k: round(st.median(v), 1) if v else None for k, v in iv.items()}}


def median_diag_to_treat(sc, fc, cohorts) -> float:
    vals = []
    for seed, pts in cohorts:
        vals += intervals(simulate(sc, fc, pts, seed=seed))["diagnosis_to_treatment"]
    return st.median(vals)


def calibrate_lead(base_raw: dict, world: str, target: float, cal_cohorts, log) -> tuple[float, dict]:
    """Secant search on the treatment-slot booking lead so that the baseline pathway's median tissue diagnosis -> treatment
    equals ``target`` (tolerance 0.5 d) on the calibration cohorts."""
    def f(lead):
        raw = build_raw(base_raw, world, lead, {"what": "calibration probe"})
        sc = scenario_from_dict(raw)
        return median_diag_to_treat(sc, sc.flowcharts["baseline"], cal_cohorts)

    x0 = float(base_raw["resources"]["treatment_slot"]["min_lead_days"])
    y0 = f(x0)
    x1 = x0 + (target - y0)          # one day of lead moves the median by about one day
    y1 = f(x1)
    trace = [(x0, round(y0, 2)), (x1, round(y1, 2))]
    for _ in range(6):
        if abs(y1 - target) <= 0.5:
            break
        slope = (y1 - y0) / (x1 - x0) if x1 != x0 else 1.0
        slope = slope if slope > 0.2 else 1.0
        x0, y0 = x1, y1
        x1 = x1 + (target - y1) / slope
        y1 = f(x1)
        trace.append((round(x1, 2), round(y1, 2)))
    log(f"  calibrated {world}: lead {x1:.1f} d -> median diagnosis-to-treatment {y1:.1f} d (target {target}); trace {trace}")
    return x1, {"target": target, "achieved_on_calibration_cohorts": round(y1, 2), "trace": trace}


# ---------------------------------------------------------------- comparison helpers
def kendall_tau(a: list, b: list) -> float:
    """Kendall rank correlation of two orderings of the same items (lists of names, best first)."""
    pos_a = {x: i for i, x in enumerate(a)}
    pos_b = {x: i for i, x in enumerate(b)}
    items = list(pos_a)
    c = d = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s = (pos_a[items[i]] - pos_a[items[j]]) * (pos_b[items[i]] - pos_b[items[j]])
            c += s > 0
            d += s < 0
    return round((c - d) / max(1, c + d), 3)


def pick(m: dict, keys=("share_within_target", "median_days_to_treatment", "missed_cancers", "confirmed_cancers", "n_cancer",
                        "tests_per_patient", "invasive_per_patient", "median_days_to_exit_noncancer", "untreated_cancers", "stuck")) -> dict:
    out = {k: m.get(k) for k in keys}
    out["by_group"] = {g: {"share_within_target": v["share_within_target"], "median_days_to_treatment": v["median_days_to_treatment"],
                           "n_cancer": v["n_cancer"]} for g, v in m["by_group"].items()}
    out["max_utilisation"] = max((u for u in m["utilisation"].values() if u is not None), default=None)
    out["utilisation"] = {k: round(v, 3) for k, v in m["utilisation"].items() if v is not None}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", default="A,N37,L67,L92,X1,X2,P,ALT")
    ap.add_argument("--quick", action="store_true", help="2 cohorts and 2 for ranking (smoke test)")
    a = ap.parse_args(argv)
    worlds = a.worlds.split(",")
    held_seeds = HELD_SEEDS[:2] if a.quick else HELD_SEEDS
    rank_seeds = RANK_SEEDS[:2] if a.quick else RANK_SEEDS
    log = lambda *x: print(*x, flush=True)  # noqa: E731
    t_start = time.time()

    base_raw = yaml.safe_load(BASE.read_text())
    sc0 = load_scenario(BASE)
    # the suggested pathway exactly as demo/export_flow.py rebuilds it
    d = json.loads(SUGGESTED_RUN.read_text())
    sug_fc = parse_flowchart("suggested", {**d["flowchart_after"], "id": "suggested"})
    validate_flowchart(sc0, sug_fc)

    log(f"generating patients: calibration {CAL_SEEDS}, held-out {held_seeds}")
    cal = [(s, generate_patients(sc0, N, s)) for s in CAL_SEEDS]
    held = [(s, generate_patients(sc0, N, s)) for s in held_seeds]   # patients do not depend on the changed inputs
    held_rank = [c for c in held if c[0] in rank_seeds]

    worlds_info, results = {}, {}
    leads = {}
    base_eq_target = {}
    for w in worlds:
        log(f"== world {w}  ({time.time() - t_start:.0f}s)")
        lead, cal_info = None, None
        if w in TARGETS_DIAG_TO_TREAT:
            lead, cal_info = calibrate_lead(base_raw, w, TARGETS_DIAG_TO_TREAT[w], cal, log)
        elif w == "ALT":
            lead = leads["L67"] if "L67" in leads else calibrate_lead(base_raw, "L67", 67.0, cal, log)[0]
        leads[w] = lead
        what = {
            "A": "Control: the scenario as it is.",
            "N37": "Treatment-slot booking lead recalibrated so that tissue diagnosis to treatment is 37 days, the scenario's own stated target (it gives about 32 as it stands).",
            "L67": "Treatment-slot booking lead recalibrated so that tissue diagnosis to treatment is 67 days (midpoint of the lung-specific Finnish medians 65 and 69). All the extra delay sits at the treatment booking step.",
            "L92": "Stress: as L67 with 92 days (upper quartile of the surgical group in the lung-specific study).",
            "X1": "Chest X-ray sensitivity 0.81 and specificity 0.68 (primary-care meta-analysis, BJR Open 2021); false-positive rates of every non-cancer condition scaled by one factor.",
            "X2": "Chest X-ray sensitivity 0.76 and specificity 0.95 (NSCLC within one year, Leeds cohort, Bhartia 2021); false-positive rates scaled by one factor.",
            "P": "PET-CT sensitivity 0.89 and specificity 0.70 (Li 2018, pulmonary nodules) instead of stand-alone PET 0.968 and 0.778; false-positive rates scaled by one factor.",
            "ALT": "L67 and X2 and P together.",
        }[w]
        raw = build_raw(base_raw, w, lead, {"what": what})
        path = write_world(raw, w)
        sc = scenario_from_dict(raw, str(path))
        # the file on disk must give the same world as the in-memory dict
        sc_disk = load_scenario(path)
        assert sc_disk.resources["treatment_slot"]["min_lead_days"] == sc.resources["treatment_slot"]["min_lead_days"]
        worlds_info[w] = {"file": str(path.relative_to(ROOT)), "what": what, "changes": raw["_evidence_world"], "calibration": cal_info}

        # 'equivalent target': the 90-day target moved by the shift of the baseline's median so that the baseline sits at the same
        # place in the distribution as in world A (so shares are comparable across worlds)
        if w == "A":
            run_a = run_set(sc, sc.flowcharts["baseline"], held, [90])
            base_med_a = run_a["mean"][90]["median_days_to_treatment"]
        probe = run_set(sc, sc.flowcharts["baseline"], held[:1], [90])
        shift = probe["mean"][90]["median_days_to_treatment"] - (base_med_a if w != "A" else probe["mean"][90]["median_days_to_treatment"])
        t_eq = int(round(90 + shift)) if w != "A" else 90
        base_eq_target[w] = t_eq
        targets = sorted({90, t_eq})

        fcs = {"baseline": sc.flowcharts["baseline"], "suggested": sug_fc}
        res = {"target_equivalent_days": t_eq, "pair": {}, "rank": {}}
        for name, fc in fcs.items():
            r = run_set(sc, fc, held, targets)
            res["pair"][name] = {"interval_median": r["interval_median"],
                                 "by_target": {str(t): {"mean": pick(r["mean"][t]), "per_cohort_share": [m["share_within_target"] for m in r["per_cohort"][t]],
                                                        "per_cohort_median": [m["median_days_to_treatment"] for m in r["per_cohort"][t]]} for t in targets},
                                 "_mean_full": {str(t): r["mean"][t] for t in targets}}
        # paired differences (same patients, same random numbers)
        diff = {}
        for t in targets:
            sb = res["pair"]["baseline"]["by_target"][str(t)]["per_cohort_share"]
            ss = res["pair"]["suggested"]["by_target"][str(t)]["per_cohort_share"]
            mb = res["pair"]["baseline"]["by_target"][str(t)]["per_cohort_median"]
            ms = res["pair"]["suggested"]["by_target"][str(t)]["per_cohort_median"]
            g = [round(100 * (y - x), 2) for x, y in zip(sb, ss)]
            dd = [round(y - x, 2) for x, y in zip(mb, ms)]
            diff[str(t)] = {"gain_pp_per_cohort": g, "gain_pp_mean": round(st.mean(g), 2), "gain_pp_min": min(g), "gain_pp_max": max(g),
                            "positive_in": f"{sum(1 for x in g if x > 0)} of {len(g)}",
                            "median_days_change_per_cohort": dd, "median_days_change_mean": round(st.mean(dd), 2)}
        res["gain"] = diff
        # safety and equity: the optimiser's own guardrails, run on the mean over cohorts as in optimiser/search.py
        full_b = res["pair"]["baseline"]["_mean_full"][str(t_eq)]
        full_s = res["pair"]["suggested"]["_mean_full"][str(t_eq)]
        res["guardrails_failed"] = guardrails(full_s, full_b, Config())
        res["guardrails_passed"] = not res["guardrails_failed"]
        bg, sg = full_b["by_group"], full_s["by_group"]
        res["equity"] = {g: {"share_base": bg[g]["share_within_target"], "share_suggested": sg[g]["share_within_target"],
                             "median_base": bg[g]["median_days_to_treatment"], "median_suggested": sg[g]["median_days_to_treatment"]} for g in bg}
        if "site_specific" in bg and "non_specific" in bg:
            res["equity"]["gap_pp_base"] = round(100 * (bg["site_specific"]["share_within_target"] - bg["non_specific"]["share_within_target"]), 1)
            res["equity"]["gap_pp_suggested"] = round(100 * (sg["site_specific"]["share_within_target"] - sg["non_specific"]["share_within_target"]), 1)
            res["equity"]["gap_days_base"] = round(bg["non_specific"]["median_days_to_treatment"] - bg["site_specific"]["median_days_to_treatment"], 1)
            res["equity"]["gap_days_suggested"] = round(sg["non_specific"]["median_days_to_treatment"] - sg["site_specific"]["median_days_to_treatment"], 1)
        # ranking of all six pathways on the ranking cohorts (baseline and suggested restricted to the same cohorts for a like-for-like order)
        shares, medians = {}, {}
        for name, fc in {"baseline": sc.flowcharts["baseline"], "suggested": sug_fc, **{o: sc.flowcharts[o] for o in OTHERS}}.items():
            r = run_set(sc, fc, held_rank, [t_eq])
            m = r["mean"][t_eq]
            shares[name], medians[name] = m["share_within_target"], m["median_days_to_treatment"]
            res["rank"][name] = {"share": m["share_within_target"], "median_days": m["median_days_to_treatment"], "missed_cancers": m["missed_cancers"],
                                 "max_utilisation": pick(m)["max_utilisation"]}
        res["rank_order_by_share"] = sorted(shares, key=lambda k: -shares[k])
        res["rank_order_by_median_days"] = sorted(medians, key=lambda k: medians[k])
        for p in res["pair"].values():
            p.pop("_mean_full", None)
        results[w] = res
        log(f"  {w}: target_eq {t_eq}  base {res['pair']['baseline']['by_target'][str(t_eq)]['mean']['share_within_target']:.3f}"
            f"  suggested {res['pair']['suggested']['by_target'][str(t_eq)]['mean']['share_within_target']:.3f}"
            f"  gain {diff[str(t_eq)]['gain_pp_mean']} pp ({diff[str(t_eq)]['positive_in']}), median days {diff[str(t_eq)]['median_days_change_mean']}"
            f"  guardrails {'pass' if res['guardrails_passed'] else res['guardrails_failed']}  rank {res['rank_order_by_share']}")

    # ranking agreement with world A
    if "A" in results:
        for w, r in results.items():
            r["rank_kendall_tau_vs_A_share"] = kendall_tau(results["A"]["rank_order_by_share"], r["rank_order_by_share"])
            r["rank_kendall_tau_vs_A_days"] = kendall_tau(results["A"]["rank_order_by_median_days"], r["rank_order_by_median_days"])

    meta = {"script": "scripts/fi_evidence_sensitivity.py", "scenario": "scenarios/finland_lung.yaml", "suggested_pathway": "runs/opt_fi_noft.json (flowchart_after)",
            "patients_per_cohort": N, "calibration_cohorts": list(CAL_SEEDS), "heldout_cohorts_pair": list(held_seeds), "heldout_cohorts_ranking": list(rank_seeds),
            "runs": "common random numbers: the same patients and the same per-patient random draws in every world and pathway",
            "seconds": round(time.time() - t_start), "quick": a.quick}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fi_evidence_worlds.json").write_text(json.dumps({"meta": meta, "worlds": worlds_info}, indent=1, default=str))
    (OUT / "fi_evidence_results.json").write_text(json.dumps({"meta": meta, "results": results}, indent=1, default=str))
    log(f"done in {time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
