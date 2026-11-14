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


PLACEHOLDER_AUTHORS = ("table",)      # the engine writes an assessment's author as "<role>_encounter/<backend_name>"


def is_placeholder_assessment(a: dict) -> bool:
    """True for an assessment the placeholder decision tables wrote (author ``gp_encounter/table``), or the
    uniform draw of an explore row (it is written under the same backend name). A real decider's author
    (``gp_encounter/birch``, an HTTP JEV's backend name, ...) is never matched."""
    return str(a.get("author", "")).rsplit("/", 1)[-1] in PLACEHOLDER_AUTHORS


def strip_placeholder_assessments(req_dict: dict) -> int:
    """Remove placeholder-authored entries from ``request.context.assessments`` in place; return how many."""
    ctx = req_dict.get("context") or {}
    old = ctx.get("assessments") or []
    new = [a for a in old if not is_placeholder_assessment(a)]
    if len(new) != len(old):
        ctx["assessments"] = new
    return len(old) - len(new)


class CapturingPolicy:
    """Delegates to ``inner`` (the world's decision tables), optionally explores, keeps every request.

    By default the assessments the placeholder tables wrote into the record ("Table rule: ...") are removed from the
    kept request (``keep_table_notes=True`` keeps them): a model trained on them would learn rule names that do not
    exist when the real decision model decides. Assessments of a real decider stay. ``with_text`` also keeps the
    text the Birch adapter would send for the same decision, rendered by the adapter's own functions."""

    decision_mode = "sample"

    def __init__(self, inner, world, seed: int, explore: float = 0.0, keep_table_notes: bool = False,
                 with_text: bool = False):
        from jev.adapter import BackendPolicy
        self.inner, self.seed, self.explore = inner, seed, float(explore)
        self.keep_table_notes, self.with_text = keep_table_notes, with_text
        self.stripped_rows = self.stripped_entries = 0
        self._text = None
        if with_text:
            from jev.birch import BirchBackend, BirchPolicy
            be = BirchBackend(cache_dir=None, max_calls=0)         # never called: only its request mapping is used
            self._text = BirchPolicy(be, mode="sample", scenario=world.scenario, flowchart=world.flowchart,
                                     catalogue=world.catalogue, care=world.care)
        self._req = BackendPolicy(_NoBackend(), mode="sample", scenario=world.scenario, flowchart=world.flowchart)
        self.captured: dict[int, list] = {}          # cohort index -> [(node, request json, offered, probs, tag, text json or None)]
        self._n: Counter = Counter()

    @property
    def backend_name(self) -> str:                    # the engine writes it into the record's assessment author
        return getattr(self.inner, "backend_name", "table")

    @property
    def model_id(self) -> str:
        return getattr(self.inner, "model_id", "table")

    def choose_with_note(self, view, options):
        req = self._req.request_for(view, list(options))          # the live path's request builder
        req_d = req.to_dict()
        if not self.keep_table_notes:
            k_out = strip_placeholder_assessments(req_d)
            self.stripped_rows += bool(k_out)
            self.stripped_entries += k_out
        text = None
        if self._text is not None:
            from jev.birch import map_request
            text = map_request(self._text.request_for(view, list(options)), self._text.backend.include_assessments)["case"]
        k = self._n[view.patient_id]
        self._n[view.patient_id] += 1
        if self.explore > 0 and uniform(self.seed, view.patient_id, "explore", k) < self.explore:
            probs = {o: 1.0 / len(options) for o in options}
            out, tag = (probs, None, {"plan": "{action}"}), "explore"
        else:
            out = self.inner.choose_with_note(view, options)
            tag = self.backend_name
        self.captured.setdefault(view.patient_id, []).append(
            (view.node, json.dumps(req_d, ensure_ascii=False, separators=(",", ":")),
             list(options), {k2: round(float(v), 4) for k2, v in out[0].items()}, tag,
             None if text is None else json.dumps(text, ensure_ascii=False, separators=(",", ":"))))
        return out

    def choose(self, view, options):
        return self.choose_with_note(view, options)[0]

    def run_summary(self):
        return self.inner.run_summary()


# ============================================================================ the JEV over HTTP (D51)

