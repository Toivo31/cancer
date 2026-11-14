"""External qualitative checks of the simulator (docs/external_checks.md).

1. ``rapid_ct_check``: England's rapid-CT finding (NOLCP, ERJ 2023): CXR-to-CT median fell 15 -> 3 days but the
   abnormal-CXR-to-treatment-decision time stayed 66 vs 65 days. In the Finnish scenario, speed up *only* the CT step and
   see whether time to treatment barely moves and where the time goes; contrast with reordering (bundled_workup).
2. ``incomplete_board_scenario`` / ``v4_check``: the Stokstad "faster PET only" over-prediction (62% vs 48% published).
   Adds the mechanism "16 of 100 patients reach the tumour board with incomplete work-up and are discussed again a week
   later" in a copy of the scenario, recalibrates the observed pathway and reports what faster-PET then predicts.

    python -m pathway_sim.checks rapid-ct [--n 11000] [--seeds 1,2,3]
    python -m pathway_sim.checks v4 [--n 1000]
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from statistics import median

import yaml

from .calibrate import calibrate, evaluate, write_best
from .engine import simulate
from .metrics import compute_metrics
from .patients import generate_patients
from .scenario import scenario_from_dict

ROOT = Path(__file__).resolve().parent.parent


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(median(xs), 1) if xs else None


# ----------------------------------------------------------------------------------------- 1. rapid CT
def _interval_stats(run, sc, warm, group=None):
    """Intervals for cancers with an abnormal chest X-ray that reached treatment (days)."""
    cxr_ct, cxr_dec, cxr_tx, arr_tx, ct_dec = [], [], [], [], []
    for pr in run.patients:
        if not pr.patient.cancer or pr.patient.arrival < warm or pr.t_treatment is None or (group and pr.patient.group != group):
            continue
        ev = {}
        for e in pr.events:
            ev.setdefault(e.node, e)
        x, mdt = ev.get("cxr"), ev.get("mdt")
        ct = next((ev[k] for k in ("ct", "ct_gp", "ct_first", "ct_spec") if k in ev), None)
        arr_tx.append(pr.t_treatment - pr.patient.arrival)
        if not (x and x.result is True and ct and mdt):
            continue
        cxr_ct.append(ct.t_result - x.t_result)
        cxr_dec.append(mdt.t_result - x.t_result)
        cxr_tx.append(pr.t_treatment - x.t_result)
        ct_dec.append(mdt.t_result - ct.t_result)
    return {"n_abnormal_cxr_treated": len(cxr_ct), "cxr_to_ct_result": _med(cxr_ct), "ct_result_to_board_decision": _med(ct_dec),
            "cxr_to_board_decision": _med(cxr_dec), "cxr_to_treatment": _med(cxr_tx), "first_contact_to_treatment": _med(arr_tx)}


RAPID_CT = {"resources.ct_scanner.capacity_per_day": 8, "resources.ct_scanner.min_lead_days": 1,
            "tests.chest_ct.report_days.median": 1.0}


def rapid_ct_check(path: str = "scenarios/finland_lung.yaml", n: int = 11000, seeds=(1, 2, 3)) -> dict:
    """Variants (all the same patients): baseline; rapid CT only (8 CT slots a day, booking lead 1 d instead of 4, report
    1 d instead of 3); rapid CT plus enough PET-CT capacity for the later step; bundled_workup (reordering, PET-CT 3 slots)."""
    from .calibrate import apply_param
    raw = yaml.safe_load(Path(path).read_text())

    def variant(name, fid, edits):
        r = copy.deepcopy(raw)
        for k, v in edits.items():
            apply_param(r, k, v)
        return name, fid, r

    variants = [variant("baseline", "baseline", {}),
                variant("rapid_ct_only", "baseline", RAPID_CT),
                variant("rapid_ct_plus_pet_capacity", "baseline", {**RAPID_CT, "resources.pet_scanner.capacity_per_day": 3}),
                variant("direct_ct (CT before referral, 8 CT slots)", "direct_ct", {}),
                variant("direct_ct + 1 d CT lead and report", "direct_ct", {"resources.ct_scanner.min_lead_days": 1, "tests.chest_ct.report_days.median": 1.0}),
                variant("bundled_workup (reorder)", "bundled_workup", {})]
    out = {}
    for name, fid, r in variants:
        sc = scenario_from_dict(r)
        acc = []
        for s in seeds:
            pts = generate_patients(sc, n, s)
            run = simulate(sc, fid, pts, seed=s)
            m = compute_metrics(run, sc)
            st = _interval_stats(run, sc, run.warmup_days)
            st_ns = _interval_stats(run, sc, run.warmup_days, "non_specific")
            nb = m["node_breakdown_all"]
            st.update({"share_within_target": m["share_within_target"], "median_days_to_treatment": m["median_days_to_treatment"],
                       "mean_wait_days_per_treated_cancer": {k: nb[k]["wait"] for k in ("spec_visit", "ct", "bronch", "ttnb", "pet", "pet_early", "pet_after_ct", "mdt", "book_treat") if k in nb},
                       "utilisation": {k: v for k, v in m["utilisation"].items() if k in ("ct_scanner", "pet_scanner", "bronchoscopy", "ttnb_slot", "treatment_slot", "clinic")}})
            st["_ns"] = st_ns
            acc.append(st)
        keys = [k for k in acc[0] if k not in ("mean_wait_days_per_treated_cancer", "utilisation", "_ns")]
        agg = {k: _med([a[k] for a in acc]) if k != "n_abnormal_cxr_treated" else round(sum(a[k] for a in acc) / len(acc)) for k in keys}
        waits = {}
        for a in acc:
            for k, v in a["mean_wait_days_per_treated_cancer"].items():
                waits.setdefault(k, []).append(v)
        agg["mean_wait_days_per_treated_cancer"] = {k: round(sum(v) / len(v), 1) for k, v in waits.items()}
        agg["non_specific_presenters_only"] = {k: (_med([a["_ns"][k] for a in acc]) if k != "n_abnormal_cxr_treated" else round(sum(a["_ns"][k] for a in acc) / len(acc))) for k in acc[0]["_ns"]}
        agg["per_seed_median_days_to_treatment"] = [a["median_days_to_treatment"] for a in acc]
        agg["per_seed_cxr_to_ct"] = [a["cxr_to_ct_result"] for a in acc]
        agg["per_seed_cxr_to_decision"] = [a["cxr_to_board_decision"] for a in acc]
        out[name] = agg
    return {"scenario": raw["id"], "n": n, "seeds": list(seeds), "rapid_ct_edits": RAPID_CT, "variants": out}


def rapid_ct_markdown(res: dict) -> str:
    cols = ["cxr_to_ct_result", "cxr_to_board_decision", "cxr_to_treatment", "first_contact_to_treatment", "median_days_to_treatment", "share_within_target"]
    lines = ["| Variant | abnormal CXR to CT result | abnormal CXR to board decision | abnormal CXR to treatment | first contact to treatment (median) | treated within 90 d |",
             "|---|---|---|---|---|---|"]
    for name, v in res["variants"].items():
        lines.append(f"| {name} | {v['cxr_to_ct_result']} | {v['cxr_to_board_decision']} | {v['cxr_to_treatment']} | {v['first_contact_to_treatment']} | {100 * v['share_within_target']:.1f}% |")
    lines += ["", "Non-specific presenters only (the group that has an abnormal X-ray in every flowchart):", "",
              "| Variant | n | abnormal CXR to CT result | abnormal CXR to board decision | abnormal CXR to treatment |", "|---|---|---|---|---|"]
    for name, v in res["variants"].items():
        q = v["non_specific_presenters_only"]
        lines.append(f"| {name} | {q['n_abnormal_cxr_treated']} | {q['cxr_to_ct_result']} | {q['cxr_to_board_decision']} | {q['cxr_to_treatment']} |")
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------- 2. V4
BOARD_OLD = "      - {id: mdt, test: tumour_board, after: [%s], label: Tumour board}\n"
BOARD_NEW = """      - {id: mdt_first, test: tumour_board, after: [%(after)s], label: Tumour board (first discussion)}
      - {id: board_check, kind: choice, after: [mdt_first], options: [board_complete, board_incomplete], label: "Was the work-up complete at the board?"}
      - {id: board_complete, label: Work-up complete}
      - {id: board_incomplete, label: "Work-up incomplete, discussed again next week"}
      - {id: mdt_redo, test: tumour_board_again, after: [board_incomplete], label: Tumour board (second discussion)}
      - {id: mdt, after: [mdt_first], after_optional: [board_check, board_complete, board_incomplete, mdt_redo], label: Board decision}
