"""What the simulated waiting days rest on: published figures or our assumptions.

Used by demo/export_research.py. Extends docs/review_checks/finland_waiting_decomposition.py (same run: baseline,
seed 7, scenario's default_n patients, treated cancers after the warm-up, critical path only) in two ways:
  1. every critical-path waiting day is attributed to the input that sets it, and that input's basis
     (published figure / assumption calibrated to a published figure / assumption);
  2. the same is done for the Norwegian scenario (observed pathway), whose per-step waits are inputs.

Waiting on the critical path = t_start - t_ready of each critical event, split into
  - the test's `extra_wait` (sampled exactly as the engine samples it), owned by the test;
  - the rest (booking lead + capacity queue for `server` resources, the weekly cycle for `batch`, the drawn
    `wait` for `delay`/`none` resources), owned by the resource for server/batch and by the test otherwise.
The owner's basis comes from its `source:` tag in the scenario file, unless the register
(docs/research_claims.yaml, `waiting_basis`) names an override with a reason (for example a resource tagged
`assumption` whose booking lead was tuned to hit a published wait).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pathway_sim import generate_patients, load_scenario, simulate  # noqa: E402
from pathway_sim.dists import sample, uniform  # noqa: E402

BASES = ("published", "calibrated", "assumption")


def _owner_basis(cfg: dict, kind: str, key: str, spec: dict, known: set[str]) -> tuple[str, str | None, str]:
    """(basis, source id or None, why) for one owner. kind is 'resource', 'test' or 'extra'."""
    ov = (cfg.get("overrides") or {}).get(f"{kind}:{key}")
    if ov:
        return ov["basis"], ov.get("source"), ov["why"]
    if kind == "extra":
        return "assumption", None, "extra waits are assumptions (most are calibrated to fit an observed total)"
    src = spec.get("source", "assumption")
    if src in known:
        return "published", src, f"`source: {src}` in the scenario"
    return "assumption", None, "`source: assumption` in the scenario"


def decompose(cfg: dict, known_sources: set[str]) -> dict:
    """cfg: one entry of `waiting_basis` in docs/research_claims.yaml."""
    sc = load_scenario(ROOT / cfg["scenario"])
    seed, fc = int(cfg["seed"]), cfg["flowchart"]
    n_pat = int(cfg["n"])
    run = simulate(sc, fc, generate_patients(sc, n_pat, seed), seed=seed)
    owners: dict[tuple, dict] = {}
    kinds = {"booking lead": 0.0, "capacity queue": 0.0, "weekly board cycle": 0.0, "drawn wait": 0.0, "extra wait": 0.0}
    n, worst, wait_total, svc_total = 0, 0.0, 0.0, 0.0

    def add(kind: str, key: str, spec: dict, days: float, test: str) -> None:
        basis, src, why = _owner_basis(cfg, kind, key, spec, known_sources)
        o = owners.setdefault((kind, key), {"owner": f"{kind}:{key}", "basis": basis, "source": src, "why": why,
                                            "note": spec.get("note", "") if kind != "extra" else (sc.tests[key].get("note", "")),
                                            "days": 0.0, "tests": set()})
        o["days"] += days
        o["tests"].add(test)

    for pr in run.patients:
        if pr.patient.arrival < run.warmup_days or not pr.patient.cancer or pr.t_treatment is None:
            continue
        n += 1
        crit = [e for e in pr.events if e.critical]
        worst = max(worst, abs(sum(e.t_result - e.t_ready for e in crit) - (pr.t_treatment - pr.patient.arrival)))
        for e in crit:
            test = sc.tests[e.test]
            rid = test.get("resource", "none")
            spec = sc.resources.get(rid, {"type": "none"})
            typ = spec.get("type", "server")
            ex = max(0.0, sample(test["extra_wait"], uniform(seed, pr.patient.id, "extra", e.test, e.attempt))) if test.get("extra_wait") is not None else 0.0
            wait = e.t_start - e.t_ready
            svc_total += e.t_result - e.t_start
            wait_total += wait
            ex = min(ex, wait)
            if ex > 0:
                add("extra", e.test, test, ex, e.test)
                kinds["extra wait"] += ex
            rest = wait - ex
            if typ == "server":
                tr = e.t_ready + ex
                d0 = math.floor(tr + spec.get("min_lead_days", 1.0))
                while d0 % 7 in (5, 6):
                    d0 += 1
                t0 = max(tr, d0 + 8 / 24)
                lead = min(rest, t0 - tr)
                kinds["booking lead"] += lead
                kinds["capacity queue"] += rest - lead
                add("resource", rid, spec, rest, e.test)
            elif typ == "batch":
                kinds["weekly board cycle"] += rest
                add("resource", rid, spec, rest, e.test)
            else:
                kinds["drawn wait"] += rest
                add("test", e.test, test, rest, e.test)
    if n == 0:
        raise RuntimeError(f"no treated cancers in {cfg['scenario']}")
    rows = []
    for o in owners.values():
        if o["days"] / n < 0.05:
            continue
        rows.append({**o, "days": round(o["days"] / n, 1), "share_of_waiting": round(o["days"] / wait_total, 3), "tests": sorted(o["tests"])})
    rows.sort(key=lambda r: -r["days"])
    by_basis = {b: 0.0 for b in BASES}
    for o in owners.values():
        by_basis[o["basis"]] += o["days"]
    return {
        "scenario": cfg["scenario"], "flowchart": fc, "seed": seed, "patients": n_pat, "treated_cancers": n,
        "critical_path_check_days": round(worst, 6),
        "waiting_days": round(wait_total / n, 1), "service_days": round(svc_total / n, 1),
        "waiting_share_of_time": round(wait_total / (wait_total + svc_total), 3),
        "by_basis_days": {b: round(v / n, 1) for b, v in by_basis.items()},
        "by_basis_share": {b: round(v / wait_total, 3) for b, v in by_basis.items()},
        "published_or_calibrated_share": round((by_basis["published"] + by_basis["calibrated"]) / wait_total, 3),
        "by_kind_days": {k: round(v / n, 1) for k, v in kinds.items() if v > 0},
        "owners": rows,
    }
