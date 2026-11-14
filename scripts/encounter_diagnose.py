#!/usr/bin/env python
"""Diagnosis of the encounter loop against the calibrated chain (w7/loop): where non-cancer referrals come from
and where a cancer's days go before referral.

    python scripts/encounter_diagnose.py [--n 6000] [--seeds 1] [--world scenarios/finland_encounter.yaml] [--json F]

Scoring side only (reads hidden conditions to group patients); nothing here feeds a decision. Patients arriving in
the first 60 days are left out, as in scripts/encounter_report.py. Prints:
  1. non-cancer referral share by condition, and by route (which table row fired at the first referral, whether the
     latest chest X-ray in the record was abnormal, which episode);
  2. episodes per patient by condition;
  3. cancer days before the first referral split into buckets (first-visit wait, test turnaround, review after a
     result, follow-up, treatment review, nurse-to-GP booking, return delay, booking after a return);
  4. the chain's cancer referral routes and their timing, for comparison.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
WARMUP = 60.0

SHORT = [  # (substring of the table rule, short label) for readability; first match wins
    ("found.haemoptysis and attempts.chest_xray == 0", "haemoptysis->X-ray row"),
    ("last.chest_xray.abnormal\"", "abnormal film row"),
    ("last.nt_probnp.positive", "NT-proBNP positive row"),
    ("last.spirometry.positive", "spirometry positive row"),
    ("last.crp.crp", "CRP>=50 row"),
    ("episode >= 2 and (found.weight_loss", "neg film, ep>=2, suspicion row"),
    ("abnormal is False and episode >= 2", "neg film, ep>=2, other row"),
    ("reason == 'result' and last.chest_xray.abnormal is False", "negative film result row"),
    ("found.ankle_oedema", "oedema+dyspnoea row"),
    ("found.wheeze", "wheeze row"),
    ("reason == 'treatment'", "treatment review row"),
    ("episode >= 3", "episode>=3 row"),
    ("episode >= 2 and attempts.chest_xray == 0", "ep>=2 no film row"),
    ("attempts.chest_xray == 0 and (found.weight_loss", "suspicion -> X-ray row"),
    ("reason == 'result' and attempts.chest_xray == 0", "result without film row"),
    ("Table default", "default row"),
]


_RULES: dict[str, str] = {}


def _load_rules(world_path: str) -> None:
    """Map each gp/nurse table rule's condition to a short label 'gp#k' (its position in the table) plus a
    hand label when one of SHORT matches."""
    from pathway_sim.encounter import load_world
    pol = load_world(world_path).policy
    for pt, spec in pol.points.items():
        for k, r in enumerate(spec["rules"]):
            lab = next((l for key, l in SHORT if key in r["when"]), "")
            _RULES[r["when"]] = f"{pt.split('_')[0]}#{k + 1:02d} {lab}".strip()


def short(note: str | None) -> str:
    if not note:
        return "?"
    body = note.replace("Table rule: ", "").strip()
    if body.endswith("."):
        body = body[:-1]
    if body in _RULES:
        return _RULES[body]
    body = note.replace("Table rule: ", "")
    if body.strip().rstrip(".") == "last.chest_xray.abnormal":
        return "abnormal film row"
    for k, lab in SHORT:
        if k in body:
            return lab
    return body[:60]


def loop_patients(world_path: str, n: int, seed: int):
    from pathway_sim.encounter import load_world, run_encounter
    world = load_world(world_path)
    log = run_encounter(world, n, seed)
    return [p for p in log.patients if p.patient.arrival >= WARMUP]


def first_referral(p):
    """(entries before and at the first referral, the referral entry, the assessment note of that encounter)."""
    es = p.record.to_json()["entries"]
    for i, e in enumerate(es):
        if e["kind"] == "referral":
            note = None
            for f in reversed(es[:i]):
                if f["kind"] == "assessment":
                    note = f.get("note")
                    break
                if f["kind"] == "encounter" and f.get("action") is not None and f is not es[i - 1]:
                    break
            return es[:i + 1], e, note
    return es, None, None


def last_film(es):
    for e in reversed(es):
        for o in e.get("observations") or []:
            if o["test"] == "chest_xray" and o["status"] == "ok":
                return o["values"].get("abnormal")
    return None


BUCKETS = ("first_visit_wait", "nurse_to_gp", "test_turnaround", "review_after_result", "follow_up_interval",
           "treatment_review", "return_delay", "booking_after_return", "other")


def day_buckets(es):
    """Split the time from arrival to the first referral into buckets by what the patient was waiting for."""
    out = dict.fromkeys(BUCKETS, 0.0)
    mech = [e for e in es if e["kind"] not in ("assessment",)]
    prev_t, state = 0.0, "first_visit_wait"
    for e in mech:
        dt = e["t_days"] - prev_t
        out[state] += dt
        prev_t = e["t_days"]
        k, a = e["kind"], e.get("action") or ""
        if k == "encounter":
            if a.startswith("order_"):
                state = "test_turnaround"
            elif a.startswith("treat_"):
                state = "treatment_review"
            elif a == "follow_up":
                state = "follow_up_interval"
            elif a.startswith("book_gp"):
                state = "nurse_to_gp"
            else:
                state = "other"
        elif k == "result":
            state = "review_after_result"
        elif k == "treatment":
            state = "treatment_review"
        elif k == "discharge":
            state = "return_delay"
        elif k == "return":
            state = "booking_after_return"
        elif k == "referral":
            break
    return out


def chain_patients(n: int, seed: int):
    from pathway_sim.engine import simulate
    from pathway_sim.patients import generate_patients
    from pathway_sim.scenario import load_scenario
    sc = load_scenario(str(ROOT / "scenarios/finland_lung.yaml"))
    log = simulate(sc, "baseline", generate_patients(sc, n, seed), seed=seed)
    return [p for p in log.patients if p.patient.arrival >= WARMUP]


def chain_route(p):
    r = p.result
    if "referral_in" not in p.t_done:
        return "not referred"
    if r.get("cxr"):
        return "positive film"
    if r.get("second_look"):
        return "second look after negative film"
    if r.get("represent"):
        return "re-presentation" + (" (no film)" if r.get("cxr") is None else " (after negative film)")
    return "?"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--world", default=str(ROOT / "scenarios/finland_encounter.yaml"))
    ap.add_argument("--no-chain", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    _load_rules(a.world)
    prs = []
    for s in a.seeds:
        prs += loop_patients(a.world, a.n, s)
    non = [p for p in prs if not p.patient.cancer]
    can = [p for p in prs if p.patient.cancer]
    res = {"n_patients": len(prs), "n_cancers": len(can)}

    # ---- 1. non-cancer referrals
    by_cond = defaultdict(list)
    for p in non:
        by_cond[p.primary_condition].append(p)
    print(f"LOOP {Path(a.world).name}: {len(prs)} patients after warm-up ({len(can)} cancers), seeds {a.seeds}")
    print(f"\n1. NON-CANCER REFERRALS: {sum(bool(p.referrals) for p in non) / len(non):.1%} of {len(non)}")
    print(f"  {'condition':<30}{'n':>6}{'share':>7}{'referred':>9}{'contrib pt':>11}{'episodes':>9}{'GP/pt':>7}")
    rc = {}
    for c, ps in sorted(by_cond.items(), key=lambda kv: -sum(bool(p.referrals) for p in kv[1])):
        r = sum(bool(p.referrals) for p in ps)
        rc[c] = dict(n=len(ps), referred=r / len(ps), contribution=r / len(non), episodes=statistics.mean(p.episode for p in ps))
        print(f"  {c:<30}{len(ps):>6}{len(ps) / len(non):>7.1%}{r / len(ps):>9.1%}{100 * r / len(non):>11.2f}"
              f"{rc[c]['episodes']:>9.2f}{statistics.mean(p.by_role.get('gp', 0) for p in ps):>7.2f}")
    res["noncancer_by_condition"] = rc
    routes, films, eps, urg = Counter(), Counter(), Counter(), Counter()
    route_cond = defaultdict(Counter)
    for p in non:
        if not p.referrals:
            continue
        es, ref, note = first_referral(p)
        lab = short(note)
        routes[lab] += 1
        route_cond[lab][p.primary_condition] += 1
        f = last_film(es)
        films["film abnormal (false positive)" if f else "film negative" if f is False else "no film"] += 1
        eps[min(ref["episode"], 4) if ref else 0] += 1
        urg[ref.get("action") if ref else "?"] += 1
    nn = len(non)
    print("  by table row that fired at the first referral (points of all non-cancers):")
    for k, v in routes.most_common():
        top = ", ".join(f"{c} {100 * x / nn:.1f}" for c, x in route_cond[k].most_common(4))
        print(f"    {k:<36}{100 * v / nn:>6.2f}   [{top}]")
    print("  by latest chest X-ray in the record:", ", ".join(f"{k} {100 * v / nn:.2f}" for k, v in films.most_common()))
    print("  by episode of the first referral:", ", ".join(f"ep{k}{'+' if k == 4 else ''} {100 * v / nn:.2f}" for k, v in sorted(eps.items())))
    print("  urgency:", ", ".join(f"{k} {100 * v / nn:.2f}" for k, v in urg.most_common()))
    res["noncancer_routes_pts"] = {k: 100 * v / nn for k, v in routes.items()}
    res["noncancer_film_pts"] = {k: 100 * v / nn for k, v in films.items()}
    res["noncancer_episode_pts"] = {str(k): 100 * v / nn for k, v in eps.items()}

    # ---- 2. episodes and outcomes
    print(f"\n2. EPISODES per patient: all {statistics.mean(p.episode for p in prs):.2f}, non-cancer {statistics.mean(p.episode for p in non):.2f}, cancer {statistics.mean(p.episode for p in can):.2f}")
    oc = Counter(p.outcome for p in non)
    print("  non-cancer outcomes:", ", ".join(f"{k} {v / nn:.1%}" for k, v in oc.most_common()))
    tr = Counter(t["id"] for p in non for t in p.treatments)
    print("  non-cancer treatments per 100:", ", ".join(f"{k} {100 * v / nn:.1f}" for k, v in tr.most_common()))

    # ---- 3. cancer days
    print(f"\n3. CANCERS ({len(can)}): outcomes", dict(Counter(p.outcome for p in can)))
    rows = []
    croute, cfilm = Counter(), Counter()
    for p in can:
        es, ref, note = first_referral(p)
        if ref is None:
            continue
        rows.append(day_buckets(es))
        croute[short(note)] += 1
        f = last_film(es)
        cfilm["film abnormal" if f else "film negative" if f is False else "no film"] += 1
    if rows:
        tot = {b: statistics.mean(r[b] for r in rows) for b in BUCKETS}
        print(f"  referred {len(rows)}; mean days before first referral {sum(tot.values()):.1f}, median "
              f"{statistics.median(sum(r.values()) for r in rows):.1f}; split (mean days):")
        for b in BUCKETS:
            print(f"    {b:<24}{tot[b]:>7.1f}")
        res["cancer_days_mean"] = tot
        print("  route of the first referral:", ", ".join(f"{k} {v}" for k, v in croute.most_common()))
        print("  film at referral:", ", ".join(f"{k} {v}" for k, v in cfilm.most_common()))
        # first-film outcome among all cancers
        ff = Counter()
        for p in can:
            es = p.record.to_json()["entries"]
            first = next((o["values"].get("abnormal") for e in es for o in (e.get("observations") or [])
                          if o["test"] == "chest_xray" and o["status"] == "ok" and e["kind"] == "result"), "none")
            ff[str(first)] += 1
        print("  first chest X-ray result among cancers:", dict(ff))
        # timing by first-film class
        cls = defaultdict(list)
        for p in can:
            if p.t_referral is None:
                continue
            es = p.record.to_json()["entries"]
            first = next((o["values"].get("abnormal") for e in es for o in (e.get("observations") or [])
                          if o["test"] == "chest_xray" and o["status"] == "ok" and e["kind"] == "result"), "none")
            cls[str(first)].append(p.t_referral - p.patient.arrival)
        print("  median days to referral by first film:", {k: (len(v), round(statistics.median(v), 1)) for k, v in cls.items()})
    if not a.no_chain:
        cps = []
        for s in a.seeds:
            cps += chain_patients(a.n, s)
        cc = [p for p in cps if p.patient.cancer]
        cn = [p for p in cps if not p.patient.cancer]
        print(f"\n4. CHAIN cancers {len(cc)}: routes and median days to referral")
        rt = defaultdict(list)
        for p in cc:
            rt[chain_route(p)].append(p.t_done["referral_in"] - p.patient.arrival if "referral_in" in p.t_done else None)
        for k, v in sorted(rt.items(), key=lambda kv: -len(kv[1])):
            xs = [x for x in v if x is not None]
            print(f"    {k:<40}{len(v):>5} ({len(v) / len(cc):.0%})  median {statistics.median(xs) if xs else float('nan'):.1f} d")
        print(f"  chain non-cancer referred {sum('referral_in' in p.t_done for p in cn) / len(cn):.1%}; by route (pts):")
        rn = Counter(chain_route(p) for p in cn)
        for k, v in rn.most_common():
            if k != "not referred":
                print(f"    {k:<40}{100 * v / len(cn):>6.2f}")
        res["chain_noncancer_routes_pts"] = {k: 100 * v / len(cn) for k, v in rn.items()}
        res["chain_cancer_routes"] = {k: len(v) / len(cc) for k, v in rt.items()}
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
