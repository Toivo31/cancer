"""The ``local`` trainer and backend (ticket M6-7): the numpy model of ``decision_model/`` trained to imitate ``chosen``.

Features come only from the request: the context (age, time, fast track, group, revealed attributes, result of
each earlier step) and per option an identity, whether it is invasive, its cost, and the queue state
(``lead_days``) when the row has it. The model is the dot-product model (or the correction model that sees the
whole offer); it is fitted by cross-entropy on the chosen option, so it learns what was done. The outcome of
a row is not read.

A trained model is a JSON artifact (weights as base64 float32 plus the feature layout) that the flowchart's
``decision_policy`` can carry::

    {"backend": "local", "mode": "sample", "model": "m_ab12", "models": {"m_ab12": <artifact>}}

so a run needs nothing but the document.
"""

from __future__ import annotations

import base64
import time

import numpy as np

from decision_model import autograd as ag
from decision_model.models import CorrectionModel, DotProductModel
from decision_model.tasks import MAX_OPTIONS, Dataset as ArrayDataset
from decision_model.train import fit

from .contract import BackendInfo, DecisionRequest, DecisionResponse, uniform_probs
from .dataset import split_by_patient
from .training import (EVAL_LABEL, TrainConfig, TrainingError, TrainResult, evaluate, prepare_rows, register)

KIND = "local_numpy"
LEAD_SCALE = 30.0


# --------------------------------------------------------------------------------- features
def layout_for(sc, fc, points: list[str]) -> dict:
    """Feature layout fixed at training time: the world's groups and attribute values, the flowchart's steps and options."""
    options, meta = [], {}
    for pt in points:
        for o in fc.nodes[pt].options:
            if o not in options:
                options.append(o)
                n = fc.nodes[o]
                spec = {**sc.tests.get(n.test, {}), **fc.test_overrides.get(n.test, {})} if n.test else {}
                meta[o] = [float(bool(spec.get("invasive"))), float(spec.get("cost_eur") or 0.0) / 1000.0]
    return {"groups": [g["id"] for g in sc.groups],
            "pairs": [[a, str(v)] for a, spec in sorted(sc.attributes.items()) for v in sorted((spec.get("values") or {}))],
            "steps": [nid for nid, n in fc.nodes.items() if n.kind != "choice" and n.test],
            "options": options, "option_meta": meta, "points": list(points)}


def n_ctx(lay: dict) -> int:
    return 4 + len(lay["groups"]) + len(lay["pairs"]) + 2 * len(lay["steps"])


def n_opt(lay: dict) -> int:
    return len(lay["options"]) + 4


def context_vector(lay: dict, c: dict) -> np.ndarray:
    v = np.zeros(n_ctx(lay))
    v[0] = (65 if c.get("age") is None else c["age"]) / 100.0
    v[1] = min(max(float(c.get("t_days") or 0.0), 0.0), 120.0) / 60.0
    v[2] = float(bool(c.get("fast_track")))
    i = 4
    if c.get("group") in lay["groups"]:
        v[i + lay["groups"].index(c["group"])] = 1.0
    i += len(lay["groups"])
    attrs = c.get("attributes") or {}
    for j, (a, val) in enumerate(lay["pairs"]):
        if a in attrs and str(attrs[a]) == val:
            v[i + j] = 1.0
    i += len(lay["pairs"])
    last = {}
    for h in c.get("history") or []:
        last[h["step"]] = h.get("result")
    for j, s in enumerate(lay["steps"]):
        if s in last:
            if last[s] is True:
                v[i + 2 * j] = 1.0
            elif last[s] is False:
                v[i + 2 * j + 1] = 1.0
    return v


def option_rows(lay: dict, options: list[dict]) -> np.ndarray:
    out = np.zeros((len(options), n_opt(lay)))
    k = len(lay["options"])
    for r, o in enumerate(options):
        if o["id"] in lay["options"]:
            out[r, lay["options"].index(o["id"])] = 1.0
            out[r, k:k + 2] = lay["option_meta"][o["id"]]
        lead = (o.get("features") or {}).get("lead_days")
        if lead is not None:
            out[r, k + 2], out[r, k + 3] = lead / LEAD_SCALE, 1.0
    return out


# --------------------------------------------------------------------------------- artifact
def _pack(a: np.ndarray) -> dict:
    return {"shape": list(a.shape), "b64": base64.b64encode(np.asarray(a, np.float32).tobytes()).decode()}


def _unpack(d: dict) -> np.ndarray:
    return np.frombuffer(base64.b64decode(d["b64"]), np.float32).reshape(d["shape"]).astype(np.float64)


def make_model(arch: dict, lay: dict):
    kw = dict(d=arch["d"], ctx_hidden=arch["hidden"], opt_hidden=arch["hidden"], n_ctx=n_ctx(lay), n_opt=n_opt(lay), seed=arch.get("seed", 0))
    return CorrectionModel(n_layers=arch.get("layers", 1), **kw) if arch["model"] == "correction" else DotProductModel(**kw)


def to_artifact(model, arch: dict, lay: dict) -> dict:
    return {"kind": KIND, "version": 1, "arch": arch, "layout": lay, "params": {k: _pack(t.data) for k, t in model.params.items()}}


