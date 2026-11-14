"""W1 / D6: the decision model making a real choice inside the simulator.

    python -m decision_model.in_loop --scenario scenarios/generated/stokstad_calibrated.yaml \
        --flowchart optimal --node method
    python -m decision_model.in_loop --scenario scenarios/finland_lung.yaml \
        --flowchart baseline --node sample_choice

Pipeline (every step uses revealed information only):

1. Exploration log. Training patients (their own seeds) run through the flowchart with the
   flowchart's rule policy at every node except ``--node``, where ``RandomPolicy`` picks
   uniformly. At each visit of ``--node`` we keep the ``PatientView`` the policy was given
   (group, age, t_now, history, revealed attributes: what the clinic knew at that moment).
2. Outcome per logged choice, from the run log's events only: the sampling procedures
   (scenario tests marked ``invasive``) started at or after the choice. ``diagnostic`` = one of
   them returned a result (positive or negative, not non-diagnostic); ``days`` = choice to the
   last of their results. Reward ``r = diagnostic - days / days_per_diagnosis``.
   ``patient.condition``, ``patient.cancer``, ``patient.results`` and hidden attributes are
   never read for training or at run time (only in the evaluation table, to count cancers).
3. Training (same data, same signal for both models): each model's logit for an option is
   regressed on the reward of the option actually taken (direct-method contextual bandit,
   ``train.fit_reward``). Under uniform exploration this estimates each option's expected
   reward given the context; the policy picks the argmax.
4. In-loop evaluation on held-out patients (other seeds): rule, random, dot-product and
   correction policies at ``--node``, rule everywhere else, same patients and random numbers.

Prints markdown tables and merges the results into ``runs/model_in_loop.json`` (keyed by
scenario/flowchart/node).
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import numpy as np

import math

from pathway_sim import RandomPolicy, RulePolicy, generate_patients, load_scenario
from pathway_sim.engine import DAY_SPAN, DAY_START, Simulation

from .features import AttrVocab
from .models import CorrectionModel, DotProductModel
from .policy import ModelPolicy
from .tasks import MAX_OPTIONS, Dataset
from .train import fit_reward, predicted_values

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- policies
class NodePolicy:
    """Rule policy everywhere except ``node``, where ``inner`` decides.

    Records, at ``node``, the view the deciding policy saw (revealed only), the options, the
    pick and what the rule would have picked for the same view (for the agreement column)."""

    def __init__(self, rule: RulePolicy, node: str, inner=None, probe: "QueueProbe | None" = None):
        self.rule, self.node, self.inner, self.probe = rule, node, inner, probe
        self.records: list[dict] = []

    def choose(self, view, options):
        if view.node != self.node:
            return self.rule.choose(view, options)
        rule_p = self.rule.choose(view, options)
        p = (self.inner or self.rule).choose(view, options)
        pick = max(options, key=lambda o: (p.get(o, 0.0), -options.index(o)))  # same tie-break as the engine
        self.records.append({"pid": view.patient_id, "view": view, "options": list(options), "pick": pick,
                             "rule_pick": max(options, key=lambda o: (rule_p.get(o, 0.0), -options.index(o))),
                             "leads": self.probe(view, options) if self.probe else {o: 0.0 for o in options}})
        return p


class QueueProbe:
    """Days from the decision to the next free slot in each option's booking system, read
    without booking (what a clinic sees in its appointment book). Non-``server`` resources
    give 0 (their wait is a published distribution, already in the static option features).

    pathway_sim's PatientView has no resource state, so this reads the running Simulation's
    ``servers`` (read-only) and the patient's clock start; see the engine requests in the README."""

    def __init__(self, sc, fc, node: str):
        self.res = {}
        for o in fc.nodes[node].options:
            t = fc.nodes[o].test
            self.res[o] = _merged_test(sc, fc, t).get("resource") if t else None
        self.sim, self.arrival = None, {}

    def has_servers(self, sc, fc) -> bool:
        res = {k: {**v, **fc.resource_overrides.get(k, {})} for k, v in sc.resources.items()}
        return any(r and res.get(r, {}).get("type", "server") == "server" for r in self.res.values())

    def attach(self, sim: Simulation):
        self.sim, self.arrival = sim, {p.id: p.arrival for p in sim.patients}

    def __call__(self, view, options) -> dict[str, float]:
        t = self.arrival[view.patient_id] + view.t_now
        return {o: _next_slot_days(self.sim.servers.get(self.res.get(o)), t) for o in options}


