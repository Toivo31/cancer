"""Open question 12: does comparing options matter, inside the simulator?

    python -m decision_model.comparison_experiment            # both flowcharts, ~6 min on 2 cores
    python -m decision_model.comparison_experiment --quick    # small, for a smoke test

Scenario: scenarios/experiments/stokstad_method_availability.yaml (built by
decision_model/make_experiment_scenario.py). Node ``method`` offers bronchoscopy (needle-biopsy
rescue if non-diagnostic), radial EBUS and needle biopsy, with varying availability.

* ``availability``: the best pick depends on what is on offer, but each option's value does not
  depend on the OTHER options (needle-biopsy wait is a fixed delay). Prediction: per-option
  scoring is enough, so dot-product = correction.
* ``rescue_queue``: needle biopsy is booked on a shared list whose lead varies a lot. Bronchoscopy's
  value depends on that lead (its rescue goes there), i.e. on a feature of ANOTHER option. A
  dot-product model that sees each option's own lead cannot use it when scoring bronchoscopy; the
  correction model can (attention over the offered options); a dot-product model with a hand-made
  summary of the offer in its context can too (ablation).

Reference policy "expected-value rule": computes each offered option's expected reward from the
scenario's published-style parameters (non-diagnostic rates by revealed location, wait and report
distributions) and the queue leads in the view. It knows the yields a clinic could read in the
literature, never a patient's hidden truth. It is a hand-built benchmark, not a learned model.
"""
from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .in_loop import RULE, ROOT, _merged_test, _paired, markdown, run_experiment, save

SCEN = ROOT / "scenarios" / "experiments" / "stokstad_method_availability.yaml"
EV = "expected-value rule (knows yields)"
LEAD_BUCKETS = [(0, 7), (7, 20), (20, 1e9)]


def _mean(d) -> float:
    """Mean of a scenario distribution spec (number, lognormal median/p90, uniform)."""
    if d is None:
        return 0.0
    if isinstance(d, (int, float)):
        return float(d)
    if d.get("dist") == "lognormal":
        s = math.log(d["p90"] / d["median"]) / 1.2816
        return d["median"] * math.exp(s * s / 2)
    if d.get("dist") == "uniform":
        return (d["low"] + d["high"]) / 2
    return float(d.get("mean", d.get("median", 0.0)))


class ExpectedValueRule:
    """argmax over offered options of P(diagnostic) - E[days]/D, from scenario parameters + leads."""

    def __init__(self, sc, fc, days_per_diag=30.0):
        self.sc, self.fc, self.D = sc, fc, days_per_diag

    def _test(self, node_id, loc, leads):
        n = self.fc.nodes[node_id]
        spec = _merged_test(self.sc, self.fc, n.test)
        nd = spec.get("p_nondiagnostic", 0.0) or 0.0
        if isinstance(nd, dict):
            nd = nd.get(loc, nd.get("default", 0.0))
        res = self.sc.resources.get(spec.get("resource", "none"), {})
        wait = leads.get(node_id) if node_id in leads else (
            _mean(spec.get("wait", res.get("wait"))) if res.get("type") == "delay" else 0.0)
        return float(nd), wait + _mean(spec.get("service_days")) + _mean(spec.get("report_days"))

    def value(self, view, o) -> float:
        loc, leads = view.attributes.get("location"), dict(view.option_leads or {})
        p, days = self._test(o, loc, leads)
        n = self.fc.nodes[o]
        fb = (n.retry or {}).get("fallback")
        p_diag = 1 - p
        if fb:
            # the rescue is booked later on the same list as the needle-biopsy option; use its current lead
            fb_test = self.fc.nodes[fb].test
            same = [x for x in leads if self.fc.nodes[x].test == fb_test]
            p2, d2 = self._test(same[0], loc, leads) if same else self._test(fb, loc, {})
            p_diag += p * (1 - p2)
            days += p * d2
        return p_diag - days / self.D

    def choose(self, view, options):
        v = {o: self.value(view, o) for o in options}
        best = max(options, key=lambda o: (v[o], -options.index(o)))
        return {o: float(o == best) for o in options}


def ev_ref(sc, fc, seed):
    return ExpectedValueRule(sc, fc)


