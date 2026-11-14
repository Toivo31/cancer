"""Export the JEV-decided simulator run for the simulator page (demo/flow.html): demo/data/flow_jev_bundle.js.

    python demo/export_jev_flow.py                                   # newest model run under runs/jev_sim/
    python demo/export_jev_flow.py --run runs/jev_sim/<file>.json    # another recorded run
    python demo/export_jev_flow.py --placeholder                     # no run recorded yet: the page says how to make one

No model calls: the run file (written by ``python -m pathway_sim.jev_run``) holds every probability the model
returned; the exporter re-simulates the same patients with those probabilities (:class:`RecordedPolicy`) and
refuses if the replay asks a question the run did not record or picks differently. The rule-table run of the
same patients is simulated alongside. A run whose answers did not come from the model (``--backend mock``) is
refused unless ``--allow-mock``; the page then labels it as a mock in every place it shows it.

flow_jev_bundle.js is a plain script (``window.FLOW_JEV_DATA = ...``) loaded after flow_bundle.js; demo/export_flow.py
and flow_bundle.js are not touched.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pathway_sim import simulate  # noqa: E402
from pathway_sim.flow import build_flow  # noqa: E402
from pathway_sim.jev_run import SCENARIOS, load, select_patients  # noqa: E402

DATA = ROOT / "demo" / "data"
OUT = DATA / "flow_jev_bundle.js"
DEFAULT_RUN = ROOT / "runs" / "jev_sim" / "norway-observed-bridge-n30.json"
PAGE_ID = {"norway": "norway", "finland": "finland"}     # flow_bundle.js scenario ids
RUN_COMMAND = ["python -m decision_api.server", "python -m pathway_sim.jev_run", "python demo/export_jev_flow.py"]


class ReplayError(RuntimeError):
    pass


class RecordedPolicy:
    """The model's recorded probabilities, keyed by (patient, node); any other question is an error."""

    def __init__(self, decisions: list[dict], mode: str, backend_name: str, model_id: str | None):
        self.table = {(d["patient"], d["node"]): d for d in decisions}
        self.decision_mode, self.backend_name, self.model_id = mode, backend_name, model_id
        self.used: set = set()

    def choose(self, view, options):
        d = self.table.get((view.patient_id, view.node))
        if d is None:
            raise ReplayError(f"patient {view.patient_id} at {view.node}: not in the recorded run")
        if list(options) != list(d["offered"]):
            raise ReplayError(f"patient {view.patient_id} at {view.node}: offered {options}, recorded {d['offered']}")
        self.used.add((view.patient_id, view.node))
        return dict(d["jev_probs"])


def replay(run: dict):
    """``(scenario, flowchart, rule_log, jev_log)`` for the recorded run's patients; checks the replay."""
    p = run["provenance"]
    sc, fcid, seed = load(p["scenario_key"])
    if fcid != p["flowchart"] or seed != p["cohort_seed"]:
        raise ReplayError(f"run was {p['flowchart']}/seed {p['cohort_seed']}; this code has {fcid}/seed {seed}")
    fc = sc.flowcharts[fcid]
    pts = select_patients(sc, p["n_patients"], seed)
    if [x.id for x in pts] != p["patient_ids"]:
        raise ReplayError("the patients differ from the recorded run (scenario or patient generator changed)")
    ident = p.get("model_identity") or {}
    pol = RecordedPolicy(run["decisions"], p["decision_mode"], "birch", f"birch-{ident.get('step')}")
    jev_log = simulate(sc, fc, pts, policy=pol, seed=seed)
    picks = {(d["patient"], d["node"]): d["jev_pick"] for d in run["decisions"]}
    for pr in jev_log.patients:
        for c in pr.choices:
            if picks.get((pr.patient.id, c["node"])) != c["chosen"]:
                raise ReplayError(f"patient {pr.patient.id} at {c['node']}: replay chose {c['chosen']}, run recorded "
                                  f"{picks.get((pr.patient.id, c['node']))}")
    if len(pol.used) != len(picks):
        raise ReplayError(f"{len(picks) - len(pol.used)} recorded decisions were not reached in the replay")
    rule_log = simulate(sc, fc, pts, seed=seed)
    return sc, fc, rule_log, jev_log