def _next_slot_days(s, t_ready: float, priority: bool = False) -> float:
    """Mirror of engine._Server.book without the booking (keep in sync with pathway_sim/engine.py)."""
    if s is None:
        return 0.0
    d = int(math.floor(t_ready + (s.urgent_lead if priority else s.min_lead)))
    limit = s.cap if priority else s.normal_cap
    for _ in range(100000):
        if not (s.weekdays_only and d % 7 in (5, 6)) and s.booked.get(d, 0) < limit:
            return max(t_ready, d + DAY_START + DAY_SPAN * s.booked.get(d, 0) / s.cap) - t_ready
        d += 1
    return float("inf")


def simulate_with(sc, fc, patients, pol: NodePolicy, seed: int):
    sim = Simulation(sc, fc, patients, pol, seed)
    if pol.probe is not None:
        pol.probe.attach(sim)
    if pol.inner is not None and getattr(pol.inner, "probe", None) is not None:
        pol.inner.probe.attach(sim)
    return sim.run()


# --------------------------------------------------------------------------- features / outcomes
def _merged_test(sc, fc, tid):
    return {**sc.tests.get(tid, {}), **fc.test_overrides.get(tid, {})}


def option_vectors(sc, fc, node: str) -> dict[str, np.ndarray]:
    """Per option: identity one-hot (position at the node) + public test metadata
    (invasive, cost/1000, median wait/30 if the scenario gives one). Nothing patient-specific."""
    opts = list(fc.nodes[node].options)
    out = {}
    for k, o in enumerate(opts):
        n = fc.nodes[o]
        spec = _merged_test(sc, fc, n.test) if n.test else {}
        wait = spec.get("wait") if isinstance(spec.get("wait"), dict) else {}
        v = np.zeros(len(opts) + 3)
        v[k] = 1.0
        v[len(opts):] = [float(bool(spec.get("invasive"))), float(spec.get("cost_eur", 0) or 0) / 1000.0,
                         float(wait.get("median", 0) or 0) / 30.0]
        out[o] = v
    return out


def sampling_tests(sc, fc=None, node: str | None = None) -> set[str]:
    """Invasive tests (public scenario metadata). With ``fc``/``node``: only those on nodes
    downstream of the choice (its options, their retry fallbacks and anything after them)."""
    inv = {t for t, spec in sc.tests.items() if spec.get("invasive")}
    if fc is None or node is None:
        return inv
    children = {n: set() for n in fc.nodes}
    for n in fc.nodes.values():
        for a in list(n.after) + list(n.after_any) + list(n.after_optional):
            children[a].add(n.id)
        if n.kind == "choice":
            children[n.id] |= set(n.options)
        if n.retry and n.retry.get("fallback"):
            children[n.id].add(n.retry["fallback"])
    seen, stack = set(), list(fc.nodes[node].options)
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            stack += children[x]
    return {fc.nodes[x].test for x in seen if fc.nodes[x].test in inv}


def outcome(pr, t_choice_rel: float, tests: set[str]) -> tuple[bool, float]:
    """(diagnostic, days) after a choice made t_choice_rel days after the clock start, from events."""
    t0 = pr.patient.arrival + t_choice_rel  # arrival is the clock start in the log, visible
    evs = [e for e in pr.events if e.test in tests and e.t_ready >= t0 - 1e-6]
    diag = any(e.result is not None for e in evs)
    t_end = max((e.t_result for e in evs), default=t0)
    return diag, t_end - t0


def _featurizer(vocab, ov) -> ModelPolicy:
    return ModelPolicy(DotProductModel(), attr_vocab=vocab, option_vectors=ov, elapsed="t_now")


LEAD_SCALE = 30.0


def option_rows(ov, options, leads, queue: bool):
    return [np.r_[ov[o], [leads[o] / LEAD_SCALE]] if queue else ov[o] for o in options]


class QueueOptionVectors:
    """Per-decision option features for ModelPolicy: static vector + next-free-slot lead."""

    def __init__(self, ov, probe: QueueProbe):
        self.ov, self.probe = ov, probe

    def __call__(self, view, options):
        return option_rows(self.ov, options, self.probe(view, options), True)