def offer_table(res, rows_by_policy, policies) -> tuple[str, dict]:
    """Per (location, offered set): the most common pick of each policy (share)."""
    cells = defaultdict(lambda: defaultdict(Counter))
    for p in policies:
        for r in rows_by_policy[p]:
            if r["at_node"]:
                cells[(r["attrs"].get("location"), r["offered"])][p][r["pick"]] += 1
    out, L = {}, ["| location | offered | " + " | ".join(policies) + " |", "|---|---|" + "---|" * len(policies)]
    for (loc, off), byp in sorted(cells.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        rowd = {}
        for p in policies:
            c = byp[p]
            tot = sum(c.values())
            pick, n = c.most_common(1)[0] if tot else ("-", 0)
            rowd[p] = {"pick": pick, "share": round(n / tot, 3) if tot else None, "n": tot}
        out[f"{loc}|{'+'.join(off)}"] = rowd
        L.append(f"| {loc} | {'+'.join(off)} | " + " | ".join(
            f"{v['pick']} {100 * v['share']:.0f}%" if v["share"] is not None else "-" for v in rowd.values()) + " |")
    return "\n".join(L), out


def lead_table(rows_by_policy, policies, lead_option="ttnb1") -> tuple[str, dict]:
    """Set-dependent cell: central lesions with bronchoscopy AND EBUS on offer. Share choosing
    bronchoscopy by the needle-biopsy lead (a feature of a third option), plus agreement with
    the expected-value rule in that cell."""
    out = {}
    L = ["| Policy | " + " | ".join(f"bronch1 share, lead {a}-{'' if b > 1e8 else b} d" for a, b in LEAD_BUCKETS)
         + " | agreement with EV rule in the cell |", "|---|" + "---|" * (len(LEAD_BUCKETS) + 1)]
    for p in policies:
        cell = [r for r in rows_by_policy[p] if r["at_node"] and r["attrs"].get("location") == "central"
                and "bronch1" in r["offered"] and "ebus1" in r["offered"] and lead_option in r["leads"]]
        shares = []
        for a, b in LEAD_BUCKETS:
            sub = [r for r in cell if a <= r["leads"][lead_option] < b]
            shares.append((np.mean([r["pick"] == "bronch1" for r in sub]) if sub else None, len(sub)))
        agree = float(np.mean([r["pick"] == r["ref_picks"][EV] for r in cell])) if cell else None
        out[p] = {"bronch1_share_by_lead": [s for s, _ in shares], "n_by_lead": [n for _, n in shares],
                  "agreement_with_ev_in_cell": agree, "n_cell": len(cell)}
        L.append(f"| {p} | " + " | ".join("-" if s is None else f"{100 * s:.0f}% (n={n})" for s, n in shares)
                 + f" | {'-' if agree is None else f'{100 * agree:.0f}%'} (n={len(cell)}) |")
    return "\n".join(L), out


def run(flowchart, quick=False, log=print, out=ROOT / "runs" / "model_in_loop.json", model_seed=0,
        n_train=None, wd_grid=None, variants=None):
    kw = dict(n_train=1500, n_eval=1200, eval_seeds=(1,), epochs=30, wd_grid=(0.3,)) if quick else \
        dict(n_train=4000, n_eval=3000, eval_seeds=(1, 2, 3), epochs=40, wd_grid=(0.1, 0.3, 1.0))
    if n_train:
        kw["n_train"] = n_train
    if wd_grid:
        kw["wd_grid"] = tuple(wd_grid)
    if variants:
        kw["variants"] = variants
    res = run_experiment(SCEN, flowchart, "method", train_seeds=(1001,), refs={EV: ev_ref}, keep_rows=True,
                         log=log, model_seed=model_seed, **kw)
    rows = res["_rows"]
    pols = list(res["table"])
    t1, offer = offer_table(res, rows, pols)
    extra = "\n\nMost common pick by location and offered set (held-out runs):\n\n" + t1
    res["by_offer"] = offer
    if res["options_with_queue"]:
        t2, cell = lead_table(rows, pols)
        res["set_dependent_cell"] = cell
        extra += ("\n\nSet-dependent cell: central lesion, bronchoscopy and EBUS both on offer. Bronchoscopy's value "
                  "depends on the needle-biopsy lead (its rescue):\n\n" + t2)
    pairs = [("correction (2 layers)", "dot-product"),
             ("correction (2 layers) + queue lead", "dot-product + queue lead"),
             ("dot-product + queue lead + set summary", "dot-product + queue lead"),
             ("correction (2 layers) + queue lead", "dot-product + queue lead + set summary"),
             ("dot-product + set summary", "dot-product"), ("correction (2 layers)", "dot-product + set summary")]
    target = res["target_days"]
    paired = {}
    lines = ["| A | B | reward at node, A - B | on-time, A - B |", "|---|---|---|---|"]
    for a, b in pairs:
        if a in rows and b in rows:
            rd = _paired([r for r in rows[a] if r["at_node"]], [r for r in rows[b] if r["at_node"]], lambda r: r["reward"])
            od = _paired([r for r in rows[a] if r["cancer"]], [r for r in rows[b] if r["cancer"]],
                         lambda r: float(r["ttt"] is not None and r["ttt"] <= target))
            paired[f"{a} vs {b}"] = {"reward_diff": rd[0], "reward_diff_se": rd[1], "on_time_diff": od[0], "on_time_diff_se": od[1]}
            lines.append(f"| {a} | {b} | {rd[0]:+.3f} (s.e. {rd[1]:.3f}) | {100 * od[0]:+.1f} pp (s.e. {100 * od[1]:.1f}) |")
    res["paired_model_comparisons"] = paired
    extra += "\n\nPaired model comparisons (same held-out patients):\n\n" + "\n".join(lines)
    agree = {p: t.get(f"agreement_with {EV}") for p, t in res["table"].items()}
    res["agreement_with_ev_rule"] = agree
    extra += "\n\nAgreement with the expected-value rule (all decisions at the node): " + ", ".join(
        f"{p} {100 * a:.0f}%" for p, a in agree.items() if a is not None)
    if out is not None:
        save(res, Path(out), extra, "" if kw["n_train"] == 4000 or quick else f"@n_train={kw['n_train']}")
    return res, markdown(res) + extra


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--flowchart", nargs="+", default=["availability", "rescue_queue"])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--model-seed", type=int, default=0)
    ap.add_argument("--n-train", type=int, default=None, help="training patients (default 4000)")
    ap.add_argument("--weight-decay", type=float, nargs="+", default=None)
    ap.add_argument("--lead-variants-only", action="store_true",
                    help="train only the queue-lead variants (rescue_queue), to save time at large n")
    ap.add_argument("--out", default=str(ROOT / "runs" / "model_in_loop.json"))
    a = ap.parse_args(argv)
    for f in a.flowchart:
        variants = None
        if a.lead_variants_only:
            variants = [("dot-product + queue lead", "dot", "lead"), ("correction (2 layers) + queue lead", "corr", "lead"),
                        ("dot-product + queue lead + set summary", "dot", "lead+set")]
        _, md = run(f, a.quick, out=a.out, model_seed=a.model_seed, n_train=a.n_train, wd_grid=a.weight_decay,
                    variants=variants)
        print("\n" + md + "\n")


if __name__ == "__main__":
    main()
