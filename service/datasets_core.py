"""Dataset and training work (spec 06): ingestion, exploration and training jobs, attaching a model to a flowchart.

Job functions are module level and take ids only; they rebuild their inputs from the store, like the run jobs.
"""

from __future__ import annotations

import copy
import json
import time

import jev
from jev import dataset as D
from pathway_sim import generate_patients, simulate
from pathway_sim.documents import doc_hash, documents_to_scenario

from .datasets_db import Datasets, Models, read_lines, rows_path, write_rows
from .store import Store, now

MAX_ROWS = 400_000
ATTACH_KIND = "attach_model"


def scenario_for_version(store: Store, project_id: str, fid: str, version: int | None):
    """(world, doc, version, scenario, flowchart) of a stored flowchart version, without locking it."""
    world, _ = store.get_world(project_id)
    doc, info = store.get_version(project_id, fid, version)
    sc = documents_to_scenario(world, [doc])
    return world, doc, info["version"], sc, sc.flowcharts[doc["id"]]


def report_for(store: Store, project_id: str, ds: D.Dataset, fid: str | None, version: int | None):
    """(report, resolved version) against a flowchart version; structure-only when there is no flowchart."""
    if fid is None:
        return D.validate(ds), None
    _, _, ver, sc, fc = scenario_for_version(store, project_id, fid, version)
    return D.validate(ds, sc, fc), ver


def finish_dataset(store: Store, project_id: str, dataset_id: str, ds: D.Dataset, fid: str | None, version: int | None,
                   source: dict) -> dict:
    """Store the rows and the report; the dataset becomes ``stored`` (errors do not stop storing, only training)."""
    if len(ds) > MAX_ROWS:
        raise ValueError(f"A dataset holds at most {MAX_ROWS} rows (this one has {len(ds)})")
    report, ver = report_for(store, project_id, ds, fid, version)
    write_rows(store, project_id, dataset_id, ds.rows)
    Datasets(store).update(dataset_id, status="stored", progress=1.0, n_rows=len(ds), n_patients=report["patients"],
                           content_hash=ds.content_hash(), trainable=int(report["trainable"]), report_json=report,
                           flowchart_version=ver, source_json=source, finished_at=now())
    return report


def load_dataset(store: Store, project_id: str, dataset_id: str) -> D.Dataset:
    ds = D.Dataset.from_jsonl(read_lines(store, project_id, dataset_id))
    return ds


# ---------------------------------------------------------------------------------- jobs
def execute_dataset_from_run(ctx, data_dir: str, project_id: str, dataset_id: str, run_id: str, seed: int | None,
                             point: str | None, measured_only: bool) -> dict:
    """Job: the decisions export of a finished run, as a dataset."""
    from .runs_core import stream_path
    store = Store(data_dir)
    ds_table = Datasets(store)
    try:
        run = store.query_one("SELECT flowchart_id, flowchart_version, seeds_json FROM runs WHERE project_id=? AND id=?", (project_id, run_id))
        seeds = [s for s in json.loads(run["seeds_json"]) if seed is None or s == seed]
        import gzip
        raw = []
        for i, s in enumerate(seeds):
            ctx.progress(i, len(seeds), f"reading seed {s}")
            with gzip.open(stream_path(store, project_id, "decisions", f"{run_id}_s{s}"), "rb") as f:
                for line in f:
                    d = json.loads(line)
                    if (point is None or d["decision_point"] == point) and (not measured_only or d.get("measured")):
                        raw.append(d)
        ds = D.Dataset.from_rows(raw)
        report = finish_dataset(store, project_id, dataset_id, ds, run["flowchart_id"], run["flowchart_version"],
                                {"kind": "run", "run": run_id, "seeds": seeds, "point": point, "measured_only": measured_only})
        ctx.progress(1, 1, "done", force=True)
        return {"dataset_id": dataset_id, "rows": len(ds), "trainable": report["trainable"]}
    except BaseException as e:
        ds_table.update(dataset_id, status="failed", error_json={"code": getattr(e, "code", type(e).__name__), "message": str(e)[:2000]}, finished_at=now())
        raise


def execute_exploration(ctx, data_dir: str, project_id: str, dataset_id: str, fid: str, version: int, points: list[str] | None,
                        n: int, seeds: list[int]) -> dict:
    """Job: an exploration run (random choices at ``points``) written as an outcome-labelled dataset."""
    store = Store(data_dir)
    try:
        _, _, ver, sc, fc = scenario_for_version(store, project_id, fid, version)
        rows = []
        for i, seed in enumerate(seeds):
            r, _log = jev.explore.explore(sc, fc, n, seed=seed, points=points,
                                          progress=lambda d, t, i=i, seed=seed: ctx.progress(i + d / max(t, 1), len(seeds), f"seed {seed}: {d} of {t} patients"))
            rows += r
        ds = D.Dataset.from_rows(rows)
        report = finish_dataset(store, project_id, dataset_id, ds, fid, ver,
                                {"kind": "exploration", "flowchart": {"id": fid, "version": ver}, "points": points, "n": n, "seeds": seeds,
                                 "outcomes": jev.explore.outcome_summary(rows)})
        ctx.progress(1, 1, "done", force=True)
        return {"dataset_id": dataset_id, "rows": len(ds), "trainable": report["trainable"]}
    except BaseException as e:
        Datasets(store).update(dataset_id, status="failed", error_json={"code": getattr(e, "code", type(e).__name__), "message": str(e)[:2000]}, finished_at=now())
        raise


