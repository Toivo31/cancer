"""Run a small cohort through a flowchart with the team's decision model (the JEV, "Birch") deciding at every
choice node, next to the same patients decided by the flowchart's rule tables (decision D51: only the JEV
decides in the final model; the tables stay as the comparison baseline).

    python -m pathway_sim.jev_run --estimate                 # calls needed, nothing sent
    python -m pathway_sim.jev_run                            # Norway, 30 held-out patients, checkpoint 2350 via the local proxy
    python -m pathway_sim.jev_run --backend mock             # offline rehearsal against a local mock (never shown as the model)
    python demo/export_jev_flow.py                           # then: replay the recorded answers into demo/data/flow_jev_bundle.js

The local proxy (``python -m decision_api.server``, no key needed) forwards to the hosted gateway. The owner's
rules and the gateway's limits are built in: one call at a time, at least ``--interval`` seconds between
submissions (6 a minute), at most ``--per-hour`` submissions in any rolling hour (120 at the gateway), a hard
``--max-calls`` budget, every answer cached on disk under a directory keyed by the checkpoint, so a rerun after
a failure or an interruption sends only what is missing (resumable). Visible information only: the request
is built by :class:`jev.flow_policy.FlowBirchPolicy` and checked by ``jev.birch.check_visible``.

Patients are independent in these scenarios when every resource is a delay or a batch (no capacity queue), so
a small cohort gives each patient exactly the path they have in the full run; :func:`check_independent`
refuses a scenario with a capacity queue (a 30-patient run there would understate the waits).

Output: ``runs/jev_sim/<scenario>-<flowchart>-<backend>-n<N>.json``: provenance (checkpoint step and weight
hash from the responses, date, n, patient ids), every JEV decision with the rule table's pick on the same
patient state, agreement per node, and outcome metrics for both runs on the same patients.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "runs" / "jev_sim"
SCENARIOS = {"norway": ("scenarios/generated/stokstad_calibrated.yaml", "observed", 201),
             "finland": ("scenarios/finland_lung.yaml", "baseline", 301)}
DEFAULT_N = 30
COHORT_SIZE = 1000            # patients are the first N of the held-out cohort the page uses (seed 201, 1,000 patients)
GATEWAY_PER_MINUTE = 6
GATEWAY_PER_HOUR = 120
DEFAULT_INTERVAL = 11.0       # seconds between submissions: under 6 a minute with a margin
DEFAULT_PER_HOUR = 115        # under the gateway's 120 an hour with a margin
DEFAULT_MAX_CALLS = 160
WARM_CALL_SECONDS = 7.0       # documented warm latency is about 5-7 s; a cold start takes minutes (allow 660 s)
COLD_START_SECONDS = 360.0


class RunStopped(RuntimeError):
    """The run stopped before the end (budget, gateway refusal, interruption); a rerun resumes from the cache."""


# =============================================================================================== pacing

class RateGate:
    """Client-side pacing for the hosted gateway: ``interval`` seconds between submissions and at most
    ``per_hour`` in any rolling hour. ``clock`` and ``sleep`` are injectable (tests)."""

    def __init__(self, interval: float = DEFAULT_INTERVAL, per_hour: int = DEFAULT_PER_HOUR, clock=time.monotonic,
                 sleep=time.sleep, log=print):
        if interval < 60.0 / GATEWAY_PER_MINUTE:
            raise ValueError(f"interval must be at least {60.0 / GATEWAY_PER_MINUTE:.0f} s (gateway: {GATEWAY_PER_MINUTE} a minute)")
        if not 1 <= per_hour <= GATEWAY_PER_HOUR:
            raise ValueError(f"per_hour must be between 1 and {GATEWAY_PER_HOUR} (the gateway's limit)")
        self.interval, self.per_hour = float(interval), int(per_hour)
        self.clock, self.sleep, self.log = clock, sleep, log
        self.sent: list[float] = []
        self.waited = 0.0

    def wait(self) -> float:
        """Sleep until the next submission is allowed; returns the seconds slept."""
        now = self.clock()
        due = now
        if self.sent:
            due = max(due, self.sent[-1] + self.interval)
        recent = [t for t in self.sent if t > now - 3600.0]
        if len(recent) >= self.per_hour:
            due = max(due, recent[-self.per_hour] + 3600.0)
            self.log(f"  hourly limit: {len(recent)} calls in the last hour; waiting {due - now:.0f} s")
        slept = max(0.0, due - now)
        if slept:
            self.sleep(slept)
            self.waited += slept
        self.sent.append(self.clock())
        return slept


# =============================================================================================== backend

def make_backend(kind: str, url: str | None = None, max_calls: int = DEFAULT_MAX_CALLS, cache_dir: str | None = None):
    """``(backend, closer)``. ``bridge``: the owner's ``decision_api.jev_bridge.backend()`` (pinned to checkpoint
    2350 and its weight hash; refuses any other model and any cache entry of another model). ``birch``: plain
    ``jev.birch.BirchBackend`` with its defaults. ``mock``: an in-process mock of the proxy (``backend.mode`` =
    mock; never cached with the model's answers, never shown as the model)."""
    opts = {"max_calls": int(max_calls)}
    if url:
        opts["url"] = url
    if cache_dir:
        opts["cache_dir"] = cache_dir
    if kind == "bridge":
        try:
            from decision_api.jev_bridge import backend as bridge_backend
        except ImportError as e:
            raise SystemExit("decision_api.jev_bridge is not on this branch yet (lane w9/jev-install brings it from "
                             f"origin/main): {e}. Merge it first, or use --backend birch once jev/birch.py defaults to 2350.")
        return bridge_backend(**opts), (lambda: None)
    from jev.birch import BirchBackend
    if kind == "birch":
        return BirchBackend(**opts), (lambda: None)
    if kind == "mock":
        from jev.birch_mock import MockProxy
        m = MockProxy().__enter__()
        opts.setdefault("cache_dir", str(ROOT / "runs" / "jev_cache" / "mock"))
        opts["url"] = m.url
        return BirchBackend(allow_non_model=True, **opts), (lambda: m.__exit__(None, None, None))
    raise SystemExit(f"unknown backend {kind!r} (bridge, birch, mock)")


class Ledger:
    """Counts and identities of every answer (live or cached), read from the responses themselves."""

    def __init__(self):
        self.live = 0
        self.cached = 0
        self.identities: Counter = Counter()
        self.latency_ms: list[float] = []
        self.wall_s: list[float] = []

    def identity(self, resp: dict) -> str:
        b = resp.get("backend") or {}
        key = json.dumps({"mode": b.get("mode"), "step": b.get("step"), "checkpoint_sha256": b.get("checkpoint_sha256"),
                          "model": b.get("model")}, sort_keys=True)
        self.identities[key] += 1
        return key


def instrument(backend, gate: RateGate | None, ledger: Ledger, log=print):
    """Wrap the backend instance's live call (pacing, ledger) and cache read (ledger). Instance-level wrappers:
    ``jev/birch.py`` and the owner's bridge stay as they are."""
    call, get = backend._call, backend._cache_get

    def paced_call(body, rid):
        if gate is not None:
            gate.wait()
        t0 = time.monotonic()
        resp = call(body, rid)
        ledger.live += 1
        ledger.wall_s.append(time.monotonic() - t0)
        if isinstance(resp.get("latency_ms"), (int, float)):
            ledger.latency_ms.append(float(resp["latency_ms"]))
        ledger.identity(resp)
        log(f"  call {ledger.live}: {rid} {ledger.wall_s[-1]:.1f} s")
        return resp

    def counted_get(key):
        resp = get(key)
        if resp is not None:
            ledger.cached += 1
            ledger.identity(resp)
        return resp

    backend._call, backend._cache_get = paced_call, counted_get
    return backend


# =============================================================================================== policy wrapper

class ComparingPolicy:
    """Delegates every choice to the JEV policy and records, for the same patient state, what the rule table
    would have picked (``RulePolicy`` is deterministic per seed, patient and node)."""

    def __init__(self, jev_policy, rule_policy, labels: dict):
        self.jev, self.rule, self.labels = jev_policy, rule_policy, labels
        self.decisions: list[dict] = []

    # the engine reads these for the run log
    @property
    def decision_mode(self):
        return self.jev.decision_mode

    @property
    def backend_name(self):
        return self.jev.backend_name

    @property
    def model_id(self):
        return self.jev.model_id

    def choose(self, view, options):
        probs = self.jev.choose(view, options)
        rp = self.rule.choose(view, options)
        jev_pick = max(options, key=lambda o: (probs.get(o, 0.0), -options.index(o)))
        rule_pick = max(options, key=lambda o: (rp.get(o, 0.0), -options.index(o)))
        self.decisions.append({"patient": view.patient_id, "node": view.node, "t_days": round(view.t_now, 3),
                               "offered": list(options), "jev_probs": {k: round(float(v), 4) for k, v in probs.items()},
                               "jev_pick": jev_pick, "rule_pick": rule_pick, "single_option": len(options) == 1,
                               "explanation": getattr(self.jev, "last_explanation", None)})
        return probs


class CountingPolicy:
    """Rule-table picks (or always the first option) and a count of decisions that would reach the model."""

    def __init__(self, inner=None):
        self.inner, self.calls, self.by_node = inner, 0, Counter()

    def choose(self, view, options):
        if len(options) > 1:
            self.calls += 1
            self.by_node[view.node] += 1
        if self.inner is not None:
            return self.inner.choose(view, options)
        return {o: (1.0 if i == 0 else 0.0) for i, o in enumerate(options)}


# =============================================================================================== cohort

def load(scenario_key: str):
    from pathway_sim import load_scenario
    path, fcid, seed = SCENARIOS[scenario_key]
    return load_scenario(ROOT / path), fcid, seed


def check_independent(sc) -> None:
    """A small cohort stands for itself only when patients do not share a capacity queue."""
    shared = [rid for rid, r in sc.resources.items() if r.get("type", "server") not in ("delay", "batch")]
    if shared:
        raise SystemExit(f"{sc.id}: resources {shared} are capacity queues; a small cohort would not see the waits "
                         "of the full run. This runner only takes scenarios whose resources are delays or batches.")


def select_patients(sc, n: int, seed: int):
    """The first ``n`` measured patients of the held-out cohort (seed, 1,000 patients) the simulator page uses."""
    from pathway_sim.patients import generate_patients
    pts = [p for p in generate_patients(sc, COHORT_SIZE, seed) if p.arrival >= sc.warmup_days]
    if n > len(pts):
        raise SystemExit(f"only {len(pts)} measured patients in the cohort")
    return pts[:n]


def estimate(sc, fc, patients, seed: int) -> dict:
    """Decisions with more than one option (each is one model call unless cached), under the rule tables and
    under 'always the first option' (which here takes every branch that leads to further decisions)."""
    from pathway_sim import simulate
    from pathway_sim.policy import RulePolicy
    rule = CountingPolicy(RulePolicy(fc.policy, seed))
    simulate(sc, fc, patients, policy=rule, seed=seed)
    first = CountingPolicy()
    simulate(sc, fc, patients, policy=first, seed=seed)
    hi = max(rule.calls, first.calls)
    minutes = hi * DEFAULT_INTERVAL / 60.0
    return {"n_patients": len(patients), "calls_rule_path": rule.calls, "calls_first_option_path": first.calls,
            "calls_estimate": hi, "per_node": dict(first.by_node),
            "minutes_paced": round(minutes, 1),
            "minutes_with_cold_start": round(minutes + COLD_START_SECONDS / 60.0, 1),
            "hours_at_gateway_limit": round(hi / GATEWAY_PER_HOUR, 2)}


# =============================================================================================== comparison

def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def outcomes(run, target: float) -> dict:
    prs = run.patients
    days = [pr.t_treatment - pr.patient.arrival for pr in prs if pr.t_treatment is not None]
    k = sum(1 for d in days if d <= target + 1e-9)
    tests = [sum(1 for e in pr.events if e.test) for pr in prs]
    return {"n": len(prs), "treated": len(days), "within_target": k, "share_within_target": round(k / len(prs), 4) if prs else None,
            "share_ci95": wilson(k, len(prs)), "median_days_to_treatment": round(statistics.median(days), 2) if days else None,
            "mean_days_to_treatment": round(statistics.fmean(days), 2) if days else None,
            "steps_per_patient": round(statistics.fmean(tests), 3) if tests else None}


def per_patient_days(run) -> dict:
    return {pr.patient.id: (pr.t_treatment - pr.patient.arrival) if pr.t_treatment is not None else None for pr in run.patients}


def agreement(decisions: list[dict], rule_cfg: dict) -> dict:
    """Per node: how often the JEV's pick equals the rule table's pick on the same state, the JEV's choice
    shares, its mean probability per option, and the table's own mix (observed practice) for reference."""
    by = defaultdict(list)
    for d in decisions:
        if not d["single_option"]:
            by[d["node"]].append(d)
    out = {}
    for node, ds in by.items():
        opts = ds[0]["offered"]
        n = len(ds)
        same = sum(1 for d in ds if d["jev_pick"] == d["rule_pick"])
        mix = (rule_cfg.get(node) or {}).get("mix")
        out[node] = {"n": n, "agree": same, "agreement": round(same / n, 4),
                     "jev_share": {o: round(sum(1 for d in ds if d["jev_pick"] == o) / n, 4) for o in opts},
                     "rule_share": {o: round(sum(1 for d in ds if d["rule_pick"] == o) / n, 4) for o in opts},
                     "jev_mean_prob": {o: round(statistics.fmean(d["jev_probs"].get(o, 0.0) for d in ds), 4) for o in opts},
                     "table_mix": mix, "table_source": (rule_cfg.get(node) or {}).get("source")}
    return out


def paired(rule_days: dict, jev_days: dict) -> dict:
    diffs = [jev_days[i] - rule_days[i] for i in rule_days if rule_days[i] is not None and jev_days.get(i) is not None]
    return {"n": len(diffs), "median_diff_days": round(statistics.median(diffs), 2) if diffs else None,
            "mean_diff_days": round(statistics.fmean(diffs), 2) if diffs else None,
            "jev_faster": sum(1 for x in diffs if x < -1e-6), "jev_slower": sum(1 for x in diffs if x > 1e-6),
            "same": sum(1 for x in diffs if abs(x) <= 1e-6)}


CAVEATS = [
    "Small cohort: with 30 patients a share has a 95% interval about 30 points wide; the paired per-patient difference is the firmer number.",
    "Agreement is measured on identical patient states (same patient, same node, same history): the rule table's pick there is a draw from the observed practice mix, not a clinical gold standard. Disagreement says the model chooses differently from the Norwegian centre's observed mix, not that either is wrong.",
    "The outcome is time to treatment only. The simulator gives no diagnostic yield for tissue sampling and no harm for skipping it, so a decider that skips tests looks faster here without being better care.",
    "Some choice nodes encode timing slippage the centre observed (PET-CT or exercise test ordered late). Offered as an explicit option, 'order it on time' is an easy answer; the tables reproduce slippage the model is not asked to explain.",
    "One checkpoint (2350), argmax of its scores, our own wording of the case and options (jev/flow_policy.py). Other wording can change the scores; the model's training data are not documented (D63).",
]


# =============================================================================================== run

def out_path(scenario_key: str, fcid: str, backend: str, n: int) -> Path:
    return OUT_DIR / f"{scenario_key}-{fcid}-{backend}-n{n}.json"


def run(scenario_key: str = "norway", n: int = DEFAULT_N, backend: str = "bridge", url: str | None = None,
        max_calls: int = DEFAULT_MAX_CALLS, interval: float = DEFAULT_INTERVAL, per_hour: int = DEFAULT_PER_HOUR,
        cache_dir: str | None = None, mode: str = "argmax", out: Path | None = None, log=print, gate=None) -> dict:
    from pathway_sim import simulate
    from pathway_sim.policy import RulePolicy
    from jev.flow_policy import FlowBirchPolicy

    sc, fcid, seed = load(scenario_key)
    check_independent(sc)
    fc = sc.flowcharts[fcid]
    patients = select_patients(sc, n, seed)
    est = estimate(sc, fc, patients, seed)
    log(f"{scenario_key}/{fcid}: {n} patients; about {est['calls_estimate']} model calls if nothing is cached "
        f"(~{est['minutes_paced']} min paced, add a cold start of several minutes)")
    if est["calls_estimate"] > max_calls:
        log(f"  note: the estimate is above --max-calls {max_calls}; the run stops there and a rerun resumes from the cache")

    be, close = make_backend(backend, url, max_calls, cache_dir)
    ledger = Ledger()
    if gate is None and backend != "mock":
        gate = RateGate(interval, per_hour, log=log)
    instrument(be, gate, ledger, log)
    jev = FlowBirchPolicy(be, sc, fc, mode=mode)
    cmp_ = ComparingPolicy(jev, RulePolicy(fc.policy, seed), {})
    t0 = time.monotonic()
    stopped = None
    try:
        jev_run = simulate(sc, fc, patients, policy=cmp_, seed=seed)
    except KeyboardInterrupt:
        stopped = "interrupted"
    except Exception as e:                         # BirchError and friends: loud, resumable
        stopped = f"{type(e).__name__}: {e}"
    finally:
        close()
    elapsed = time.monotonic() - t0
    if stopped:
        log(f"STOPPED after {ledger.live} live calls and {ledger.cached} cached answers: {stopped}")
        log("Every answer so far is cached; run the same command again to resume.")
        raise RunStopped(stopped)

    rule_run = simulate(sc, fc, patients, seed=seed)
    ids = list(ledger.identities)
    ident = json.loads(ids[0]) if len(ids) == 1 else None
    if len(ids) > 1:
        log(f"WARNING: answers from more than one model identity: {ids}")
    summary = be.summary() if hasattr(be, "summary") else {}
    doc = {
        "format": "jev-sim-run/1",
        "provenance": {
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "scenario": sc.id, "scenario_key": scenario_key, "flowchart": fcid, "cohort_seed": seed,
            "cohort": f"first {n} of the held-out cohort (seed {seed}, {COHORT_SIZE} patients) used on the simulator page",
            "n_patients": n, "patient_ids": [p.id for p in patients],
            "backend": backend, "decision_mode": mode, "url": getattr(be, "url", None),
            "cache_dir": str(be.cache_dir) if getattr(be, "cache_dir", None) else None,
            "model_identity": ident, "model_identities": {k: v for k, v in ledger.identities.items()},
            "checkpoint_step": (ident or {}).get("step"), "checkpoint_sha256": (ident or {}).get("checkpoint_sha256"),
            "is_model": bool(ident and ident.get("mode") == "model"),
            "calls_live": ledger.live, "answers_from_cache": ledger.cached,
            "single_option_decisions": sum(1 for d in cmp_.decisions if d["single_option"]),
            "latency_ms_median": round(statistics.median(ledger.latency_ms), 1) if ledger.latency_ms else None,
            "wall_seconds": round(elapsed, 1), "paced_wait_seconds": round(gate.waited, 1) if gate else 0.0,
            "backend_summary": summary, "estimate": est,
            "request_builder": "jev/flow_policy.py FlowBirchPolicy (visible state only; check_visible on every payload)"},
        "decisions": cmp_.decisions,
        "agreement": agreement(cmp_.decisions, fc.policy),
        "outcomes": {"rule_tables": outcomes(rule_run, sc.target_days), "jev": outcomes(jev_run, sc.target_days)},
        "paired": paired(per_patient_days(rule_run), per_patient_days(jev_run)),
        "target_days": sc.target_days,
        "caveats": CAVEATS,
    }
    out = out or out_path(scenario_key, fcid, backend, n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1))
    log(report(doc))
    log(f"wrote {out}")
    log(f"next: python demo/export_jev_flow.py --run {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}   "
        "(replays the recorded probabilities, no calls; writes demo/data/flow_jev_bundle.js)")
    return doc


