#!/usr/bin/env python3
"""Fill every [[placeholder]] in docs/pitch/*.md from the real run outputs.

Reads
  demo/data/demo_bundle.json      simulation results (Norwegian check, Finnish scenario, parameter list)
  docs/validation_results.json    calibration run against Stokstad et al. 2019 (accepted parameter sets)
  docs/sensitivity_*.json         optional; keys are exposed as sens_<file>_<key> if present
  decision_model/README.md        benchmark tables (parsed, not retyped)

Writes filled copies to docs/pitch/filled/. Templates keep their [[placeholders]], so rerun this
after every new demo run:   python3 docs/pitch/fill_numbers.py

No simulation number is typed in the templates. Published literature numbers (Stokstad 40/48/80 etc.)
are read from the bundle's `published` block or the validation file, where they carry their source.
Placeholders that cannot be filled are printed, and left as they are in the filled copy.
Use --strict to exit non-zero if any remain. Use --list to print every value.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PITCH = ROOT / "docs" / "pitch"
OUT = PITCH / "filled"
PLACEHOLDER = re.compile(r"\[\[([a-z0-9_]+)\]\]")


# ---------------------------------------------------------------- formatting
def rhu(x: float, nd: int = 0) -> float:
    """Round half up (Python's round() is banker's rounding)."""
    f = 10 ** nd
    return int(x * f + (0.5 if x >= 0 else -0.5)) / f


def n0(x: float) -> str:
    return f"{rhu(x):.0f}"


def n1(x: float) -> str:
    return f"{rhu(x, 1):.1f}"


def n2(x: float) -> str:
    return f"{rhu(x, 2):.2f}"


def pc(x: float) -> str:  # share 0-1 -> "40"
    return n0(100 * x)


def pc1(x: float) -> str:
    return n1(100 * x)


def thousands(x: float) -> str:
    return f"{int(rhu(x)):,}".replace(",", " ")


def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


# ---------------------------------------------------------------- loading
def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def scenario(bundle: dict, sid: str) -> dict | None:
    return next((s for s in bundle["scenarios"] if s["id"] == sid), None)


def by_role(sc: dict, role: str) -> dict | None:
    return next((v for v in sc["variants"] if v.get("role") == role), None)


def by_flowchart(sc: dict, fid: str) -> dict | None:
    return next((v for v in sc["variants"] if v["metrics"]["flowchart"] == fid), None)


def group_stats(m: dict, g: str) -> dict:
    return m["by_group"][g]


def missed_share(m: dict) -> float:
    return m["missed_cancers"] / m["n_cancer"]


# ---------------------------------------------------------------- values
def stokstad_values(V: dict, bundle: dict, val: dict | None) -> None:
    s = scenario(bundle, "stokstad")
    if not s:
        return
    pub = s["published"]
    base = s["baseline"]["metrics"]
    fast = by_role(s, "faster_pet")["metrics"]
    auth = by_role(s, "authors_pathway")["metrics"]
    opt = by_role(s, "optimiser")
    noeq = by_role(s, "optimiser_no_new_equipment")
    V.update({
        "s_source": pub["source"],
        "s_target_days": n0(s["target_days"]),
        "s_pub_base": pc(pub["baseline_share"]),
        "s_pub_fast": pc(pub["faster_pet_share"]),
        "s_pub_opt": pc(pub["optimal_share"]),
        "s_obs_share": pc(base["share_within_target"]),
        "s_obs_median": n0(base["median_days_to_treatment"]),
        "s_fast_share": pc(fast["share_within_target"]),
        "s_fast_median": n0(fast["median_days_to_treatment"]),
        "s_auth_share": pc(auth["share_within_target"]),
        "s_auth_median": n0(auth["median_days_to_treatment"]),
        "s_opt_share": pc(opt["metrics"]["share_within_target"]),
        "s_opt_median": n0(opt["metrics"]["median_days_to_treatment"]),
        "s_noeq_share": pc(noeq["metrics"]["share_within_target"]),
        "s_noeq_median": n0(noeq["metrics"]["median_days_to_treatment"]),
        "s_n": thousands(base["n"]),
        "s_missed_max": n0(max(opt["metrics"]["missed_cancers"], noeq["metrics"]["missed_cancers"],
                               auth["missed_cancers"])),
        "s_fast_over_pp": n0(100 * (fast["share_within_target"] - pub["faster_pet_share"])),
        "s_tests_base": n2(base["tests_per_patient"]),
        "s_tests_auth": n2(auth["tests_per_patient"]),
        "s_tests_opt": n2(opt["metrics"]["tests_per_patient"]),
        "s_tests_noeq": n2(noeq["metrics"]["tests_per_patient"]),
    })
    # optimiser: steps, train vs held-out, optimism
    for tag, o in (("opt", opt), ("noeq", noeq)):
        steps = o["optimiser"]["steps"] if "optimiser" in o else None
    so = s["optimiser"]
    sn = s["optimiser_no_new_equipment"]
    V["s_opt_train"] = pc(so["steps"][-1]["evidence"]["train_on_time_after"])
    V["s_noeq_train"] = pc(sn["steps"][-1]["evidence"]["train_on_time_after"])
    V["s_opt_train_start"] = pc(so["steps"][0]["evidence"]["train_on_time_before"])
    V["s_noeq_train_start"] = pc(sn["steps"][0]["evidence"]["train_on_time_before"])
    V["s_opt_optimism_pp"] = n1(so["selection_optimism_pp"])
    V["s_noeq_optimism_pp"] = n1(sn["selection_optimism_pp"])
    V["s_candidates"] = n0(so["candidates_evaluated"])
    V["s_opt_nsteps"] = n0(len(so["steps"]))
    V["s_noeq_nsteps"] = n0(len(sn["steps"]))
    V["s_opt_changes"] = "\n".join(f"{i}. {c}" for i, c in enumerate(opt["changes"], 1))
    V["s_noeq_changes"] = "\n".join(f"{i}. {c}" for i, c in enumerate(noeq["changes_detail"], 1))
    st = base["stage_breakdown"]
    top = max(st, key=lambda k: st[k]["wait"])
    V["s_top_stage"] = top.replace("_", " ")
    V["s_top_stage_wait"] = n0(st[top]["wait"])

    if val:
        pp = val["published"]
        ps = val["prediction_summary"]
        V.update({
            "val_pub_base_ci": f"{pc(pp['observed']['ci95'][0])}-{pc(pp['observed']['ci95'][1])}",
            "val_pub_fast_ci": f"{pc(pp['faster_pet']['ci95'][0])}-{pc(pp['faster_pet']['ci95'][1])}",
            "val_pub_opt_ci": f"{pc(pp['optimal']['ci95'][0])}-{pc(pp['optimal']['ci95'][1])}",
            "val_pub_median": n1(pp["observed"]["median_days_to_treatment"]),
            "val_fast_min": pc(ps["faster_pet"]["share_min"]),
            "val_fast_med": pc(ps["faster_pet"]["share_median"]),
            "val_fast_max": pc(ps["faster_pet"]["share_max"]),
            "val_opt_min": pc(ps["optimal"]["share_min"]),
            "val_opt_med": pc(ps["optimal"]["share_median"]),
            "val_opt_max": pc(ps["optimal"]["share_max"]),
            "val_accepted": n0(val["accepted"]),
            "val_grid": n0(val["grid_points"]),
            "val_n": thousands(val["n"]),
            "val_target_share": pc(val["targets"]["share_within_target"][0]),
            "val_target_tol": pc(val["targets"]["share_within_target"][1]),
        })
        obs = [a["observed"]["share_within_target"] for a in val["accepted_sets"]]
        V["val_obs_min"], V["val_obs_max"] = pc(min(obs)), pc(max(obs))
        b = val["best"]
        r_sim = b["optimal"]["sampling_per_patient"] / b["observed"]["sampling_per_patient"]
        V["val_samp_obs"] = n2(b["observed"]["sampling_per_patient"])
        V["val_samp_opt"] = n2(b["optimal"]["sampling_per_patient"])
        V["val_samp_ratio"] = n2(r_sim)
        sp = pp["sampling_procedures"]
        V["val_samp_pub_obs"] = n0(sp["observed"])
        V["val_samp_pub_opt"] = n0(sp["optimal"])
        V["val_samp_pub_ratio"] = n2(sp["optimal"] / sp["observed"])

    # tables
    V["s_validation_table"] = md_table(
        ["Flowchart", "Published (Stokstad 2019)", "Our simulation (held-out)", "Verdict"],
        [["Observed pathway", f"{V['s_pub_base']}% within {V['s_target_days']} d", f"{V['s_obs_share']}% (fitted)", "fitted to this number"],
         ["Faster PET-CT only (7 d)", f"{V['s_pub_fast']}% (not significant)", f"{V['s_fast_share']}%",
          "we over-predict"],
         ["Authors' reordered pathway", f"{V['s_pub_opt']}%", f"{V['s_auth_share']}%", "predicted, not fitted: matches"]]
        if True else [])
    V["s_optimiser_table"] = md_table(
        ["Search starting point", "Share within 42 d, held-out", "Median days", "Missed cancers"],
        [["Observed pathway (no change)", f"{V['s_obs_share']}%", V["s_obs_median"], "0"],
         ["Blind search, with the faster scanner (the authors' premise)", f"{V['s_opt_share']}%", V["s_opt_median"], V["s_missed_max"]],
         ["Blind search, no new equipment", f"{V['s_noeq_share']}%", V["s_noeq_median"], V["s_missed_max"]]])


def finland_values(V: dict, bundle: dict) -> None:
    f = scenario(bundle, "finland_lung")
    if not f:
        return
    base = f["baseline"]["metrics"]
    opt = by_role(f, "optimiser")["metrics"]
    direct = by_flowchart(f, "direct_ct")["metrics"]
    bundled = by_flowchart(f, "bundled_workup")["metrics"]
    fast = by_flowchart(f, "fast_track_nonspecific")["metrics"]
    capctl = by_flowchart(f, "baseline_plus_capacity")["metrics"]
    so = f["optimiser"]
    sh = lambda m: m["share_within_target"]  # noqa: E731
    V.update({
        "f_target": n0(f["target_days"]),
        "f_n": thousands(base["n"]),
        "f_cancers": thousands(base["n_cancer"]),
        "f_prevalence": n1(100 * base["n_cancer"] / base["n"]),
        "f_share_base": pc(sh(base)),
        "f_share_opt": pc(sh(opt)),
        "f_share_gain_pp": n0(100 * (sh(opt) - sh(base))),
        "f_median_base": n0(base["median_days_to_treatment"]),
        "f_median_opt": n0(opt["median_days_to_treatment"]),
        "f_median_gain": n0(base["median_days_to_treatment"] - opt["median_days_to_treatment"]),
        "f_missed_base": n1(base["missed_cancers"]),
        "f_missed_opt": n1(opt["missed_cancers"]),
        "f_missed_pct_base": pc1(missed_share(base)),
        "f_missed_pct_opt": pc1(missed_share(opt)),
        "f_tests_base": n2(base["tests_per_patient"]),
        "f_tests_opt": n2(opt["tests_per_patient"]),
        "f_cost_base": n0(base["cost_per_patient"]),
        "f_cost_opt": n0(opt["cost_per_patient"]),
        "f_noncancer_base": n1(base["median_days_to_exit_noncancer"]),
        "f_noncancer_opt": n1(opt["median_days_to_exit_noncancer"]),
        "f_train_base": pc(so["steps"][0]["evidence"]["train_on_time_before"]),
        "f_train_opt": pc(so["steps"][-1]["evidence"]["train_on_time_after"]),
        "f_optimism_pp": n1(so["selection_optimism_pp"]),
        "f_candidates": n0(so["candidates_evaluated"]),
        "f_changes": "; ".join(by_role(f, "optimiser")["changes"]),
        "f_n_changes": {1: "One step", 2: "Two steps", 3: "Three steps"}.get(len(by_role(f, "optimiser")["changes"]),
                                                                              f"{len(by_role(f, 'optimiser')['changes'])} steps"),
        "f_direct_share": pc(sh(direct)), "f_direct_median": n0(direct["median_days_to_treatment"]),
        "f_bundle_share": pc(sh(bundled)), "f_bundle_median": n0(bundled["median_days_to_treatment"]),
        "f_fast_share": pc(sh(fast)), "f_fast_median": n0(fast["median_days_to_treatment"]),
        "f_capctl_share": pc(sh(capctl)), "f_capctl_median": n0(capctl["median_days_to_treatment"]),
        "f_bundle_gain_pp": n0(100 * (sh(bundled) - sh(base))),
        "f_capctl_gain_pp": n0(100 * (sh(capctl) - sh(base))),
        "f_order_only_pp": n0(100 * (sh(bundled) - sh(capctl))),
        "f_direct_gain_pp": n0(100 * (sh(direct) - sh(base))),
        "f_fast_gain_pp": n0(100 * (sh(fast) - sh(base))),
    })

    # where time is lost
    st = base["stage_breakdown"]
    for k, short in (("detection", "detection"), ("referral", "referral"), ("diagnosis", "diagnosis"),
                     ("treatment_start", "treatment")):
        V[f"f_wait_{short}"] = n0(st[k]["wait"])
        V[f"f_svc_{short}"] = n0(st[k]["service"])
    tot_wait = sum(x["wait"] for x in st.values())
    tot_svc = sum(x["service"] for x in st.values())
    V["f_wait_share"] = n0(100 * tot_wait / (tot_wait + tot_svc))
    V["f_wait_total"] = n0(tot_wait)
    V["f_svc_total"] = n0(tot_svc)
    top = max(st, key=lambda k: st[k]["wait"])
    V["f_top_stage"] = top.replace("_", " ")
    V["f_top_stage_wait"] = n0(st[top]["wait"])
    labels = {n["id"]: n.get("label", n["id"]) for n in f["flowchart_before"]["nodes"]}
    nodes = sorted(base["node_breakdown"].items(), key=lambda kv: -kv[1]["wait"])[:3]
    for i, (nid, x) in enumerate(nodes, 1):
        V[f"f_node{i}_name"] = labels.get(nid, nid).lower()
        V[f"f_node{i}_wait"] = n0(x["wait"])
    V["f_node_list"] = ", ".join(f"{V[f'f_node{i}_name']} ({V[f'f_node{i}_wait']} d)" for i in (1, 2, 3))

    # equity: presentation groups
    ns, ss = "non_specific", "site_specific"
    g = lambda m, k, key: group_stats(m, k)[key]  # noqa: E731
    gaps = {}
    for tag, m in (("base", base), ("opt", opt), ("direct", direct), ("bundle", bundled), ("fast", fast),
                   ("capctl", capctl)):
        V[f"f_ns_share_{tag}"] = pc(g(m, ns, "share_within_target"))
        V[f"f_ss_share_{tag}"] = pc(g(m, ss, "share_within_target"))
        V[f"f_ns_median_{tag}"] = n0(g(m, ns, "median_days_to_treatment"))
        V[f"f_ss_median_{tag}"] = n0(g(m, ss, "median_days_to_treatment"))
        gap_pp = 100 * (g(m, ss, "share_within_target") - g(m, ns, "share_within_target"))
        gap_d = g(m, ns, "median_days_to_treatment") - g(m, ss, "median_days_to_treatment")
        V[f"equity_gap_{tag}_pp"] = n1(gap_pp)
        V[f"f_gap_days_{tag}"] = n1(gap_d)
        gaps[tag] = (gap_pp, gap_d)
        V[f"f_ns_missed_pct_{tag}"] = pc1(g(m, ns, "missed_cancers") / g(m, ns, "n_cancer"))
        V[f"f_ss_missed_pct_{tag}"] = pc1(g(m, ss, "missed_cancers") / g(m, ss, "n_cancer"))
    # legacy names used by the earlier templates
    V["equity_gap_before_pp"] = V["equity_gap_base_pp"]
    V["equity_gap_after_pp"] = V["equity_gap_opt_pp"]
    V["f_gap_days_before"], V["f_gap_days_after"] = V["f_gap_days_base"], V["f_gap_days_opt"]
    V["f_ns_n_cancer"] = n0(g(base, ns, "n_cancer"))
    V["f_ss_n_cancer"] = n0(g(base, ss, "n_cancer"))
    V["f_ss_presenter_share"] = pc(g(base, ss, "n") / base["n"])
    V["f_ns_share_gain_pp"] = n0(100 * (g(opt, ns, "share_within_target") - g(base, ns, "share_within_target")))
    V["f_ss_share_gain_pp"] = n0(100 * (g(opt, ss, "share_within_target") - g(base, ss, "share_within_target")))
    V["f_gap_pp_widens"] = "widens" if gaps["opt"][0] > gaps["base"][0] else "narrows"
    V["f_gap_days_narrows"] = "narrows" if gaps["opt"][1] < gaps["base"][1] else "widens"

    # tables
    def row(label, m, kind):
        return [label, kind, f"{pc(sh(m))}%", n0(m["median_days_to_treatment"]), n1(m["missed_cancers"]),
                n2(m["tests_per_patient"])]

    V["f_variant_table"] = md_table(
        ["Flowchart (same patients)", "Origin", f"Treated within {V['f_target']} d", "Median days", "Missed cancers per cohort", "Tests per patient"],
        [row("Baseline", base, "starting point"),
         row("Suggested change (2 steps)", opt, "optimiser, held-out"),
         row("GPs order CT directly (needs 8 CT slots)", direct, "hand-written"),
         row("Order CT + PET-CT together, board before sampling (needs 3 PET slots)", bundled, "hand-written"),
         row("Fast lane for vague symptoms", fast, "hand-written"),
         row("Baseline order, same extra CT and PET capacity", capctl, "capacity-only control")])
    V["f_equity_table"] = md_table(
        ["Flowchart", "Vague (non-specific) symptoms: within target", "Alarm (site-specific) symptoms: within target",
         "Gap, pp", "Gap in median days"],
        [[lab, f"{V[f'f_ns_share_{t}']}%", f"{V[f'f_ss_share_{t}']}%", V[f"equity_gap_{t}_pp"], V[f"f_gap_days_{t}"]]
         for lab, t in (("Baseline", "base"), ("Suggested change", "opt"), ("GPs order CT directly", "direct"),
                        ("Order together", "bundle"), ("Fast lane for vague symptoms", "fast"),
                        ("Capacity-only control", "capctl"))])

    probe = f["capacity_probe"]
    V["f_cap_top_name"] = probe[0]["label"]
    V["f_cap_top_pp"] = n1(probe[0]["delta_share_pp"])
    V["f_cap_second_name"] = probe[1]["label"]
    V["f_cap_second_pp"] = n1(probe[1]["delta_share_pp"])
    V["f_cap_rest_max_pp"] = n1(max(p["delta_share_pp"] for p in probe[2:]))
    V["f_cap_n"] = n0(len(probe))
    V["f_cap_table"] = md_table(
        ["Resource", "Slots a day now", "Utilisation", f"Change in share within {V['f_target']} d with one more slot"],
        [[p["label"], n0(p["capacity_per_day"]), f"{pc(p['utilisation'])}%", f"{p['delta_share_pp']:+.1f} pp"]
         for p in probe])


def bundle_values(V: dict, bundle: dict) -> None:
    a = bundle["assumptions"]
    V["parameter_count"] = n0(len(a))
    V["assumption_count"] = n0(sum(1 for x in a if x["status"] == "assumption"))
    V["sourced_count"] = n0(sum(1 for x in a if x["status"] == "sourced"))
    V["bundle_date"] = bundle["generated_at"][:10]
    V["bundle_is_fixture"] = "illustrative fixture" if bundle.get("fixture") else "real run"


def decision_model_values(V: dict) -> None:
    p = ROOT / "decision_model" / "README.md"
    if not p.exists():
        return
    txt = p.read_text()
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in txt.splitlines() if ln.startswith("|")]
    acc = {}
    for r in rows:
        if len(r) == 5 and r[0].startswith(("comparison", "control")):
            acc[(r[0].split(" ")[0], r[1])] = (r[2], r[3], r[4])
    get = lambda task, prefix: next((v for (t, m), v in acc.items() if t == task and m.startswith(prefix)), None)  # noqa: E731
    dp, dpw, cm = get("comparison", "Dot-product (d"), get("comparison", "Dot-product, wider"), get("comparison", "Correction")
    cdp, ccm = get("control", "Dot-product"), get("control", "Correction")
    if dp and cm and dpw:
        V["dm_acc_dot"] = n1(100 * float(dp[1]))
        V["dm_acc_dot_wide"] = n1(100 * float(dpw[1]))
        V["dm_acc_corr"] = n1(100 * float(cm[1]))
        V["dm_gain_pp"] = n1(100 * (float(cm[1]) - float(dpw[1])))
        V["dm_params_dot_wide"] = dpw[0]
        V["dm_params_corr"] = cm[0]
    if cdp and ccm:
        V["dm_ctrl_dot"] = n1(100 * float(cdp[1]))
        V["dm_ctrl_corr"] = n1(100 * float(ccm[1]))
        V["dm_ctrl_gain_pp"] = n1(100 * (float(ccm[1]) - float(cdp[1])))
    ratios = []
    for r in rows:
        if len(r) == 6 and r[1] in ("default", "heavy (hidden 512)"):
            try:
                ratios.append((r[0], r[1], float(r[4])))
            except ValueError:
                pass
    dflt = [x[2] for x in ratios if x[1] == "default"]
    heavy = [x[2] for x in ratios if x[1].startswith("heavy") and x[0].startswith("Correction")]
    if dflt:
        V["dm_second_lo"], V["dm_second_hi"] = pc(min(dflt)), pc(max(dflt))
    if heavy:
        V["dm_second_heavy"] = n2(heavy[0])


def sensitivity_values(V: dict) -> None:
    for p in sorted(glob.glob(str(ROOT / "docs" / "sensitivity_*.json"))):
        d = load(Path(p))
        tag = Path(p).stem.replace("sensitivity_", "")
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (int, float, str)):
                    V[f"sens_{tag}_{k}"] = str(v)
    V["sens_files"] = ", ".join(Path(p).name for p in sorted(glob.glob(str(ROOT / "docs" / "sensitivity_*.json")))) or "none yet"


def build_values() -> dict:
    bundle = load(ROOT / "demo" / "data" / "demo_bundle.json")
    if bundle is None:
        sys.exit("demo/data/demo_bundle.json missing")
    val = load(ROOT / "docs" / "validation_results.json")
    V: dict[str, str] = {}
    bundle_values(V, bundle)
    stokstad_values(V, bundle, val)
    finland_values(V, bundle)
    decision_model_values(V)
    sensitivity_values(V)
    return V


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 if any placeholder is left unfilled")
    ap.add_argument("--list", action="store_true", help="print every value (single-line ones)")
    a = ap.parse_args()
    V = build_values()
    if a.list:
        for k in sorted(V):
            if "\n" not in V[k]:
                print(f"{k} = {V[k]}")
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()  # drop stale copies of renamed or deleted templates
    missing: dict[str, set[str]] = {}
    used: set[str] = set()
    n_files = 0
    for p in sorted(PITCH.glob("*.md")):
        text = p.read_text()

        def sub(mo, name=p.name):
            k = mo.group(1)
            used.add(k)
            if k in V:
                return V[k]
            missing.setdefault(k, set()).add(name)
            return mo.group(0)

        (OUT / p.name).write_text(PLACEHOLDER.sub(sub, text))
        n_files += 1
    print(f"filled {n_files} files into {OUT.relative_to(ROOT)}/ from bundle {V.get('bundle_date')} ({V.get('bundle_is_fixture')})")
    print(f"{len(used)} distinct placeholders used, {len(V)} values available")
    if missing:
        print("UNFILLED placeholders (no source value available):")
        for k, fs in sorted(missing.items()):
            print(f"  [[{k}]] in {', '.join(sorted(fs))}")
        return 1 if a.strict else 0
    print("all placeholders filled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
