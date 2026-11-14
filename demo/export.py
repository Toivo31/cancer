"""Build demo/data/demo_bundle.json from real simulator and optimiser runs.

    python demo/export.py                 # all scenarios that exist
    python demo/export.py --quick         # smaller cohorts, for a smoke test

Every number in the bundle comes from a run in this script; nothing is typed in by hand except
the published Stokstad figures (with their source). Metrics are reported on held-out cohorts
the optimiser never saw.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from optimiser import Config, search  # noqa: E402
from optimiser.edits import Edit, apply as apply_edit  # noqa: E402
from optimiser.search import cohorts, evaluate  # noqa: E402
from pathway_sim import load_scenario  # noqa: E402
from pathway_sim.scenario import Flowchart, Scenario  # noqa: E402

OUT = ROOT / "demo" / "data" / "demo_bundle.json"


# ---------------------------------------------------------------- display flowchart
def _preds(fc: Flowchart, nid: str) -> list[str]:
    n = fc.nodes[nid]
    ps = list(n.after) + list(n.after_any) + list(n.after_optional)
    for c in fc.nodes.values():
        if c.kind == "choice" and nid in c.options:
            ps.append(c.id)
    return ps


def _clean(label: str) -> str:
    return label.split(" (")[0].strip()


def display_flowchart(sc: Scenario, fc: Flowchart) -> dict:
    """Collapse logic nodes (choices, joins) into the steps a patient experiences.
    Display node id = test id (alternative timings of the same test merge into one step)."""
    disp_of = {}
    labels: dict[str, list[str]] = defaultdict(list)
    for n in fc.nodes.values():
        if n.test and sc.tests[n.test].get("kind", "test") != "treatment" or (n.kind == "exit"):
            did = n.test if n.kind != "exit" else n.id
            if n.test and sc.tests[n.test].get("kind") == "admin" and n.test == "baseline_ct":
                did = n.test
            disp_of[n.id] = did
            labels[did].append(n.label or n.id.replace("_", " "))
    memo: dict[str, dict] = {}

    def nearest(nid: str) -> dict:
        """display predecessor -> True if reached only through optional prerequisites."""
        if nid in memo:
            return memo[nid]
        memo[nid] = {}
        n = fc.nodes[nid]
        out: dict[str, bool] = {}
        for p in _preds(fc, nid):
            opt = p in n.after_optional
            sub = {disp_of[p]: False} if p in disp_of else nearest(p)
            for d, o in sub.items():
                out[d] = out.get(d, True) and (o or opt)
        memo[nid] = out
        return out

    edges: dict[str, dict] = defaultdict(dict)
    for nid, did in disp_of.items():
        for p, opt in nearest(nid).items():
            if p != did:
                edges[did][p] = edges[did].get(p, True) and opt

    def reach(a: str, seen=None) -> set:
        """ancestors through required edges only (an optional step never makes another redundant)."""
        seen = seen if seen is not None else set()
        for p, opt in edges.get(a, {}).items():
            if not opt and p not in seen:
                seen.add(p)
                reach(p, seen)
        return seen

    nodes = []
    for did in dict.fromkeys(disp_of.values()):
        prs = edges.get(did, {})
        reduced = [p for p in prs if not any(p in reach(q) for q, o in prs.items() if q != p and not o)]
        any_node = next(n for n in fc.nodes.values() if disp_of.get(n.id) == did)
        stage = sc.stage_of(any_node)
        node = {"id": did, "label": min(labels[did], key=len), "stage": stage}
        if reduced:
            node["after"] = sorted(reduced)
        if any_node.kind == "exit":
            node["kind"] = "exit"
        nodes.append(node)
    return {"id": fc.id, "nodes": nodes}


def rekey_nodes(m: dict, sc: Scenario, fc: Flowchart) -> dict:
    """node_breakdown keyed by display node (test id), summing alternative timings."""
    m = dict(m)
    for key in ("node_breakdown", "node_breakdown_all"):
        agg: dict[str, dict] = {}
        for nid, v in (m.get(key) or {}).items():
            did = v.get("test") or nid
            a = agg.setdefault(did, {"wait": 0.0, "service": 0.0, "n": 0, "stage": v.get("stage")})
            a["wait"] = round(a["wait"] + v["wait"], 2)
            a["service"] = round(a["service"] + v["service"], 2)
            a["n"] += v["n"]
        m[key] = agg
    return m


# ---------------------------------------------------------------- assumptions table
def short_cite(s: dict) -> str:
    c = s.get("citation", s["id"])
    first = c.split(",")[0].split(" ")[0].strip(".")
    if "," in c and first and first[0].isupper() and len(first) > 2 and " et al" in c:
        return f"{first} et al. {s.get('year', '')}".strip()
    return c.split(".")[0][:70]


def fmt_fraction(val) -> str:
    """0.0035 -> '0.35%', 0.013 -> '1.3%', 0.4 -> '40%' (integer rounding showed small risks as 0% or 1%)."""
    if not isinstance(val, (int, float)):
        return str(val)
    pct = 100 * val
    if pct == 0 or abs(pct) >= 10:
        return f"{round(pct)}%"
    return f"{pct:.2g}%"


def assumptions() -> list[dict]:
    src = {}
    raw = yaml.safe_load((ROOT / "params" / "sources.yaml").read_text())
    items = raw.get("sources", raw) if isinstance(raw, dict) else raw
    for s in items:
        src[s["id"]] = s
    rows = []
    for f in sorted((ROOT / "params").glob("*.yaml")):
        if f.name == "sources.yaml":
            continue
        data = yaml.safe_load(f.read_text()) or {}
        for section, params in data.items():
            if not isinstance(params, dict):
                continue
            for name, p in params.items():
                if not isinstance(p, dict) or "source" not in p:
                    continue
                val = p.get("value")
                unit = p.get("unit", "")
                s = src.get(p["source"])
                rows.append({
                    "parameter": name.replace("_", " "),
                    "value": f"{val} {unit}".strip() if unit not in ("fraction",) else fmt_fraction(val),
                    "source": short_cite(s) if s else "Our assumption",
                    "url": s.get("url") if s else None,
                    "status": "assumption" if p["source"] == "assumption" else "sourced",
                    "file": f"params/{f.name}",
                })
    return rows



# ---------------------------------------------------------------- plain-language change labels
# Hand-written wording for the changes the search is known to find; anything else falls back to a
# generator built from the edit kind and the step labels. The raw optimiser text is kept as "raw".
POLISHED = {
    ("relax", "book_treat", "mdt"): "Reserve the treatment slot when the case is sent to the tumour board, not after the board has met",
    ("relax", "spec_visit", "triage"): "Book the specialist visit as soon as the referral arrives, not after it has been handled",
    ("standardise", "first_contact", "gp_visit"): "Book a GP appointment, not a nurse, at first contact",
    ("standardise", "first_contact", "nurse_visit"): "Book a nurse appointment, not a GP, at first contact",
    ("fast_track", "triage", None): "Fast lane: once the hospital has handled a referral, give that patient priority in every later queue",
    ("detach", "diagnosis", "sampling_done"): "Hold the tumour board without waiting for tissue sampling to finish; sampling runs alongside while treatment is booked",
    ("standardise", "pet_timing", "pet_on_time"): "Always order the PET-CT scan at triage or the first visit, never late",
    ("standardise", "ex_timing", "ex_early"): "Always order the exercise test early, together with the other tests",
    # relax(sample_plan, visit): sample_plan inherits the visit's prerequisite (the baseline CT at referral
    # receipt), so sampling is planned when the referral is triaged, BEFORE the first visit (D18).
    ("relax", "sample_plan", "visit"): "Plan tissue sampling when the referral is triaged, before the first hospital visit",
}


def _lab(fc: Flowchart, nid: str) -> str:
    n = fc.nodes[nid]
    return _clean(n.label or nid.replace("_", " "))


def polish_change(fc: Flowchart, kind: str, target: str, other: str | None) -> str:
    if (kind, target, other) in POLISHED:
        return POLISHED[(kind, target, other)]
    if kind == "fast_track":
        return f"Fast lane: patients who have completed {_lab(fc, target).lower()} get priority in every later queue"
    if kind == "standardise":
        return f"At \u201c{_lab(fc, target)}\u201d always choose \u201c{_lab(fc, other).lower()}\u201d"
    a = _lab(fc, other.split("/")[-1] if other else target).lower() if other else ""
    x = _lab(fc, target)
    if kind == "detach":
        return f"{x}: no longer waits for {a}; it runs alongside and treatment still waits for it"
    if kind == "relax":
        return f"Order {x.lower()} at the same time as {a}, not after it"
    return kind


def _pp(x):
    return None if x is None else round(100 * x)


def why_text(step: dict) -> dict:
    """The evidence for one accepted change, in plain words (numbers come from the search record)."""
    ev = step.get("evidence") or {}
    d = ev.get("predicted_days_saved")
    kind = step["kind"]
    if ev.get("records_reading"):
        read = ev["records_reading"] + "."
    elif kind in ("detach", "relax"):
        read = f"In the clinic records, patients waited on average {d} days for this step while it held back on an earlier one" if d else ""
    else:
        read = f"The clinic records point to about {d} days of average waiting at this point" if d else ""
    b, a = ev.get("train_on_time_before"), ev.get("train_on_time_after")
    rerun = ""
    if b is not None and a is not None:
        rerun = (f"Rerunning the same patients confirmed it: treated on time {_pp(b)}% to {_pp(a)}%, median "
                 f"{round(ev['train_median_before'])} to {round(ev['train_median_after'])} days.")
    return {"records_said": read, "rerun_said": rerun}


def step_details(sc: Scenario, fc0: Flowchart, res: dict, cum: list[dict]) -> list[dict]:
    out = []
    for i, st in enumerate(res["steps"]):
        ev = st.get("evidence") or {}
        out.append({
            "label": polish_change(fc0, st["kind"], st["target"], st["other"]),
            "raw": st["plain"], "kind": st["kind"],
            **why_text(st),
            "predicted_days_saved": ev.get("predicted_days_saved"),
            "train_on_time_before": ev.get("train_on_time_before"), "train_on_time_after": ev.get("train_on_time_after"),
            "train_median_before": ev.get("train_median_before"), "train_median_after": ev.get("train_median_after"),
            "heldout_on_time_after": cum[i + 1]["share"] if i + 1 < len(cum) else None,
        })
    return out


def cumulative_view(sc: Scenario, fc0: Flowchart, res: dict, held, start_label: str, lead_rows=None) -> list[dict]:
    """Held-out metrics after 0, 1, 2 ... accepted changes (steps applied one by one, same cohorts)."""
    def row(step, label, m, kind):
        return {"step": step, "label": label, "kind": kind, "share": m["share_within_target"],
                "median_days": m["median_days_to_treatment"], "missed_cancers": m["missed_cancers"],
                "tests_per_patient": m["tests_per_patient"]}
    steps = res["steps"]
    rows = list(lead_rows or [])
    rows.append(row(0, start_label, res["heldout"]["before"], "start"))
    cur = fc0.copy(f"{fc0.id}_optimised")
    for i, st in enumerate(steps):
        cur = apply_edit(sc, cur, Edit(st["kind"], st["target"], st["other"]))
        if cur is None:
            raise RuntimeError(f"step {i + 1} no longer applies: {st['plain']}")
        last = i == len(steps) - 1
        m = res["heldout"]["after"] if last else metrics_on(sc, cur, held)
        rows.append(row(i + 1, polish_change(fc0, st["kind"], st["target"], st["other"]), m, "change"))
    return rows


def optimiser_view(sc, fc0, res, held, start_label, lead_rows=None) -> dict:
    cum = cumulative_view(sc, fc0, res, held, start_label, lead_rows)
    core = [r for r in cum if r["kind"] != "lead"]
    cfg = res["config"]
    n_held = (cfg.get("n_heldout") or cfg["n_train"])
    return {**{k: res[k] for k in ("steps", "selection_optimism_pp", "candidates_evaluated", "guardrails_heldout") if k in res},
            "details": step_details(sc, fc0, res, core), "cumulative": cum,
            "n_train": cfg["n_train"], "n_heldout": n_held, "heldout_cohorts": len(cfg["heldout_seeds"])}


def sensitivity_rows(scenario_id: str):
    """Optional tornado data from docs/sensitivity_<scenario id>.json (see demo/README.md)."""
    f = ROOT / "docs" / f"sensitivity_{scenario_id}.json"
    if not f.exists():
        return None
    try:
        raw = json.loads(f.read_text())
    except ValueError:
        return None
    rows = raw if isinstance(raw, list) else raw.get("rows") or (raw.get("scenarios") or {}).get(scenario_id)
    tor = raw.get("tornado") if isinstance(raw, dict) else None
    if not rows and tor and tor.get("rows"):
        # pathway_sim.sensitivity output: pick the reordering comparison and reshape to tornado rows
        pair = {"stokstad": "observed>optimal", "finland_lung": "baseline>bundled_workup"}.get(scenario_id) \
            or next(iter(tor.get("pairs", {})), None)
        if not pair:
            return None
        a, b = pair.split(">")
        out = []
        for r in tor["rows"]:
            x = r.get(pair)
            if not x:
                continue
            out.append({"parameter": r["label"], "low_gain_pp": x["gain_pp_low"], "high_gain_pp": x["gain_pp_high"],
                        "base_gain_pp": x["gain_pp_base"], "swing_pp": x["swing_pp"], "comparison": f"{b} vs {a}",
                        "low": r.get("low"), "high": r.get("high")})
        out.sort(key=lambda r: -(r["swing_pp"] or 0))
        rows = out[:10]
    return rows or None


# ---------------------------------------------------------------- scenarios
def metrics_on(sc, fc, held):
    m, _ = evaluate(sc, fc, held)
    return m


def build_stokstad(quick: bool) -> dict:
    sc = load_scenario(ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml")
    n = 300 if quick else 1000
    cfg = Config(n_train=n, heldout_seeds=(201, 202, 203), n_heldout=n)
    held = cohorts(sc, cfg.heldout_seeds, n)
    obs, fpet, opt = (sc.flowcharts[k] for k in ("observed", "faster_pet", "optimal"))
    m_obs0 = metrics_on(sc, obs, held)
    res_fast = search(sc, "faster_pet", cfg, log=lambda *a: None)
    res_noeq = search(sc, "observed", cfg, log=lambda *a: None)
    m_fpet = metrics_on(sc, fpet, held)
    m_opt = metrics_on(sc, opt, held)
    lead = [{"step": -1, "label": "Observed pathway", "kind": "lead", "share": m_obs0["share_within_target"],
             "median_days": m_obs0["median_days_to_treatment"], "missed_cancers": m_obs0["missed_cancers"],
             "tests_per_patient": m_obs0["tests_per_patient"]}]
    view_fast = optimiser_view(sc, fpet, res_fast, held, "Faster PET-CT scanner", lead)
    view_noeq = optimiser_view(sc, obs, res_noeq, held, "Observed pathway")
    from pathway_sim.scenario import parse_flowchart
    after_fast = parse_flowchart("suggested", res_fast["flowchart_after"])
    from pathway_sim.scenario import validate_flowchart
    validate_flowchart(sc, after_fast)
    m_obs = rekey_nodes(m_obs0, sc, obs)
    pub = sc.raw["published"]
    return {
        "id": "stokstad",
        "title": "Norwegian check: does the model reproduce a real hospital?",
        "description": "100 early-stage lung cancer patients at one Norwegian centre (Stokstad et al. 2019), rebuilt step by step. "
                       "Calibrated on the observed pathway only; everything else is a prediction.",
        "target_days": sc.target_days,
        "baseline": {"label": "Observed pathway", "metrics": m_obs},
        "variants": [
            {"label": "Suggested change (found without seeing the authors' answer)",
             "metrics": rekey_nodes(res_fast["heldout"]["after"], sc, after_fast),
             "changes": ["Use the faster PET-CT scanner (the same assumption the authors made)"] + [d["label"] for d in view_fast["details"]],
             "role": "optimiser"},
            {"label": "Faster PET-CT scan only", "metrics": rekey_nodes(m_fpet, sc, fpet), "role": "faster_pet"},
            {"label": "Authors' reordered pathway, simulated", "metrics": rekey_nodes(m_opt, sc, opt), "role": "authors_pathway"},
            {"label": "Suggested change without any new equipment",
             "metrics": rekey_nodes(res_noeq["heldout"]["after"], sc, obs),
             "changes": [d["label"] for d in view_noeq["details"]], "changes_detail": [d["raw"] for d in view_noeq["details"]], "role": "optimiser_no_new_equipment"},
        ],
        "published": {"baseline_share": pub["observed"]["share_within_target"],
                      "faster_pet_share": pub["faster_pet"]["share_within_target"],
                      "optimal_share": pub["optimal"]["share_within_target"],
                      "source": "Stokstad et al. 2019, BMC Health Services Research"},
        "flowchart_before": display_flowchart(sc, obs),
        "flowchart_after": display_flowchart(sc, after_fast),
        "optimiser": view_fast,
        "optimiser_no_new_equipment": view_noeq,
        "capacity_vs_order": {
            "title": "Faster scanner or better order?",
            "capacity_label": "New equipment: the faster PET-CT scanner alone",
            "rows": [
                {"kind": "today", "label": "Observed pathway", "share": m_obs0["share_within_target"], "median_days": m_obs0["median_days_to_treatment"]},
                {"kind": "capacity", "label": "Faster PET-CT scanner only (7-day wait)", "share": m_fpet["share_within_target"], "median_days": m_fpet["median_days_to_treatment"]},
                {"kind": "order", "label": "Reordered steps, no new equipment", "share": res_noeq["heldout"]["after"]["share_within_target"], "median_days": res_noeq["heldout"]["after"]["median_days_to_treatment"]},
                {"kind": "both", "label": "Reordered steps and the faster scanner", "share": res_fast["heldout"]["after"]["share_within_target"], "median_days": res_fast["heldout"]["after"]["median_days_to_treatment"]},
            ],
        },
        "headline_no_new_equipment": {"share": res_noeq["heldout"]["after"]["share_within_target"],
                                      "median_days": res_noeq["heldout"]["after"]["median_days_to_treatment"]},
        **({"sensitivity": sens} if (sens := sensitivity_rows("stokstad")) else {}),
    }


NICE_RESOURCE = {"pet_scanner": "PET-CT scanner", "ct_scanner": "CT scanner", "ttnb_slot": "Needle biopsy slots",
                 "bronchoscopy": "Bronchoscopy", "nurse_appt": "Nurse appointments", "gp_appt": "GP appointments",
                 "xray": "Chest X-ray", "clinic": "Specialist clinic", "treatment_slot": "Treatment slots"}


def nice_resource(rid: str, fallback: str) -> str:
    return NICE_RESOURCE.get(rid, fallback.capitalize())


def capacity_probe(sc: Scenario, fc: Flowchart, held, base: dict) -> list[dict]:
    """One more slot per day at each capacity-limited step: which helps most? (open question 4)"""
    rows = []
    for rid, r in sc.resources.items():
        if r.get("type", "server") != "server":
            continue
        new = fc.copy(fc.id)
        new.resource_overrides = {**new.resource_overrides, rid: {"capacity_per_day": int(r["capacity_per_day"]) + 1}}
        m = metrics_on(sc, new, held)
        rows.append({"resource": rid, "label": nice_resource(rid, r.get("label", rid.replace("_", " "))),
                     "capacity_per_day": r["capacity_per_day"],
                     "delta_share_pp": round(100 * (m["share_within_target"] - base["share_within_target"]), 1),
                     "delta_median_days": round(m["median_days_to_treatment"] - base["median_days_to_treatment"], 1),
                     "utilisation": base["utilisation"].get(rid)})
    return sorted(rows, key=lambda x: -x["delta_share_pp"])



def suggested_change_label(res: dict) -> str:
    """Bar label for the optimiser's result in the capacity-vs-order chart, from the kinds of change it accepted."""
    kinds = {st["kind"] for st in res.get("steps", [])}
    reorder = bool(kinds & {"detach", "relax", "standardise"})
    fast = "fast_track" in kinds
    what = ("new order and a fast lane" if reorder and fast else "new order" if reorder
            else "a fast lane (priority booking), same order" if fast else "no change accepted")
    return f"Suggested change: {what}, no new capacity"


