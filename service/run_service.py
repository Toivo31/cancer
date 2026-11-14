"""Starting runs and optimisations: limits, validation, identical-run cache, job submission.

Used by the routes (``routes/runs.py``, ``routes/optimisations.py``) and by ``apply`` (which reruns).
"""

from __future__ import annotations

import copy

from .errors import ApiError
from .jobs import QueueFull
from .runs_core import (ENGINE_VERSION, _scenario_for, execute_optimisation, execute_run, min_patients, patients_key, policy_for,
                        run_key)
from .runtime import Runtime
from .store import NotFound
from .validation import has_errors, validate_documents

DEFAULT_SEEDS = [1]
KINDS = ("detach", "relax", "standardise", "fast_track")


def _flowchart_ref(rt: Runtime, project_id: str, fid: str, version: int | None) -> tuple[dict, int]:
    try:
        return rt.store.get_version_for_run(project_id, fid, version)   # also locks the version
    except NotFound:
        raise ApiError(404, "not_found", f"No flowchart '{fid}'" + (f" version {version}" if version else "")) from None


def check_limits(rt: Runtime, world: dict, n: int, seeds: list[int], what: str = "run") -> None:
    s = rt.settings
    if n < 1 or not seeds:
        raise ApiError(422, "invalid_request", "n must be at least 1 and at least one seed is needed")
    if n > s.max_patients:
        raise ApiError(429, "limit_exceeded", f"At most {s.max_patients} patients per {what} (asked for {n})")
    if len(seeds) > s.max_seeds or len(set(seeds)) != len(seeds):
        raise ApiError(429 if len(seeds) > s.max_seeds else 422, "limit_exceeded" if len(seeds) > s.max_seeds else "invalid_request",
                       f"Use between 1 and {s.max_seeds} different seeds")
    lo = min_patients(world)
    if n < lo:
        raise ApiError(422, "n_too_small",
                       f"With this world's arrival rate and warm-up, fewer than {lo} patients leaves nobody measured; "
                       f"ask for at least {lo} (the template default is {world.get('default_n', lo)})")


def checked_document(world: dict, doc: dict, policy: dict | None) -> dict:
    d = copy.deepcopy(doc)
    if policy is not None:
        d["decision_policy"] = policy
    problems = validate_documents(world, [d])
    if has_errors(problems):
        raise ApiError(422, "invalid_document", "The flowchart has problems that stop it from running", problems)
    if (d.get("decision_policy") or {}).get("backend", "rule") != "rule":
        try:     # fail at the request, not minutes later in the job: does the decision policy fit this flowchart?
            sc, fc, _ = _scenario_for({"world": world, "flowchart_doc": d, "decision_policy": None})
            policy_for(sc, fc, d, 0)
        except ValueError as e:
            raise ApiError(422, "invalid_decision_policy", str(e),
                           [{"severity": "error", "code": "invalid_decision_policy", "message": str(e)}]) from None
    return d


def start_run(rt: Runtime, project_id: str, fid: str, version: int | None, n: int | None, seeds: list[int] | None,
              policy: dict | None, label: str | None, source: dict | None = None) -> tuple[dict, bool]:
    """Create (or find) the run and queue its job. Returns (run row, created)."""
    world, rev = rt.store.get_world(project_id)
    doc, ver = _flowchart_ref(rt, project_id, fid, version)
    n = int(n if n is not None else world.get("default_n") or 1000)
    seeds = [int(x) for x in (seeds or DEFAULT_SEEDS)]
    check_limits(rt, world, n, seeds)
    checked_document(world, doc, policy)
    key = run_key(world, doc, policy, n, seeds)
    row, created = rt.runs.create_or_get(project_id, key, {
        "patients_key": patients_key(world, n, seeds), "label": label or "", "flowchart_id": fid, "flowchart_version": ver,
        "n": n, "seeds_json": seeds, "policy_json": policy, "engine_version": ENGINE_VERSION, "world_rev": rev,
        "source_json": source})
    if not created:
        return row, False
    rid = row["id"]
    rt.store.put_blob(project_id, "runspec", rid, {"world": world, "flowchart_doc": doc, "decision_policy": policy,
                                                   "n": n, "seeds": seeds, "label": label or ""})
    try:
        job = rt.runner.submit("run", execute_run, {"data_dir": str(rt.store.data_dir), "project_id": project_id, "run_id": rid},
                               label=label or f"run {fid} v{ver}", owner={"project": project_id, "kind": "run", "id": rid})
    except QueueFull as e:
        rt.runs.update(rid, status="failed", error_json='{"code": "queue_full", "message": "too many jobs are waiting"}')
        raise ApiError(429, "queue_full", f"Too many jobs are waiting ({e}); try again in a minute") from None
    rt.runs.update(rid, job_id=job.id)
    return rt.runs.get(project_id, rid), True


