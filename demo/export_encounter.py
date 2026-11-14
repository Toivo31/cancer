"""Export the data for the offline encounter-loop page (demo/encounter.html).

    python demo/export_encounter.py                 # runs scenarios/finland_encounter.yaml, writes demo/data/encounter_bundle.js
    python demo/export_encounter.py --n 2000 --sample 200 --out /tmp/x.js

The scenario files are read at run time (world, care model, catalogue, decision tables), so whatever another
lane has tuned is what the page shows. Nothing about the loop is hard-coded here except the drawing layout:
the graph nodes come from the care model (roles, order/treat/refer/discharge actions, test groups) and from the
hospital flowchart of the world; the edges and their thickness are counted from what the simulated patients did.

``encounter_bundle.js`` is a plain script (``window.ENC_DATA = ...``) so the page opens from file:// with no server.
It has a default part (everything the page shows by default: record lines, paths, counts, results tables) and a
``truth`` part (hidden conditions, whether a treatment matched them, teaching captions) that the page reads only
after the viewer switches on "reveal truth (teaching view)". tests/test_demo_encounter.py checks the split.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from patient_engine.record_text import render  # noqa: E402
from pathway_sim.encounter import load_world, outcomes, run_encounter  # noqa: E402

SCENARIO = ROOT / "scenarios" / "finland_encounter.yaml"
OUT = ROOT / "demo" / "data" / "encounter_bundle.js"

W, H = 1040, 640            # logical drawing size used by the page
NODE_W, NODE_H = 108, 40
TOP = 74                    # room above the top row for piles of dots

# path state codes (page): 0 waiting, 1 being served / under way, 2 at home between episodes, 3 ended
WAIT, SERVED, HOME, END = 0, 1, 2, 3

IMAGING = {"xray", "ct_scanner", "mri", "pet_scanner"}
LAB = {"lab", "pathology", "mycobacteriology"}

END_NODES = [
    ("end_resolved", "Left, symptoms gone", "left_resolved"),
    ("end_symptoms", "Left, symptoms persist", "left_with_symptoms"),
    ("end_horizon", "Still in primary care at 1 year", "undiagnosed_at_horizon"),
]

ROLE_SHORT = {"nurse": "Nurse", "gp": "GP", "specialist": "Specialist"}


# ============================================================================ the graph

def classify_tests(world) -> dict[str, str]:
    """test id -> group id, for the tests that primary care can order."""
    cat, care = world.catalogue, world.care
    role_res = {r.resource for r in care.roles.values() if r.resource}
    out = {}
    for a in care.actions.values():
        if a.kind != "order" or a.test not in cat.tests:
            continue
        t = cat.tests[a.test]
        rk = t.resource_kind or ""
        if any((o.measures or "").startswith("dx_") for o in t.outputs):
            g = "tg_definitive"
        elif rk in role_res or "poc" in rk:
            g = "tg_inline"
        elif rk in LAB:
            g = "tg_lab"
        elif rk in IMAGING:
            g = "tg_imaging"
        else:
            g = "tg_function"
        out[a.test] = g
    return out


TEST_GROUPS = [
    ("tg_inline", "In-visit test", "Done during the visit"),
    ("tg_lab", "Lab test", "Blood tests and cultures"),
    ("tg_imaging", "Imaging", "X-ray and CT"),
    ("tg_function", "Function test", "Spirometry, echo and similar"),
    ("tg_definitive", "Definitive test", "A test that settles one diagnosis"),
]


def action_target(world, test_group: dict[str, str]) -> dict[str, tuple[str, int]]:
    """action id -> (node id the patient goes to after it, state)."""
    out = {}
    for a in world.care.actions.values():
        if a.kind == "order":
            out[a.id] = (test_group.get(a.test, "tg_function"), SERVED)
        elif a.kind == "book":
            out[a.id] = (a.role, WAIT)
        elif a.kind == "follow_up":
            out[a.id] = (None, WAIT)               # stays with the same role
    return out                                    # treat, refer and discharge have their own record entries


def hospital_layers(fcdef: dict) -> list[list[dict]]:
    """Kept hospital nodes (tested steps and the treatment exit) grouped by depth in the flowchart."""
    nodes = {n["id"]: n for n in fcdef["nodes"]}
    memo: dict[str, int] = {}

    def depth(i: str) -> int:
        if i in memo:
            return memo[i]
        memo[i] = 0
        n = nodes[i]
        deps = list(n.get("after", [])) + list(n.get("after_optional", []))
        memo[i] = 1 + max([depth(d) for d in deps if d in nodes], default=-1)
        return memo[i]

    kept = [n for n in fcdef["nodes"]
            if (n["kind"] == "step" and n.get("test")) or (n["kind"] == "exit" and n.get("outcome") == "treatment")]
    layers: dict[int, list[dict]] = {}
    for n in kept:
        layers.setdefault(depth(n["id"]), []).append(n)
    return [layers[k] for k in sorted(layers)]


def build_nodes(world, fcdef: dict, test_group: dict[str, str]) -> list[dict]:
    care = world.care
    nodes: list[dict] = []

    def add(i, label, kind, x, y, **kw):
        nodes.append({"id": i, "label": label, "kind": kind, "x": x, "y": y + TOP, **kw})

    add("first", "First contact", "start", 70, 196)
    roles = list(care.roles.values())
    for i, r in enumerate(roles):
        add(r.id, ROLE_SHORT.get(r.id, r.label), "role", 225 + 150 * i, 80 + 116 * i, long=r.label)
    present = [g for g in TEST_GROUPS if g[0] in set(test_group.values())]
    labels_of = {g[0]: sorted(world.catalogue.tests[t].label for t, gid in test_group.items() if gid == g[0]) for g in present}
    for i, (gid, lab, sub) in enumerate(present):
        add(gid, lab, "test", 600, 28 + 56 * i, long=sub, tests=labels_of[gid])
    if any(a.kind == "treat" for a in care.actions.values()):
        add("treat_pc", "Treatment started", "treat", 600, 330, long="Antibiotics, inhaler, reflux or heart treatment started in primary care")
    add("referral", "Referral to hospital", "referral", 790, 120)
    add("discharge", "Discharge", "rest", 600, 454, long="Sent home, with or without advice to come back")
    for i, (nid, lab, _) in enumerate(END_NODES):
        add(nid, lab, "end", 250 + 160 * i, 540)
    layers = hospital_layers(fcdef)
    for li, layer in enumerate(layers):
        for k, n in enumerate(layer):
            span = (len(layer) - 1) * 116
            x = 925 - span / 2 + 116 * k
            kind = "end" if n["kind"] == "exit" else "hosp"
            add("h_" + n["id"], n.get("label", n["id"]), kind, x, 28 + 62 * li, long=n.get("label", ""), hospital=True)
    return nodes


# ============================================================================ paths

def build_path(pr, world, idx: dict[str, int], tgt: dict, hosp_ids: set[str]) -> list[list]:
    """[[t, node index, state], ...] in days since first contact, from the record and the hospital events."""
    rec = pr.record
    a0 = pr.patient.arrival
    pts: list[tuple[float, str, int]] = []
    ents = [e for e in rec.entries if e.kind != "assessment"]

    def next_role(i: int) -> str | None:
        for e in ents[i + 1:]:
            if e.kind == "encounter" and e.role:
                return e.role
        return None

    first_role = next_role(-1)
    pts.append((0.0, "first", WAIT))
    if first_role:
        pts.append((0.001, first_role, WAIT))
    for i, e in enumerate(ents):
        t = float(e.t_days)
        if e.kind == "encounter":
            pts.append((t, e.role, SERVED))
            if e.action in tgt:
                node, st = tgt[e.action]
                pts.append((t + 0.01, node or e.role, st))
        elif e.kind == "result":
            pts.append((t, e.role, WAIT))
        elif e.kind == "treatment":
            pts.append((t, "treat_pc", SERVED))
        elif e.kind == "referral":
            pts.append((t, "referral", WAIT))
        elif e.kind == "discharge":
            pts.append((t, "discharge", HOME))
        elif e.kind == "return":
            pts.append((t, "first", WAIT))
            r = next_role(i)
            if r:
                pts.append((t + 0.001, r, WAIT))
    hev = [ev for ev in pr.events if ev.node in hosp_ids]
    crit = [ev for ev in hev if getattr(ev, "critical", False)]
    for ev in sorted(crit if (crit and pr.exit_node) else hev, key=lambda v: v.t_ready):
        pts.append((ev.t_ready - a0, "h_" + ev.node, WAIT))
        pts.append((ev.t_start - a0, "h_" + ev.node, SERVED))
    t_exit = None if pr.t_exit is None else pr.t_exit - a0
    if t_exit is not None:
        end = {"treatment": "h_treat", "left_resolved": "end_resolved", "left_with_symptoms": "end_symptoms",
               "undiagnosed_at_horizon": "end_horizon"}.get(pr.outcome)
        if end and end in idx:
            pts.append((max(t_exit, max((p[0] for p in pts), default=0.0) + 0.01), end, END))
    pts.sort(key=lambda p: p[0])
    out: list[list] = []
    for t, n, s in pts:
        if n not in idx:
            continue
        if out and out[-1][1] == idx[n] and out[-1][2] == s:
            continue
        out.append([round(t, 2), idx[n], s])
    return out


# ============================================================================ choosing patients to show

def stats(pr, a0_events=None) -> dict:
    rec = pr.record
    ents = rec.entries
    t_ref = None if pr.t_referral is None else pr.t_referral - pr.patient.arrival
    t_tx = None if pr.t_treatment is None else pr.t_treatment - pr.patient.arrival
    pc_tx = [x for x in pr.treatments]
    hosp = [ev for ev in pr.events]
    return {"n_ent": len(ents), "ep": pr.episode, "t_ref": t_ref, "t_tx": t_tx, "n_tx": len(pc_tx), "n_hosp": len(hosp),
            "tests": len(pr.tests_ordered), "enc": sum(pr.by_role.values()),
            "urgent": any(e.action == "refer_urgent" for e in ents),
            "t_end": 0.0 if pr.t_exit is None else pr.t_exit - pr.patient.arrival,
            "first_tx": min([x["t"] for x in pc_tx], default=None)}


def pick_examples(log) -> list[dict]:
    """Interesting patients, chosen from the whole run by what happened to them. Each: key, id, default label
    (what the record shows) and teaching label (what the hidden truth adds)."""
    P = [(pr, stats(pr)) for pr in log.patients]
    chosen: dict[str, tuple] = {}
    used: set[int] = set()

    def take(key, cands, score):
        cands = [c for c in cands if c[0].patient.id not in used]
        if not cands:
            return
        best = max(cands, key=score)
        chosen[key] = best
        used.add(best[0].patient.id)

    cancers = [c for c in P if c[0].patient.cancer]
    treated = [c for c in cancers if c[0].outcome == "treatment"]
    # a cancer first treated as an infection, then referred and treated: the typical delay
    inf = [c for c in treated if c[1]["first_tx"] is not None and c[1]["t_ref"] is not None
           and c[1]["first_tx"] < c[1]["t_ref"] and c[1]["n_ent"] <= 60]
    inf = [c for c in inf if not any(x["matched"] for x in c[0].treatments)] or inf   # treatment helped nothing, if possible
    if inf:
        inf.sort(key=lambda c: c[1]["t_tx"])
        take("cancer_as_infection", [inf[len(inf) // 2]], lambda c: 0)
    # the quickest correct route to treatment (urgent referral, little primary care)
    quick = [c for c in treated if c[1]["urgent"]]
    take("quick_referral", quick or treated, lambda c: (-c[1]["t_tx"], -c[1]["enc"]))
    # the longest loop in the run that still reads on one screen
    take("long_loop", [c for c in P if c[1]["n_ent"] <= 80], lambda c: (c[1]["ep"], c[1]["t_end"]))
    # a worried-well patient investigated anyway
    ww = [c for c in P if c[0].primary_condition == "worried_well"]
    take("worried_well", ww, lambda c: (c[1]["tests"] + c[1]["enc"], -c[1]["n_ent"]))
    # a benign patient sent through hospital tests
    ben = [c for c in P if not c[0].patient.cancer and c[1]["n_hosp"] >= 2 and c[1]["n_ent"] <= 70]
    take("benign_over_investigated", ben, lambda c: (c[1]["n_hosp"], c[1]["tests"]))
    # a cancer that left primary care and never came back
    lost = [c for c in cancers if c[0].outcome in ("left_with_symptoms", "undiagnosed_at_horizon") and c[1]["n_ent"] <= 60]
    take("cancer_lost", lost, lambda c: (c[1]["enc"], c[1]["t_end"]))

    def d(x):
        return int(round(x))

    out = []
    for key, (pr, s) in chosen.items():
        if key == "cancer_as_infection":
            label = f"Antibiotics on day {d(s['first_tx'])}, referred day {d(s['t_ref'])}, in treatment day {d(s['t_tx'])}"
            teach = "A cancer first treated as an infection: treatment for the wrong thing, the referral came late"
        elif key == "quick_referral":
            label = f"Urgent referral on day {d(s['t_ref'])}, in treatment day {d(s['t_tx'])}"
            teach = "A quick, correct referral: cancer found and treated fast"
        elif key == "long_loop":
            label = f"{s['ep']} episodes over {d(s['t_end'])} days, {s['enc']} visits"
            teach = ("Long loop, and a cancer in the middle of it" if pr.patient.cancer
                     else "Long loop, no cancer: the system kept this patient circling")
        elif key == "worried_well":
            label = f"{s['enc']} visits and {s['tests']} tests, nothing found"
            teach = "A worried-well patient, with nothing wrong, who was investigated anyway"
        elif key == "benign_over_investigated":
            label = f"Referred, then {s['n_hosp']} hospital steps"
            teach = "A benign patient over-investigated: no cancer, but sent through hospital tests"
        else:
            label = f"Left primary care on day {d(s['t_end'])} and did not return"
            teach = "A cancer lost: the patient left with symptoms and the loop never caught it"
        out.append({"key": key, "id": pr.patient.id, "label": label, "teach": teach})
    return out


# ============================================================================ main

def compact(text: str) -> str:
    """record_text lists what was found and then repeats it as 'Structured history: ...' and 'Physical examination: ...'
    for the same visit; keep the first list only. Nothing else is changed."""
    return " · ".join(seg for seg in text.split(" · ") if not seg.startswith(("Structured history:", "Physical examination:")))


def band(age) -> str:
    a = int(age or 0)
    return "under 50" if a < 50 else "50-64" if a < 65 else "65-74" if a < 75 else "75+"


def median(xs):
    return round(statistics.median(xs), 2) if xs else None


def build(n: int | None, seed: int, sample: int, target_cancers: int, scenario: Path = SCENARIO, proposals: dict | None = None) -> dict:
    t0 = time.time()
    world = load_world(scenario)
    if n is None:
        prev = world.prevalence().get("lung_cancer") or 0.013
        n = int(math.ceil(target_cancers / max(prev, 1e-4) / 100.0) * 100)
    log = run_encounter(world, n, seed)
    run_s = time.time() - t0
    fcdef = log.flowchart_def
    test_group = classify_tests(world)
    tgt = action_target(world, test_group)
    nodes = build_nodes(world, fcdef, test_group)
    idx = {nd["id"]: i for i, nd in enumerate(nodes)}
    hosp_ids = {n_["id"][2:] for n_ in nodes if n_.get("hospital")}
    res = outcomes(log)

    # paths of everyone -> edges and node statistics
    paths = {pr.patient.id: build_path(pr, world, idx, tgt, hosp_ids) for pr in log.patients}
    edges: dict[tuple[int, int], dict] = {}
    visits = [0] * len(nodes)
    pats = [set() for _ in nodes]
    dwell: list[list[float]] = [[] for _ in nodes]
    for pid, path in paths.items():
        seen = set()
        for k, (t, ni, s) in enumerate(path):
            prev = path[k - 1][1] if k else None
            if prev is not None and prev != ni:
                e = edges.setdefault((prev, ni), {"trips": 0, "who": set()})
                e["trips"] += 1
                e["who"].add(pid)
                visits[ni] += 1
                # time at the node: until the next move to another node
                j = k + 1
                while j < len(path) and path[j][1] == ni:
                    j += 1
                if j < len(path):
                    dwell[ni].append(path[j][0] - t)
            elif k == 0:
                visits[ni] += 1
            pats[ni].add(pid)
            seen.add(ni)
    for i, nd in enumerate(nodes):
        nd["n"] = len(pats[i])
        nd["visits"] = visits[i]
        nd["dwell"] = median(dwell[i]) if nd["kind"] not in ("rest", "end", "start") else None
    edge_list = [{"id": f"{nodes[a]['id']}>{nodes[b]['id']}", "source": nodes[a]["id"], "target": nodes[b]["id"],
                  "n": len(v["who"]), "trips": v["trips"]} for (a, b), v in sorted(edges.items())]

    # who is drawn: the examples, up to 'target_cancers' cancers and a random sample of the others
    examples = pick_examples(log)
    rng = random.Random(seed * 1000 + 7)
    by_id = {pr.patient.id: pr for pr in log.patients}
    pick = [e["id"] for e in examples]
    pool_c = [pr.patient.id for pr in log.patients if pr.patient.cancer and pr.patient.id not in pick]
    pool_o = [pr.patient.id for pr in log.patients if not pr.patient.cancer and pr.patient.id not in pick]
    rng.shuffle(pool_c)
    rng.shuffle(pool_o)
    n_c = min(len(pool_c), max(0, min(target_cancers, sample // 5) - sum(1 for i in pick if by_id[i].patient.cancer)))
    pick += pool_c[:n_c]
    pick += pool_o[:max(0, sample - len(pick))]
    pick = sorted(set(pick))

    cat = world.catalogue
    treat_label = {k: v.label for k, v in world.care.treatments.items()}
    patients, truth = [], {}
    for pid in pick:
        pr = by_id[pid]
        rec = pr.record
        lines_txt = render(rec, cat, world.care)
        lines = [[round(float(e.t_days), 1), 1 if e.kind == "assessment" else 0, compact(txt), e.episode]
                 for e, txt in zip(rec.entries, lines_txt)]
        bg = rec.background
        patients.append({"id": pid,
                         "g": f"{band(bg.get('age'))} years, {'female' if bg.get('sex') == 'f' else 'male'}, "
                              f"{bg.get('smoking_status', '?')} smoker, {bg.get('region', '?')}",
                         "age": bg.get("age"), "out": pr.outcome, "ep": pr.episode,
                         "path": paths[pid], "lines": lines})
        if proposals and proposals.get(str(pid)):      # optional: decision model proposals, shown in a labelled panel slot
            patients[-1]["proposals"] = proposals[str(pid)]
        marks = {}
        for i, e in enumerate(rec.entries):
            if e.kind == "treatment":
                m = next((x for x in pr.treatments if abs(x["t"] - e.t_days) < 0.02 and x["id"] == (world.care.actions[e.action].treatment if e.action in world.care.actions else None)), None)
                if m is None:
                    m = next((x for x in pr.treatments if abs(x["t"] - e.t_days) < 0.02), None)
                if m is not None:
                    marks[i] = bool(m["matched"])
        truth[pid] = {"cancer": bool(pr.patient.cancer),
                      "conditions": [cat.conditions[c].label if c in cat.conditions else c for c in (pr.conditions or (pr.primary_condition,))],
                      "primary": pr.primary_condition,
                      "treatments": [{"label": treat_label.get(x["id"], x["id"]), "day": round(x["t"], 1), "matched": bool(x["matched"])} for x in pr.treatments],
                      "marks": marks}
    for e in examples:
        truth[e["id"]]["caption"] = e.pop("teach")
    truth["_run"] = {"treatments_matching_share": res["overall"].get("treatments_matching_share"),
                     "treatments_per_patient": res["overall"].get("treatments_per_patient")}

    n_c_total = sum(1 for pr in log.patients if pr.patient.cancer)
    # keep the matching share out of the default results table (it is a truth-side score)
    res_default = json.loads(json.dumps(res))
    for blk in [res_default["overall"]] + [v for g in res_default["by_group"].values() for v in g.values()]:
        blk.pop("treatments_matching_share", None)
        blk.pop("treatments_per_patient", None)

    return {
        "format": "encounter-bundle/1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scenario": world.id, "description": " ".join(str(world.raw.get("description", "")).split()),
        "seed": seed, "n": n, "n_cancer": n_c_total, "target_days": world.target_days,
        "run_seconds": round(run_s, 1),
        "size": {"w": W, "h": H, "node_w": NODE_W, "node_h": NODE_H},
        "nodes": nodes, "edges": edge_list,
        "patients": patients, "examples": examples,
        "results": res_default,
        "truth": truth,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="patients (default: enough for about --cancers cancers)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sample", type=int, default=320, help="patients drawn as moving dots")
    ap.add_argument("--cancers", type=int, default=50, help="cancers to expect in the run, and at most this many drawn")
    ap.add_argument("--scenario", default=str(SCENARIO))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--proposals", default=None, help="JSON {patient id: [{decision_point, options[{id,label,score}], proposed, chosen, delivery}]}")
    a = ap.parse_args(argv)
    t0 = time.time()
    b = build(a.n, a.seed, a.sample, a.cancers, Path(a.scenario), json.loads(Path(a.proposals).read_text()) if a.proposals else None)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = "window.ENC_DATA = " + json.dumps(b, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";\n"
    out.write_text(text, encoding="utf-8")
    print(f"run {b['run_seconds']} s ({b['n']} patients, {b['n_cancer']} cancers), export {time.time() - t0:.1f} s total; "
          f"wrote {out} ({len(text) / 1e6:.2f} MB), {len(b['patients'])} patients drawn")
    for e in b["examples"]:
        print(f"  example {e['key']:<26} patient {e['id']:>5}: {e['label']}")


if __name__ == "__main__":
    main()
