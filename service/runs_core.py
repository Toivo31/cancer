"""Run and optimisation work that happens inside a job process (spec 03, 05).

Everything here is plain functions on documents and engine objects; the routes only start jobs and read
results. A job receives ids, rebuilds its inputs from the stored *spec snapshot* (world, flowchart
document, policy, n, seeds), writes large results straight to disk and returns a small dict, so a
19k-patient run never travels through a pipe and a later edit of the project cannot change a stored run.

Memory: one seed at a time. A Finnish seed (about 19k patients) holds a few hundred MB while it runs
and is released before the next seed; the patient log and the decision rows are streamed to gzip.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from pathlib import Path

from pathway_sim import compute_metrics, generate_patients, simulate
from pathway_sim.documents import canonical_json, documents_to_scenario, flowchart_to_document

from .store import Store

BLOB_KEY = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


# ------------------------------------------------------------------------------------ identity
def _engine_version() -> str:
    """Short hash of the simulation sources: a run is only a cache hit under the same engine."""
    h = hashlib.sha1()
    root = Path(__file__).resolve().parent.parent
    for pkg in ("pathway_sim", "jev"):
        for f in sorted((root / pkg).glob("*.py")) if (root / pkg).exists() else []:
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:10]


ENGINE_VERSION = _engine_version()


def _hash(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()[:20]


def patients_key(world: dict, n: int, seeds: list[int]) -> str:
    """Two runs with the same key simulate exactly the same patients (the flowchart does not enter patient generation)."""
    return _hash({"world": world, "n": n, "seeds": list(seeds), "engine": ENGINE_VERSION})


def run_key(world: dict, flowchart_doc: dict, decision_policy, n: int, seeds: list[int]) -> str:
    """Identity of a run: (world, flowchart version, decision policy, n, seeds, engine version)."""
    return _hash({"world": world, "flowchart": flowchart_doc, "policy": decision_policy, "n": n,
                  "seeds": list(seeds), "engine": ENGINE_VERSION})


def min_patients(world: dict) -> int:
    """Fewest patients that leave any measured after the warm-up (arrivals are Poisson at ``rate_per_day``)."""
    rate = float((world.get("arrivals") or {}).get("rate_per_day") or 0)
    return int(rate * float(world.get("warmup_days") or 0)) + 50


# ------------------------------------------------------------------------------------ metrics
def mean_deep(ms: list[dict]) -> dict:
    """Mean of numeric leaves across seeds, recursively (the optimiser's own mean only goes one level)."""
    def merge(vals):
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        if all(isinstance(v, dict) for v in vals):
            keys = list(dict.fromkeys(k for v in vals for k in v))
            return {k: merge([v.get(k) for v in vals]) for k in keys}
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            return round(sum(vals) / len(vals), 4)
        return vals[0]
    out = merge(ms)
    # keys whose value is None in every seed vanish above: restore them for a stable shape
    for k in ms[0]:
        out.setdefault(k, None)
    return out


def headline(m: dict) -> dict:
    return {"on_time": m.get("share_within_target"), "median_days": m.get("median_days_to_treatment"),
            "missed_cancers": m.get("missed_cancers"), "tests_per_patient": m.get("tests_per_patient"),
            "n": m.get("n"), "n_cancer": m.get("n_cancer"), "stuck": m.get("stuck")}


# ------------------------------------------------------------------------------------ files
def stream_path(store: Store, project_id: str, kind: str, key: str) -> Path:
    for part in (project_id, kind, key):
        if not BLOB_KEY.match(part):
            raise ValueError(f"bad path part {part!r}")
    return store.blob_dir / project_id / kind / f"{key}.jsonl.gz"


class LineWriter:
    """Atomic gzip JSON-lines writer: the file appears only when closed cleanly."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.tmp = path, path.with_name(path.name + f".{os.getpid()}.tmp")
        self.f = gzip.open(self.tmp, "wb", compresslevel=5)

    def write(self, obj) -> None:
        self.f.write(json.dumps(obj, separators=(",", ":")).encode() + b"\n")

    def close(self) -> None:
        self.f.close()
        os.replace(self.tmp, self.path)

    def abort(self) -> None:
        self.f.close()
        self.tmp.unlink(missing_ok=True)


def read_lines(path: Path, offset: int = 0, limit: int | None = None):
    with gzip.open(path, "rb") as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            if limit is not None and i >= offset + limit:
                break
            yield json.loads(line)


def count_lines(path: Path) -> int:
    with gzip.open(path, "rb") as f:
        return sum(1 for _ in f)


# ------------------------------------------------------------------------------------ decisions
def decision_rows(sc, fc, pr, seed: int, warmup: float):
    """One dataset row per decision the patient met (spec 06): the request that was made plus the answer."""
    a = pr.patient.arrival
    events = sorted(pr.events, key=lambda e: e.t_result)
    for ch in pr.choices:
        t = ch["t"]
        hist, attrs, fast = [], {}, False
        for e in events:
            rel = e.t_result - a
            if rel > t + 1e-9:
                break
            hist.append({"step": e.node, "test": e.test, "result": e.result, "t_days": round(rel, 3)})
            for k in sc.tests.get(e.test, {}).get("reveals") or []:
                attrs[k] = pr.patient.attributes.get(k)
            if e.node in fc.nodes and fc.nodes[e.node].fast_track:
                fast = True
        yield {"decision_point": ch["node"], "patient_id": f"s{seed}:{pr.patient.id}", "t_days": t,
               "context": {"group": pr.patient.group, "age": pr.patient.age, "t_days": t, "fast_track": fast,
                           "attributes": attrs, "history": hist},
               "offered": ch["offered"], "chosen": ch["chosen"], "probs": ch["probs"],
               "measured": a >= warmup}


# ------------------------------------------------------------------------------------ policy hook
def policy_for(sc, fc, doc: dict, seed: int):
    """``(flowchart, policy)`` to simulate with for one seed.

    The ``rule`` backend (today's YAML policies) is the engine's default (policy None). ``stub`` and
    ``http`` go through ``jev.prepare``, which may hand back a migrated copy of the flowchart."""
    dp = doc.get("decision_policy") or {}
    backend = dp.get("backend", "rule")
    if backend == "rule":
        return fc, None
    from .policy import build_policy
    return build_policy(sc, fc, doc, seed)


# ------------------------------------------------------------------------------------ bundle
def build_bundle(sc, fc, label: str, metrics: dict, title: str | None = None, baseline: dict | None = None) -> dict:
    """Result in the dashboard bundle format (demo/README.md): one scenario, this run as the baseline.

    With ``baseline`` = ``{"label", "metrics", "sc", "fc"}`` the other run becomes the baseline and this
    run the single variant, so the dashboard's before/after screens show the comparison."""
    import datetime as dt

    from demo.export import assumptions, display_flowchart, rekey_nodes
    here = {"label": label, "metrics": rekey_nodes(metrics, sc, fc)}
    if baseline:
        base = {"label": baseline["label"], "metrics": rekey_nodes(baseline["metrics"], baseline["sc"], baseline["fc"])}
        before = display_flowchart(baseline["sc"], baseline["fc"])
        variants = [{**here, "changes": [], "role": "run"}]
    else:
        base, before, variants = here, display_flowchart(sc, fc), []
    scenario = {"id": sc.id, "title": title or sc.raw.get("name") or sc.id, "description": sc.description,
                "target_days": sc.target_days, "baseline": base, "variants": variants,
                "flowchart_before": before, "flowchart_after": display_flowchart(sc, fc)}
    return {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "fixture": False,
            "scenarios": [scenario], "assumptions": assumptions()}


# ------------------------------------------------------------------------------------ the run job
def load_spec(store: Store, project_id: str, kind: str, key: str) -> dict:
    return store.get_blob(project_id, kind, key)


def _scenario_for(spec: dict):
    doc = dict(spec["flowchart_doc"])
    if spec.get("decision_policy") is not None:
        doc["decision_policy"] = spec["decision_policy"]
    sc = documents_to_scenario(spec["world"], [doc])
    return sc, sc.flowcharts[doc["id"]], doc


def execute_run(ctx, data_dir: str, project_id: str, run_id: str) -> dict:
    """Job function: simulate every seed, write metrics, bundle, patient log and decision rows."""
    from .runs_db import Runs
    store = Store(data_dir)
    runs = Runs(store)
    spec = load_spec(store, project_id, "runspec", run_id)
    runs.update(run_id, status="running", started_at=_now())
    sc, fc, doc = _scenario_for(spec)
    seeds, n = spec["seeds"], spec["n"]
    per_seed, resources, written = [], {}, []
    pw = dw = None
    try:
        for i, seed in enumerate(seeds):
            ctx.log(f"seed {seed}: generating {n} patients")
            pts = generate_patients(sc, n, seed)
            ctx.progress(i, len(seeds), f"seed {seed} ({i + 1} of {len(seeds)})", force=True)
            fc_run, pol = policy_for(sc, fc, doc, seed)
            log = simulate(sc, fc_run, pts, policy=pol, seed=seed,
                           progress=lambda d, t, i=i, seed=seed: ctx.progress(i + d / max(t, 1), len(seeds),
                                                                             f"seed {seed}: {d} of {t} patients"),
                           progress_every=250)
            m = compute_metrics(log, sc)
            per_seed.append(m)
            resources[str(seed)] = log.resources
            pw = LineWriter(stream_path(store, project_id, "runlogs", f"{run_id}_s{seed}"))
            dw = LineWriter(stream_path(store, project_id, "decisions", f"{run_id}_s{seed}"))
            written += [pw, dw]
            for pr in log.patients:
                pw.write({**pr.to_dict(), "seed": seed})
                for row in decision_rows(sc, fc, pr, seed, log.warmup_days):
                    dw.write(row)
            pw.close()
            dw.close()
            pw = dw = None
            del log, pts
        metrics = mean_deep(per_seed)
        bundle = build_bundle(sc, fc, spec.get("label") or run_id, metrics, title=spec["world"].get("name"))
        store.put_blob(project_id, "bundles", run_id, bundle)
        store.put_blob(project_id, "metrics", run_id, {"mean": metrics, "per_seed": per_seed, "seeds": seeds})
        runs.update(run_id, status="succeeded", finished_at=_now(), metrics_json=json.dumps(metrics),
                    headline_json=json.dumps(headline(metrics)),
                    per_seed_json=json.dumps([{"seed": s, **headline(m)} for s, m in zip(seeds, per_seed)]),
                    resources_json=json.dumps(resources), progress=1.0)
        ctx.progress(1, 1, "done", force=True)
        return {"run_id": run_id, "headline": headline(metrics)}
    except BaseException:
        for w in (pw, dw):
            if w is not None:
                w.abort()
        raise


def _now() -> str:
    from .store import now
    return now()


# ------------------------------------------------------------------------------------ optimisation job
def execute_optimisation(ctx, data_dir: str, project_id: str, opt_id: str) -> dict:
    """Job function: ``optimiser.search`` on the stored spec, then the report with labels and evidence."""
    from optimiser import Config, search
    from optimiser.report import build_report
    from pathway_sim.scenario import parse_flowchart

    from .runs_db import Optimisations
    store = Store(data_dir)
    opts = Optimisations(store)
    spec = load_spec(store, project_id, "optspec", opt_id)
    opts.update(opt_id, status="running", started_at=_now())
    sc, fc0, doc = _scenario_for(spec)
    s = spec["settings"]
    cfg = Config(n_train=s["n"], n_heldout=s["n"], train_seeds=tuple(s["train_seeds"]), heldout_seeds=tuple(s["heldout_seeds"]),
                 max_steps=s["max_changes"], allow=tuple(s["allow"]), tests_tolerance=s["tests_tolerance"],
                 equity_guardrail=s["equity"])
    pf = lambda fc, seed: policy_for(sc, fc, doc, seed)  # noqa: E731
    res = search(sc, fc0, cfg, log=ctx.log, progress=lambda d, t, msg: ctx.progress(d, t, msg, force=True),
                 policy_factory=pf)
    report = build_report(sc, fc0, res, policy_factory=pf,
                          progress=lambda d, t, msg: ctx.progress(0.9 + 0.1 * d / max(t, 1), 1, msg, force=True))
    after = parse_flowchart(doc["id"], res["flowchart_after"])
    report["proposed_flowchart"] = flowchart_to_document(after, spec["world"].get("id"))
    report.pop("proposed_flowchart_engine", None)
    store.put_blob(project_id, "optimisations", opt_id, {"report": report, "steps": res["steps"], "config": res["config"]})
    opts.update(opt_id, status="succeeded", finished_at=_now(), progress=1.0,
                summary_json=json.dumps({"n_changes": len(report["changes"]), "n_blocked": len(report["blocked"]),
                                         "heldout_before": report["heldout"]["before"]["share_within_target"],
                                         "heldout_after": report["heldout"]["after"]["share_within_target"]}))
    return {"optimisation_id": opt_id, "n_changes": len(report["changes"])}


def wait_for(cond, timeout: float, poll: float = 0.05) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(poll)
    return False
