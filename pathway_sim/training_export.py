"""Training data for the JEV from simulated patients (WP-W4-4).

``python -m pathway_sim export-training scenarios/finland_encounter.yaml --flowchart encounter --n 20000 \\
    --seeds 1,2,3 --explore 0.3 --out runs/training/v1.jsonl.gz``

One JSON line per decision the encounter loop takes. ``request`` is produced by the live JEV path
(``jev.adapter.BackendPolicy.request_for`` -> ``build_context`` -> ``jev.record_context``), from the patient's
record only (I1). ``label`` and ``outcome`` are the hidden side and sit outside ``request``. Format and
cautions: ``docs/platform/jev-training-data.md``.

No hook in the engine is needed: a wrapper policy passed to ``run_encounter(policy=...)`` sees every
``PatientView`` the engine builds, delegates the choice to the world's decision tables (or draws uniformly when
exploring) and keeps the request; the chosen action and the outcome are read from the finished run.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from .dists import uniform

FORMAT = "jev_training/1"
SPLITS = (("train", 0.8), ("val", 0.1), ("test", 0.1))


class _NoBackend:
    """Stands in for the JEV when only requests are built (BackendPolicy needs ``info()``)."""

    def info(self):
        from jev.contract import BackendInfo
        return BackendInfo(name="export", model="export")


class CapturingPolicy:
    """Delegates to ``inner`` (the world's decision tables), optionally explores, keeps every request."""

    backend_name = "table"
    decision_mode = "sample"

    def __init__(self, inner, world, seed: int, explore: float = 0.0):
        from jev.adapter import BackendPolicy
        self.inner, self.seed, self.explore = inner, seed, float(explore)
        self.model_id = getattr(inner, "model_id", "table")
        self._req = BackendPolicy(_NoBackend(), mode="sample", scenario=world.scenario, flowchart=world.flowchart)
        self.captured: dict[int, list] = {}          # cohort index -> [(node, request json, offered, probs, tag)]
        self._n: Counter = Counter()

    def choose_with_note(self, view, options):
        req = self._req.request_for(view, list(options))          # the live path's request builder
        k = self._n[view.patient_id]
        self._n[view.patient_id] += 1
        if self.explore > 0 and uniform(self.seed, view.patient_id, "explore", k) < self.explore:
            probs = {o: 1.0 / len(options) for o in options}
            out, tag = (probs, None, {"plan": "{action}"}), "explore"
        else:
            out = self.inner.choose_with_note(view, options)
            tag = "table"
        self.captured.setdefault(view.patient_id, []).append(
            (view.node, json.dumps(req.to_dict(), ensure_ascii=False, separators=(",", ":")),
             list(options), {k2: round(float(v), 4) for k2, v in out[0].items()}, tag))
        return out

    def choose(self, view, options):
        return self.choose_with_note(view, options)[0]

    def run_summary(self):
        return self.inner.run_summary()


def split_of(key: str, salt: str = "jev-train-split") -> str:
    """Deterministic 80/10/10 split from a key."""
    u = int(hashlib.sha256(f"{salt}|{key}".encode()).hexdigest()[:12], 16) / 16 ** 12
    acc = 0.0
    for name, share in SPLITS:
        acc += share
        if u < acc:
            return name
    return SPLITS[-1][0]


def _outcome(pr) -> dict:
    a = pr.patient.arrival
    matched = [x["t"] for x in pr.treatments if x["matched"]]
    cands = matched + ([pr.t_treatment - a] if pr.t_treatment is not None else [])
    return {"diagnosed": pr.t_diagnosis is not None,
            "days_to_diagnosis": None if pr.t_diagnosis is None else round(pr.t_diagnosis - a, 2),
            "days_to_correct_treatment": round(min(cands), 2) if cands else None,
            "cost_eur": round(sum(pr.cost.values()), 2), "encounters": pr.enc_total, "episodes": pr.episode,
            "referred": bool(pr.referrals), "final": pr.outcome}


def rows_for_run(world, log, cohort, pol: CapturingPolicy, seed: int, split_by: str = "card",
                 holdout_generator: str | None = None):
    """Yield ``(row_json, row_info)`` for one finished run."""
    cat_hash = world.catalogue.version_hash[:12]
    for pr in log.patients:
        pid = pr.patient.id
        caps = pol.captured.get(pid, [])
        chosen = [c for c in pr.choices if str(c["node"]).endswith("_encounter")]
        if len(caps) != len(chosen):
            raise RuntimeError(f"patient {pid}: {len(caps)} captured requests but {len(chosen)} encounter choices")
        if not caps:
            continue
        card = cohort.card(pid)
        generator = card.provenance.generator
        classes = world.catalogue.conditions
        coexisting = [c for c in pr.conditions if c != pr.primary_condition]
        label = {"primary": pr.primary_condition, "coexisting": coexisting,
                 "class": classes[pr.primary_condition].cls}
        out = _outcome(pr)
        card_key = card.id
        if holdout_generator and generator == holdout_generator:
            split = "test"
        else:
            split = split_of(card_key if split_by == "card" else f"{seed}:{pid}")
        meta = {"catalogue": f"{world.catalogue.id}@{cat_hash}", "library": cohort.library_id, "generator": generator,
                "seed": seed, "patient": f"P{pid:06d}", "split": split}
        for (node, req_json, offered, probs, tag), ch in zip(caps, chosen):
            if ch["node"] != node or ch["offered"] != offered:
                raise RuntimeError(f"patient {pid}: captured request does not match the engine's choice at {node}")
            pol_tag = f"{pol.model_id}|{tag}" if tag == "explore" else pol.model_id
            line = ('{"request":' + req_json + ',"chosen":' + json.dumps(ch["chosen"]) + ',"policy":' + json.dumps(pol_tag)
                    + ',"behaviour_probs":' + json.dumps(probs, separators=(",", ":"))
                    + ',"label":' + json.dumps(label, separators=(",", ":"))
                    + ',"outcome":' + json.dumps(out, separators=(",", ":"))
                    + ',"meta":' + json.dumps(meta, separators=(",", ":")) + "}")
            yield line, (node, label["primary"], split, tag)


def export(scenario: str, n: int, seeds: list[int], out: str, explore: float = 0.0, split_by: str = "card",
           holdout_generator: str | None = None, quiet: bool = False) -> dict:
    from .encounter import load_world, run_encounter, world_cohort
    t0 = time.time()
    world = load_world(scenario)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    tmp = out + ".tmp"
    by_point, by_label, by_class, by_split, by_chosen, by_policy = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    patients = set()
    rows = 0
    with open(tmp, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz:
        for seed in seeds:
            cohort = world_cohort(world, n, seed)
            pol = CapturingPolicy(world.policy, world, seed, explore)
            log = run_encounter(world, n, seed, policy=pol, cohort=cohort)
            for line, (node, primary, split, tag) in rows_for_run(world, log, cohort, pol, seed, split_by, holdout_generator):
                gz.write(line.encode() + b"\n")
                rows += 1
                by_point[node] += 1
                by_label[primary] += 1
                by_split[split] += 1
                by_policy[tag] += 1
            patients.update((seed, pid) for pid in pol.captured)
            by_class.update(world.catalogue.conditions[cohort.card(pid).primary_condition].cls for pid in pol.captured)
            if not quiet:
                print(f"seed {seed}: {sum(len(v) for v in pol.captured.values())} decisions, {time.time() - t0:.0f} s", file=sys.stderr)
            del pol, log
    os.replace(tmp, out)
    summary = {"format": FORMAT, "scenario": scenario, "n_per_seed": n, "seeds": seeds, "explore": explore,
               "split_by": split_by, "holdout_generator": holdout_generator, "rows": rows, "patients": len(patients),
               "rows_per_decision_point": dict(by_point), "rows_per_primary_condition": dict(sorted(by_label.items())),
               "rows_per_split": dict(by_split), "rows_per_policy": dict(by_policy),
               "patients_per_class": dict(by_class), "file": out, "file_bytes": os.path.getsize(out),
               "seconds": round(time.time() - t0, 1)}
    sp = out[:-len(".jsonl.gz")] + ".summary.json" if out.endswith(".jsonl.gz") else out + ".summary.json"
    Path(sp).write_text(json.dumps(summary, indent=2))
    summary["summary_file"] = sp
    return summary


def cmd_export(a) -> None:
    from .__main__ import _seeds
    s = export(a.scenario, a.n, _seeds(a.seeds), a.out, a.explore, a.split_by, a.holdout_generator)
    print(f"wrote {s['file']}: {s['rows']} rows from {s['patients']} patients, {s['file_bytes'] / 1e6:.1f} MB, {s['seconds']} s")
    print("rows per decision point:", s["rows_per_decision_point"])
    print("rows per split:", s["rows_per_split"], "| policy:", s["rows_per_policy"])
    print("label (primary condition):", s["rows_per_primary_condition"])
    print("summary:", s["summary_file"])


def add_cli(sub) -> None:
    p = sub.add_parser("export-training", help="write JEV training rows (request, chosen, label, outcome) from an encounter world")
    p.add_argument("scenario")
    p.add_argument("--flowchart", default="encounter", help="accepted for symmetry with `run`; encounter worlds have one")
    p.add_argument("--n", type=int, default=2000, help="patients per seed")
    p.add_argument("--seeds", default="1", help="e.g. 1,2,3 or 1-3")
    p.add_argument("--explore", type=float, default=0.0, help="probability that a decision is drawn uniformly among the offered options")
    p.add_argument("--split-by", choices=["card", "patient"], default="card",
                   help="card (default): all patients drawn from one library card share a split, so no card is in train and test; patient: per patient and seed")
    p.add_argument("--holdout-generator", help="rows from cards made by this generator (e.g. reference) are marked test")
    p.add_argument("--out", required=True, help="path ending in .jsonl.gz")
    p.set_defaults(f=cmd_export)
