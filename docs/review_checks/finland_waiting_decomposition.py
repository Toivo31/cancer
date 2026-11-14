"""Review check M1: what the Finnish 'waiting in queues' is made of (critical path, treated cancers,
baseline, seed 7). Also checks that critical-path waiting + service add up to time to treatment. ~10 s.
    python3 docs/review_checks/finland_waiting_decomposition.py"""
import math
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import generate_patients, load_scenario, simulate  # noqa: E402
from pathway_sim.dists import sample, uniform  # noqa: E402

sc = load_scenario(ROOT / "scenarios" / "finland_lung.yaml")
seed = 7
run = simulate(sc, "baseline", generate_patients(sc, 18800, seed), seed=seed)
n, worst = 0, 0.0
acc = {"fixed booking lead (min_lead_days)": 0.0, "assumed extra_wait": 0.0, "capacity queue": 0.0, "paper / weekly board": 0.0}
for pr in run.patients:
    if pr.patient.arrival < run.warmup_days or not pr.patient.cancer or pr.t_treatment is None:
        continue
    n += 1
    crit = [e for e in pr.events if e.critical]
    worst = max(worst, abs(sum(e.t_result - e.t_ready for e in crit) - (pr.t_treatment - pr.patient.arrival)))
    for e in crit:
        test, spec = sc.tests[e.test], sc.resources.get(e.resource, {})
        ex = max(0.0, sample(test["extra_wait"], uniform(seed, pr.patient.id, "extra", e.test, e.attempt))) if test.get("extra_wait") else 0.0
        acc["assumed extra_wait"] += ex
        if spec.get("type") == "server":
            tr = e.t_ready + ex
            d0 = math.floor(tr + spec.get("min_lead_days", 1.0))
            while d0 % 7 in (5, 6):
                d0 += 1
            t0 = max(tr, d0 + 8 / 24)
            acc["fixed booking lead (min_lead_days)"] += t0 - tr
            acc["capacity queue"] += max(0.0, e.t_start - t0)
        else:
            acc["paper / weekly board"] += e.t_start - e.t_ready - ex
print(f"{n} treated cancers; max |critical path - time to treatment| = {worst:.2g} d")
print({k: round(v / n, 1) for k, v in acc.items()}, "total", round(sum(acc.values()) / n, 1))
