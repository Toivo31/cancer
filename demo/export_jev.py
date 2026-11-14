#!/usr/bin/env python3
"""Build the data behind the JEV node page (demo/jev.html): window.JEV_DATA in demo/data/jev_bundle.js.

    python demo/export_jev.py                      # about 1 to 2 minutes (reruns the encounter loop once)
    python demo/export_jev.py --refresh-recorded origin/main
                                                   # copy the model owner's recorded outputs into demo/data/jev_recorded.json
    python demo/export_jev.py --record URL         # score every preset once on a live endpoint and keep the answers
                                                   # (URL like http://127.0.0.1:8771/api/decision; it costs GPU time)

What goes into the bundle, and where each part comes from:

* ``presets``: the example cards. Their context, question and answers are written here, except the default
  GP visit, which is a real decision point of the encounter loop: the export reruns the loop with the seed and
  size of demo/data/encounter_bundle.js, stops at the example patient "treated as an infection" at the GP visit
  where the placeholder table gave antibiotics, and builds the request with the same adapter code the simulator
  uses for the model (``jev.birch.BirchPolicy.request_for`` and ``map_request``). The placeholder table's
  numbers at that visit are stored next to it (they are what the simulator uses today, not the model).
* ``recorded``: answers of the deployed model that the model owner recorded (demo/data/jev_recorded.json, a copy
  of files under decision_api/web and decision_api/validation on the owner's branch). Only the reasoning preset has
  one. ``--record`` adds answers for the other presets in demo/data/jev_preset_outputs.json.
* ``model``: the facts on the model card, each with the file it comes from.

Nothing on the page is typed by hand in the HTML or JS: a missing file becomes null and the page says so.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "demo" / "data" / "jev_bundle.js"
RECORDED = ROOT / "demo" / "data" / "jev_recorded.json"
PRESET_OUTPUTS = ROOT / "demo" / "data" / "jev_preset_outputs.json"
ENCOUNTER_BUNDLE = ROOT / "demo" / "data" / "encounter_bundle.js"
SCENARIO = ROOT / "scenarios" / "finland_encounter.yaml"
EXAMPLE_KEY = "cancer_as_infection"
GATEWAY_MAX_CHOICES = 8          # decision_api/hosted.py: the public gateway refuses a question with more choices
NATIVE_MAX_CHOICES = 16          # decision_api/runtime/decision_model/inference_schema.py (Question.choices, Node.actions)
#: the eight GP actions offered in the live request (of the node's full list); every action the table gives weight to
#: at the chosen visit is kept, the rest are common next steps
GP_SUBSET = ["advice_return", "follow_up", "order_blood_count", "order_chest_xray", "order_chest_ct",
             "treat_antibiotics", "treat_inhaler", "refer_urgent"]

#: files the recorded part is copied from (``--refresh-recorded REF``)
OWNER_FILES = {
    "precomputed": "decision_api/web/precomputed.json",
    "reasoning": "decision_api/web/precomputed-reasoning.json",
    "validation": "decision_api/validation/step2350.json",
    "performance": "decision_api/validation/performance2350.json",
}


# ------------------------------------------------------------------------------------------------ recorded outputs

def refresh_recorded(ref: str) -> dict:
    """Copy the owner's recorded outputs (the parts the page uses) from git ``ref`` into jev_recorded.json."""
    def show(rel):
        return json.loads(subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT, check=True,
                                         capture_output=True, text=True).stdout)
    commit = subprocess.run(["git", "rev-parse", "--short", ref], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    pre, rea, val, perf = (show(OWNER_FILES[k]) for k in ("precomputed", "reasoning", "validation", "performance"))
    out = {
        "format": "jev-recorded/1",
        "copied_from": {"ref": ref, "commit": commit, "files": OWNER_FILES},
        "copied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Recorded by the model owner on the deployed checkpoint; copied unchanged (subset). Not live inference.",
        "pathway_plain": {"description": pre.get("description"), **pre["entries"]["pathway"]},
        "pathway_reasoning": rea,
        "validation": {"purpose": val.get("purpose"), "sanity": val.get("sanity"), "selection": val.get("selection"),
                       "gpu_preflight": {k: val["gpu_preflight"].get(k) for k in
                                         ("max_score_error", "shared_prefix", "decision_branch_restored", "generation_seconds")}},
        "performance": {"first_score_seconds": perf["measured"]["first_score"]["seconds"],
                        "cached_score_seconds": perf["measured"]["cached_score"]["seconds"]},
    }
    RECORDED.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ the GP visit

def encounter_bundle() -> dict | None:
    try:
        t = ENCOUNTER_BUNDLE.read_text(encoding="utf-8")
        return json.loads(t[t.index("{"):t.rindex("}") + 1])
    except (OSError, ValueError):
        return None


def capture_gp_visit(enc: dict) -> dict:
    """Rerun the encounter loop as demo/export_encounter.py did and capture the example patient's GP decision.

    The capture wraps the world's own decision tables and returns their answer unchanged, so the run is the same run
    (same world, size, seed, policy); the request for the model is only built, never sent."""
    from pathway_sim.encounter import load_world, run_encounter
    from jev.birch import BirchBackend, BirchPolicy, map_request

    ex = next((e for e in enc.get("examples", []) if e["key"] == EXAMPLE_KEY), None)
    if ex is None:
        raise SystemExit(f"the encounter bundle has no '{EXAMPLE_KEY}' example; run demo/export_encounter.py first")
    pid = ex["id"]
    pat = next(p for p in enc["patients"] if p["id"] == pid)
    # the GP visit at which the record shows antibiotics (the first primary-care treatment) in the bundle
    treat = next((l for l in pat["lines"] if "treatment (GP)" in l[2] and "antibiotic" in l[2].lower()), None)
    if treat is None:
        raise SystemExit("the example patient has no GP antibiotics line in the encounter bundle")
    t_visit = treat[0]

    world = load_world(SCENARIO)
    be = BirchBackend("http://127.0.0.1:9", max_calls=0, cache_dir=None, forbidden_values=frozenset(world.catalogue.conditions))
    bp = BirchPolicy(be, catalogue=world.catalogue, care=world.care)
    caught: list[dict] = []

    class Capture:
        backend_name = getattr(world.policy, "backend_name", "table")
        model_id = getattr(world.policy, "model_id", None)

        def choose(self, view, options):
            return self.choose_with_note(view, options)[0]

        def choose_with_note(self, view, options):
            r = world.policy.choose_with_note(view, options)
            if view.patient_id == pid and view.node == "gp_encounter" and abs(view.t_now - t_visit) < 0.06:
                req = bp.request_for(view, options)
                caught.append({"t": view.t_now, "payload": map_request(req), "table": dict(r[0]), "table_note": r[1],
                               "labels": {o["id"]: o.get("label") or o["id"] for o in req.options}})
            return r

    t0 = time.time()
    log = run_encounter(world, int(enc["n"]), int(enc["seed"]), policy=Capture())
    print(f"encounter loop rerun: {enc['n']} patients, seed {enc['seed']}, {time.time() - t0:.0f} s", flush=True)
    if not caught:
        raise SystemExit("the rerun did not reach the example's GP visit: the scenario changed after the encounter bundle "
                         "was written. Run demo/export_encounter.py, then this script.")
    c = caught[0]
    pr = next(p for p in log.patients if p.patient.id == pid)
    if c["table"].get("treat_antibiotics", 0) <= 0:
        raise SystemExit("captured visit does not offer antibiotics with weight; the run differs from the bundle")

    payload = c["payload"]
    node = payload["node_id"]
    full = payload["workflow"]["nodes"][node]["actions"]
    keep = [a for a in full if a["id"] in GP_SUBSET]
    missing = [k for k, v in c["table"].items() if v > 0 and k not in GP_SUBSET]
    if missing:
        raise SystemExit(f"the table gives weight to actions outside the offered subset: {missing}")
    live = json.loads(json.dumps(payload))
    live["workflow"]["nodes"] = {node: {**payload["workflow"]["nodes"][node], "actions": keep},
                                 **{a["next"]: {"terminal": True} for a in keep}}
    live["case"]["case_id"] = f"demo-jev-gp-visit-{pid}"
    # the text the model reads: the proxy's propose step joins case context, visible evidence and protocol like this
    # (decision_api/runtime/decision_model/inference_service.py DecisionService.propose and tree.node_request)
    vis = [e for e in live["case"]["evidence"] if e["available_at_step"] <= live["case"]["step"]]
    model_text = live["case"]["context"] + ("\nAvailable observations:\n" + "\n".join(f"[{e['source_id']}] {e['text']}" for e in vis) if vis else "") \
        + "\nProtocol for this node:\n" + live["workflow"]["nodes"][node]["protocol"]
    return {
        "patient_id": pid, "example_label": ex["label"], "t_days": round(c["t"], 1), "node": node,
        "group": pat.get("g"), "evidence": vis, "case_context": live["case"]["context"],
        "question": live["workflow"]["nodes"][node]["question"],
        "offered_all": [{"id": a["id"], "text": a["description"]} for a in full],
        "offered": [{"id": a["id"], "text": a["description"]} for a in keep],
        "table": {"probs": {k: v for k, v in c["table"].items() if v > 0}, "note": c["table_note"],
                  "drawn": "treat_antibiotics", "drawn_from": "encounter bundle record line: " + treat[2]},
        "request": live, "model_text": model_text,
        "link": f"encounter.html?p={pid}&paused&day={int(c['t'])}",
        "teach": {"primary": pr.primary_condition, "outcome": pr.outcome, "example": ex["label"]},
        "scenario": "scenarios/finland_encounter.yaml", "encounter_generated_at": enc.get("generated_at"),
    }


# ------------------------------------------------------------------------------------------------ the presets

def score_request(case_id: str, context: str, questions: list[dict]) -> dict:
    return {"context": context, "case_id": case_id, "questions": questions}


def presets(gp: dict | None, rec: dict | None) -> list[dict]:
    out = []
    # 1. the default: a basic GP visit, a real node of the encounter loop
    if gp:
        out.append({
            "key": "gp_visit", "default": True, "tag": "Simulator node",
            "title": "A GP visit: what next?",
            "pitch": "Symptoms and the record so far are the context; the next steps the simulator allows are the answers. "
                     "This is the call the encounter loop makes at every GP decision.",
            "source_of_text": "Built by the simulator's own adapter (jev.birch.BirchPolicy.request_for, map_request) from a synthetic patient's record",
            "route": "/pathway", "request": gp["request"], "gp": gp,
            "question_id": gp["node"], "questions": [{"id": gp["node"], "text": gp["question"], "choices": gp["offered"]}],
            "limits": ["Synthetic patient; the record lines are what the simulator wrote, not a real clinic note.",
                       "The simulator offers more actions at this node than the public demo endpoint accepts in one question; "
                       "this card offers a subset (all actions the placeholder table weighs, plus common next steps)."],
        })
    # 2. reasoning: the owner's recorded refinement run
    rr = rec and rec.get("pathway_reasoning")
    plain = rec and rec.get("pathway_plain")
    if rr and plain:
        req = plain["request"]
        node = req["workflow"]["nodes"][req["node_id"]]
        out.append({
            "key": "reasoning", "tag": "Reasoning and retrieval",
            "title": "Enrich the context before deciding",
            "pitch": "Before scoring, the frozen original language-model head may call read-only tools (here: the patient's "
                     "history) and write a short evidence summary. That text is added to the context; then the trained head "
                     "scores the same answers. A decision model that can look things up first.",
            "source_of_text": "The model owner's synthetic intake example (decision_api/web, recorded on the deployed checkpoint)",
            "route": "/reason",
            "request": {"example_id": "pathway", "reasoning": {
                "enabled": True, "max_tokens": (rr["refinement"].get("budget") or {}).get("max_tokens", 128),
                "max_rounds": 3, "max_tool_calls": 2,
                "additional_prompt": "Retrieve the available patient history, then give a quick evidence summary."}},
            "question_id": req["node_id"],
            "questions": [{"id": req["node_id"], "text": node["question"],
                           "choices": [{"id": a["id"], "text": a["description"]} for a in node["actions"]]}],
            "context_display": req["case"]["context"],
            "recorded": {"with_refinement": rr, "without_refinement": plain["decision"],
                         "without_recorded_at": plain.get("recorded_at"), "source": rec.get("copied_from")},
            "limits": ["The only tool in this deployment reads one bundled synthetic record (sim:demo-record); a custom case "
                       "gets text refinement without tools.",
                       "The generated summary is fallible text, not a source record; in the owner's checks it sometimes "
                       "recommends an action although told to summarise evidence only.",
                       "Retrieval from real databases (guidelines, registries, the patient's own record) is the intended "
                       "direction, not something this deployment does."],
        })
    # 3. triage
    out.append({
        "key": "triage", "tag": "Prioritisation",
        "title": "Triage: how urgent is this referral?",
        "pitch": "The same model, with priority classes as the answers. Sorting a queue by the score on the urgent class, "
                 "and sending the human-review class to a person, turns it into a prioritisation tool.",
        "source_of_text": "Written for this page (synthetic)",
        "route": "/score",
        "request": score_request("demo-jev-triage", (
            "Synthetic referral to the respiratory outpatient clinic, written by a GP. Patient 71, man, current smoker, "
            "about 45 pack-years. Cough for 7 weeks, worse lately, one episode of blood-streaked sputum last week. "
            "Lost 4 kg in two months without trying. Chest X-ray 5 days ago: 2.5 cm opacity in the right upper lobe, "
            "radiologist recommends CT. CRP 12 mg/L. No fever. Lives alone, independent."),
            [{"id": "priority", "text": "How urgently should the specialist clinic see this patient?",
              "choices": [{"id": "urgent", "text": "Urgent: see within days on a suspected-cancer pathway"},
                          {"id": "soon", "text": "Soon: see within a few weeks"},
                          {"id": "routine", "text": "Routine: normal waiting list"},
                          {"id": "human_review", "text": "Unclear from the referral: a clinician should review it before triage"}]}]),
        "limits": ["The score on 'urgent' is relative to these four classes, not a calibrated risk.",
                   "A triage rule built on it would need checking against outcomes before any use; every flag goes to a person."],
    })
    # 4. screening
    out.append({
        "key": "screening", "tag": "Screening existing records",
        "title": "Screening: does this record suggest a missed cancer?",
        "pitch": "Read old records in bulk and flag the few that deserve a second look. Cheap to run over a whole register, "
                 "and it targets the cases a busy GP can miss, because advanced cancer diagnostics is not their training.",
        "source_of_text": "Written for this page (synthetic)",
        "route": "/score",
        "request": score_request("demo-jev-screening", (
            "Synthetic primary-care record, three visits in five months. Woman, 63, former smoker (quit 8 years ago, "
            "30 pack-years). Visit 1: hoarse voice for 3 weeks, treated as a viral laryngitis. Visit 2: hoarseness persists, "
            "new dry cough; advised voice rest. Visit 3: tired, appetite poor, weight down from 68 to 64 kg; blood count "
            "normal, calcium 2.71 mmol/L (slightly high), not followed up. No chest imaging in the record."),
            [{"id": "flag", "text": "Should this record be flagged for a clinician to check for a possible undiagnosed cancer?",
              "choices": [{"id": "flag", "text": "Flag: the record suggests a possible cancer that has not been investigated"},
                          {"id": "no_flag", "text": "Do not flag: another explanation fits and nothing is left unexplained"},
                          {"id": "unclear", "text": "Not enough information in the record to say"}]}]),
        "limits": ["The output is the model's relative score on 'flag' among three answers. It is not the probability that "
                   "the patient has cancer: that needs calibration on records with known outcomes.",
                   "Not validated on any real records. In a real register, cancer is rare, so even a good flag rate means "
                   "many false alarms per true case; flags go to a person, never straight to the patient."],
    })
    # 5. comparison
    out.append({
        "key": "compare", "tag": "Answers compared with each other",
        "title": "Which answer is the largest, and the second largest?",
        "pitch": "Each answer is encoded on its own, but the scoring head lets the answers look at each other before they "
                 "are scored. So the model can answer questions about the set, such as 'which is the second largest', "
                 "that a scorer looking at one answer at a time cannot. Two questions share one context.",
        "source_of_text": "Written for this page (synthetic)",
        "route": "/score",
        "request": score_request("demo-jev-compare", (
            "Synthetic CT follow-up of one lung nodule. The radiology reports give its longest diameter on four scans. "
            "The candidate answers are those four measurements."),
            [{"id": "largest", "text": "Which of the candidate measurements is the largest?",
              "choices": [{"id": "a", "text": "Scan in January: 9 mm"}, {"id": "b", "text": "Scan in March: 14 mm"},
                          {"id": "c", "text": "Scan in June: 11 mm"}, {"id": "d", "text": "Scan in October: 8 mm"}]},
             {"id": "second", "text": "Which of the candidate measurements is the second largest?",
              "choices": [{"id": "a", "text": "Scan in January: 9 mm"}, {"id": "b", "text": "Scan in March: 14 mm"},
                          {"id": "c", "text": "Scan in June: 11 mm"}, {"id": "d", "text": "Scan in October: 8 mm"}]}]),
        "limits": ["Whether this checkpoint answers set questions correctly is an empirical question; the page shows the "
                   "answer of a live call, or says that there is none.",
                   "What is guaranteed by construction is the symmetry: no answer position enters the model, so reordering "
                   "the answers reorders the scores (up to rounding)."],
    })
    for p in out:
        if p.get("route") == "/score":
            p["questions"] = p["request"]["questions"]
            p["context_display"] = p["request"]["context"]
            assert all(len(q["choices"]) <= GATEWAY_MAX_CHOICES for q in p["questions"])
    return out


# ------------------------------------------------------------------------------------------------ model card facts

def model_card(rec: dict | None) -> dict:
    be = None
    if rec:
        be = (rec.get("pathway_plain") or {}).get("decision", {}).get("backend")
    v = (rec or {}).get("validation") or {}
    s = v.get("sanity") or {}
    perf = (rec or {}).get("performance") or {}
    src_rt = "decision_api/runtime/decision_model/"
    return {
        "backend": be,
        "adapt_last_n": 7,
        "head_layers_default": 2,
        "max_choices_native": NATIVE_MAX_CHOICES,
        "max_choices_gateway": GATEWAY_MAX_CHOICES,
        "max_questions_gateway": 4,
        "sanity": {"correct": s.get("new_correct"), "total": s.get("total"), "previous_correct": s.get("old_correct"),
                   "datasets": sorted({r.get("dataset") for r in s.get("records", []) if r.get("dataset")})} if s else None,
        "selection": v.get("selection"),
        "first_score_seconds": perf.get("first_score_seconds"),
        "sources": {
            "encoder": src_rt + "model.py, gemma.py, nemotron.py",
            "head": src_rt + "head.py (ValueHead, InteractionBlock)",
            "routing": src_rt + "tree.py, inference_service.py",
            "contract": src_rt + "inference_schema.py; gateway limits: decision_api/hosted.py (both on main, PR 6)",
            "refinement": "decision_api/REASONING_HANDOFF.md, decision_api/reasoning.py, decision_api/shared_generation.py",
            "checks": "decision_api/validation/README.md, step2350.json",
            "prototype": "decision_model/README.md (small numpy prototype of the comparison claim)",
        },
    }


# ------------------------------------------------------------------------------------------------ --record

def call(base: str, route: str, body: dict, timeout_s: float = 660.0) -> dict:
    """One explicit call; follows a 202 job by polling once a second. No retry of the POST."""
    def req(method, url, data=None):
        r = urllib.request.Request(url, method=method, data=None if data is None else json.dumps(data).encode(),
                                   headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=180) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    t0 = time.time()
    st, out = req("POST", base.rstrip("/") + route, body)
    while st == 202 and out.get("status_url"):
        if time.time() - t0 > timeout_s:
            raise TimeoutError("no answer in time; the job may still finish on the server")
        time.sleep(1.0)
        st, out = req("GET", base.rstrip("/") + out["status_url"])
    return out


def record_presets(base: str, items: list[dict], allow_non_model: bool) -> dict:
    old = read_json(PRESET_OUTPUTS) or {"format": "jev-preset-outputs/1", "outputs": {}}
    for p in items:
        if p["key"] == "reasoning" and not p.get("record_live"):
            continue                       # the owner's recording is used; rerun it from the page if wanted
        print(f"scoring {p['key']} on {base}{p['route']} ...", flush=True)
        try:
            out = call(base, p["route"], p["request"])
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"  failed: {e}; nothing stored for {p['key']}")
            continue
        dec = out.get("decision", out)
        mode = (dec.get("backend") or {}).get("mode")
        if mode != "model" and not allow_non_model:
            print(f"  backend mode is {mode!r}, not 'model': not stored (use --allow-non-model to keep it, labelled)")
            continue
        old["outputs"][p["key"]] = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "endpoint": base, "route": p["route"], "request": p["request"], "response": out}
        print(f"  stored ({mode})")
    PRESET_OUTPUTS.write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return old