def build_dataset(records, run, feat: ModelPolicy, ov, queue: bool, tests, days_per_diag):
    by_id = {pr.patient.id: pr for pr in run.patients}
    ctx, opts, mask, y, r, meta = [], [], [], [], [], []
    for rec in records:
        pr = by_id[rec["pid"]]
        diag, days = outcome(pr, rec["view"].t_now, tests)
        ctx.append(feat.context_array(rec["view"]))
        rows = option_rows(ov, rec["options"], rec["leads"], queue)
        o = np.zeros((MAX_OPTIONS, len(rows[0])))
        o[:len(rows)] = rows
        opts.append(o)
        mask.append(np.arange(MAX_OPTIONS) < len(rec["options"]))
        y.append(rec["options"].index(rec["pick"]))
        r.append(float(diag) - days / days_per_diag)
        meta.append({"diag": diag, "days": days, "attrs": dict(rec["view"].attributes), "pick": rec["pick"],
                     "leads": rec["leads"]})
    return Dataset(np.array(ctx), np.array(opts), np.array(mask), np.array(y, int)), np.array(r), meta


# --------------------------------------------------------------------------- evaluation
def _per_patient(run, sc, recs, tests, seed=0):
    """Per post-warm-up patient: what the table needs. Hidden truth (cancer) is used only to score."""
    rec_by = {}
    for rec in recs:
        rec_by.setdefault(rec["pid"], rec)
    rows = []
    for pr in run.patients:
        if pr.patient.arrival < run.warmup_days:
            continue
        rec = rec_by.get(pr.patient.id)
        samp = [e for e in pr.events if e.test in tests]
        row = {"pid": (seed, pr.patient.id), "cancer": pr.patient.cancer,
               "ttt": None if pr.t_treatment is None else pr.t_treatment - pr.patient.arrival,
               "at_node": rec is not None, "n_sampling": len(samp),
               "confirmed": pr.patient.cancer and any(e.result is True for e in samp)}
        if rec is not None:
            d, days = outcome(pr, rec["view"].t_now, tests)
            row.update(pick=rec["pick"], agree=rec["pick"] == rec["rule_pick"], diag=d, days=days,
                       attrs=dict(rec["view"].attributes))
        rows.append(row)
    return rows


def summarise(rows, target, rule_rows=None):
    cancers = [r for r in rows if r["cancer"]]
    node = [r for r in rows if r["at_node"]]
    on = np.array([r["ttt"] is not None and r["ttt"] <= target for r in cancers], float)
    ttt = [r["ttt"] for r in cancers if r["ttt"] is not None]
    nc = [r for r in node if r["cancer"]]
    out = {
        "n_patients": len(rows), "n_cancer": len(cancers), "n_at_node": len(node),
        "on_time": float(on.mean()) if len(on) else None,
        "on_time_se": float(on.std(ddof=1) / np.sqrt(len(on))) if len(on) > 1 else None,
        "median_days_to_treatment": float(median(ttt)) if ttt else None,
        "sampling_per_patient_at_node": float(np.mean([r["n_sampling"] for r in node])) if node else None,
        "sampling_per_100_patients": 100.0 * sum(r["n_sampling"] for r in rows) / max(1, len(rows)),
        "tissue_confirmed_cancers": int(sum(r["confirmed"] for r in cancers)),
        "tissue_confirmed_share_at_node": float(np.mean([r["confirmed"] for r in nc])) if nc else None,
        "diagnostic_share_at_node": float(np.mean([r["diag"] for r in node])) if node else None,
        "mean_days_choice_to_sampling_done": float(np.mean([r["days"] for r in node])) if node else None,
        "agreement_with_rule": float(np.mean([r["agree"] for r in node])) if node else None,
    }
    if rule_rows is not None:  # paired difference in on-time on the same patients
        rb = {r["pid"]: r for r in rule_rows if r["cancer"]}
        d = np.array([float(r["ttt"] is not None and r["ttt"] <= target)
                      - float(rb[r["pid"]]["ttt"] is not None and rb[r["pid"]]["ttt"] <= target)
                      for r in cancers if r["pid"] in rb])
        out["on_time_minus_rule"] = float(d.mean()) if len(d) else None
        out["on_time_minus_rule_se"] = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None
    return out


def confusion(rows, attr):
    c = Counter((r["attrs"].get(attr), r["pick"]) for r in rows if r["at_node"])
    return {f"{a}->{p}": n for (a, p), n in sorted(c.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))}


# --------------------------------------------------------------------------- main experiment
WD_GRID = (0.0, 0.1, 0.3, 1.0)


def _default_n(path) -> int:
    import yaml
    with open(path) as f:
        return int(yaml.safe_load(f).get("default_n") or 1000)


