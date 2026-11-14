"""W1 / D6: the decision model making a real choice inside the simulator.

    python -m decision_model.in_loop --scenario scenarios/generated/stokstad_calibrated.yaml \
        --flowchart optimal --node method
    python -m decision_model.in_loop --scenario scenarios/finland_lung.yaml \
        --flowchart baseline --node sample_choice --n-train 18800 --train-seeds 1001 1002 --eval-seeds 1 2
    python -m decision_model.comparison_experiment          # open question 12 (option sets that vary)

Pipeline (every step uses revealed information only):

1. Exploration log. Training patients (their own seeds) run through the flowchart with the
   flowchart's rule policy at every node except ``--node``, where ``RandomPolicy`` picks
   uniformly among the options on offer. At each visit of ``--node`` we keep the ``PatientView``
   the policy was given (group, age, t_now, history, revealed attributes, options on offer and
   their queue leads: what the clinic knew at that moment).
2. Outcome per logged choice, from the run log's events only: the invasive tests downstream of
   the choice. ``diagnostic`` = one of them returned a result (positive or negative, not
   non-diagnostic); ``days`` = choice to the last of their results.
   Reward ``r = diagnostic - days / days_per_diagnosis``. ``patient.condition``, ``patient.cancer``,
   ``patient.results`` and hidden attributes are never read for training or at run time (only in
   the evaluation table, to count cancers).
3. Training (same data, same signal for every model): each model's logit for an option is
   regressed on the reward of the option actually taken (direct-method contextual bandit,
   ``train.fit_reward``). Under uniform exploration this estimates each option's expected
   reward given the context; the policy picks the argmax among the options on offer.
4. In-loop evaluation on held-out patients (other seeds): rule, random and the models at
   ``--node``, rule everywhere else, same patients and random numbers.

Feature sets: ``static`` (option identity + public test metadata), ``lead`` (+ each option's own
queue lead from ``PatientView.option_leads``), ``set`` / ``lead+set`` (+ a fixed-size summary of the
whole offer in the CONTEXT: per option of the node, offered flag and lead; a hand-made set feature
that lets a per-option dot-product model see the other options).

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

from pathway_sim import RandomPolicy, RulePolicy, generate_patients, load_scenario, simulate

from .features import AttrVocab
from .models import CorrectionModel, DotProductModel
from .policy import ModelPolicy
from .tasks import MAX_OPTIONS, Dataset
from .train import fit_reward, predicted_values

ROOT = Path(__file__).resolve().parent.parent
LEAD_SCALE = 30.0
WD_GRID = (0.0, 0.1, 0.3, 1.0)
RULE = "rule (hand-written)"


def _pick(p: dict, options: list[str]) -> str:
    return max(options, key=lambda o: (p.get(o, 0.0), -options.index(o)))  # same tie-break as the engine


# --------------------------------------------------------------------------- policies
class NodePolicy:
    """Rule policy everywhere except ``node``, where ``inner`` decides.

    Records, at ``node``, the view the deciding policy saw (revealed only), the options on offer,
    their queue leads, the pick, and what the rule (and any reference policies) would have picked
    for the same view (agreement columns)."""

    def __init__(self, rule: RulePolicy, node: str, inner=None, refs: dict | None = None):
        self.rule, self.node, self.inner, self.refs = rule, node, inner, refs or {}
        self.records: list[dict] = []

    def choose(self, view, options):
        if view.node != self.node:
            return self.rule.choose(view, options)
        p = (self.inner or self.rule).choose(view, options)
        ref_picks = {RULE: _pick(self.rule.choose(view, options), options)}
        for name, ref in self.refs.items():
            ref_picks[name] = _pick(ref.choose(view, options), options)
        self.records.append({"pid": view.patient_id, "view": view, "options": list(options),
                             "pick": _pick(p, options), "ref_picks": ref_picks,
                             "leads": dict(getattr(view, "option_leads", {}) or {})})
        return p


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


def options_with_queue(sc, fc, node: str) -> list[str]:
    """Options whose first test is booked on a capacity-limited (server) resource."""
    res = {k: {**v, **fc.resource_overrides.get(k, {})} for k, v in sc.resources.items()}
    out = []
    for o in fc.nodes[node].options:
        t = fc.nodes[o].test
        rid = _merged_test(sc, fc, t).get("resource", "none") if t else "none"
        if res.get(rid, {}).get("type", "server" if rid in res else "none") == "server":
            out.append(o)
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


FEATURE_SETS = {"static": (False, False), "lead": (True, False), "set": (False, True), "lead+set": (True, True)}


def option_rows(ov, options, leads, lead: bool):
    return [np.r_[ov[o], [leads.get(o, 0.0) / LEAD_SCALE, float(o in leads)]] if lead else ov[o] for o in options]


class SetSummary:
    """Fixed-size summary of the whole offer, for the context: per option of the node,
    [offered, lead/30] (lead 0 when the option has no queue or is not offered)."""

    def __init__(self, node_options: list[str], lead: bool):
        self.node_options, self.lead = list(node_options), lead

    def __call__(self, view):
        offered, leads = set(view.offered or []), view.option_leads or {}
        v = []
        for o in self.node_options:
            v.append(float(o in offered))
            if self.lead:
                v.append(leads.get(o, 0.0) / LEAD_SCALE if o in offered else 0.0)
        return np.array(v)


class FeatureSet:
    def __init__(self, name, vocab, ov, node_options):
        self.name = name
        self.lead, use_set = FEATURE_SETS[name]
        self.ov = ov
        self.ctx = ModelPolicy(DotProductModel(), attr_vocab=vocab, option_vectors=ov, elapsed="t_now",
                               extra_context=SetSummary(node_options, self.lead) if use_set else None)

    def rows(self, view, options):
        return option_rows(self.ov, options, dict(view.option_leads or {}), self.lead)

    def policy(self, model) -> ModelPolicy:
        return ModelPolicy(model, attr_vocab=self.ctx.attr_vocab, elapsed="t_now", extra_context=self.ctx.extra_context,
                           option_vectors=(lambda view, options: self.rows(view, options)) if self.lead else self.ov)


def build_dataset(records, run, fs: FeatureSet, tests, days_per_diag):
    by_id = {pr.patient.id: pr for pr in run.patients}
    ctx, opts, mask, y, r, meta = [], [], [], [], [], []
    for rec in records:
        pr = by_id[rec["pid"]]
        diag, days = outcome(pr, rec["view"].t_now, tests)
        ctx.append(fs.ctx.context_array(rec["view"]))
        rows = option_rows(fs.ov, rec["options"], rec["leads"], fs.lead)
        o = np.zeros((MAX_OPTIONS, len(rows[0])))
        o[:len(rows)] = rows
        opts.append(o)
        mask.append(np.arange(MAX_OPTIONS) < len(rows))
        y.append(rec["options"].index(rec["pick"]))
        r.append(float(diag) - days / days_per_diag)
        meta.append({"diag": diag, "days": days, "attrs": dict(rec["view"].attributes), "pick": rec["pick"],
                     "leads": rec["leads"], "options": rec["options"]})
    return Dataset(np.array(ctx), np.array(opts), np.array(mask), np.array(y, int)), np.array(r), meta


# --------------------------------------------------------------------------- evaluation
def _per_patient(run, recs, tests, days_per_diag, seed=0):
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
            row.update(pick=rec["pick"], ref_picks=rec["ref_picks"], diag=d, days=days,
                       reward=float(d) - days / days_per_diag, attrs=dict(rec["view"].attributes),
                       offered=tuple(rec["options"]), leads=rec["leads"])
        rows.append(row)
    return rows


def _paired(rows, base_rows, f):
    b = {r["pid"]: r for r in base_rows}
    d = np.array([f(r) - f(b[r["pid"]]) for r in rows if r["pid"] in b])
    if not len(d):
        return None, None
    return float(d.mean()), (float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None)


def summarise(rows, target, rule_rows=None, ref_names=(RULE,)):
    cancers = [r for r in rows if r["cancer"]]
    node = [r for r in rows if r["at_node"]]
    on = np.array([r["ttt"] is not None and r["ttt"] <= target for r in cancers], float)
    ttt = [r["ttt"] for r in cancers if r["ttt"] is not None]
    nc = [r for r in node if r["cancer"]]
    rw = np.array([r["reward"] for r in node])
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
        "mean_reward_at_node": float(rw.mean()) if len(rw) else None,
        "agreement_with_rule": float(np.mean([r["pick"] == r["ref_picks"][RULE] for r in node])) if node else None,
    }
    for name in ref_names:
        if name != RULE and node:
            out[f"agreement_with {name}"] = float(np.mean([r["pick"] == r["ref_picks"][name] for r in node]))
    if rule_rows is not None:  # paired differences on the same patients
        on_f = lambda r: float(r["ttt"] is not None and r["ttt"] <= target)
        out["on_time_minus_rule"], out["on_time_minus_rule_se"] = _paired(cancers, [r for r in rule_rows if r["cancer"]], on_f)
        out["reward_minus_rule"], out["reward_minus_rule_se"] = _paired(node, [r for r in rule_rows if r["at_node"]],
                                                                        lambda r: r["reward"])
    return out


def confusion(rows, attr):
    c = Counter((r["attrs"].get(attr), r["pick"]) for r in rows if r["at_node"])
    return {f"{a}->{p}": n for (a, p), n in sorted(c.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))}


# --------------------------------------------------------------------------- main experiment
def _default_n(path) -> int:
    import yaml
    with open(path) as f:
        return int(yaml.safe_load(f).get("default_n") or 1000)


def default_variants(n_options: int, has_queue: bool, set_ablation: bool = True) -> list[tuple[str, str, str]]:
    """(name, model kind, feature set)."""
    v = [("dot-product", "dot", "static"), ("correction (2 layers)", "corr", "static")]
    if has_queue:
        v += [("dot-product + queue lead", "dot", "lead"), ("correction (2 layers) + queue lead", "corr", "lead")]
    if set_ablation and has_queue:
        v.append(("dot-product + queue lead + set summary", "dot", "lead+set"))
    elif set_ablation and n_options >= 3:
        v.append(("dot-product + set summary", "dot", "set"))
    return v


def run_experiment(scenario, flowchart, node, n_train=None, n_eval=None, train_seeds=(1001,), eval_seeds=(1, 2, 3),
                   days_per_diag=30.0, epochs=60, model_seed=0, confusion_attr="location", log=print,
                   val_seed=999, n_val=None, wd_grid=WD_GRID, queue_features=True, set_ablation=True,
                   variants=None, refs=None, keep_rows=False):
    """refs: name -> callable(sc, fc, seed) returning a reference policy, evaluated in the loop and
    used for an agreement column (e.g. an expected-value rule that knows the scenario's yields)."""
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
    queued = options_with_queue(sc, fc, node)
    if variants is None:
        variants = default_variants(len(options), bool(queued) and queue_features, set_ablation)
    refs = refs or {}

    # 1. exploration logs (training seeds + one validation seed for model selection)
    def explore(s, n):
        pts = generate_patients(sc, n, seed=s)
        pol = NodePolicy(RulePolicy(fc.policy, s), node, RandomPolicy(seed=s))
        return pol.records, simulate(sc, fc, pts, pol, seed=s)

    train_recs = [explore(s, n_train) for s in train_seeds]
    val_recs = explore(val_seed, n_val or max(1, n_train // 2)) if len(wd_grid) > 1 else None
    vocab = AttrVocab.from_attributes(rec["view"].attributes for recs, _ in train_recs for rec in recs)
    fsets = {f: FeatureSet(f, vocab, ov, options) for f in {v[2] for v in variants} | {"static"}}

    def dataset(recs_runs, fs):
        parts = [build_dataset(recs, run, fs, tests, days_per_diag) for recs, run in recs_runs]
        d = Dataset(*(np.concatenate([getattr(p[0], k) for p in parts]) for k in ("ctx", "opts", "mask", "y")))
        return d, np.concatenate([p[1] for p in parts]), [m for p in parts for m in p[2]]

    data = {f: dataset(train_recs, fs) for f, fs in fsets.items()}
    val = {f: dataset([val_recs], fs)[:2] for f, fs in fsets.items()} if val_recs else {}
    ds, r, meta = data["static"]
    log(f"exploration: {len(ds)} logged choices at '{node}' from {len(train_seeds)} x {n_train} training patients "
        f"({time.time() - t_start:.0f}s); context dims {ds.ctx.shape[1]} (attribute one-hot {len(vocab)}); "
        f"options with a queue: {queued}; variants {[v[0] for v in variants]}")

    # empirical outcome table from the exploration log (what the signal says)
    signal = defaultdict(list)
    for m, rr in zip(meta, r):
        signal[(m["attrs"].get(confusion_attr), m["pick"])].append((m["diag"], m["days"], rr, m["leads"].get(m["pick"], 0.0)))

    # 2-3. train every model on the same data and signal; weight decay per model chosen by
    # reward MSE on the validation exploration log (never by agreement with the rule)
    models, selection, model_fs = {}, {}, {}
    for name, kind, f in variants:
        d, rr, _ = data[f]
        n_ctx, n_opt = d.ctx.shape[1], d.opts.shape[2]
        make = ((lambda: DotProductModel(n_ctx=n_ctx, n_opt=n_opt, seed=model_seed)) if kind == "dot" else
                (lambda: CorrectionModel(n_layers=2, n_ctx=n_ctx, n_opt=n_opt, seed=model_seed)))
        dv, rv = val.get(f, (None, None))
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
        models[name], model_fs[name] = best[2], f
        selection.setdefault(name, {})["chosen_weight_decay"] = best[1]
        log(f"trained {name} ({best[2].n_params()} params), weight decay {best[1]} "
            f"(val reward MSE {selection[name]}) in {time.time() - t:.0f}s")
    dv, rv = val.get("static", (None, None))

    # 4. in-loop evaluation on held-out patients
    policies = {RULE: None, "random": "random", **{k: k for k in refs}, **{k: k for k in models}}
    rows = {k: [] for k in policies}
    learned = {k: defaultdict(list) for k in models}
    for s in eval_seeds:
        pts = generate_patients(sc, n_eval, seed=s)
        ref_pols = {k: mk(sc, fc, s) for k, mk in refs.items()}
        for pname, kind in policies.items():
            if kind is None:
                inner = None
            elif kind == "random":
                inner = RandomPolicy(seed=s + 7919)
            elif kind in refs:
                inner = ref_pols[kind]
            else:
                inner = fsets[model_fs[kind]].policy(models[kind])
            pol = NodePolicy(RulePolicy(fc.policy, s), node, inner, refs=ref_pols)
            run = simulate(sc, fc, pts, pol, seed=s)
            rows[pname] += _per_patient(run, pol.records, tests, days_per_diag, s)
            if kind in models and pol.records:
                eds, _, emeta = build_dataset(pol.records, run, fsets[model_fs[kind]], tests, days_per_diag)
                pv = predicted_values(models[kind], eds)
                for m_, v, msk in zip(emeta, pv, eds.mask):
                    full = np.full(len(options), np.nan)
                    for j, o in enumerate(m_["options"]):
                        full[options.index(o)] = v[j]
                    learned[kind][m_["attrs"].get(confusion_attr)].append(full)
        log(f"eval seed {s} done ({time.time() - t_start:.0f}s)")
    rule_rows = rows[RULE]
    ref_names = (RULE, *refs)
    table = {p: summarise(rows[p], sc.target_days, None if p == RULE else rule_rows, ref_names) for p in policies}
    conf = {p: confusion(rows[p], confusion_attr) for p in policies}
    learned_tab = {k: {str(a): dict(zip(options, [None if np.isnan(x) else round(float(x), 3)
                                                  for x in np.nanmean(np.array(v), 0)]))
                       for a, v in sorted(d.items(), key=lambda kv: str(kv[0]))}
                   for k, d in learned.items()}
    signal_tab = {f"{a}->{p}": {"n": len(v), "diagnostic": round(float(np.mean([x[0] for x in v])), 3),
                                "days": round(float(np.mean([x[1] for x in v])), 2),
                                "reward": round(float(np.mean([x[2] for x in v])), 3),
                                "lead_days_at_choice": round(float(np.mean([x[3] for x in v])), 2)}
                  for (a, p), v in sorted(signal.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))}
    res = {
        "scenario": str(scenario), "flowchart": flowchart, "node": node, "options": options,
        "options_with_queue": queued, "availability": fc.nodes[node].availability or {},
        "target_days": sc.target_days, "n_train_choices": len(ds), "train_seeds": list(train_seeds),
        "n_train_patients_per_seed": n_train, "eval_seeds": list(eval_seeds), "n_eval_patients_per_seed": n_eval,
        "reward": f"diagnostic - days_from_choice_to_last_sampling_result / {days_per_diag:g}",
        "days_per_diagnosis": days_per_diag, "epochs": epochs, "model_seed": model_seed,
        "val_seed": val_seed, "n_val_choices": 0 if dv is None else len(dv),
        "variants": [list(v) for v in variants], "references": list(refs),
        "model_selection_val_reward_mse": selection, "val_reward_variance": None if rv is None else round(float(rv.var()), 4),
        "attribute_vocab": vocab.to_list(), "table": table, "confusion_attr": confusion_attr,
        "confusion": conf, "exploration_signal": signal_tab, "learned_values": learned_tab,
        "runtime_s": round(time.time() - t_start, 1),
    }
    if keep_rows:
        res["_rows"] = rows
        res["_models"] = models
    return res


def markdown(res) -> str:
    def f(x, fmt="{:.1f}"):
        return "-" if x is None else fmt.format(x)

    def pp(t, key, scale=100, unit=" pp"):
        d = t.get(key)
        return "-" if d is None else f"{scale * d:+.1f}{unit} (s.e. {scale * (t.get(key + '_se') or 0):.1f})"

    L = [f"### {Path(res['scenario']).name} / {res['flowchart']} / node `{res['node']}` "
         f"(held-out seeds {res['eval_seeds']} x {res['n_eval_patients_per_seed']} patients; "
         f"trained on {res['n_train_choices']} exploration choices; target {res['target_days']:g} d)", "",
         "| Policy at node | Mean reward at node | vs rule (paired) | On-time | vs rule (paired) | Median days to treatment "
         "| Sampling procs / patient at node | Tissue-confirmed cancers | Diagnostic sample at node "
         "| Days choice->sampling done | Agreement with rule |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p, t in res["table"].items():
        rw = "-" if t.get("reward_minus_rule") is None else f"{t['reward_minus_rule']:+.3f} (s.e. {t['reward_minus_rule_se'] or 0:.3f})"
        L.append(f"| {p} | {f(t['mean_reward_at_node'], '{:+.3f}')} | {rw} "
                 f"| {f(t['on_time'] and 100 * t['on_time'])}% (s.e. {f(t['on_time_se'] and 100 * t['on_time_se'])}) "
                 f"| {pp(t, 'on_time_minus_rule')} "
                 f"| {f(t['median_days_to_treatment'])} | {f(t['sampling_per_patient_at_node'], '{:.2f}')} "
                 f"| {t['tissue_confirmed_cancers']} / {t['n_cancer']} | {f(t['diagnostic_share_at_node'] and 100 * t['diagnostic_share_at_node'])}% "
                 f"| {f(t['mean_days_choice_to_sampling_done'])} | {f(t['agreement_with_rule'] and 100 * t['agreement_with_rule'])}% |")
    attr = res["confusion_attr"]
    keys = sorted({k for c in res["confusion"].values() for k in c})
    L += ["", f"Choices by revealed `{attr}` (counts, held-out runs):", "",
          "| Policy | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for p, c in res["confusion"].items():
        L.append(f"| {p} | " + " | ".join(str(c.get(k, 0)) for k in keys) + " |")
    lead_h = bool(res.get("options_with_queue"))
    L += ["", f"Exploration signal (random choice at the node; reward = {res['reward']}):", "",
          "| " + attr + " -> option | n | diagnostic | days | mean reward |" + (" mean lead at choice (d) |" if lead_h else ""),
          "|---|---|---|---|---|" + ("---|" if lead_h else "")]
    for k, v in res["exploration_signal"].items():
        L.append(f"| {k} | {v['n']} | {v['diagnostic']:.2f} | {v['days']:.1f} | {v['reward']:+.3f} |"
                 + (f" {v['lead_days_at_choice']:.1f} |" if lead_h else ""))
    L += ["", "Learned predicted reward per option (mean over held-out contexts at the node where offered):", "",
          "| Model | " + attr + " | " + " | ".join(res["options"]) + " |", "|---|---|" + "---|" * len(res["options"])]
    for mname, d in res["learned_values"].items():
        for a, vals in d.items():
            L.append(f"| {mname} | {a} | " + " | ".join("-" if vals[o] is None else f"{vals[o]:+.3f}" for o in res["options"]) + " |")
    return "\n".join(L)


def save(res, out: Path, extra_markdown: str = "", key_suffix: str = ""):
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if out.exists():
        try:
            data = json.loads(out.read_text())
        except json.JSONDecodeError:
            data = {}
    key = f"{Path(res['scenario']).stem}/{res['flowchart']}/{res['node']}{key_suffix}"
    clean = {k: v for k, v in res.items() if not k.startswith("_")}
    data[key] = {**clean, "markdown": markdown(res) + extra_markdown}
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
                    help="skip the model variants that see the options' queue leads")
    ap.add_argument("--no-set-ablation", action="store_true",
                    help="skip the dot-product variant with a hand-made set summary in the context")
    ap.add_argument("--confusion-attr", default="location")
    ap.add_argument("--model-seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "runs" / "model_in_loop.json"))
    a = ap.parse_args(argv)
    res = run_experiment(a.scenario, a.flowchart, a.node, a.n_train, a.n_eval, tuple(a.train_seeds),
                         tuple(a.eval_seeds), a.days_per_diagnosis, a.epochs, a.model_seed, confusion_attr=a.confusion_attr,
                         val_seed=a.val_seed, wd_grid=tuple(a.weight_decay),
                         queue_features=not a.no_queue_features, set_ablation=not a.no_set_ablation)
    print()
    print(markdown(res))
    key = save(res, Path(a.out))
    print(f"\nwrote {a.out} [{key}] (runtime {res['runtime_s']:.0f}s)")


if __name__ == "__main__":
    main()
