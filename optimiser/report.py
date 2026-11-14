"""Turn a ``search`` result into the record the service returns (spec 05): one entry per accepted
change with a plain label, what the records said, what the rerun confirmed and the held-out number
after that change; plus the changes the safety checks blocked and the before/after report."""

from __future__ import annotations

from pathway_sim.scenario import Flowchart, Scenario

from .apply import apply_changes, linked_groups
from .edits import Edit, apply
from .labels import polish_change
from .search import cohorts, evaluate

HONESTY = ("Suggestions come from what a clinic's records would show. The acceptance rerun uses the same simulated "
           "patients, which in real life is a pilot. The numbers shown are from patients the search never saw.")


def _heldout_row(m: dict) -> dict:
    return {"on_time": m["share_within_target"], "median_days": m["median_days_to_treatment"],
            "missed_cancers": m["missed_cancers"], "tests_per_patient": m["tests_per_patient"]}


def build_report(sc: Scenario, fc0: Flowchart, res: dict, progress=None, policy_factory=None) -> dict:
    cfg = res["config"]
    held = cohorts(sc, cfg["heldout_seeds"], cfg.get("n_heldout") or cfg["n_train"])
    steps = res["steps"]
    groups = {i: g for g in linked_groups(steps) for i in g}
    changes, cur = [], fc0.copy(f"{fc0.id}_optimised")
    for i, st in enumerate(steps):
        cur = apply(sc, cur, Edit(st["kind"], st["target"], st["other"], st.get("plain", "")))
        if cur is None:
            raise RuntimeError(f"change {i} no longer applies: {st.get('plain')}")
        if progress:
            progress(i, max(1, len(steps)), f"checking change {i + 1} on unseen patients")
        m = res["heldout"]["after"] if i == len(steps) - 1 else evaluate(sc, cur, held, policy_factory)[0]
        ev = st.get("evidence") or {}
        changes.append({
            "index": i, "kind": st["kind"], "target": st["target"], "other": st["other"],
            "label": polish_change(fc0, st["kind"], st["target"], st["other"]),
            "raw": st.get("plain", ""),
            "records_reading": ev.get("records_reading", ""),
            "predicted_days_saved": ev.get("predicted_days_saved"),
            "linked_with": [j for j in groups[i] if j != i],
            "train": {"on_time_before": ev.get("train_on_time_before"), "on_time_after": ev.get("train_on_time_after"),
                      "median_before": ev.get("train_median_before"), "median_after": ev.get("train_median_after")},
            "heldout_after_this_change": _heldout_row(m),
        })
    blocked, seen = [], set()
    for r in sorted(res.get("rejected_by_guardrails", []), key=lambda r: -r["gain_pp"]):
        key = (r.get("kind"), r.get("target"), r.get("other"), r["change"])
        if key in seen:
            continue
        seen.add(key)
        label = polish_change(fc0, r["kind"], r["target"], r["other"]) if r.get("kind") else r["change"]
        blocked.append({"label": label, "raw": r["change"], "gain_pp": r["gain_pp"], "blocked_by": r["blocked_by"]})
    return {
        "changes": changes, "blocked": blocked,
        "heldout": res["heldout"], "train": res["train"],
        "selection_optimism_pp": res["selection_optimism_pp"], "guardrails_heldout": res["guardrails_heldout"],
        "candidates_evaluated": res["candidates_evaluated"],
        "n_train": cfg["n_train"], "n_heldout": cfg.get("n_heldout") or cfg["n_train"],
        "train_seeds": cfg["train_seeds"], "heldout_seeds": cfg["heldout_seeds"],
        "honesty": HONESTY,
        "proposed_flowchart_engine": res["flowchart_after"],
    }
