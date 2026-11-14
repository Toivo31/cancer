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
    train_seeds: tuple = (101, 102)    # several training cohorts: a change must help in each (noise-aware)
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
    equity_guardrail: bool = True      # no presentation group may get slower or less often on time
    equity_days_tolerance: float = 1.0
    equity_share_tolerance: float = 0.01
    equity_min_cancers: int = 10       # groups with fewer cancers per cohort are too noisy to judge
    lookahead: int = 6                 # if no single change helps, try pairs among the top-N (0 = off)


def objective(m: dict) -> float:
    """Share treated within target, then 1 pp per 5 days of median time to treatment."""
    share = m["share_within_target"] or 0.0
    med = m["median_days_to_treatment"] or 999.0
    return share - 0.002 * med


def _mean_dict(ds: list[dict]) -> dict:
    out = dict(ds[0])
    for k, v in ds[0].items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals = [d[k] for d in ds if d.get(k) is not None]
            out[k] = round(sum(vals) / len(vals), 4) if vals else None
        elif isinstance(v, dict) and k == "by_group":
            out[k] = {g: _mean_dict([d[k][g] for d in ds if g in d.get(k, {})]) for g in v}
    return out


def mean_metrics(ms: list[dict]) -> dict:
    out = _mean_dict(ms)
    out["cohort_objectives"] = [round(objective(m), 5) for m in ms]
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
    if cfg.equity_guardrail and len(base.get("by_group") or {}) > 1:
        for g, b in base["by_group"].items():
            a = (m.get("by_group") or {}).get(g)
            if not a or (b.get("n_cancer") or 0) < cfg.equity_min_cancers:
                continue
            if b.get("median_days_to_treatment") is not None and a.get("median_days_to_treatment") is not None \
                    and a["median_days_to_treatment"] > b["median_days_to_treatment"] + cfg.equity_days_tolerance:
                bad.append(f"slower for {g.replace('_', '-')} presenters")
            if b.get("share_within_target") is not None and a.get("share_within_target") is not None \
                    and a["share_within_target"] < b["share_within_target"] - cfg.equity_share_tolerance:
                bad.append(f"fewer {g.replace('_', '-')} presenters on time")
    return bad


def records_reading(c: Edit, fc: Flowchart) -> str:
    """One plain line on what ``predicted_days_saved`` means for this kind of change."""
    from .edits import label
    d = round(c.score, 1)
    if c.kind in ("detach", "relax"):
        other = c.other.split("/")[-1] if c.other else ""
        what = label(fc, other).lower() if other in fc.nodes else other
        return (f"In the records, the step '{label(fc, c.target).lower()}' was held back by {what}: "
                f"on average {d} days per patient on the critical path")
    if c.kind == "standardise":
        return (f"In the records, patients for whom '{label(fc, c.other).lower()}' was chosen left the pathway "
                f"sooner; spread over everyone else that is about {d} days per patient (a biased, unadjusted comparison)")
    if c.kind == "fast_track":
        return (f"In the records, patients spent on average {round(2 * c.score, 1)} days in appointment queues after "
                f"'{label(fc, c.target).lower()}'; half of that is counted as the possible saving")
    return ""


def _gains(m: dict, cur_m: dict) -> list[float]:
    return [a - b for a, b in zip(m["cohort_objectives"], cur_m["cohort_objectives"])]


def cohorts(sc: Scenario, seeds, n) -> list[tuple[int, list]]:
    return [(s, generate_patients(sc, n, s)) for s in seeds]


def search(sc: Scenario, start: Flowchart | str, cfg: Config | None = None, log=print) -> dict:
    cfg = cfg or Config()
    fc0 = sc.flowcharts[start] if isinstance(start, str) else start
    train = cohorts(sc, cfg.train_seeds, cfg.n_train)
    servers = {rid for rid, r in sc.resources.items() if r.get("type", "server") == "server"}
    base_m, base_runs = evaluate(sc, fc0, train)
    cur, cur_m, cur_runs = fc0.copy(f"{fc0.id}_optimised"), base_m, base_runs
    steps, tried, all_rejected = [], 0, []
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
        best, rejected = None, []
        for c, new in pool:
            tried += 1
            m, runs = evaluate(sc, new, train)
            gains = _gains(m, cur_m)
            gain = sum(gains) / len(gains)
            bad = guardrails(m, base_m, cfg)
            if min(gains) < 0:
                bad = bad + ["not better in every training cohort"]
            if not bad and gain >= cfg.min_gain and (best is None or gain > best[0]):
                best = (gain, [c], new, m, runs)
            elif bad and gain >= cfg.min_gain:
                rejected.append({"change": c.plain, "gain_pp": round(100 * gain, 2), "blocked_by": bad})
        if best is None and cfg.lookahead:
            # two changes that only help together (e.g. move a step, then stop waiting for it)
            top = sorted(pool, key=lambda cn: -cn[0].score)[: cfg.lookahead]
            for i, (c1, n1) in enumerate(top):
                for c2, _ in top[i + 1:]:
                    n2 = apply(sc, n1, c2)
                    if n2 is None:
                        continue
                    tried += 1
                    m, runs = evaluate(sc, n2, train)
                    gains = _gains(m, cur_m)
                    gain = sum(gains) / len(gains)
                    if min(gains) >= 0 and gain >= cfg.min_gain and not guardrails(m, base_m, cfg) \
                            and (best is None or gain > best[0]):
                        best = (gain, [c1, c2], n2, m, runs)
        all_rejected.extend(rejected)
        if best is None:
            log(f"step {step + 1}: no candidate improves by >= {cfg.min_gain} within guardrails; stop")
            break
        gain, cs, new, m, runs = best
        for c in cs:
            c.evidence = {"predicted_days_saved": round(c.score, 2),
                          "train_on_time_before": cur_m["share_within_target"], "train_on_time_after": m["share_within_target"],
                          "train_median_before": cur_m["median_days_to_treatment"], "train_median_after": m["median_days_to_treatment"],
                          "accepted_together_with": [x.plain for x in cs if x is not c],
                          "records_reading": records_reading(c, cur)}
            steps.append(c)
        log(f"step {step + 1}: accept {' + '.join(f'{c.kind}({c.target}, {c.other})' for c in cs)} -> on-time "
            f"{m['share_within_target']:.3f}, median {m['median_days_to_treatment']} d  [{' + '.join(c.plain for c in cs)}]")
        cur, cur_m, cur_runs = new, m, runs
    held = cohorts(sc, cfg.heldout_seeds, cfg.n_heldout or cfg.n_train)
    h0, _ = evaluate(sc, fc0, held)
    h1, _ = evaluate(sc, cur, held)
    return {
        "scenario": sc.id, "start": fc0.id, "config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.__dict__.items()},
        "candidates_evaluated": tried,
        "rejected_by_guardrails": all_rejected[:20],
        "steps": [s.to_dict() for s in steps],
        "train": {"before": base_m, "after": cur_m},
        "heldout": {"before": h0, "after": h1},
        "selection_optimism_pp": round(100 * ((cur_m["share_within_target"] - base_m["share_within_target"])
                                              - (h1["share_within_target"] - h0["share_within_target"])), 2),
        "guardrails_heldout": guardrails(h1, h0, cfg),
        "flowchart_before": fc0.to_dict(),
        "flowchart_after": cur.to_dict(),
    }