def provenance_line(p: dict) -> str:
    ident = p.get("model_identity") or {}
    if not p.get("is_model"):
        return f"MOCK rehearsal, not the decision model ({ident.get('model') or 'mock'}); {p['n_patients']} patients"
    sha = (p.get("checkpoint_sha256") or "")[:12]
    return (f"Recorded run · checkpoint {p.get('checkpoint_step')}{' (' + sha + ')' if sha else ''} · "
            f"{p['recorded_at'][:10]} · {p['n_patients']} patients · {p['decision_mode']}")


def build(run: dict) -> dict:
    p = run["provenance"]
    sc, fc, rule_log, jev_log = replay(run)
    n = p["n_patients"]
    mock = not p.get("is_model")
    who = "a local mock (not the model)" if mock else f"the decision model, checkpoint {p.get('checkpoint_step')}"
    meta = {"jev": True, "mock": mock}
    rules = build_flow([rule_log], sc, fc, sample=n, seed=7, meta={"variant": "jev_rules", "label": "Rule tables", **meta})
    jev = build_flow([jev_log], sc, fc, sample=n, seed=7, meta={"variant": "jev", "label": "JEV decides", **meta})
    variants = [
        {"key": "jev_rules", "label": f"Rule tables, same {n} patients", "role": "jev_baseline", "conditional": False,
         "changes": [], "flow": rules,
         "note": f"Today's pathway; every choice made by the scenario's rule tables (observed practice mixes from the paper) for the {n} patients the model saw."},
        {"key": "jev", "label": f"JEV decides ({'MOCK' if mock else 'checkpoint ' + str(p.get('checkpoint_step'))}), {n} patients",
         "role": "jev", "conditional": False, "changes": [], "flow": jev,
         "note": f"Same pathway and patients; every choice with more than one option made by {who} (argmax of its scores), recorded {p['recorded_at'][:10]}."},
    ]
    return {"id": PAGE_ID[p["scenario_key"]], "status": "recorded", "mock": mock, "provenance": p,
            "provenance_line": provenance_line(p), "agreement": run["agreement"], "outcomes": run["outcomes"],
            "paired": run["paired"], "target_days": run["target_days"], "caveats": run["caveats"],
            "node_labels": {nid: (fc.nodes[nid].label or nid) for nid in fc.nodes},
            "default_pair": ["jev_rules", "jev"], "variants": variants}


def latest_model_run() -> Path | None:
    """The newest run file under runs/jev_sim/ whose answers came from the model (mock rehearsals are skipped)."""
    best = None
    for f in sorted((ROOT / "runs" / "jev_sim").glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        p = d.get("provenance") or {}
        if d.get("format") == "jev-sim-run/1" and p.get("is_model") and (best is None or p["recorded_at"] > best[0]):
            best = (p["recorded_at"], f)
    return best[1] if best else None


def bundle(scenarios: list[dict], status: str) -> dict:
    return {"format": "flow-jev-bundle/1", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "status": status, "how_to_record": RUN_COMMAND, "scenarios": scenarios}


def write(b: dict, out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.FLOW_JEV_DATA = " + json.dumps(b, separators=(",", ":")) + ";\n")
    print("wrote", out, f"{out.stat().st_size / 1e3:.0f} kB")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, action="append", help=f"recorded run file(s) (default {DEFAULT_RUN.relative_to(ROOT)})")
    ap.add_argument("--allow-mock", action="store_true", help="bundle a mock rehearsal (labelled MOCK on the page)")
    ap.add_argument("--placeholder", action="store_true", help="write a bundle that says no run is recorded yet")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.placeholder:
        write(bundle([], "not_recorded"), a.out)
        return 0
    runs = a.run or [latest_model_run() or DEFAULT_RUN]
    scs = []
    for f in runs:
        if not f.exists():
            raise SystemExit(f"{f} not found: record it first ({' ; '.join(RUN_COMMAND[:2])}), or write --placeholder")
        run = json.loads(f.read_text())
        if run.get("format") != "jev-sim-run/1":
            raise SystemExit(f"{f}: not a jev-sim-run/1 file")
        if not run["provenance"].get("is_model") and not a.allow_mock:
            raise SystemExit(f"{f}: answers are not from the model ({run['provenance'].get('model_identity')}); "
                             "pass --allow-mock only for a labelled rehearsal")
        s = build(run)
        print(f"  {s['id']}: {s['provenance_line']}; within target rules "
              f"{s['variants'][0]['flow']['metrics']['share_within_target']:.3f}, JEV {s['variants'][1]['flow']['metrics']['share_within_target']:.3f}")
        scs.append(s)
    write(bundle(scs, "recorded"), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
