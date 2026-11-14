#!/usr/bin/env python
"""WP-W4-1: consistency check of the encounter loop against the calibrated chain, and the primary-care finding.

    python scripts/encounter_report.py [--n 6600] [--seeds 1 2 3 4] [--procs 2] [--world scenarios/finland_encounter.yaml]

Runs the encounter world (decision tables = placeholder decisions, D51) and the calibrated chain
(scenarios/finland_lung.yaml, flowchart baseline) on the same number of patients, the same arrival rate and the same
60-day warm-up, over several seeds; prints the tables and writes docs/review_checks/encounter_results.json.
Numbers are means over seeds with a 95% interval (Student t across seeds). Everything about primary-care behaviour is
assumed (see docs/encounter_results.md)."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WARMUP = 60.0
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31}
BENIGN = ("viral_self_limiting", "no_disease_found", "copd_exacerbation", "asthma", "reflux_postinfectious_cough",
          "pneumonia", "heart_failure", "benign_nodule", "tuberculosis")
# tolerance of the consistency check: (absolute, unit). A metric passes when |loop mean - chain mean| <= tolerance.
# Interval overlap is reported too but does not pass a metric (4 seeds of about 50 cancers give wide intervals).
TOLERANCE = {"ref_med": (4.0, "days"), "ref14": (0.08, "share"), "ref28": (0.08, "share"), "ref42": (0.08, "share"),
             "referred": (0.08, "share"), "treated": (0.08, "share"), "within90": (0.08, "share"),
             "noncancer_referred": (0.03, "share")}


def _med(x):
    return statistics.median(x) if x else None


def chain_seed(args):
    n, seed = args
    from pathway_sim.engine import simulate
    from pathway_sim.patients import generate_patients
    from pathway_sim.scenario import load_scenario
    sc = load_scenario(str(ROOT / "scenarios/finland_lung.yaml"))
    log = simulate(sc, "baseline", generate_patients(sc, n, seed), seed=seed)
    prs = [p for p in log.patients if p.patient.arrival >= WARMUP]
    can = [p for p in prs if p.patient.cancer]
    non = [p for p in prs if not p.patient.cancer]
    a = lambda p: p.patient.arrival
    ref = [p.t_done["referral_in"] - a(p) for p in can if "referral_in" in p.t_done]
    tr = [p for p in can if p.outcome == "treatment"]
    return dict(cancers=len(can), ref_med=_med(ref), ref14=sum(x <= 14 for x in ref) / len(can),
                ref28=sum(x <= 28 for x in ref) / len(can), ref42=sum(x <= 42 for x in ref) / len(can),
                referred=len(ref) / len(can), treated=len(tr) / len(can),
                within90=sum(p.t_treatment - a(p) <= 90 for p in tr) / len(can),
                tx_med=_med([p.t_treatment - a(p) for p in tr]),
                noncancer_referred=sum("referral_in" in p.t_done for p in non) / len(non))


def _entries(p):
    return p.record.to_json()["entries"]


def loop_seed(args):
    world_path, n, seed = args
    from pathway_sim.encounter import load_world, run_encounter
    world = load_world(world_path)
    log = run_encounter(world, n, seed)
    prs = [p for p in log.patients if p.patient.arrival >= WARMUP]
    can = [p for p in prs if p.patient.cancer]
    non = [p for p in prs if not p.patient.cancer]
    a = lambda p: p.patient.arrival
    ref = [p.t_referral - a(p) for p in can if p.t_referral is not None]
    tr = [p for p in can if p.outcome == "treatment"]
    m = dict(cancers=len(can), ref_med=_med(ref), ref14=sum(x <= 14 for x in ref) / len(can),
             ref28=sum(x <= 28 for x in ref) / len(can), ref42=sum(x <= 42 for x in ref) / len(can),
             referred=len(ref) / len(can), treated=len(tr) / len(can),
             within90=sum(p.t_treatment - a(p) <= 90 for p in tr) / len(can),
             tx_med=_med([p.t_treatment - a(p) for p in tr]),
             noncancer_referred=sum(bool(p.referrals) for p in non) / len(non),
             cancer_missed=sum(p.outcome == "left_with_symptoms" for p in can) / len(can),
             cancer_stuck=sum(p.outcome == "undiagnosed_at_horizon" for p in can) / len(can))
    # ---- the finding: what happens before the first referral of a cancer
    f = dict(n_cancers=len(can))
    wait_first, after_first, visits, episodes, treated_else, lost, nr_med = [], [], [], [], [], [], []
    with_tx, without_tx = [], []
    for p in can:
        if p.t_referral is None:
            continue
        es = _entries(p)
        tref = p.t_referral - a(p)
        enc = [e for e in es if e["kind"] == "encounter" and e["t_days"] <= tref + 1e-6]
        if not enc:
            continue
        wait_first.append(enc[0]["t_days"])
        after_first.append(tref - enc[0]["t_days"])
        visits.append(len(enc))
        episodes.append(max(e["episode"] for e in enc))
        tx = [e["t_days"] for e in es if e["kind"] == "treatment" and e["t_days"] <= tref + 1e-6]
        if tx:
            with_tx.append(tref)
            lost.append(tref - min(tx))
        else:
            without_tx.append(tref)
    f.update(referred=len(visits), days_to_referral_median=_med([w + x for w, x in zip(wait_first, after_first)]),
             days_wait_for_first_visit_median=_med(wait_first), days_after_first_visit_median=_med(after_first),
             visits_before_referral_mean=statistics.mean(visits) if visits else None,
             episodes_before_referral_mean=statistics.mean(episodes) if episodes else None,
             share_first_treated_as_something_else=len(with_tx) / len(visits) if visits else None,
             days_from_wrong_treatment_to_referral_median=_med(lost),
             days_to_referral_median_with_wrong_treatment=_med(with_tx),
             days_to_referral_median_without_wrong_treatment=_med(without_tx),
             share_first_visit_chest_xray=None)
    first_xr = 0
    for p in can:
        for e in _entries(p):
            if e["kind"] == "encounter" and e["role"] == "gp":
                first_xr += e.get("action") == "order_chest_xray"
                break
    f["share_first_gp_visit_orders_chest_xray"] = first_xr / len(can)
    m["finding"] = f
    # ---- by patient group (pooled cancers; counts are small, see caveats)
    groups = {}
    for gname, key in (("age", lambda p: _band(p.record.background.get("age"))), ("sex", lambda p: p.record.background.get("sex")),
                       ("smoking", lambda p: p.record.background.get("smoking_status")), ("region", lambda p: p.record.background.get("region"))):
        d = {}
        for p in can:
            d.setdefault(str(key(p)), []).append(p)
        groups[gname] = {}
        for k, ps in sorted(d.items()):
            rr = [p.t_referral - a(p) for p in ps if p.t_referral is not None]
            groups[gname][k] = dict(n=len(ps), referred_share=len(rr) / len(ps), ref_med=_med(rr),
                                    treated_share=sum(p.outcome == "treatment" for p in ps) / len(ps),
                                    missed_share=sum(p.outcome == "left_with_symptoms" for p in ps) / len(ps),
                                    visits=statistics.mean([sum(1 for e in _entries(p) if e["kind"] == "encounter") for p in ps]))
    m["groups"] = groups
    # ---- worried well and benign: tests and cost per patient
    per = {}
    for name, sel in (("worried_well", [p for p in non if p.primary_condition == "worried_well"]),
                      ("benign_all", [p for p in non if p.primary_condition in BENIGN]),
                      ("viral_self_limiting", [p for p in non if p.primary_condition == "viral_self_limiting"]),
                      ("no_disease_found", [p for p in non if p.primary_condition == "no_disease_found"]),
                      ("lung_cancer", can)):
        if sel:
            per[name] = dict(n=len(sel), tests_pp=sum(len(p.tests_ordered) for p in sel) / len(sel),
                             cost_pp=sum(sum(p.cost.values()) for p in sel) / len(sel),
                             primary_care_cost_pp=sum(p.cost["visits"] + p.cost["tests"] for p in sel) / len(sel),
                             gp_visits_pp=sum(p.by_role.get("gp", 0) for p in sel) / len(sel),
                             episodes_pp=sum(p.episode for p in sel) / len(sel),
                             referred_share=sum(bool(p.referrals) for p in sel) / len(sel))
    m["per_condition_group"] = per
    m["load"] = dict(gp_pp=sum(p.by_role.get("gp", 0) for p in prs) / len(prs), nurse_pp=sum(p.by_role.get("nurse", 0) for p in prs) / len(prs),
                     episodes_pp=sum(p.episode for p in prs) / len(prs), tests_pp=sum(len(p.tests_ordered) for p in prs) / len(prs),
                     cost_pp=sum(sum(p.cost.values()) for p in prs) / len(prs), patients=len(prs))
    return m


def _band(age):
    a = int(age or 0)
    return "<50" if a < 50 else "50-64" if a < 65 else "65-74" if a < 75 else "75+"


def ci(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    m = statistics.mean(xs)
    if len(xs) < 2:
        return dict(mean=m, lo=m, hi=m, n=len(xs))
    h = T95.get(len(xs) - 1, 2.0) * statistics.stdev(xs) / len(xs) ** 0.5
    return dict(mean=m, lo=m - h, hi=m + h, n=len(xs))


def agg(dicts):
    out = {}
    for k in dicts[0]:
        vals = [d[k] for d in dicts]
        if isinstance(vals[0], dict):
            out[k] = agg(vals)
        elif isinstance(vals[0], (int, float)) or vals[0] is None:
            out[k] = ci(vals)
    return out


def fmt(c, d=2, pct=False):
    if c is None:
        return "-"
    s = 100 if pct else 1
    return f"{c['mean'] * s:.{d}f} [{c['lo'] * s:.{d}f}, {c['hi'] * s:.{d}f}]" + ("%" if pct else "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--world", default=str(ROOT / "scenarios/finland_encounter.yaml"))
    ap.add_argument("--out", default=str(ROOT / "docs/review_checks/encounter_results.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    with Pool(a.procs) as pl:
        loop = pl.map(loop_seed, [(a.world, a.n, s) for s in a.seeds])
        chain = pl.map(chain_seed, [(a.n, s) for s in a.seeds])
    L = agg([{k: v for k, v in m.items() if k not in ("finding", "groups", "per_condition_group", "load")} for m in loop])
    C = agg(chain)
    cons = {}
    for k, (tol, unit) in TOLERANCE.items():
        l, c = L[k], C[k]
        diff = l["mean"] - c["mean"]
        overlap = l["lo"] <= c["hi"] and c["lo"] <= l["hi"]
        cons[k] = dict(loop=l, chain=c, diff=diff, tolerance=tol, unit=unit, intervals_overlap=overlap,
                       within_tolerance=abs(diff) <= tol, passes=abs(diff) <= tol)
    res = dict(format="encounter_results/1", n=a.n, seeds=a.seeds, warmup_days=WARMUP, world=Path(a.world).name,
               decisions="placeholder decision tables (D51): the JEV decides in the final model",
               consistency=cons, finding=agg([m["finding"] for m in loop]), groups=agg([m["groups"] for m in loop]),
               per_condition_group=agg([m["per_condition_group"] for m in loop]), load=agg([m["load"] for m in loop]),
               loop_other=dict(tx_med=L["tx_med"], cancer_missed=L["cancer_missed"], cancer_stuck=L["cancer_stuck"]),
               chain_other=dict(tx_med=C["tx_med"]), seconds=round(time.time() - t0, 1))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    # ---- print
    print(f"encounter loop vs calibrated chain: n={a.n} per seed, seeds {a.seeds}, warm-up {WARMUP:g} d, 95% interval across seeds")
    print(f"{'metric':<20}{'loop':>26}{'chain':>26}{'diff':>8}{'tol':>7}  ok")
    for k, c in cons.items():
        pct = c["unit"] == "share"
        print(f"{k:<20}{fmt(c['loop'], 1 if pct else 1, pct):>26}{fmt(c['chain'], 1 if pct else 1, pct):>26}"
              f"{c['diff'] * (100 if pct else 1):>8.1f}{c['tolerance'] * (100 if pct else 1):>7.0f}  {'yes' if c['passes'] else 'NO'}{'' if c['passes'] or not c['intervals_overlap'] else ' (intervals overlap)'}")
    print(f"median days to treatment: loop {fmt(L['tx_med'], 0)} chain {fmt(C['tx_med'], 0)};  cancers missed in primary care (loop) {fmt(L['cancer_missed'], 1, True)}")
    F = res["finding"]
    print("\nFINDING (cancers, loop, placeholder decisions)")
    for k in ("days_to_referral_median", "days_wait_for_first_visit_median", "days_after_first_visit_median", "visits_before_referral_mean",
              "episodes_before_referral_mean", "share_first_treated_as_something_else", "days_from_wrong_treatment_to_referral_median",
              "days_to_referral_median_with_wrong_treatment", "days_to_referral_median_without_wrong_treatment", "share_first_gp_visit_orders_chest_xray"):
        print(f"  {k:<52}{fmt(F[k], 2)}")
    print("\nby group (cancers pooled per seed; mean cancers per seed in n)")
    print(f"  {'group':<14}{'n':>6}{'referred':>22}{'median d to referral':>26}{'treated':>22}")
    for g, rows in res["groups"].items():
        for k, r in rows.items():
            print(f"  {g + ' ' + k:<14}{r['n']['mean']:>6.1f}{fmt(r['referred_share'], 0, True):>22}{fmt(r['ref_med'], 1):>26}{fmt(r['treated_share'], 0, True):>22}")
    print("\nper patient (tests, cost EUR incl. hospital, GP visits, referred share)")
    for k, r in res["per_condition_group"].items():
        print(f"  {k:<22} n/seed {r['n']['mean']:>6.0f}  tests {fmt(r['tests_pp'], 2):>20}  cost {fmt(r['cost_pp'], 0):>22}  primary-care cost {fmt(r['primary_care_cost_pp'], 0):>20}  GP {fmt(r['gp_visits_pp'], 2):>18}  referred {fmt(r['referred_share'], 1, True)}")
    print(f"\nwrote {a.out} in {res['seconds']} s")
    return res


if __name__ == "__main__":
    main()