def capacity_vs_order(sc: Scenario, fc0: Flowchart, base: dict, probe: list[dict], hand: dict, res: dict) -> dict | None:
    """Same patients: one more slot at the busiest step, a large capacity increase, and the suggested reorder."""
    ctl = sc.flowcharts.get("baseline_plus_capacity")
    if not probe or ctl is None or "baseline_plus_capacity" not in hand:
        return None
    top = probe[0]
    big = hand["baseline_plus_capacity"]
    ov = ctl.resource_overrides or {}
    parts = []
    for rid, o in ov.items():
        lab = nice_resource(rid, sc.resources.get(rid, {}).get("label", rid.replace("_", " ")))
        parts.append(f"{lab} {o.get('capacity_per_day')} a day (from {sc.resources[rid]['capacity_per_day']})")
    h = res["heldout"]["after"]
    b = base
    return {
        "title": "More capacity or a better order?",
        "rows": [
            {"kind": "today", "label": "Today", "share": b["share_within_target"], "median_days": b["median_days_to_treatment"]},
            {"kind": "capacity", "label": f"One more appointment a day at the busiest step ({top['label'].replace(' appointments', '')}, from {top['capacity_per_day']} to {top['capacity_per_day'] + 1})",
             "share": round(b["share_within_target"] + top["delta_share_pp"] / 100, 4),
             "median_days": round(b["median_days_to_treatment"] + top["delta_median_days"], 1)},
            {"kind": "capacity", "label": "A large capacity increase, same order: " + "; ".join(parts),
             "share": big["share_within_target"], "median_days": big["median_days_to_treatment"]},
            {"kind": "order", "label": suggested_change_label(res),
             "share": h["share_within_target"], "median_days": h["median_days_to_treatment"]},
        ],
    }


