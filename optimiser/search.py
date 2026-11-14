"""Propose -> rerun -> accept, then report on held-out patients.

Loop (greedy):
1. Run the current flowchart on the *training* cohort.
2. Propose candidate edits and rank them with revealed-information scores (analysis.py).
3. Rerun the training cohort (same patients, same random numbers) with the top-K candidates.
4. Accept the best one if it improves the objective by at least ``min_gain`` AND passes the
   guardrails against the *starting* flowchart. Repeat.
5. Evaluate the starting and final flowcharts on *held-out* cohorts the search never saw.
   Reporting held-out numbers removes the optimism of picking the best of many candidates on the
   same patients (selection on noise).

Honesty note: proposals use revealed information only; the acceptance rerun uses the
simulator's hidden truth (e.g. to count missed cancers). In a real health system that rerun is a
pilot or a prospective audit, not something the data already contains.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pathway_sim import compute_metrics, generate_patients, simulate
from pathway_sim.scenario import Flowchart, Scenario

from .analysis import reveal, score_edit
from .edits import Edit, apply, candidates


@dataclass
class Config:
    n_train: int = 1000
    train_seeds: tuple = (101,)
    heldout_seeds: tuple = (201, 202, 203)
    n_heldout: int | None = None
    top_k: int = 12
    max_steps: int = 8
    min_gain: float = 0.005            # objective units (= 0.5 pp share within target)
    allow: tuple = ("detach", "relax", "standardise")
    tests_tolerance: float = 0.02      # tests per patient may rise at most 2%
    noncancer_exit_tolerance: float = 1.0   # days
    exhaustive: bool = False           # evaluate every candidate, not only the top-K by score
    confirmed_tolerance: float = 0.02  # tissue-confirmed cancers may fall at most 2% (noise)


def objective(m: dict) -> float:
    """Share treated within target, then 1 pp per 5 days of median time to treatment."""
    share = m["share_within_target"] or 0.0
    med = m["median_days_to_treatment"] or 999.0
    return share - 0.002 * med


def mean_metrics(ms: list[dict]) -> dict:
    out = dict(ms[0])
    for k, v in ms[0].items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals = [m[k] for m in ms if m.get(k) is not None]
            out[k] = round(sum(vals) / len(vals), 4) if vals else None
    return out


def evaluate(sc: Scenario, fc: Flowchart, cohorts: list[tuple[int, list]]) -> tuple[dict, list]:
    ms, runs = [], []
    for seed, pts in cohorts:
        run = simulate(sc, fc, pts, seed=seed)
        runs.append(run)
        ms.append(compute_metrics(run, sc))
    return mean_metrics(ms), runs


def guardrails(m: dict, base: dict, cfg: Config) -> list[str]:
    bad = []
    if m["missed_cancers"] > base["missed_cancers"] + 1e-9:
        bad.append("more missed cancers")
    if m.get("confirmed_cancers") is not None and base.get("confirmed_cancers"):
        if m["confirmed_cancers"] < base["confirmed_cancers"] * (1 - cfg.confirmed_tolerance) - 1e-9:
            bad.append("fewer tissue-confirmed diagnoses")
    if m["untreated_cancers"] > base["untreated_cancers"] + 1e-9:
        bad.append("more untreated cancers")
    if m["stuck"]:
        bad.append("patients stuck")
    if m["tests_per_patient"] > base["tests_per_patient"] * (1 + cfg.tests_tolerance) + 1e-9:
        bad.append("more tests per patient")
    if m["invasive_per_patient"] > base["invasive_per_patient"] * (1 + cfg.tests_tolerance) + 1e-9:
        bad.append("more invasive procedures")
    if base.get("median_days_to_exit_noncancer") is not None and m.get("median_days_to_exit_noncancer") is not None:
        if m["median_days_to_exit_noncancer"] > base["median_days_to_exit_noncancer"] + cfg.noncancer_exit_tolerance:
            bad.append("longer waits for patients without cancer")
    return bad


def cohorts(sc: Scenario, seeds, n) -> list[tuple[int, list]]:
    return [(s, generate_patients(sc, n, s)) for s in seeds]


def search(sc: Scenario, start: Flowchart | str, cfg: Config | None = None, log=print) -> dict:
    cfg = cfg or Config()
    fc0 = sc.flowcharts[start] if isinstance(start, str) else start
    train = cohorts(sc, cfg.train_seeds, cfg.n_train)
    servers = {rid for rid, r in sc.resources.items() if r.get("type", "server") == "server"}
    base_m, base_runs = evaluate(sc, fc0, train)
    cur, cur_m, cur_runs = fc0.copy(f"{fc0.id}_optimised"), base_m, base_runs
    steps, tried = [], 0
    log(f"start {fc0.id}: on-time {base_m['share_within_target']:.3f}, median {base_m['median_days_to_treatment']} d")
    for step in range(cfg.max_steps):
        pts = [p for run in cur_runs for p in reveal(run, servers)]
        cands = candidates(sc, cur, set(cfg.allow))
        for c in cands:
            c.score = score_edit(cur, pts, c)
        valid = []
        for c in cands:
            new = apply(sc, cur, c)
            if new is not None:
                valid.append((c, new))
        ranked = sorted(valid, key=lambda cn: -cn[0].score)
        pool = ranked if cfg.exhaustive else [cn for cn in ranked if cn[0].score > 0][: cfg.top_k]
        best = None
        for c, new in pool:
            tried += 1
            m, runs = evaluate(sc, new, train)
            gain = objective(m) - objective(cur_m)
            bad = guardrails(m, base_m, cfg)
            if not bad and gain >= cfg.min_gain and (best is None or gain > best[0]):
                best = (gain, c, new, m, runs)
        if best is None:
            log(f"step {step + 1}: no candidate improves by >= {cfg.min_gain} within guardrails; stop")
            break
        gain, c, new, m, runs = best
        c.evidence = {"predicted_days_saved": round(c.score, 2),
                      "train_on_time_before": cur_m["share_within_target"], "train_on_time_after": m["share_within_target"],
                      "train_median_before": cur_m["median_days_to_treatment"], "train_median_after": m["median_days_to_treatment"]}
        steps.append(c)
        log(f"step {step + 1}: accept {c.kind}({c.target}, {c.other}) -> on-time {m['share_within_target']:.3f}, "
            f"median {m['median_days_to_treatment']} d  [{c.plain}]")
        cur, cur_m, cur_runs = new, m, runs
    held = cohorts(sc, cfg.heldout_seeds, cfg.n_heldout or cfg.n_train)
    h0, _ = evaluate(sc, fc0, held)
    h1, _ = evaluate(sc, cur, held)
    return {
        "scenario": sc.id, "start": fc0.id, "config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.__dict__.items()},
        "candidates_evaluated": tried,
        "steps": [s.to_dict() for s in steps],
        "train": {"before": base_m, "after": cur_m},
        "heldout": {"before": h0, "after": h1},
        "selection_optimism_pp": round(100 * ((cur_m["share_within_target"] - base_m["share_within_target"])
                                              - (h1["share_within_target"] - h0["share_within_target"])), 2),
        "guardrails_heldout": guardrails(h1, h0, cfg),
        "flowchart_before": fc0.to_dict(),
        "flowchart_after": cur.to_dict(),
    }