class TimedBackend:
    """Wraps a backend: counts calls and failures and keeps the latency of each ``decide`` call."""

    def __init__(self, inner):
        self.inner, self.latencies, self.failures, self.calls = inner, [], 0, 0

    def info(self):
        return self.inner.info()

    def decide(self, requests):
        t, h0 = time.perf_counter(), getattr(self.inner, "http_calls", None)
        self.calls += 1
        try:
            return self.inner.decide(requests)
        except Exception:
            self.failures += 1
            raise
        finally:
            if h0 is None or getattr(self.inner, "http_calls", h0) != h0:      # only calls that went over the network
                self.latencies.append(time.perf_counter() - t)

    def summary(self) -> dict:
        xs = sorted(self.latencies)
        q = lambda p: round(xs[min(len(xs) - 1, int(p * len(xs)))] * 1000, 1) if xs else None
        out = {"calls": self.calls, "network_calls": len(xs), "failures": self.failures, "median_ms": q(0.5), "p95_ms": q(0.95)}
        fn = getattr(self.inner, "summary", None)
        if callable(fn):
            out.update(fn())
        return out


def jev_policy(world, spec: str, model: str | None = None, timeout: float = 5.0):
    """``BackendPolicy`` over the JEV named by ``spec``: an HTTP URL (host must be in JEV_ALLOWED_HOSTS /
    JEV_DEFAULT_URL, as for the service) or any other backend kind ``jev.factory`` knows (``stub``, ``http``, ``local``,
    and kinds other lanes register there, e.g. ``birch``). Raises SystemExit with a plain message when the host is not
    allowed, the kind is unknown or the JEV is unreachable."""
    from jev import factory
    from jev.adapter import BackendPolicy
    from jev.contract import BackendError
    from jev.stub import StubBackend
    cfg = {"timeout": timeout}
    if model:
        cfg["model"] = model
    kind = spec
    if spec.startswith(("http://", "https://")):
        try:
            from service.security import check_jev_url
            check_jev_url(spec, where="--jev")
        except ImportError:
            pass
        except ValueError as e:                               # HostNotAllowed
            raise SystemExit(f"error: {e}") from None
        kind, cfg["url"] = "http", spec
    if kind == "rule":
        raise SystemExit("error: for encounter worlds --jev takes a URL or a backend kind such as stub or birch (the world's decision tables are the default)")
    try:
        be = TimedBackend(factory._make_backend(kind, cfg, StubBackend({}), "--jev", world.flowchart, 0))
        return BackendPolicy(be, mode="sample", scenario=world.scenario, flowchart=world.flowchart)
    except (BackendError, ValueError) as e:
        raise SystemExit(f"error: the JEV {spec!r} is not usable: {e}\n"
                         "       for a URL: start the service (for a test: python -m jev.stub_server) and check the address") from None


def jev_summary(pol) -> dict | None:
    be = getattr(pol, "backend", None)
    return be.summary() if isinstance(be, TimedBackend) else None


def format_jev_summary(sm: dict) -> str:
    return (f"JEV decisions {sm['calls']} (network calls {sm['network_calls']}), failures {sm['failures']}, latency per network call: median {sm['median_ms']} ms, p95 {sm['p95_ms']} ms"
            + (f", cache hits {sm['cache_hits']}" if "cache_hits" in sm else ""))


# ============================================================================ libraries (reference or model-written)

def load_libraries(world, paths: list[str]) -> list:
    """Load and verify card libraries (``patient_engine.library.load_library``: file hashes, and the catalogue hash
    must equal the world's). Without paths: the world's own library."""
    from patient_engine.library import LibraryError, load_library
    from .encounter import world_library
    if not paths:
        return [world_library(world)]
    out = []
    for p in paths:
        try:
            out.append(load_library(p, world.catalogue))
        except LibraryError as e:
            raise SystemExit(f"error: library {p}: {e}") from None
    return out


def library_cohort(world, lib, n: int, seed: int):
    """Like ``encounter.world_cohort`` but for a given library."""
    from patient_engine.cohort import CohortSpec, draw_cohort
    prev = {c: v for c, v in world.prevalence().items() if c in lib.by_condition and v > 0}
    arr = {k: v for k, v in (world.raw.get("arrivals") or {"rate_per_day": 44}).items() if k in ("rate_per_day", "spread_days")}
    return draw_cohort(lib, CohortSpec(library_id=lib.id, prevalence=prev, n=n, seed=seed), arr)


def generator_name(lib) -> str:
    m = lib.manifest
    return m.generator if not m.model else f"{m.generator}:{m.model}"


