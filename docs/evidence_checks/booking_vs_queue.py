"""Booking time versus queueing, per Finnish flowchart (critical path of treated cancers, held-out seeds 301, 302).

Splits the waiting on each treated cancer's critical path into: booking lead (`min_lead_days`, or the shorter
`urgent_lead_days`), assumed `extra_wait`, capacity queue, and paper / weekly board. Same decomposition as
docs/review_checks/finland_waiting_decomposition.py, extended to both held-out cohorts and to the suggested flowchart.
Needs docs/evidence_checks/finland_suggested_flowchart.json (run finland_suggested.py first).

    python3 docs/evidence_checks/booking_vs_queue.py        # about 1 min, writes docs/booking_vs_queue.json
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import generate_patients, load_scenario, simulate  # noqa: E402
from pathway_sim.dists import sample, uniform  # noqa: E402
from pathway_sim.scenario import parse_flowchart  # noqa: E402

sc = load_scenario(ROOT / "scenarios" / "finland_lung.yaml")
sug = parse_flowchart("suggested", json.loads((Path(__file__).with_name("finland_suggested_flowchart.json")).read_text())["flowchart"])
sc.flowcharts["suggested"] = sug
n_pat = int(sc.raw.get("default_n", 2000))
KEYS = ["booking lead", "assumed extra_wait", "capacity queue", "paper / weekly board"]


def decompose(fid: str, seed: int) -> dict:
    run = simulate(sc, fid, generate_patients(sc, n_pat, seed), seed=seed)
    acc = dict.fromkeys(KEYS, 0.0)
    n, worst, ttt = 0, 0.0, 0.0
    for pr in run.patients:
        if pr.patient.arrival < run.warmup_days or not pr.patient.cancer or pr.t_treatment is None:
            continue
        n += 1
        crit = [e for e in pr.events if e.critical]
        tt = pr.t_treatment - pr.patient.arrival
        ttt += tt
        worst = max(worst, abs(sum(e.t_result - e.t_ready for e in crit) - tt))
        for e in crit:
            test, spec = sc.tests[e.test], sc.resources.get(e.resource, {})
            ex = max(0.0, sample(test["extra_wait"], uniform(seed, pr.patient.id, "extra", e.test, e.attempt))) if test.get("extra_wait") else 0.0
            acc["assumed extra_wait"] += ex
            if spec.get("type") == "server":
                tr = e.t_ready + ex
                lead = spec.get("min_lead_days", 1.0)   # neither flowchart uses fast_track, so no urgent leads
                d0 = math.floor(tr + lead)
                while d0 % 7 in (5, 6):
                    d0 += 1
                t0 = max(tr, d0 + 8 / 24)
                acc["booking lead"] += t0 - tr
                acc["capacity queue"] += max(0.0, e.t_start - t0)
            else:
                acc["paper / weekly board"] += e.t_start - e.t_ready - ex
    return {"treated_cancers": n, "mean_days_to_treatment": ttt / n, "max_accounting_error_days": worst,
            **{k: v / n for k, v in acc.items()}}


out = {}
for fid in ("baseline", "suggested"):
    rs = [decompose(fid, s) for s in (301, 302)]
    avg = {k: sum(r[k] for r in rs) / 2 for k in rs[0]}
    out[fid] = {"cohorts": {"301": rs[0], "302": rs[1]}, "mean": avg}
    print(fid, {k: round(v, 1) for k, v in avg.items()})
(ROOT / "docs" / "booking_vs_queue.json").write_text(json.dumps(out, indent=1))