# ------------------------------------------------------------------------------------------------ main

def build(skip_gp: bool = False) -> dict:
    rec = read_json(RECORDED)
    enc = encounter_bundle()
    gp = None
    if enc and not skip_gp:
        gp = capture_gp_visit(enc)
    items = presets(gp, rec)
    outs = (read_json(PRESET_OUTPUTS) or {}).get("outputs", {})
    for p in items:
        o = outs.get(p["key"])
        if o and o.get("request") == p["request"]:
            p["recorded_preset"] = o                # an answer recorded with --record for exactly this request
    return {"format": "jev-bundle/1", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "presets": items, "model": model_card(rec),
            "recorded_source": rec and {"copied_from": rec.get("copied_from"), "copied_at": rec.get("copied_at")}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--refresh-recorded", metavar="GIT_REF", help="copy the owner's recorded outputs from this git ref first")
    ap.add_argument("--record", metavar="API_BASE", help="score each preset once on this live endpoint (explicit GPU use)")
    ap.add_argument("--allow-non-model", action="store_true", help="with --record: also keep fixture/mock answers (labelled by their mode)")
    ap.add_argument("--skip-gp", action="store_true", help="leave out the encounter-loop GP visit (fast; for tests)")
    a = ap.parse_args(argv)
    if a.refresh_recorded:
        refresh_recorded(a.refresh_recorded)
    data = build(skip_gp=a.skip_gp)
    if a.record:
        record_presets(a.record, data["presets"], a.allow_non_model)
        data = build(skip_gp=a.skip_gp)
    Path(a.out).write_text("window.JEV_DATA = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(data['presets'])} presets"
          + ("" if any(p["key"] == "gp_visit" for p in data["presets"]) else " (no GP visit: encounter bundle missing or --skip-gp)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