def run_experiment(scenario, flowchart, node, n_train=None, n_eval=None, train_seeds=(1001,), eval_seeds=(1, 2, 3),
                   days_per_diag=30.0, epochs=60, model_seed=0, confusion_attr="location", log=print,
                   val_seed=999, n_val=None, wd_grid=WD_GRID, queue_features=True):
    t_start = time.time()
    sc = load_scenario(str(scenario))
    fc = sc.flowcharts[flowchart]
    if fc.nodes.get(node) is None or fc.nodes[node].kind != "choice":
        raise SystemExit(f"{node} is not a choice node of {flowchart}")
    default_n = _default_n(scenario)
    n_train = n_train or max(3000, 3 * default_n)
    n_eval = n_eval or max(1000, default_n)
    tests = sampling_tests(sc, fc, node)
    ov = option_vectors(sc, fc, node)
    options = list(fc.nodes[node].options)
    probe = QueueProbe(sc, fc, node)
    feature_sets = ["static"] + (["queue"] if queue_features and probe.has_servers(sc, fc) else [])

    # 1. exploration logs (training seeds + one validation seed for model selection)
    def explore(s, n):
        pts = generate_patients(sc, n, seed=s)
        pol = NodePolicy(RulePolicy(fc.policy, s), node, RandomPolicy(seed=s), probe=probe)
        return pol.records, simulate_with(sc, fc, pts, pol, seed=s)

    train_recs = [explore(s, n_train) for s in train_seeds]
    val_recs = explore(val_seed, n_val or max(1, n_train // 2)) if len(wd_grid) > 1 else None
    vocab = AttrVocab.from_attributes(rec["view"].attributes for recs, _ in train_recs for rec in recs)
    feat = _featurizer(vocab, ov)

    def dataset(recs_runs, queue):
        parts = [build_dataset(recs, run, feat, ov, queue, tests, days_per_diag) for recs, run in recs_runs]
        d = Dataset(*(np.concatenate([getattr(p[0], k) for p in parts]) for k in ("ctx", "opts", "mask", "y")))
        return d, np.concatenate([p[1] for p in parts]), [m for p in parts for m in p[2]]

    data = {fs: dataset(train_recs, fs == "queue") for fs in feature_sets}
    val = {fs: dataset([val_recs], fs == "queue")[:2] for fs in feature_sets} if val_recs else {}
    ds, r, meta = data["static"]
    log(f"exploration: {len(ds)} logged choices at '{node}' from {len(train_seeds)} x {n_train} training patients "
        f"({time.time() - t_start:.0f}s); context dims {ds.ctx.shape[1]} (attribute one-hot {len(vocab)}), "
        f"option dims {ds.opts.shape[2]}; feature sets {feature_sets}")

    # empirical outcome table from the exploration log (what the signal says)
    signal = defaultdict(list)
    for m, rr in zip(meta, r):
        signal[(m["attrs"].get(confusion_attr), m["pick"])].append((m["diag"], m["days"], rr, m["leads"][m["pick"]]))

    # 2-3. train both models on the same data and signal; weight decay per model chosen by
    # reward MSE on the validation exploration log (never by agreement with the rule)
    models, selection, model_fs = {}, {}, {}
    for fs in feature_sets:
        d, rr, _ = data[fs]
        n_ctx, n_opt = d.ctx.shape[1], d.opts.shape[2]
        suffix = "" if fs == "static" else " + queue lead"
        makers = {"dot-product" + suffix: lambda: DotProductModel(n_ctx=n_ctx, n_opt=n_opt, seed=model_seed),
                  "correction (2 layers)" + suffix: lambda: CorrectionModel(n_layers=2, n_ctx=n_ctx, n_opt=n_opt,
                                                                            seed=model_seed)}
        dv, rv = val.get(fs, (None, None))
        for name, make in makers.items():
            t = time.time()
            best = None
            for wd in wd_grid:
                m = fit_reward(make(), d, rr, epochs=epochs, seed=model_seed, max_seconds=90, weight_decay=wd)
                if dv is None or not len(dv):
                    best = (0.0, wd, m)
                    break
                pv = predicted_values(m, dv)
                mse = float(np.mean((pv[np.arange(len(dv)), dv.y] - rv) ** 2))
                selection.setdefault(name, {})[str(wd)] = round(mse, 4)
                if best is None or mse < best[0]:
                    best = (mse, wd, m)
            models[name], model_fs[name] = best[2], fs
            selection.setdefault(name, {})["chosen_weight_decay"] = best[1]
            log(f"trained {name} ({best[2].n_params()} params), weight decay {best[1]} "
                f"(val reward MSE {selection[name]}) in {time.time() - t:.0f}s")
    dv, rv = val.get("static", (None, None))

    # 4. in-loop evaluation on held-out patients
    policies = {"rule (hand-written)": None, "random": "random", **{k: k for k in models}}
    rows = {k: [] for k in policies}
    learned = {k: defaultdict(list) for k in models}
    for s in eval_seeds:
        pts = generate_patients(sc, n_eval, seed=s)
        for pname, kind in policies.items():
            if kind is None:
                inner = None
            elif kind == "random":
                inner = RandomPolicy(seed=s + 7919)
            else:
                q = model_fs[kind] == "queue"
                inner = ModelPolicy(models[kind], attr_vocab=vocab, elapsed="t_now",
                                    option_vectors=QueueOptionVectors(ov, probe) if q else ov)
            pol = NodePolicy(RulePolicy(fc.policy, s), node, inner, probe=probe)
            run = simulate_with(sc, fc, pts, pol, seed=s)
            rows[pname] += _per_patient(run, sc, pol.records, tests, s)
            if kind in models and pol.records:
                eds, _, emeta = build_dataset(pol.records, run, feat, ov, model_fs[kind] == "queue", tests,
                                              days_per_diag)
                pv = predicted_values(models[kind], eds)
                for m_, v in zip(emeta, pv):
                    learned[kind][m_["attrs"].get(confusion_attr)].append(v[:len(options)])
        log(f"eval seed {s} done ({time.time() - t_start:.0f}s)")
    rule_rows = rows["rule (hand-written)"]
    table = {p: summarise(rows[p], sc.target_days, None if p.startswith("rule") else rule_rows) for p in policies}
    conf = {p: confusion(rows[p], confusion_attr) for p in policies}
    learned_tab = {k: {str(a): dict(zip(options, np.round(np.mean(v, 0), 3).tolist())) for a, v in sorted(d.items(), key=lambda kv: str(kv[0]))}
                   for k, d in learned.items()}
    signal_tab = {f"{a}->{p}": {"n": len(v), "diagnostic": round(float(np.mean([x[0] for x in v])), 3),
                                "days": round(float(np.mean([x[1] for x in v])), 2),
                                "reward": round(float(np.mean([x[2] for x in v])), 3),
                                "lead_days_at_choice": round(float(np.mean([x[3] for x in v])), 2)}
                  for (a, p), v in sorted(signal.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))}
    return {
        "scenario": str(scenario), "flowchart": flowchart, "node": node, "options": options,
        "target_days": sc.target_days, "n_train_choices": len(ds), "train_seeds": list(train_seeds),
        "n_train_patients_per_seed": n_train, "eval_seeds": list(eval_seeds), "n_eval_patients_per_seed": n_eval,
        "reward": f"diagnostic - days_from_choice_to_last_sampling_result / {days_per_diag:g}",
        "days_per_diagnosis": days_per_diag, "epochs": epochs, "model_seed": model_seed,
        "val_seed": val_seed, "n_val_choices": 0 if dv is None else len(dv), "feature_sets": feature_sets,
        "model_selection_val_reward_mse": selection, "val_reward_variance": None if rv is None else round(float(rv.var()), 4),
        "attribute_vocab": vocab.to_list(), "table": table, "confusion_attr": confusion_attr,
        "confusion": conf, "exploration_signal": signal_tab, "learned_values": learned_tab,
        "runtime_s": round(time.time() - t_start, 1),
    }


def markdown(res) -> str:
    def f(x, fmt="{:.1f}"):
        return "-" if x is None else fmt.format(x)

    L = [f"### {Path(res['scenario']).name} / {res['flowchart']} / node `{res['node']}` "
         f"(held-out seeds {res['eval_seeds']} x {res['n_eval_patients_per_seed']} patients; "
         f"trained on {res['n_train_choices']} exploration choices; target {res['target_days']:g} d)", "",
         "| Policy at node | On-time | vs rule (paired) | Median days to treatment | Sampling procs / patient at node "
         "| Tissue-confirmed cancers | Diagnostic sample at node | Days choice->sampling done | Agreement with rule |",
         "|---|---|---|---|---|---|---|---|---|"]
    for p, t in res["table"].items():
        d = t.get("on_time_minus_rule")
        vs = "-" if d is None else f"{100 * d:+.1f} pp (s.e. {100 * t['on_time_minus_rule_se']:.1f})"
        L.append(f"| {p} | {f(t['on_time'] and 100 * t['on_time'])}% (s.e. {f(t['on_time_se'] and 100 * t['on_time_se'])}) | {vs} "
                 f"| {f(t['median_days_to_treatment'])} | {f(t['sampling_per_patient_at_node'], '{:.2f}')} "
                 f"| {t['tissue_confirmed_cancers']} / {t['n_cancer']} | {f(t['diagnostic_share_at_node'] and 100 * t['diagnostic_share_at_node'])}% "
                 f"| {f(t['mean_days_choice_to_sampling_done'])} | {f(t['agreement_with_rule'] and 100 * t['agreement_with_rule'])}% |")
    attr = res["confusion_attr"]
    keys = sorted({k for c in res["confusion"].values() for k in c})
    L += ["", f"Choices by revealed `{attr}` (counts, held-out runs):", "",
          "| Policy | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for p, c in res["confusion"].items():
        L.append(f"| {p} | " + " | ".join(str(c.get(k, 0)) for k in keys) + " |")
    L += ["", f"Exploration signal (random choice at the node; reward = {res['reward']}):", "",
          "| " + attr + " -> option | n | diagnostic | days | mean reward |" + (lead_h := (
              " next-slot lead at choice (d) |" if "queue" in res.get("feature_sets", []) else "")),
          "|---|---|---|---|---|" + ("---|" if lead_h else "")]
    for k, v in res["exploration_signal"].items():
        L.append(f"| {k} | {v['n']} | {v['diagnostic']:.2f} | {v['days']:.1f} | {v['reward']:+.3f} |"
                 + (f" {v['lead_days_at_choice']:.1f} |" if lead_h else ""))
    L += ["", "Learned predicted reward per option (mean over held-out contexts at the node):", "",
          "| Model | " + attr + " | " + " | ".join(res["options"]) + " |", "|---|---|" + "---|" * len(res["options"])]
    for mname, d in res["learned_values"].items():
        for a, vals in d.items():
            L.append(f"| {mname} | {a} | " + " | ".join(f"{vals[o]:+.3f}" for o in res["options"]) + " |")
    return "\n".join(L)


def save(res, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if out.exists():
        try:
            data = json.loads(out.read_text())
        except json.JSONDecodeError:
            data = {}
    key = f"{Path(res['scenario']).stem}/{res['flowchart']}/{res['node']}"
    data[key] = {**res, "markdown": markdown(res)}
    out.write_text(json.dumps(data, indent=1))
    return key


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scenario", default="scenarios/generated/stokstad_calibrated.yaml")
    ap.add_argument("--flowchart", default="optimal")
    ap.add_argument("--node", default="method")
    ap.add_argument("--n-train", type=int, default=None, help="training patients per seed (default max(3000, 3 x scenario default_n))")
    ap.add_argument("--n-eval", type=int, default=None, help="held-out patients per seed (default max(1000, scenario default_n))")
    ap.add_argument("--train-seeds", type=int, nargs="+", default=[1001])
    ap.add_argument("--eval-seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--days-per-diagnosis", type=float, default=30.0,
                    help="reward exchange rate: a diagnostic sample is worth this many days (value judgement)")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--weight-decay", type=float, nargs="+", default=list(WD_GRID),
                    help="grid; chosen per model by reward MSE on a validation exploration log")
    ap.add_argument("--val-seed", type=int, default=999)
    ap.add_argument("--no-queue-features", action="store_true",
                    help="skip the model variants that see each option's next-free-slot lead")
    ap.add_argument("--confusion-attr", default="location")
    ap.add_argument("--model-seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "runs" / "model_in_loop.json"))
    a = ap.parse_args(argv)
    res = run_experiment(a.scenario, a.flowchart, a.node, a.n_train, a.n_eval, tuple(a.train_seeds),
                         tuple(a.eval_seeds), a.days_per_diagnosis, a.epochs, a.model_seed, confusion_attr=a.confusion_attr,
                         val_seed=a.val_seed, wd_grid=tuple(a.weight_decay),
                         queue_features=not a.no_queue_features)
    print()
    print(markdown(res))
    key = save(res, Path(a.out))
    print(f"\nwrote {a.out} [{key}] (runtime {res['runtime_s']:.0f}s)")


if __name__ == "__main__":
    main()