def cli_run_world(a) -> None:
    """``run`` for encounter worlds: ``encounter.cli_run`` plus ``--library`` and ``--jev URL``."""
    from .encounter import format_outcomes, load_world, outcomes, run_encounter
    t0 = time.time()
    world = load_world(a.scenario)
    n = a.n or int(world.raw.get("default_n", 2000))
    libs = getattr(a, "library", None) or []
    if len(libs) > 1:
        raise SystemExit("error: `run` takes one --library (export-training takes several)")
    lib = load_libraries(world, libs)[0]
    cohort = library_cohort(world, lib, n, a.seed)
    if a.decision_mode or a.set:
        raise SystemExit("error: --decision-mode and --set apply to flowchart scenarios, not encounter worlds")
    pol = None
    if a.jev:
        pol = jev_policy(world, a.jev, a.jev_model, a.jev_timeout or 5.0)
    try:
        log = run_encounter(world, n, a.seed, policy=pol, cohort=cohort)
    except Exception as e:
        if type(e).__name__ in ("BackendError", "ContractError"):
            raise SystemExit(f"error: the run stopped, the JEV failed: {e}") from None
        raise
    o = outcomes(log)
    who = getattr(pol or world.policy, "model_id", "")
    print(f"{world.id}: library {log.library_id} ({generator_name(lib)}, {log.distinct_cards} distinct cards), care {world.care_path}, "
          f"policy {who}; {time.time() - t0:.1f} s")
    print(format_outcomes(o, world.target_days))
    if pol is not None:
        sm = jev_summary(pol)
        if sm:
            print(format_jev_summary(sm))
    elif world.policy.run_summary():
        print("policy warnings:", world.policy.run_summary())
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"run": log.to_dict(), "outcomes": o}))
        print("wrote", a.out)


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
                 holdout_generator: str | None = None, force_split: str | None = None):
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
        generator = generator_name(cohort.library)
        classes = world.catalogue.conditions
        coexisting = [c for c in pr.conditions if c != pr.primary_condition]
        label = {"primary": pr.primary_condition, "coexisting": coexisting,
                 "class": classes[pr.primary_condition].cls}
        out = _outcome(pr)
        card_key = card.id
        if force_split:
            split = force_split
        elif holdout_generator and generator.split(":")[0] == holdout_generator:
            split = "test"
        else:
            split = split_of(card_key if split_by == "card" else f"{seed}:{pid}")
        meta = {"catalogue": f"{world.catalogue.id}@{cat_hash}", "library": cohort.library_id, "generator": generator,
                "seed": seed, "policy_model": pol.model_id, "patient": f"P{pid:06d}", "split": split}
        for (node, req_json, offered, probs, tag, text_json), ch in zip(caps, chosen):
            if ch["node"] != node or ch["offered"] != offered:
                raise RuntimeError(f"patient {pid}: captured request does not match the engine's choice at {node}")
            pol_tag = f"{pol.model_id}|explore" if tag == "explore" else pol.model_id
            line = ('{"request":' + req_json + ("" if text_json is None else ',"request_text":' + text_json) + ',"chosen":' + json.dumps(ch["chosen"]) + ',"policy":' + json.dumps(pol_tag)
                    + ',"behaviour_probs":' + json.dumps(probs, separators=(",", ":"))
                    + ',"label":' + json.dumps(label, separators=(",", ":"))
                    + ',"outcome":' + json.dumps(out, separators=(",", ":"))
                    + ',"meta":' + json.dumps(meta, separators=(",", ":")) + "}")
            yield line, (node, label["primary"], split, tag)