class LocalModelBackend:
    """Backend over a trained artifact. A decision point the model was not trained on, or one with more than
    ``MAX_OPTIONS`` options, gets uniform probabilities and is counted in :meth:`summary`."""

    def __init__(self, artifact: dict, model_id: str = "local@1"):
        if artifact.get("kind") != KIND:
            raise ValueError(f"not a local model artifact (kind {artifact.get('kind')!r})")
        self.artifact, self.model_id, self.lay = artifact, model_id, artifact["layout"]
        self.model = make_model(artifact["arch"], self.lay)
        for k, d in artifact["params"].items():
            self.model.params[k].data = _unpack(d)
        self.fallbacks = 0

    def info(self) -> BackendInfo:
        return BackendInfo("local", self.model_id, True, None)

    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]:
        out = []
        for q in requests:
            ids = q.option_ids
            if q.decision_point not in self.lay["points"] or len(ids) > MAX_OPTIONS:
                self.fallbacks += 1
                out.append(DecisionResponse(q.request_id, uniform_probs(ids), "model does not cover this decision point; uniform"))
                continue
            o = np.zeros((1, MAX_OPTIONS, n_opt(self.lay)))
            o[0, :len(ids)] = option_rows(self.lay, q.options)
            mask = (np.arange(MAX_OPTIONS) < len(ids))[None]
            p = self.model.predict(context_vector(self.lay, q.context)[None], o, mask)[0, :len(ids)]
            out.append(DecisionResponse(q.request_id, {i: float(x) for i, x in zip(ids, p)}))
        return out

    def summary(self) -> dict:
        return {"model_fallbacks": self.fallbacks} if self.fallbacks else {}


def backend_from_config(cfg: dict, where: str = "decision_policy") -> LocalModelBackend:
    """``cfg``: the ``decision_policy`` (or a point's) with ``model`` and the ``models`` map holding its artifact."""
    mid = cfg.get("model")
    art = (cfg.get("models") or {}).get(mid) if mid else None
    if art is None:
        raise ValueError(f"{where}: the local backend needs 'model' naming an artifact in 'models' (attach a trained model to the flowchart)")
    return LocalModelBackend(art, mid)


# --------------------------------------------------------------------------------- training
def _arrays(rows: list[dict], lay: dict) -> ArrayDataset:
    n = len(rows)
    ctx = np.zeros((n, n_ctx(lay)))
    opts = np.zeros((n, MAX_OPTIONS, n_opt(lay)))
    mask = np.zeros((n, MAX_OPTIONS), bool)
    y = np.zeros(n, int)
    for i, r in enumerate(rows):
        q = DecisionRequestLite(r)
        ctx[i] = context_vector(lay, q.context)
        k = len(q.options)
        opts[i, :k] = option_rows(lay, q.options)
        mask[i, :k] = True
        y[i] = r["offered"].index(r["chosen"])
    return ArrayDataset(ctx, opts, mask, y)


class DecisionRequestLite:
    def __init__(self, row: dict):
        leads = row.get("option_leads") or {}
        self.options = [{"id": o, **({"features": {"lead_days": leads[o]}} if o in leads else {})} for o in row["offered"]]
        self.context = {**row["context"], "t_days": row["t_days"] if row["t_days"] is not None else row["context"].get("t_days")}


def train_local(ds, sc, fc, cfg: TrainConfig) -> TrainResult:
    rows, options, _fields, warnings = prepare_rows(ds, sc, fc, cfg)
    big = [pt for pt, o in options.items() if len(o) > MAX_OPTIONS or any(len(r["offered"]) > MAX_OPTIONS for r in rows if r["decision_point"] == pt)]
    for pt in big:
        warnings.append(f"{pt}: more than {MAX_OPTIONS} options, skipped by the local trainer (uniform at run time)")
    points = [pt for pt in options if pt not in big]
    rows = [r for r in rows if r["decision_point"] in points]
    if len(rows) < 20:
        raise TrainingError(f"Only {len(rows)} usable rows; the local model needs at least 20")
    x = cfg.extra
    arch = {"model": x.get("model", "dot"), "d": int(x.get("d", 16)), "hidden": int(x.get("hidden", 32)), "layers": int(x.get("layers", 1)),
            "seed": cfg.seed, "epochs": int(x.get("epochs", 25)), "lr": float(x.get("lr", 3e-3))}
    if arch["model"] not in ("dot", "correction"):
        raise TrainingError("model must be 'dot' or 'correction'")
    lay = layout_for(sc, fc, points)
    max_s = float(x.get("max_seconds", 60))

    def fit_on(rs):
        a = _arrays(rs, lay)
        m = make_model(arch, lay)
        fit(m, a, epochs=arch["epochs"], batch=min(64, len(a)), lr=arch["lr"], seed=cfg.seed, max_seconds=max_s)
        return m

    train, hold = split_by_patient(rows, cfg.holdout, cfg.seed)
    ev = None
    if len(train) >= 20 and hold and len({r["patient_id"] for r in hold}) >= 2:
        art = to_artifact(fit_on(train), arch, lay)
        ev = evaluate(LocalModelBackend(art), hold, train, options)         # through the reloaded float32 artifact, as a run would use it
        ev["fit_on"] = f"{len(train)} training rows of {len({r['patient_id'] for r in train})} patients"
        ev["note"] = "Scored on patients not used to fit the model. The delivered model is refitted on all rows."
    else:
        warnings.append("Too few patients to hold any out: no evaluation was computed")
    art = to_artifact(fit_on(rows), arch, lay)
    n_params = sum(int(np.prod(p["shape"])) for p in art["params"].values())
    return TrainResult("local", "local_model", art, points, {**cfg.to_dict(), **arch, "parameters": n_params}, ev, warnings)


register("local", train_local)