FINLAND_SUMMARY = ("Synthetic patients with chest symptoms in one large Finnish county, followed from first contact in primary care (nurse or GP) to the start of treatment. Time to treatment is counted against a provisional 90-day target.")


def urgent_booking_conditional(sc: Scenario, fc0: Flowchart, held) -> dict | None:
    """Conditional finding: every referred patient booked with the urgent lead. The gain depends entirely on
    the assumed urgent booking leads, so it is shown with 0 / 50 / 100% of the lead reduction applied."""
    node = (sc.raw.get("optimiser") or {}).get("urgent_booking_node", "triage")
    if node not in fc0.nodes:
        return None
    servers = {rid: r for rid, r in sc.resources.items()
               if r.get("type", "server") == "server" and "urgent_lead_days" in r}
    rows = []
    for frac in (0.0, 0.5, 1.0):
        fc = fc0.copy(f"urgent_{int(100 * frac)}")
        for rid, r in servers.items():
            lead = float(r.get("min_lead_days", 1.0)) - frac * (float(r.get("min_lead_days", 1.0)) - float(r["urgent_lead_days"]))
            fc.resource_overrides = {**fc.resource_overrides, rid: {"min_lead_days": lead}}
        m = metrics_on(sc, fc, held)
        rows.append({"share_of_lead_reduction": frac, "share_within_target": m["share_within_target"],
                     "median_days_to_treatment": m["median_days_to_treatment"], "missed_cancers": m["missed_cancers"]})
    full = fc0.copy("urgent_booking")
    full.nodes[node].fast_track = True
    m = metrics_on(sc, full, held)
    return {"label": "Urgent booking for every referred patient (depends on assumed urgent booking times)",
            "metrics": rekey_nodes(m, sc, full), "role": "conditional_urgent_booking",
            "conditional": rows,
            "note": "Gives every referred patient the urgent booking lead at specialist, CT, sampling, PET-CT and "
                    "treatment. Nobody is crowded out because everyone downstream is urgent; the gain is exactly the "
                    "assumed lead reduction (0% of it: no gain). Needs real booking-lead data before it is a recommendation."}


