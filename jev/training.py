"""Trainers and evaluation (spec 06, tickets M6-3, M6-7).

``train(trainer, dataset, sc, fc, config)`` returns a :class:`TrainResult`. The ``frequency`` trainer counts
how often each option was chosen per context cell and writes a **stub table** (``decision_policy.points``),
so a trained model is something people can read and edit. The ``local`` trainer (``jev.local_model``) fits
the numpy model. Both only learn from ``decision_point``, ``context``, ``offered`` and ``chosen``: the
outcome of a row is never read, so what is learned is what was done.

Evaluation splits by patient (80/20), fits on the 80%, and scores the 20% through the same backend that
a run would use. It reports agreement with past decisions, not the quality of care.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .contract import DecisionRequest
from .dataset import (MIN_CELL, Dataset, cell_key, default_context_fields, field_value, point_fields, split_by_patient,
                      validate)
from .stub import StubBackend

IMITATION_NOTICE = ("Learning from decision logs reproduces practice, including its flaws: a model trained on what was chosen "
                    "copies the habits and the inequities in the data. Its score is agreement with past decisions, "
                    "not the quality of care.")
EVAL_LABEL = "Agreement with past decisions (not accuracy of care)"


class TrainingError(ValueError):
    code = "training_failed"


@dataclass
class TrainConfig:
    context_fields: list[str] | None = None      # None: group and revealed categorical attributes
    decision_points: list[str] | None = None     # None: every decision point with rows
    min_cell: int = MIN_CELL                     # cells with fewer training rows fall back to the point's overall row
    smoothing: float = 1.0                       # pseudo-count per option (add-one)
    holdout: float = 0.2
    seed: int = 0
    extra: dict = field(default_factory=dict)    # trainer specific (local: epochs, d, model, max_seconds)

    @classmethod
    def from_dict(cls, d: dict | None) -> "TrainConfig":
        d = dict(d or {})
        known = {k: d.pop(k) for k in list(d) if k in cls.__dataclass_fields__ and k != "extra"}
        return cls(**known, extra=d)

    def to_dict(self) -> dict:
        return {"context_fields": self.context_fields, "decision_points": self.decision_points, "min_cell": self.min_cell,
                "smoothing": self.smoothing, "holdout": self.holdout, "seed": self.seed, **self.extra}


@dataclass
class TrainResult:
    trainer: str
    kind: str                       # "stub_table" or "local_model"
    artifact: dict                  # stub: {"points": {...}}; local: the serialised model
    decision_points: list[str]
    config: dict                    # resolved
    evaluation: dict | None
    warnings: list[str]
    notice: str = IMITATION_NOTICE

    def to_dict(self) -> dict:
        return {"trainer": self.trainer, "kind": self.kind, "artifact": self.artifact, "decision_points": self.decision_points,
                "config": self.config, "evaluation": self.evaluation, "warnings": self.warnings, "notice": self.notice}


# --------------------------------------------------------------------------------- choice estimation
def luce_weights(rows: list[dict], options: list[str], k: float, iters: int = 60) -> dict[str, float]:
    """Probability of each option from choices made among varying offered sets.

    The stub restricts a row to what is offered and renormalises, which is Luce's choice rule, so the
    weights are fitted for exactly that rule (minorise-maximise iteration, Hunter 2004). When every row
    offers every option this is the add-``k`` frequency. ``k`` pseudo-rows per option, each choosing that
    option from the full set, keep every probability above zero."""
    full = tuple(options)
    sets = Counter(tuple(o for o in r["offered"] if o in options) for r in rows)
    wins = Counter(r["chosen"] for r in rows if r["chosen"] in options)
    sets[full] += 0
    n_aug = {o: wins.get(o, 0) + k for o in options}
    w = {o: 1.0 / len(options) for o in options}
    pseudo = k * len(options)
    for _ in range(iters):
        denom = {o: 0.0 for o in options}
        for s, n in list(sets.items()) + [(full, pseudo)]:
            if not s or n == 0:
                continue
            tot = sum(w[o] for o in s)
            for o in s:
                denom[o] += n / tot
        new = {o: (n_aug[o] / denom[o] if denom[o] > 0 else w[o]) for o in options}
        z = sum(new.values())
        new = {o: v / z for o, v in new.items()}
        done = max(abs(new[o] - w[o]) for o in options) < 1e-10
        w = new
        if done:
            break
    return w


def _literal(v) -> str:
    return repr(v)


def _when(fields: list[str], key: tuple) -> str:
    parts = []
    for f, v in zip(fields, key):
        name = f.split(".", 1)[1] if "." in f else f
        parts.append(f"{name} is {_literal(v)}" if v is None or isinstance(v, bool) else f"{name} == {_literal(v)}")
    return " and ".join(parts)


def fit_frequency(rows: list[dict], options: dict[str, list[str]], fields: list[str], min_cell: int, smoothing: float) -> tuple[dict, dict]:
    """(stub points, info). ``options``: decision point -> its option ids. Rows below ``min_cell`` in a cell
    are not given their own rule: they fall to the point's ``default``, the overall row (so the default is
    the fallback for unseen and thin cells, not the answer for the rest)."""
    by_point: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["decision_point"] in options:
            by_point[r["decision_point"]].append(r)
    points, info = {}, {}
    for pt, rs in sorted(by_point.items()):
        opts = options[pt]
        overall = luce_weights(rs, opts, smoothing)
        eff = point_fields(rs, fields)
        cells: dict[tuple, list[dict]] = defaultdict(list)
        for r in rs:
            cells[cell_key(r, eff)].append(r)
        rules, dropped = [], []
        for key, crs in sorted(cells.items(), key=lambda kv: str(kv[0])):
            if not eff:
                break
            if len(crs) < min_cell:
                dropped.append({"cell": dict(zip(eff, key)), "rows": len(crs)})
                continue
            w = luce_weights(crs, opts, smoothing)
            rules.append({"when": _when(eff, key), "probs": {o: round(w[o], 6) for o in opts}, "n": len(crs)})
        spec = {"default": {o: round(overall[o], 6) for o in opts}}
        if rules:
            spec["rules"] = [{"when": r["when"], "probs": r["probs"]} for r in rules]
        points[pt] = spec
        info[pt] = {"rows": len(rs), "fields": eff, "cells": len(cells), "rules": len(rules), "cells_dropped": dropped,
                    "rule_rows": {r["when"]: r["n"] for r in rules}}
    return points, info


# --------------------------------------------------------------------------------- evaluation
def request_for_row(row: dict, i: int = 0) -> DecisionRequest:
    leads = row.get("option_leads") or {}
    opts = []
    for o in row["offered"]:
        d = {"id": o}
        if o in leads:
            d["features"] = {"lead_days": leads[o]}
        opts.append(d)
    ctx = dict(row["context"])
    ctx["t_days"] = row["t_days"] if row["t_days"] is not None else ctx.get("t_days")
    return DecisionRequest(f"{row['patient_id']}:{row['decision_point']}:{i}", row["decision_point"], ctx, opts)


def evaluate(backend, holdout: list[dict], baseline_rows: list[dict], options: dict[str, list[str]], smoothing: float = 1.0,
             min_cell_rows: dict | None = None) -> dict:
    """Score a backend on held-out rows: log-loss against the uniform and option-frequency baselines,
    agreement (top option equals the chosen one) and calibration in ten bins."""
    if not holdout:
        return {"holdout_rows": 0, "note": "No held-out rows: too few patients to split."}
    freq = {}
    for pt in {r["decision_point"] for r in baseline_rows}:
        if pt in options:
            freq[pt] = luce_weights([r for r in baseline_rows if r["decision_point"] == pt], options[pt], smoothing)
    reqs = [request_for_row(r, i) for i, r in enumerate(holdout)]
    resps = backend.decide(reqs)
    tot = {"ll": 0.0, "uni": 0.0, "freq": 0.0, "hit": 0, "n": 0}
    per: dict[str, dict] = defaultdict(lambda: {"ll": 0.0, "uni": 0.0, "freq": 0.0, "hit": 0, "n": 0})
    bins = [[0.0, 0.0, 0] for _ in range(10)]
    eps = 1e-6
    for r, q, resp in zip(holdout, reqs, resps):
        p = resp.probs
        pc = max(p.get(r["chosen"], 0.0), eps)
        fw = freq.get(r["decision_point"])
        if fw is not None:
            z = sum(fw[o] for o in r["offered"] if o in fw) or 1.0
            pf = max(fw.get(r["chosen"], 0.0) / z, eps)
        else:
            pf = 1.0 / len(r["offered"])
        top = max(r["offered"], key=lambda o: (p.get(o, 0.0), -r["offered"].index(o)))
        for acc in (tot, per[r["decision_point"]]):
            acc["ll"] -= math.log(pc)
            acc["uni"] += math.log(len(r["offered"]))
            acc["freq"] -= math.log(pf)
            acc["hit"] += int(top == r["chosen"])
            acc["n"] += 1
        for o in r["offered"]:
            b = min(int(p.get(o, 0.0) * 10), 9)
            bins[b][0] += p.get(o, 0.0)
            bins[b][1] += float(o == r["chosen"])
            bins[b][2] += 1

    def fin(a):
        n = a["n"]
        return {"rows": n, "log_loss": round(a["ll"] / n, 5), "log_loss_uniform": round(a["uni"] / n, 5),
                "log_loss_option_frequency": round(a["freq"] / n, 5), "accuracy": round(a["hit"] / n, 5), "agreement": round(a["hit"] / n, 5)}

    out = {"label": EVAL_LABEL, "holdout_rows": tot["n"], "holdout_patients": len({r["patient_id"] for r in holdout}),
           **{k: v for k, v in fin(tot).items() if k != "rows"},
           "by_decision_point": {pt: fin(a) for pt, a in sorted(per.items())},
           "calibration": [[round(s / n, 4), round(h / n, 4)] for s, h, n in bins if n],
           "calibration_n": [n for _, _, n in bins if n], "split": "by patient"}
    if min_cell_rows is not None:
        out["rare_cells"] = min_cell_rows
    return out


# --------------------------------------------------------------------------------- frequency trainer
def _options_of(fc, rows: list[dict], points: list[str] | None) -> dict[str, list[str]]:
    opts = {nid: list(n.options) for nid, n in fc.nodes.items() if n.kind == "choice"}
    have = {r["decision_point"] for r in rows}
    return {pt: o for pt, o in opts.items() if pt in have and (points is None or pt in points)}


def prepare_rows(ds: Dataset, sc, fc, cfg: TrainConfig) -> tuple[list[dict], dict, list[str], list[str]]:
    """Refuse a dataset with errors, drop exact duplicates, return (rows, options per point, fields, warnings)."""
    rep = validate(ds, sc, fc, cfg.context_fields, cfg.min_cell)
    if not rep["trainable"]:
        errs = [f"{g['message']} ({g['count']} rows)" for g in rep["problems"] if g["severity"] == "error"][:5]
        raise TrainingError("The dataset has errors and cannot be trained on: " + "; ".join(errs))
    clean, dropped = ds.dedup()
    warnings = [g["message"] for g in rep["problems"] if g["severity"] == "warning" and g["code"] in
                ("small_cell", "option_never_chosen", "no_rows_for_point", "unknown_attribute", "unknown_step", "many_options")]
    if dropped:
        warnings.append(f"{dropped} duplicate rows were dropped before training")
    if cfg.decision_points:
        bad = [p for p in cfg.decision_points if not any(r["decision_point"] == p for r in clean.rows)]
        if bad:
            raise TrainingError(f"No rows for the decision points {bad}")
    options = _options_of(fc, clean.rows, cfg.decision_points)
    fields = cfg.context_fields if cfg.context_fields is not None else default_context_fields(clean.rows, sc)
    for f in fields:
        field_value(clean.rows[0], f)          # raises ValueError on a malformed field name
    return [r for r in clean.rows if r["decision_point"] in options], options, fields, warnings


def train_frequency(ds: Dataset, sc, fc, cfg: TrainConfig) -> TrainResult:
    rows, options, fields, warnings = prepare_rows(ds, sc, fc, cfg)
    train, hold = split_by_patient(rows, cfg.holdout, cfg.seed)
    ev = None
    if train and hold and len({r["patient_id"] for r in hold}) >= 2:
        pts, info = fit_frequency(train, options, fields, cfg.min_cell, cfg.smoothing)
        # decision points the training part lacks are scored uniformly by the stub (its documented fallback)
        be = StubBackend(pts)
        ev = evaluate(be, hold, train, options, cfg.smoothing, _rare_cells(hold, pts, info, options, train, cfg.smoothing))
        ev["fit_on"] = f"{len(train)} training rows of {len({r['patient_id'] for r in train})} patients"
        ev["note"] = "Scored on patients not used to fit the table. The delivered table is refitted on all rows."
    else:
        warnings.append("Too few patients to hold any out: no evaluation was computed")
    points, info = fit_frequency(rows, options, fields, cfg.min_cell, cfg.smoothing)
    for pt, i in info.items():
        d = i["cells_dropped"]
        if d:
            shown = "; ".join(f"{c['cell']} ({c['rows']} rows)" for c in d[:3]) + (f"; and {len(d) - 3} more" if len(d) > 3 else "")
            warnings.append(f"{pt}: {len(d)} cells have fewer than {cfg.min_cell} rows and use the overall row: {shown}")
    cfg_out = {**cfg.to_dict(), "context_fields": fields}
    return TrainResult("frequency", "stub_table", {"points": points, "info": info}, sorted(points), cfg_out, ev, warnings)


def _rare_cells(hold: list[dict], points: dict, info: dict, options: dict, train: list[dict], smoothing: float) -> dict:
    """Held-out rows at points that have cells but whose own cell got no rule (too few training rows, or never seen):
    they are scored by the overall row. This is the check against being overconfident on rare combinations."""
    from .conditions import compile_condition
    from .stub import condition_env
    rare = []
    for r in hold:
        i = info.get(r["decision_point"])
        if not i or not i["fields"]:
            continue
        env = condition_env(r["context"])
        rules = points[r["decision_point"]].get("rules") or []
        if not any(compile_condition(x["when"]).holds(env) for x in rules):
            rare.append(r)
    if not rare:
        return {"rows": 0}
    ev = evaluate(StubBackend(points), rare, train, options, smoothing)
    return {"rows": len(rare), "log_loss": ev["log_loss"], "log_loss_uniform": ev["log_loss_uniform"],
            "log_loss_option_frequency": ev["log_loss_option_frequency"],
            "note": "Rows whose cell has no rule of its own; they use the overall row for the decision point."}


TRAINERS = {"frequency": train_frequency}


def register(name: str, fn) -> None:
    TRAINERS[name] = fn


def train(trainer: str, ds: Dataset, sc, fc, config: dict | TrainConfig | None = None) -> TrainResult:
    cfg = config if isinstance(config, TrainConfig) else TrainConfig.from_dict(config)
    if trainer == "local" and "local" not in TRAINERS:
        from . import local_model                # noqa: F401  (registers itself)
    if trainer not in TRAINERS:
        raise TrainingError(f"Unknown trainer {trainer!r}; use one of {sorted(TRAINERS)}"
                            + ("; the jev trainer waits for the JEV API" if trainer == "jev" else ""))
    return TRAINERS[trainer](ds, sc, fc, cfg)


def table_to_points(result: TrainResult) -> dict:
    return result.artifact["points"]
