"""Revealed-information analysis of a run log.

Everything here reads only what a clinic would see in its own records: when each step was
ordered, started and reported, what it showed, which choice was made, and when the patient left
the pathway. It never reads a patient's true condition. ``RevealedPatient`` enforces that: the
optimiser's proposal step only ever sees these objects.

Scores estimate how many days a change *could* save. They are biased in known ways (a late
test is only observed on patients who already passed earlier ones; patients who took an option
differ from those who did not), which is why every proposal is checked by a full rerun of the
same patients before it is accepted (see search.py).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from pathway_sim.engine import RunLog
from pathway_sim.scenario import Flowchart

from .edits import Edit


@dataclass
class RevealedPatient:
    id: int
    group: str
    arrival: float
    t_exit: float | None
    outcome: str | None             # treatment / discharged (what the clinic sees)
    t_done: dict[str, float]
    status: dict[str, str]
    cause: dict[str, str | None]
    critical: set[str]
    choices: list[dict]
    server_waits: list[tuple[str, float, float]]   # (node, t_ready, wait) at capacity-limited steps


def reveal(run: RunLog, server_resources: set[str]) -> list[RevealedPatient]:
    out = []
    for pr in run.patients:
        chain, x, seen = set(), pr.exit_node, set()
        while x is not None and x not in seen:
            seen.add(x)
            chain.add(x)
            x = pr.cause.get(x)
        out.append(RevealedPatient(
            id=pr.patient.id, group=pr.patient.group, arrival=pr.patient.arrival, t_exit=pr.t_exit,
            outcome=pr.outcome, t_done=dict(pr.t_done), status=dict(pr.status), cause=dict(pr.cause),
            critical=chain, choices=list(pr.choices),
            server_waits=[(e.node, e.t_ready, e.t_start - e.t_ready) for e in pr.events if e.resource in server_resources],
        ))
    return out


def _prereqs(fc: Flowchart, nid: str) -> list[str]:
    n = fc.nodes[nid]
    return list(n.after) + list(n.after_optional) + list(n.after_any)


def score_edit(fc: Flowchart, pts: list[RevealedPatient], e: Edit) -> float:
    """Expected days saved per patient on the critical path, estimated from revealed timestamps."""
    n = max(len(pts), 1)
    if e.kind == "detach" and e.other and "/" in e.other:
        x, (j, b) = e.target, e.other.split("/")
        others = [p for p in _prereqs(fc, x) if p != j] + [p for p in _prereqs(fc, j) if p != b]
        gain = 0.0
        for p in pts:
            if p.cause.get(x) != j or p.cause.get(j) != b or x not in p.critical or b not in p.t_done:
                continue
            base = [p.t_done[o] for o in others if o in p.t_done]
            gain += max(0.0, p.t_done[b] - (max(base) if base else p.arrival))
        return gain / max(len(pts), 1)
    if e.kind in ("detach", "relax"):
        x, a = e.target, e.other
        others = [p for p in _prereqs(fc, x) if p != a]
        a_pre = _prereqs(fc, a) if e.kind == "relax" else []
        gain = 0.0
        for p in pts:
            if p.cause.get(x) != a or x not in p.critical or a not in p.t_done:
                continue
            base = [p.t_done[o] for o in others + a_pre if o in p.t_done]
            floor = max(base) if base else p.arrival
            gain += max(0.0, p.t_done[a] - floor)
        return gain / n
    if e.kind == "standardise":
        # stratified by presentation group: time from the choice to exit, option o vs the rest
        gain = 0.0
        by_group: dict[str, list] = defaultdict(list)
        for p in pts:
            for c in p.choices:
                if c["node"] == e.target and p.t_exit is not None:
                    by_group[p.group].append((c["chosen"], p.t_exit - p.arrival - c["t"]))
        for g, rows in by_group.items():
            with_o = [d for ch, d in rows if ch == e.other]
            without = [d for ch, d in rows if ch != e.other]
            if with_o and without:
                gain += (sum(without) / len(without) - sum(with_o) / len(with_o)) * len(without) / n
        return gain
    if e.kind == "fast_track":
        total = 0.0
        for p in pts:
            if p.status.get(e.target) != "done":
                continue
            t0 = p.t_done[e.target]
            total += sum(w for node, tr, w in p.server_waits if tr >= t0)
        return 0.5 * total / n
    return 0.0


def where_time_goes(pts: list[RevealedPatient], fc: Flowchart) -> list[dict]:
    """Which prerequisite most often held each step back (revealed timestamps only)."""
    held: dict[tuple[str, str], list[float]] = defaultdict(list)
    for p in pts:
        for x in p.critical:
            a = p.cause.get(x)
            if a is None or a not in p.t_done:
                continue
            others = [p.t_done[o] for o in _prereqs(fc, x) if o != a and o in p.t_done]
            if others:
                held[(x, a)].append(max(0.0, p.t_done[a] - max(others)))
    rows = [{"step": x, "waited_for": a, "patients": len(v), "mean_days_held": round(sum(v) / len(v), 2)}
            for (x, a), v in held.items() if v]
    return sorted(rows, key=lambda r: -r["patients"] * r["mean_days_held"])