def build_capacity_scenario(path: Path, quick: bool, start: str = "baseline", compare: list[str] | None = None) -> dict:
    sc = load_scenario(path)
    n = int(sc.raw.get("default_n", 2000))
    n = max(300, n // 3) if quick else n
    cfg = Config(n_train=n, heldout_seeds=(301, 302) if not quick else (301,), n_heldout=n,
                 allow=("detach", "relax", "standardise"), max_steps=6)
    # fast_track is excluded from the headline search: applied to every referred patient it only swaps
    # each booking lead for the assumed urgent lead (review B1). It is reported below as a conditional finding.
    held = cohorts(sc, cfg.heldout_seeds, n)
    fc0 = sc.flowcharts[start]
    res = search(sc, start, cfg, log=lambda *a: None)
    from pathway_sim.scenario import parse_flowchart, validate_flowchart
    after = parse_flowchart("suggested", res["flowchart_after"])
    validate_flowchart(sc, after)
    base = metrics_on(sc, fc0, held)
    view = optimiser_view(sc, fc0, res, held, "Today's pathway")
    variants = [{"label": "Suggested change", "metrics": rekey_nodes(res["heldout"]["after"], sc, after),
                 "changes": [d["label"] for d in view["details"]] or ["No change passed the safety checks"], "role": "optimiser"}]
    hand = {}
    for fid in compare or [k for k in sc.flowcharts if k != start]:
        fc = sc.flowcharts[fid]
        mm = metrics_on(sc, fc, held)
        hand[fid] = mm
        variants.append({"label": fc.description or fid.replace("_", " "), "metrics": rekey_nodes(mm, sc, fc),
                         "role": "hand_written", "flowchart_id": fid})
    urgent = urgent_booking_conditional(sc, fc0, held)
    if urgent:
        variants.append(urgent)
    probe = capacity_probe(sc, fc0, held, base)
    cvo = capacity_vs_order(sc, fc0, base, probe, hand, res)
    return {
        "id": sc.id, "title": sc.raw.get("title", "Finnish lung pathway (synthetic)"),
        "description": sc.description, "summary": FINLAND_SUMMARY, "target_days": sc.target_days,
        "baseline": {"label": "Today's pathway", "metrics": rekey_nodes(base, sc, fc0)},
        "variants": variants,
        "flowchart_before": display_flowchart(sc, fc0), "flowchart_after": display_flowchart(sc, after),
        "optimiser": view,
        "capacity_probe": probe,
        **({"capacity_vs_order": cvo} if cvo else {}),
        **({"sensitivity": sens} if (sens := sensitivity_rows(sc.id)) else {}),
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    scenarios = []
    print("stokstad ...", flush=True)
    scenarios.append(build_stokstad(a.quick))
    fi = ROOT / "scenarios" / "finland_lung.yaml"
    if fi.exists():
        print("finland_lung ...", flush=True)
        scenarios.append(build_capacity_scenario(fi, a.quick))
    bundle = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "fixture": False, "scenarios": scenarios, "assumptions": assumptions()}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(bundle, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
