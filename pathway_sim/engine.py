"""Discrete-event engine: runs patients through a flowchart.

Resource types (docs/architecture.md):

* ``server``: appointment-book capacity. A patient who becomes ready books the
  earliest working day with a free slot (FIFO by readiness time). Fast-track
  patients may use reserved slots (``urgent_reserved_share``). Queues emerge
  when demand exceeds ``capacity_per_day``.
* ``delay``: the wait is drawn from a published distribution, no capacity.
  Used to re-time patients the way Stokstad et al. 2019 did.
* ``batch``: sessions on fixed weekdays (e.g. a weekly tumour board).
* ``none``: no wait.

Every node records which prerequisite became ready last (its *cause*). Tracing
causes back from a patient's exit gives the critical path, whose waiting and
service times add up exactly to the patient's time to exit.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from .dists import sample, uniform
from .patients import Patient
from .policy import PatientView, Policy, RulePolicy, _Names
from .scenario import Flowchart, Node, Scenario

DAY_START = 8 / 24      # appointments start 08:00
DAY_SPAN = 8 / 24       # and run over an 8-hour working day


@dataclass
class Event:
    node: str
    test: str
    resource: str
    stage: str
    t_ready: float
    t_start: float
    t_end: float
    t_result: float
    result: bool | None = None
    attempt: int = 0
    critical: bool = False

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


@dataclass
class PatientRun:
    patient: Patient
    status: dict[str, str] = field(default_factory=dict)
    result: dict[str, bool | None] = field(default_factory=dict)
    t_done: dict[str, float] = field(default_factory=dict)
    cause: dict[str, str | None] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    revealed: dict = field(default_factory=dict)
    priority: bool = False
    outcome: str | None = None
    exit_node: str | None = None
    t_exit: float | None = None
    t_diagnosis: float | None = None
    t_treatment: float | None = None
    choices: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        p = self.patient
        a = p.arrival

        def rel(x):
            return None if x is None else round(x - a, 4)

        return {
            "id": p.id, "group": p.group, "age": p.age, "condition": p.condition, "cancer": p.cancer,
            "arrival": round(a, 4), "outcome": self.outcome, "exit_node": self.exit_node,
            "t_exit": rel(self.t_exit), "t_diagnosis": rel(self.t_diagnosis), "t_treatment": rel(self.t_treatment),
            "fast_track": self.priority,
            "events": [e.to_dict() for e in self.events],
            "choices": self.choices,
        }


@dataclass
class RunLog:
    scenario: str
    flowchart: str
    seed: int
    patients: list[PatientRun]
    resources: dict[str, dict]
    target_days: float
    warmup_days: float
    flowchart_def: dict
    policy: str

    def to_dict(self, include_patients: bool = True) -> dict:
        d = {
            "scenario": self.scenario, "flowchart": self.flowchart, "seed": self.seed,
            "n_patients": len(self.patients), "target_days": self.target_days,
            "warmup_days": self.warmup_days, "policy": self.policy,
            "flowchart_def": self.flowchart_def, "resources": self.resources,
        }
        if include_patients:
            d["patients"] = [pr.to_dict() for pr in self.patients]
        return d


class _Server:
    def __init__(self, rid: str, spec: dict):
        self.rid = rid
        self.cap = int(spec["capacity_per_day"])
        self.reserved = float(spec.get("urgent_reserved_share", 0.0))
        self.normal_cap = max(1, int(math.floor(self.cap * (1 - self.reserved)))) if self.reserved else self.cap
        self.weekdays_only = bool(spec.get("weekdays_only", True))
        self.min_lead = float(spec.get("min_lead_days", 1.0))
        self.urgent_lead = float(spec.get("urgent_lead_days", self.min_lead))   # fast-track booking lead
        self.booked: dict[int, int] = {}

    def _slot(self, t_ready: float, priority: bool) -> tuple[int, int]:
        d = int(math.floor(t_ready + (self.urgent_lead if priority else self.min_lead)))
        limit = self.cap if priority else self.normal_cap
        for _ in range(100000):
            if not (self.weekdays_only and d % 7 in (5, 6)) and self.booked.get(d, 0) < limit:
                return d, self.booked.get(d, 0)
            d += 1
        raise RuntimeError(f"resource {self.rid}: no slot found")

    def preview(self, t_ready: float, priority: bool) -> float:
        """Start time the next booking would get, without booking it (queue state for policies)."""
        d, k = self._slot(t_ready, priority)
        return max(t_ready, d + DAY_START + DAY_SPAN * k / self.cap)

    def book(self, t_ready: float, priority: bool) -> float:
        d, k = self._slot(t_ready, priority)
        self.booked[d] = k + 1
        return max(t_ready, d + DAY_START + DAY_SPAN * k / self.cap)

    def summary(self, t0: float, t1: float) -> dict:
        days = [d for d in range(int(math.floor(t0)), int(math.ceil(t1)))
                if not (self.weekdays_only and d % 7 in (5, 6))]
        used = sum(self.booked.get(d, 0) for d in days)
        return {"type": "server", "capacity_per_day": self.cap,
                "utilisation": round(used / (self.cap * len(days)), 4) if days else None}


class _Batch:
    def __init__(self, rid: str, spec: dict):
        self.rid = rid
        self.weekdays = set(int(x) for x in spec["weekdays"])
        self.cutoff = float(spec.get("cutoff_days", 0.0))
        self.cap = spec.get("capacity_per_session")
        self.booked: dict[int, int] = {}

    def book(self, t_ready: float) -> float:
        d = int(math.ceil(t_ready + self.cutoff - 0.5 - 1e-9))  # first day whose noon is >= ready + cutoff
        for _ in range(100000):
            if d % 7 in self.weekdays and (self.cap is None or self.booked.get(d, 0) < int(self.cap)):
                self.booked[d] = self.booked.get(d, 0) + 1
                return d + 0.5
            d += 1
        raise RuntimeError(f"batch {self.rid}: no session found")


class Simulation:
    def __init__(self, sc: Scenario, fc: Flowchart, patients: list[Patient], policy: Policy | None, seed: int):
        self.sc, self.fc, self.patients, self.seed = sc, fc, patients, seed
        self.policy = policy or RulePolicy(fc.policy, seed)
        # how probabilities become a choice (spec 02, F2); legacy policies keep today's argmax
        self.decision_mode = getattr(self.policy, "decision_mode", "argmax")
        if self.decision_mode not in ("sample", "argmax"):
            raise ValueError(f"decision mode must be 'sample' or 'argmax', not {self.decision_mode!r}")
        self.backend_name = getattr(self.policy, "backend_name", type(self.policy).__name__)
        self.model_id = getattr(self.policy, "model_id", None)
        self.resources = {k: dict(v) for k, v in sc.resources.items()}
        for rid, ov in fc.resource_overrides.items():
            self.resources[rid] = {**self.resources[rid], **ov}
        self.tests = {k: dict(v) for k, v in sc.tests.items()}
        for tid, ov in fc.test_overrides.items():
            self.tests[tid] = {**self.tests[tid], **ov}
        self.order = self._topo()
        self.option_of = {o: n.id for n in fc.nodes.values() if n.kind == "choice" for o in n.options}
        self.servers: dict[str, _Server] = {}
        self.batches: dict[str, _Batch] = {}
        for rid, spec in self.resources.items():
            t = spec.get("type", "server")
            if t == "server":
                self.servers[rid] = _Server(rid, spec)
            elif t == "batch":
                self.batches[rid] = _Batch(rid, spec)
        self.heap: list = []
        self.seq = 0
        self.progress = None          # optional callback(done, total), set by simulate(progress=...)
        self.progress_every = 200

    def _topo(self) -> list[str]:
        fc = self.fc
        deps = {n.id: set(n.after) | set(n.after_any) | set(n.after_optional) for n in fc.nodes.values()}
        for n in fc.nodes.values():
            if n.kind == "choice":
                for o in n.options:
                    deps[o].add(n.id)
        order, seen = [], set()

        def visit(x):
            if x in seen:
                return
            seen.add(x)
            for y in sorted(deps[x], key=list(fc.nodes).index):
                visit(y)
            order.append(x)

        for x in fc.nodes:
            visit(x)
        return order

    def push(self, t: float, kind: str, pid: int, node: str = "", attempt: int = 0) -> None:
        self.seq += 1
        heapq.heappush(self.heap, (t, self.seq, kind, pid, node, attempt))

    # ------------------------------------------------------------------ main loop
    def run(self) -> RunLog:
        runs = {p.id: PatientRun(p) for p in self.patients}
        for p in self.patients:
            self.push(p.arrival, "arrive", p.id)
        done = 0
        while self.heap:
            t, _, kind, pid, node, attempt = heapq.heappop(self.heap)
            pr = runs[pid]
            if pr.outcome is not None:
                continue
            if kind == "arrive":
                for nid in self.fc.nodes:
                    pr.status[nid] = "pending"
                self.advance(pr, t)
            elif kind == "done":
                self.on_done(pr, node, attempt, t)
            elif kind == "exit":
                self.exit(pr, node, t)
            if self.progress is not None and pr.outcome is not None:   # this patient just finished
                done += 1
                if done % self.progress_every == 0:
                    self.progress(done, len(runs))
        if self.progress is not None:
            self.progress(len(runs), len(runs))
        # utilisation over the arrival window (excludes warm-up and the drain tail after the last arrival)
        horizon = max(pr.patient.arrival for pr in runs.values()) if runs else 0.0
        resources = {}
        for rid, s in self.servers.items():
            resources[rid] = s.summary(self.sc.warmup_days, horizon)
        for rid in self.resources:
            resources.setdefault(rid, {"type": self.resources[rid].get("type", "server")})
        log = RunLog(self.sc.id, self.fc.id, self.seed, list(runs.values()), resources,
                     self.sc.target_days, self.sc.warmup_days, self.fc.to_dict(), type(self.policy).__name__)
        for pr in log.patients:
            mark_critical(pr, self.fc)
        return log

    # ------------------------------------------------------------------ helpers
    def names(self, pr: PatientRun) -> _Names:
        d = _Names({"group": pr.patient.group, "age": pr.patient.age})
        d.update(pr.revealed)
        for nid, r in pr.result.items():
            d[nid] = r
        return d

    def option_leads(self, pr: PatientRun, options: list[str], t: float) -> dict[str, float]:
        """Days until the earliest appointment for each option that starts with a capacity-limited test."""
        out = {}
        for o in options:
            n = self.fc.nodes[o]
            if not n.test:
                continue
            rid = self.tests[n.test].get("resource", "none")
            if rid in self.servers:
                out[o] = round(self.servers[rid].preview(t, pr.priority) - t, 3)
        return out

    def view(self, pr: PatientRun, node: str, t: float, options: list[str] | None = None) -> PatientView:
        a = pr.patient.arrival
        hist = [(e.node, e.test, e.result, round(e.t_result - a, 3)) for e in pr.events if e.t_result <= t + 1e-9]
        v = PatientView(pr.patient.id, pr.patient.group, pr.patient.age, t - a, node, hist, dict(pr.revealed))
        v.priority = pr.priority
        v.offered = list(options or [])
        v.option_leads = self.option_leads(pr, options or [], t)
        return v

    def offered(self, pr: PatientRun, n: Node, t: float) -> list[str]:
        """Options on offer at a choice: ``availability: {option: {p_available: .., weekdays: [..]}}``.
        Unavailable options are dropped (deterministic per patient); if none remain, all are offered."""
        av = n.availability or {}
        out = []
        for o in n.options:
            rule = av.get(o)
            ok = True
            if rule:
                if "weekdays" in rule and int(math.floor(t)) % 7 not in set(rule["weekdays"]):
                    ok = False
                if "p_available" in rule and uniform(self.seed, pr.patient.id, "avail", n.id, o) >= float(rule["p_available"]):
                    ok = False
            if ok:
                out.append(o)
        return out or list(n.options)

    def pick_option(self, pr: PatientRun, n: Node, offered: list[str], probs: dict) -> str:
        """Choose among ``offered`` from ``probs``.

        ``argmax``: highest probability, ties broken by option order. ``sample``: inverse CDF over the
        offered options in the node's option order, driven by the common-random-number draw
        ``uniform(seed, patient, "mix", node)``, so the same patient facing the same probabilities at
        the same decision point makes the same choice in every flowchart variant."""
        if self.decision_mode == "argmax":
            return max(offered, key=lambda o: (probs.get(o, 0.0), -n.options.index(o)))
        w = [max(0.0, float(probs.get(o, 0.0))) for o in offered]
        total = sum(w)
        if total <= 0.0:
            return offered[0]
        u, acc, last = uniform(self.seed, pr.patient.id, "mix", n.id), 0.0, offered[0]
        for o, x in zip(offered, w):
            if x <= 0.0:
                continue
            last = o
            acc += x / total
            if u < acc:
                return o
        return last

    def ready_cause(self, pr: PatientRun, n: Node) -> tuple[bool, bool, str | None]:
        """(ready, dead, cause). Option nodes also need their choice to have picked them;
        ``forced`` nodes (retry fallbacks) bypass their prerequisites."""
        st = pr.status
        if st[n.id] == "forced":
            return True, False, pr.cause.get(n.id)
        cands = []
        if n.id in self.option_of:
            if st[n.id] != "enabled":
                return False, False, None
            c = self.option_of[n.id]
            cands.append((pr.t_done[c], c))
        for a in n.after:
            if st[a] in ("skipped", "failed"):
                return False, True, a
        if any(st[a] != "done" for a in n.after):
            return False, False, None
        cands += [(pr.t_done[a], a) for a in n.after]
        if any(st[a] not in ("done", "skipped", "failed") for a in n.after_optional):
            return False, False, None
        cands += [(pr.t_done[a], a) for a in n.after_optional]
        if n.after_any:
            done_any = [(pr.t_done[a], a) for a in n.after_any if st[a] == "done"]
            if not done_any:
                if all(st[a] in ("skipped", "failed") for a in n.after_any):
                    return False, True, n.after_any[0]
                return False, False, None
            cands.append(min(done_any))
        return True, False, (max(cands)[1] if cands else None)

    def skip(self, pr: PatientRun, nid: str, t: float, cause: str | None = None) -> None:
        pr.status[nid], pr.t_done[nid] = "skipped", t
        if cause is not None:
            pr.cause[nid] = cause
        n = self.fc.nodes[nid]
        if n.kind == "choice":
            for o in n.options:
                if pr.status[o] in ("pending", "enabled"):
                    self.skip(pr, o, t, nid)

    def revive_descendants(self, pr: PatientRun, fb: str) -> None:
        """A retry fallback that had been skipped (e.g. the option not chosen) now runs after all.
        Steps downstream of it that were skipped only because it was skipped go back to pending,
        so they are re-evaluated once it finishes. Options skipped by a choice that was actually made
        stay skipped."""
        if not hasattr(self, "_children"):
            self._children: dict[str, set[str]] = {x: set() for x in self.fc.nodes}
            for n in self.fc.nodes.values():
                for d in list(n.after) + list(n.after_any) + list(n.after_optional):
                    self._children[d].add(n.id)
                if n.kind == "choice":
                    for o in n.options:
                        self._children[n.id].add(o)
        stack, seen = list(self._children[fb]), set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            if pr.status.get(x) != "skipped":
                continue
            c = self.option_of.get(x)
            if c is not None and pr.status.get(c) == "done":
                continue
            pr.status[x] = "pending"
            pr.t_done.pop(x, None)
            pr.cause.pop(x, None)
            pr.result.pop(x, None)
            stack.extend(self._children[x])

    def advance(self, pr: PatientRun, t: float) -> None:
        changed = True
        while changed and pr.outcome is None:
            changed = False
            for nid in self.order:
                st = pr.status[nid]
                if st not in ("pending", "enabled", "forced"):
                    continue
                n = self.fc.nodes[nid]
                ready, dead, cause = self.ready_cause(pr, n)
                if dead:
                    self.skip(pr, nid, t, cause)
                    changed = True
                    continue
                if not ready:
                    continue
                pr.cause[nid] = cause
                changed = True
                if st != "forced" and n.code is not None and not n.code(self.names(pr)):
                    self.skip(pr, nid, t)
                    continue
                if n.kind == "choice":
                    offered = self.offered(pr, n, t)
                    probs = self.policy.choose(self.view(pr, nid, t, offered), offered)
                    pick = self.pick_option(pr, n, offered, probs)
                    pr.choices.append({"node": nid, "t": round(t - pr.patient.arrival, 4), "chosen": pick,
                                       "offered": offered,
                                       "probs": {k: round(float(v), 4) for k, v in probs.items()},
                                       "mode": self.decision_mode, "backend": self.backend_name,
                                       "model": self.model_id})
                    for o in n.options:
                        if o == pick:
                            pr.status[o] = "enabled"
                        else:
                            self.skip(pr, o, t, nid)
                    pr.status[nid], pr.t_done[nid] = "done", t
                elif n.test:
                    self.start(pr, n, 0, t)
                    if pr.outcome is not None:
                        return
                else:
                    pr.status[nid], pr.t_done[nid] = "done", t
                    pr.result.setdefault(nid, True)
                    if n.kind == "milestone" and n.milestone == "diagnosis" and pr.t_diagnosis is None:
                        pr.t_diagnosis = t
                    if n.kind == "exit":
                        self.exit(pr, nid, t)
                        return
                    if n.fast_track:
                        pr.priority = True
                break  # restart scan in topological order after any change
        if pr.outcome is None and not any(s == "active" for s in pr.status.values()):
            pr.outcome, pr.t_exit = "stuck", t

    def start(self, pr: PatientRun, n: Node, attempt: int, t_ready: float) -> None:
        test = self.tests[n.test]
        rid = test.get("resource", "none")
        spec = self.resources.get(rid, {"type": "none"})
        typ = spec.get("type", "server")
        pid, seed = pr.patient.id, self.seed
        t_ready0 = t_ready
        if test.get("extra_wait") is not None:   # e.g. a late referral before the queue
            t_ready = t_ready + max(0.0, sample(test["extra_wait"], uniform(seed, pid, "extra", n.test, attempt)))
        if typ == "server":
            t_start = self.servers[rid].book(t_ready, pr.priority)
        elif typ == "delay":
            wait = test.get("wait", spec.get("wait"))
            t_start = t_ready + sample(wait, uniform(seed, pid, "wait", n.test, attempt))
        elif typ == "batch":
            t_start = self.batches[rid].book(t_ready)
        else:
            t_start = t_ready + sample(test.get("wait"), uniform(seed, pid, "wait", n.test, attempt))
        t_start = max(t_start, t_ready0)
        if n.kind == "exit":
            ev = Event(n.id, n.test, rid, self.sc.stage_of(n), t_ready0, t_start, t_start, t_start, None, attempt)
            pr.events.append(ev)
            pr.status[n.id] = "active"
            self.push(t_start, "exit", pid, n.id, attempt)
            return
        t_end = t_start + sample(test.get("service_days"), uniform(seed, pid, "svc", n.test, attempt))
        t_result = t_end + sample(test.get("report_days"), uniform(seed, pid, "rep", n.test, attempt))
        ev = Event(n.id, n.test, rid, self.sc.stage_of(n), t_ready0, t_start, t_end, t_result, None, attempt)
        pr.events.append(ev)
        pr.status[n.id] = "active"
        self.push(t_result, "done", pid, n.id, attempt)

    def on_done(self, pr: PatientRun, nid: str, attempt: int, t: float) -> None:
        n = self.fc.nodes[nid]
        test = self.tests[n.test]
        res_list = pr.patient.results.get(n.test) or [True]
        r = res_list[min(attempt, len(res_list) - 1)]
        for e in reversed(pr.events):
            if e.node == nid and e.attempt == attempt:
                e.result = r
                break
        if r is None and n.retry and n.retry.get("on", "nondiagnostic") == "nondiagnostic":
            if attempt < int(n.retry.get("max", 1)):
                self.start(pr, n, attempt + 1, t)
                return
            fb = n.retry.get("fallback")
            if fb and pr.status.get(fb) in ("pending", "skipped"):
                pr.status[nid], pr.t_done[nid], pr.result[nid] = "failed", t, None
                pr.status[fb], pr.cause[fb] = "forced", nid
                self.revive_descendants(pr, fb)
                self.advance(pr, t)
                return
        pr.status[nid], pr.t_done[nid], pr.result[nid] = "done", t, r
        for a in test.get("reveals", []) or []:
            pr.revealed[a] = pr.patient.attributes.get(a)
        if n.fast_track:
            pr.priority = True
        if n.kind == "milestone" and n.milestone == "diagnosis" and pr.t_diagnosis is None:
            pr.t_diagnosis = t
        self.advance(pr, t)

    def exit(self, pr: PatientRun, nid: str, t: float) -> None:
        n = self.fc.nodes[nid]
        pr.status[nid], pr.t_done[nid] = "done", t
        pr.outcome, pr.exit_node, pr.t_exit = n.outcome, nid, t
        if n.outcome == "treatment":
            pr.t_treatment = t
            if pr.t_diagnosis is None:
                pr.t_diagnosis = t


def mark_critical(pr: PatientRun, fc: Flowchart) -> list[str]:
    """Mark events on the critical path (cause chain back from the exit node)."""
    if pr.exit_node is None:
        return []
    chain, x, seen = [], pr.exit_node, set()
    while x is not None and x not in seen:
        seen.add(x)
        chain.append(x)
        x = pr.cause.get(x)
    on = set(chain)
    for e in pr.events:
        if e.node in on:
            e.critical = True
    return chain


def simulate(sc: Scenario, fc: Flowchart | str, patients: list[Patient], policy: Policy | None = None,
             seed: int = 0, progress=None, progress_every: int = 200) -> RunLog:
    """Run ``patients`` through flowchart ``fc``. Deterministic in (patients, seed, policy).

    ``progress(done, total)`` is called every ``progress_every`` finished patients and once at the end;
    it may raise to abort the run. It never changes the result."""
    if isinstance(fc, str):
        fc = sc.flowcharts[fc]
    sim = Simulation(sc, fc, patients, policy, seed)
    sim.progress, sim.progress_every = progress, max(1, int(progress_every))
    return sim.run()
