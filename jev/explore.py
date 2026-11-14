"""Exploration runs (ticket M6-8, spec 06 source 3): random choices at chosen decision points.

Practice rarely takes every option, so a log of practice says little about the options it avoids. In an
exploration run the chosen decision points pick uniformly at random among what is on offer (the other
points keep their normal backend), and every row gets an ``outcome`` from what happened afterwards in
the same simulated patient's pathway. Outcomes are read from the run log after the fact and are never part
of the context: a row's context is what was revealed at the decision.

This is a policy, not an engine change::

    rows = jev.explore.explore(sc, fc, n=4000, seed=7, points=["sample_choice"])

Each row also carries ``option_leads`` (the queue state the chooser saw), so a model can learn from it.
Outcome fields: ``usable_result`` (the chosen step returned a result; None if it never ran), ``days_to_result``
(decision to that step's last result), ``days_to_next_milestone`` (decision to the next milestone node reached),
``treated`` and ``days_to_treatment``. Which of these is "better" is a value judgement (decision D25) and
is not made here.
"""

from __future__ import annotations

from collections import defaultdict

from pathway_sim.dists import uniform

from .dataset import rows_from_patient

EXPLORE_KEY = "explore"


class ExplorationPolicy:
    """Engine ``Policy``: uniform random at ``points`` (None = every decision point), ``inner`` elsewhere."""

    def __init__(self, inner, points: list[str] | None = None, seed: int = 0):
        self.inner, self.points, self.seed = inner, (None if points is None else set(points)), seed
        self.decision_mode = getattr(inner, "decision_mode", "argmax")
        self.leads: dict[tuple, dict] = {}
        self.explored = 0
        self._last_explored = False

    @property
    def backend_name(self) -> str:
        return "explore" if self._last_explored else getattr(self.inner, "backend_name", type(self.inner).__name__)

    @property
    def model_id(self):
        return None if self._last_explored else getattr(self.inner, "model_id", None)

    def choose(self, view, options: list[str]) -> dict[str, float]:
        if self.points is not None and view.node not in self.points:
            self._last_explored = False
            return self.inner.choose(view, options)
        self._last_explored = True
        self.explored += 1
        k = int(uniform(self.seed, view.patient_id, EXPLORE_KEY, view.node) * len(options))
        self.leads[(view.patient_id, view.node)] = dict(getattr(view, "option_leads", {}) or {})
        return {o: float(i == k) for i, o in enumerate(options)}

    def run_summary(self) -> dict:
        fn = getattr(self.inner, "run_summary", None)
        return {"explored_decisions": self.explored, **(fn() if callable(fn) else {})}


def outcome_for(fc, pr, choice: dict) -> dict:
    """What happened after one decision, from the patient's own events (read after the run)."""
    a, t = pr.patient.arrival, choice["t"]
    evs = [e for e in pr.events if e.node == choice["chosen"]]
    out = {"usable_result": (any(e.result is not None for e in evs) if evs else None),
           "days_to_result": round(max(e.t_result for e in evs) - a - t, 3) if evs else None}
    miles = [pr.t_done[n] - a - t for n, nd in fc.nodes.items() if nd.milestone and n in pr.t_done and pr.status.get(n) == "done"
             and pr.t_done[n] - a >= t - 1e-9]
    out["days_to_next_milestone"] = round(min(miles), 3) if miles else None
    out["treated"] = pr.t_treatment is not None
    out["days_to_treatment"] = None if pr.t_treatment is None else round(pr.t_treatment - a - t, 3)
    return out


def exploration_rows(sc, fc, log, policy: ExplorationPolicy, seed: int | None = None, points: list[str] | None = None) -> list[dict]:
    rows = []
    for pr in log.patients:
        for row, ch in zip(rows_from_patient(sc, fc, pr, seed, log.warmup_days), pr.choices):
            if points is not None and row["decision_point"] not in points:
                continue
            row["outcome"] = outcome_for(fc, pr, ch)
            lead = policy.leads.get((pr.patient.id, row["decision_point"]))
            if lead:
                row["option_leads"] = {k: v for k, v in lead.items() if v is not None and v >= 0}
            rows.append(row)
    return rows


def explore(sc, fc, n: int, seed: int = 1, points: list[str] | None = None, backend: str | None = None, patients=None, progress=None):
    """Simulate ``n`` patients with random choices at ``points`` and return ``(rows, log)``. The remaining decision
    points use ``backend`` (default: the flowchart's own decision policy)."""
    from pathway_sim import generate_patients, simulate

    from .factory import prepare
    fc_run, inner = prepare(sc, fc, backend=backend, seed=seed)
    if points is not None:
        bad = [p for p in points if p not in fc_run.nodes or fc_run.nodes[p].kind != "choice"]
        if bad:
            raise ValueError(f"not decision points of this flowchart: {bad}")
    pol = ExplorationPolicy(inner, points, seed)
    log = simulate(sc, fc_run, patients or generate_patients(sc, n, seed), policy=pol, seed=seed, progress=progress)
    return exploration_rows(sc, fc_run, log, pol, seed, points), log


def outcome_summary(rows: list[dict]) -> dict:
    """Per decision point and option: rows and the average of each numeric outcome, to show that every option
    was tried. Descriptive only; no option is called better."""
    acc: dict = defaultdict(lambda: defaultdict(lambda: {"rows": 0, "sum": defaultdict(float), "n": defaultdict(int)}))
    for r in rows:
        a = acc[r["decision_point"]][r["chosen"]]
        a["rows"] += 1
        for k, v in (r.get("outcome") or {}).items():
            if v is not None:
                a["sum"][k] += float(v)
                a["n"][k] += 1
    return {pt: {o: {"rows": a["rows"], **{f"mean_{k}": round(a["sum"][k] / a["n"][k], 4) for k in a["sum"]}} for o, a in sorted(opts.items())}
            for pt, opts in acc.items()}