def report(doc: dict) -> str:
    p, o = doc["provenance"], doc["outcomes"]
    lines = [f"model: {p['model_identity']}  live calls {p['calls_live']}, cached {p['answers_from_cache']}"]
    for node, a in doc["agreement"].items():
        lines.append(f"  {node:<14} n={a['n']:3d}  agree {a['agreement']:.0%}  JEV {a['jev_share']}  table mix {a['table_mix']}")
    for k in ("rule_tables", "jev"):
        m = o[k]
        lines.append(f"  {k:<12} within {doc['target_days']:.0f} d: {m['within_target']}/{m['n']} "
                     f"({m['share_within_target']:.0%}, 95% {m['share_ci95']}), median {m['median_days_to_treatment']} d")
    pr = doc["paired"]
    lines.append(f"  paired: JEV faster for {pr['jev_faster']}, slower for {pr['jev_slower']}, same for {pr['same']}; "
                 f"median difference {pr['median_diff_days']} d")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scenario", default="norway", choices=sorted(SCENARIOS))
    ap.add_argument("--n", type=int, default=DEFAULT_N, help="patients (default 30)")
    ap.add_argument("--backend", default="bridge", choices=("bridge", "birch", "mock"),
                    help="bridge: the owner's checkpoint-2350 pin (default); birch: jev.birch defaults; mock: offline rehearsal")
    ap.add_argument("--url", help="local proxy url (default http://127.0.0.1:8771)")
    ap.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS, help="hard limit on live calls in this run")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="seconds between submissions (>= 10)")
    ap.add_argument("--per-hour", type=int, default=DEFAULT_PER_HOUR, help="submissions in any rolling hour (<= 120)")
    ap.add_argument("--cache-dir", help="override the cache directory (default: the backend's, keyed by checkpoint)")
    ap.add_argument("--mode", default="argmax", choices=("argmax", "sample"))
    ap.add_argument("--estimate", action="store_true", help="print the call estimate and exit; nothing is sent")
    a = ap.parse_args(argv)
    if a.estimate:
        sc, fcid, seed = load(a.scenario)
        check_independent(sc)
        print(json.dumps(estimate(sc, sc.flowcharts[fcid], select_patients(sc, a.n, seed), seed), indent=1))
        return 0
    try:
        run(a.scenario, a.n, a.backend, a.url, a.max_calls, a.interval, a.per_hour, a.cache_dir, a.mode)
    except RunStopped:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