def execute_training(ctx, data_dir: str, project_id: str, model_id: str) -> dict:
    """Job: train ``trainer`` on the dataset against the model's flowchart version and register the result."""
    store = Store(data_dir)
    models = Models(store)
    try:
        m = models.get(project_id, model_id)
        models.update(model_id, status="running")
        ctx.progress(0, 1, "reading the dataset", force=True)
        ds = load_dataset(store, project_id, m["dataset_id"])
        _, doc, _, sc, fc = scenario_for_version(store, project_id, m["flowchart_id"], m["flowchart_version"])
        ctx.progress(0.1, 1, f"training ({m['trainer']})", force=True)
        t0 = time.time()
        res = jev.train(m["trainer"], ds, sc, fc, m["config"])
        store.put_blob(project_id, "models", model_id, res.artifact)
        models.update(model_id, status="ready", progress=1.0, finished_at=now(), evaluation_json=res.evaluation, warnings_json=res.warnings,
                      decision_points_json=res.decision_points, config_json=res.config, kind=res.kind, message=f"trained in {time.time() - t0:.1f} s",
                      dataset_hash=ds.content_hash())
        ctx.progress(1, 1, "done", force=True)
        return {"model_id": model_id, "decision_points": res.decision_points}
    except BaseException as e:
        models.update(model_id, status="failed", error_json={"code": getattr(e, "code", None) or type(e).__name__, "message": str(e)[:2000]}, finished_at=now())
        raise


# ---------------------------------------------------------------------------------- attach
def attach(doc: dict, model: dict, artifact: dict, points: list[str] | None) -> tuple[dict, list[dict], list[str], list[str]]:
    """The flowchart document with ``model`` used at ``points``: ``(new document, mismatches, attached, skipped)``.

    A frequency model writes its table into ``decision_policy.points`` (a stub table, readable and editable). A local
    model is stored once in ``decision_policy.models`` and the point is routed to it, keeping the point's stub table
    as its documented fallback. Points whose options do not match the flowchart are skipped and listed."""
    nodes = {n["id"]: n for n in doc["nodes"]}
    edges = doc.get("edges") or []
    options: dict[str, list[str]] = {}
    for e in sorted((e for e in edges if e.get("type") == "option"), key=lambda e: e.get("index", 10 ** 6)):
        options.setdefault(e["from"], []).append(e["to"])
    wanted = points or model["decision_points"]
    mism: list[dict] = []
    attached, skipped = [], []
    new = copy.deepcopy(doc)
    dp = new.setdefault("decision_policy", {})
    dp.setdefault("backend", "stub")
    dp.setdefault("mode", "sample")
    pts = dp.setdefault("points", {})
    for pt in wanted:
        if pt not in model["decision_points"]:
            mism.append({"severity": "error", "code": "not_in_model", "point": pt, "message": f"The model was not trained on '{pt}'"})
            skipped.append(pt)
            continue
        node = nodes.get(pt)
        if node is None or node.get("kind") not in ("decision", "choice"):
            mism.append({"severity": "error", "code": "not_a_decision", "point": pt,
                         "message": f"'{pt}' is {'not a node' if node is None else 'not a decision'} in this flowchart version"})
            skipped.append(pt)
            continue
        have = options.get(pt) or list(node.get("options") or [])
        if artifact.get("points") is not None:                      # frequency: a stub table
            spec = artifact["points"][pt]
            known = set(spec["default"])
        else:
            spec, known = None, set(artifact["layout"]["point_options"].get(pt, []))
        extra = sorted(known - set(have))
        if extra:
            mism.append({"severity": "error", "code": "option_removed", "point": pt,
                         "message": f"The model gives probability to {extra}, which '{pt}' no longer offers; retrain on this version"})
            skipped.append(pt)
            continue
        new_opts = sorted(set(have) - known)
        if new_opts:
            mism.append({"severity": "warning", "code": "option_added", "point": pt,
                         "message": f"'{pt}' offers {new_opts}, which the model never saw. " +
                                    ("They get probability 0 from the table" if spec is not None else "The model has no identity for them, so it scores them only by cost, invasiveness and queue")})
        if spec is not None:
            row = {"default": {o: spec["default"].get(o, 0.0) for o in have}}
            if spec.get("rules"):
                row["rules"] = [{"when": r["when"], "probs": {o: r["probs"].get(o, 0.0) for o in have}} for r in spec["rules"]]
            row["source"] = f"trained: model {model['id']} on dataset {model['dataset_id']}"
            if dp["backend"] != "stub":
                row["backend"] = "stub"
            pts[pt] = row
        else:
            row = dict(pts.get(pt) or {})
            row.update(backend="local", model=model["id"], source=f"trained: model {model['id']} on dataset {model['dataset_id']}")
            pts[pt] = row
        attached.append(pt)
    if attached and artifact.get("points") is None:
        dp.setdefault("models", {})[model["id"]] = artifact
    new["edits_from_parent"] = [{"index": 0, "kind": ATTACH_KIND, "target": ", ".join(attached), "other": model["id"]}]
    return new, mism, attached, skipped