"""
TEST_NEW = """  tumour_board_again:
    kind: admin
    resource: tumour_board
    stage: treatment_start
    report_days: 0.5
    source: STOKSTAD2019
    note: "second discussion at the next weekly board (16 of 100 patients reached the board with incomplete work-up and were discussed again)"
"""


def incomplete_board_scenario(share: float = 0.16, optimal_too: bool = False, base: str = "scenarios/stokstad.yaml") -> str:
    """Text of a copy of the Stokstad scenario where ``share`` of patients are discussed twice at the board."""
    txt = (ROOT / base).read_text()
    assert BOARD_OLD % "diagnosis, exercise" in txt
    txt = txt.replace(BOARD_OLD % "diagnosis, exercise", BOARD_NEW % {"after": "diagnosis, exercise"})
    if optimal_too:
        assert BOARD_OLD % "pet, exercise" in txt
        txt = txt.replace(BOARD_OLD % "pet, exercise", BOARD_NEW % {"after": "pet, exercise"})
    pol = f"      board_check: {{mix: {{board_complete: {1 - share:.2f}, board_incomplete: {share:.2f}}}, source: STOKSTAD2019}}\n"
    anchor = "      ex_timing: {mix: {ex_early: 0.24, ex_late: 0.76}, source: STOKSTAD2019}\n"
    assert anchor in txt
    txt = txt.replace(anchor, anchor + pol)
    if optimal_too:
        a2 = "      sample_plan: {mix: {method: 0.78, no_sampling: 0.22}}\n"
        assert a2 in txt
        txt = txt.replace(a2, a2 + pol.replace(", source: STOKSTAD2019", ""))
    txt = txt.replace("tests:\n  baseline_ct:", "tests:\n" + TEST_NEW + "  baseline_ct:", 1)
    txt = txt.replace("id: stokstad\n", "id: stokstad_incomplete_board\n", 1)
    return "# EXPERIMENT (pathway_sim.checks): Stokstad scenario plus 'incomplete work-up at the tumour board, discussed again a week later'.\n" + txt


def v4_check(n: int = 1000, seeds=(1,), out_dir: str = "scenarios/experiments") -> dict:
    res = {}
    base_raw = yaml.safe_load((ROOT / "scenarios/stokstad.yaml").read_text())
    for name, both in (("incomplete_board_observed_and_faster_pet", False), ("incomplete_board_all_flowcharts", True)):
        p = ROOT / out_dir / f"stokstad_{name}.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(incomplete_board_scenario(0.16, both))
        cal = calibrate(str(p), n, list(seeds))
        best_path = ROOT / out_dir / f"stokstad_{name}_calibrated.yaml"
        write_best(str(p), cal, str(best_path))
        entry = {"scenario_file": str(p.relative_to(ROOT)), "calibrated_file": str(best_path.relative_to(ROOT)),
                 "accepted": cal["accepted"], "grid_points": cal["grid_points"], "prediction_summary": cal["prediction_summary"],
                 "best_params": (cal["best"] or cal["closest_if_none_accepted"])["params"], "best": None}
        if cal["best"]:
            raw = yaml.safe_load(best_path.read_text())
            entry["best"] = evaluate(raw, {}, ["observed", "faster_pet", "optimal"], 100, list(range(1, 51)))
        res[name] = entry
    # reference: the original (no mechanism) calibration, seed-averaged the same way
    raw0 = yaml.safe_load((ROOT / "scenarios/generated/stokstad_calibrated.yaml").read_text())
    res["reference_no_mechanism"] = evaluate(raw0, {}, ["observed", "faster_pet", "optimal"], 100, list(range(1, 51)))
    res["published"] = base_raw["published"]
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["rapid-ct", "v4"])
    ap.add_argument("--n", type=int)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    seeds = [int(s) for s in a.seeds.split(",")]
    if a.what == "rapid-ct":
        res = rapid_ct_check(n=a.n or 11000, seeds=seeds)
        print(rapid_ct_markdown(res))
    else:
        res = v4_check(a.n or 1000, seeds[:1])
        print(json.dumps({k: v for k, v in res.items() if k != "published"}, indent=1)[:4000])
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