def export(scenario: str, n: int, seeds: list[int], out: str, explore: float = 0.0, split_by: str = "card",
           holdout_generator: str | None = None, quiet: bool = False, libraries: list[str] | None = None,
           holdout_libraries: list[str] | None = None, jev: str | None = None, jev_model: str | None = None,
           jev_timeout: float = 5.0, keep_table_notes: bool = False, with_text: bool = False) -> dict:
    from .encounter import load_world, run_encounter
    t0 = time.time()
    world = load_world(scenario)
    train_libs = load_libraries(world, libraries or [])
    hold_libs = load_libraries(world, holdout_libraries) if holdout_libraries else []
    plan = [(lib, False) for lib in train_libs] + [(lib, True) for lib in hold_libs]
    if len({lib.id for lib, _ in plan}) != len(plan):
        raise SystemExit("error: the same library is given twice (or as both --library and --holdout-library)")
    jev_stats = []
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    tmp = out + ".tmp"
    by_point, by_label, by_class, by_split, by_chosen, by_policy = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    patients = set()
    rows = stripped_rows = stripped_entries = 0
    with open(tmp, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz:
        for (lib, is_hold), seed in ((lp, sd) for lp in plan for sd in seeds):
            cohort = library_cohort(world, lib, n, seed)
            inner = jev_policy(world, jev, jev_model, jev_timeout) if jev else world.policy
            pol = CapturingPolicy(inner, world, seed, explore, keep_table_notes, with_text)
            try:
                log = run_encounter(world, n, seed, policy=pol, cohort=cohort)
            except Exception as e:
                if type(e).__name__ in ("BackendError", "ContractError"):
                    raise SystemExit(f"error: the export stopped, the JEV failed: {e}") from None
                raise
            if jev:
                jev_stats.append(jev_summary(inner))
            for line, (node, primary, split, tag) in rows_for_run(world, log, cohort, pol, seed, split_by, holdout_generator,
                                                                  force_split="test" if is_hold else None):
                gz.write(line.encode() + b"\n")
                rows += 1
                by_point[node] += 1
                by_label[primary] += 1
                by_split[split] += 1
                by_policy[tag] += 1
            stripped_rows += pol.stripped_rows
            stripped_entries += pol.stripped_entries
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
               "libraries": [{"id": lib.id, "generator": generator_name(lib), "holdout": h} for lib, h in plan],
               "keep_table_notes": keep_table_notes, "with_text": with_text,
               "rows_with_table_assessments_removed": stripped_rows, "table_assessments_removed": stripped_entries,
               "jev": jev, "jev_calls": jev_stats or None, "patients_per_class": dict(by_class), "file": out, "file_bytes": os.path.getsize(out),
               "seconds": round(time.time() - t0, 1)}
    sp = out[:-len(".jsonl.gz")] + ".summary.json" if out.endswith(".jsonl.gz") else out + ".summary.json"
    Path(sp).write_text(json.dumps(summary, indent=2))
    summary["summary_file"] = sp
    return summary


def cmd_export(a) -> None:
    from .__main__ import _seeds
    s = export(a.scenario, a.n, _seeds(a.seeds), a.out, a.explore, a.split_by, a.holdout_generator,
               libraries=a.library, holdout_libraries=a.holdout_library, jev=a.jev, jev_model=a.jev_model,
               jev_timeout=a.jev_timeout, keep_table_notes=a.keep_table_notes, with_text=a.with_text)
    print(f"wrote {s['file']}: {s['rows']} rows from {s['patients']} patients, {s['file_bytes'] / 1e6:.1f} MB, {s['seconds']} s")
    print("rows per decision point:", s["rows_per_decision_point"])
    print("rows per split:", s["rows_per_split"], "| policy:", s["rows_per_policy"])
    print("label (primary condition):", s["rows_per_primary_condition"])
    for sm in s["jev_calls"] or []:
        print(format_jev_summary(sm))
    print(f"table assessments removed from requests: {s['table_assessments_removed']} entries in "
          f"{s['rows_with_table_assessments_removed']} of {s['rows']} rows" + (" (kept: --keep-table-notes)" if s["keep_table_notes"] else ""))
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
    p.add_argument("--library", action="append", metavar="DIR", help="card library directory (patient_engine library); repeatable. Default: the world's reference library")
    p.add_argument("--holdout-library", action="append", metavar="DIR", help="library whose patients all go to the test split (generalisation check); repeatable")
    p.add_argument("--jev", metavar="URL|KIND", help="decide with the JEV instead of the decision tables: an HTTP URL (host must be in JEV_ALLOWED_HOSTS or be JEV_DEFAULT_URL) or a jev.factory backend kind (stub, birch, ...)")
    p.add_argument("--jev-model", help="model id to ask the JEV for")
    p.add_argument("--jev-timeout", type=float, default=5.0, help="seconds per JEV call (the client caps it at 5)")
    p.add_argument("--keep-table-notes", action="store_true",
                   help="keep the placeholder decision tables' own assessments (\"Table rule: ...\") in request.context.assessments; by default they are removed, a real decider's stay")
    p.add_argument("--with-text", action="store_true",
                   help="also write request_text per row: the case text and evidence lines the Birch adapter would send (jev.birch.map_request), for training on rendered text")
    p.add_argument("--out", required=True, help="path ending in .jsonl.gz")
    p.set_defaults(f=cmd_export)