def start_optimisation(rt: Runtime, project_id: str, fid: str, version: int | None, settings: dict) -> dict:
    world, rev = rt.store.get_world(project_id)
    doc, ver = _flowchart_ref(rt, project_id, fid, version)
    backend = (doc.get("decision_policy") or {}).get("backend", "rule")
    s = dict(settings)
    s["n"] = int(s.get("n") or world.get("default_n") or 1000)
    s["train_seeds"] = [int(x) for x in (s.get("train_seeds") or [101, 102])]
    s["heldout_seeds"] = [int(x) for x in (s.get("heldout_seeds") or [301, 302])]
    if set(s["train_seeds"]) & set(s["heldout_seeds"]):
        raise ApiError(422, "invalid_request", "Training and held-out seeds must be different patients")
    s["max_changes"] = int(s.get("max_changes") or 6)
    if not 1 <= s["max_changes"] <= 12:
        raise ApiError(429, "limit_exceeded", "max_changes must be between 1 and 12")
    hardcoded = backend in ("rule", "stub")                 # spec 05 / F7: a model (http, local) competes with "always choose X"; hardcoded tables do not
    allow = s.get("allow") or (["detach", "relax", "standardise"] if hardcoded else ["detach", "relax"])
    bad = [a for a in allow if a not in KINDS]
    if bad:
        raise ApiError(422, "invalid_request", f"Unknown change kind {bad}; use {list(KINDS)}")
    if "standardise" in allow and not hardcoded and not s.get("allow_standardise_under_jev"):
        raise ApiError(422, "standardise_under_jev",
                       "'standardise' overrides a decision point and competes with the decision model; leave it out, or "
                       "set allow_standardise_under_jev to accept that (decision F7)")
    s["allow"] = list(allow)
    safety = s.get("safety") or {}
    s["tests_tolerance"] = float(safety.get("tests_tolerance", 0.02))
    s["equity"] = bool(safety.get("equity", True))
    s.pop("safety", None)
    check_limits(rt, world, s["n"], s["train_seeds"], "optimisation")
    check_limits(rt, world, s["n"], s["heldout_seeds"], "optimisation")
    checked_document(world, doc, None)
    row = rt.opts.create(project_id, {"flowchart_id": fid, "flowchart_version": ver, "settings_json": s})
    oid = row["id"]
    rt.store.put_blob(project_id, "optspec", oid, {"world": world, "flowchart_doc": doc, "decision_policy": None, "settings": s,
                                                   "world_rev": rev})
    try:
        job = rt.runner.submit("optimisation", execute_optimisation,
                               {"data_dir": str(rt.store.data_dir), "project_id": project_id, "opt_id": oid},
                               label=f"optimise {fid} v{ver}", owner={"project": project_id, "kind": "optimisation", "id": oid})
    except QueueFull as e:
        rt.opts.update(oid, status="failed", error_json='{"code": "queue_full", "message": "too many jobs are waiting"}')
        raise ApiError(429, "queue_full", f"Too many jobs are waiting ({e}); try again in a minute") from None
    rt.opts.update(oid, job_id=job.id)
    return rt.opts.get(project_id, oid)
