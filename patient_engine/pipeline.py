"""The generation pipeline (WP-C1-5): skeleton, G1, settled error plan, G2, validate and repair, library.

::

    client = LLMClient.from_env(budget=Budget(max_calls=2000), cache_dir="runs/libraries/L1.work/cache")
    manifest = generate_library(catalogue, make_design(catalogue, counts), seed=1, client=client,
                                out_dir="runs/libraries/L1")

Per card (``generate_card``)::

    make_skeleton                      engine: condition, attributes, background, persona, nominal plan
    G1  patient author  (model)        findings with causes, what the patient reports, the account
    settle_error_plan                  engine: the plan for the findings G1 wrote (``guided`` mode)
    G2  result author   (model)        every attempt of every test following the plan, plus a GP note
    validate_card                      schema and rules 1 to 9; ``card_reveals_condition`` counts as an error here
    repair, at most ``max_repairs``    the failing author gets its own answer back with ``repair_prompt``;
                                       a G1 repair re-asks G2 (the findings, hence the plan, changed)
    discard and log                    after the last repair

Cards run in parallel (``GenerationConfig.concurrency`` threads, one card per thread, so a budget stop leaves
whole cards rather than a layer of half-finished ones; ``LLMClient.map`` works on single calls and would not).
The client's cache makes a rerun on the same cache directory free for every call already answered.

Budget stop. ``BudgetExceeded`` stops starting new cards; cards in flight finish or give up. What was
completed is written as a partial library and ``generation_report.json`` (in the work directory) says
``"partial": true``. ``LibraryManifest`` has no field for that, so the report is the place; rerun with
``resume=True`` (same cache directory) to continue: the partial library is replaced, never extended.

Work directory (``<out_dir>.work`` unless given): ``cache/`` and ``calls.jsonl`` (the client's), ``discarded.jsonl``
and ``generation_report.json``. It never holds the API key (the client scrubs it; the pipeline writes
only card ids, problem texts and counts).
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .authors import PROMPT_VERSIONS, Authors
from .card import LibraryManifest
from .catalogue import Catalogue
from .library import LibraryError, load_library, write_library
from .llm import (Budget, BudgetExceeded, FakeLLMClient, LLMError, LLMHTTPError, LLMOutputError)
from .problems import ERROR, Problem
from .reference import generate_reference
from .skeleton import Design, Skeleton, make_skeleton, settle_error_plan
from .validate import has_errors, repair_prompt, validate_card

REPORT_FILE = "generation_report.json"
DISCARD_FILE = "discarded.jsonl"

#: Warning codes that the pipeline repairs like errors (the validator itself leaves them as warnings).
PROMOTED_CODES = frozenset({"card_reveals_condition"})


class GenerationError(RuntimeError):
    """The run produced no library (nothing completed, or the output directory is taken)."""


@dataclass(frozen=True)
class GenerationConfig:
    concurrency: int = 4
    max_repairs: int = 2
    g1_temperature: float | None = None
    g2_temperature: float | None = None
    #: stop the run when this many cards in a row fail on the endpoint (HTTP error) and none has succeeded
    abort_after_failures: int = 8
    progress_every: int = 10


@dataclass
class CardOutcome:
    card_id: str
    status: str                          # accepted | discarded | failed | budget | not_started
    card: dict | None = None
    repairs: int = 0
    reason: str | None = None
    problems: list[str] = field(default_factory=list)


@dataclass
class GenerationReport:
    library_id: str | None
    partial: bool
    stop_reason: str | None
    requested: int
    accepted: int
    discarded: int
    failed: int
    not_completed: int
    repairs: dict[str, int]              # number of repairs -> cards accepted with that many
    calls: int
    tokens: int
    model: str | None
    prompts: dict[str, str]
    seed: int
    elapsed_s: float
    discards: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


# ============================================================================ one card

def _promote(problems: list[Problem]) -> list[Problem]:
    return [dataclasses.replace(p, severity=ERROR) if p.code in PROMOTED_CODES else p for p in problems]


def generate_card(authors: Authors, sk: Skeleton, client, results_client=None, cfg: GenerationConfig | None = None
                  ) -> CardOutcome:
    """One card through G1 (every state, one call), the settled plan per state, G2 (one call per state),
    validation and at most ``cfg.max_repairs`` repairs. A repair round re-asks only the author that failed
    (G1 re-asks all of G2: the findings, hence the plans, changed; G2 re-asks the states with problems).
    ``BudgetExceeded`` is returned as status ``budget`` and endpoint failures as ``failed``; neither raises."""
    cfg = cfg or GenerationConfig()
    cat = authors.cat
    rclient = results_client or client
    states = tuple(sk.states)
    models = client.model if rclient.model == client.model else f"{client.model}+{rclient.model}"

    def ask(c, req: dict, tag: str, temperature, user: str | None = None) -> dict:
        r = dict(req)
        if user is not None:
            r["user"] = user
        return c.complete_json(**r, key=f"{sk.id}:{tag}", temperature=temperature)

    try:
        req1 = authors.g1_request(sk)
        g1: Any = ask(client, req1, "g1", cfg.g1_temperature)
        g2: dict[str, Any] = {}
        reqs: dict[str, dict] = {}
        plans: dict[str, Any] = {}
        for rep in range(cfg.max_repairs + 1):
            r1: list[Problem] = []
            r2: dict[str, list[Problem]] = {}
            p1 = authors.g1_problems(g1, states)
            if p1:
                r1 = p1
            else:
                for st in states:
                    if st not in g2:
                        plans[st] = settle_error_plan(cat, sk, authors.findings_of(g1, st), st)[st]
                        reqs[st] = authors.g2_request(sk, g1, plans[st], st)
                        g2[st] = ask(rclient, reqs[st], f"g2:{st}", cfg.g2_temperature)
                for st in states:
                    ps = authors.g2_problems(g2[st])
                    if ps:
                        r2[st] = ps
                if not r2:
                    prov = {"library": None, "catalogue_id": cat.id, "catalogue_hash": cat.version_hash,
                            "generator": "llm", "model": models, "prompts": dict(PROMPT_VERSIONS),
                            "error_source": "guided", "validation": {}}
                    card = authors.assemble(sk, g1, g2, plans, prov)
                    found = _promote(validate_card(card, cat))
                    errs = [p for p in found if p.severity == ERROR]
                    warnings = [p for p in found if p.severity != ERROR]
                    if not errs:
                        card["provenance"]["validation"] = {
                            "ok": True, "repairs": rep, "states": len(states),
                            "warnings": [{"code": p.code, "path": p.path} for p in warnings[:10]]}
                        return CardOutcome(sk.id, "accepted", card, rep)
                    for p in errs:
                        role, st = authors.route(p, states)
                        if role == "g1":
                            r1.append(p)
                        else:
                            for target in ([st] if st else states):
                                r2.setdefault(target, []).append(p)
            if rep == cfg.max_repairs:
                allp = [*r1, *(p for ps in r2.values() for p in ps)]
                return CardOutcome(sk.id, "discarded", None, rep, "errors remain after the last repair",
                                   [str(p) for p in allp[:20]])
            if r1:
                g1 = ask(client, req1, f"g1:r{rep + 1}", cfg.g1_temperature,
                         authors.repair_user("g1", req1["user"], g1, repair_prompt({"id": sk.id}, r1)))
                g2, plans = {}, {}
            else:
                for st, ps in r2.items():
                    g2[st] = ask(rclient, reqs[st], f"g2:{st}:r{rep + 1}", cfg.g2_temperature,
                                 authors.repair_user("g2", reqs[st]["user"], g2[st], repair_prompt({"id": sk.id}, ps)))
    except BudgetExceeded as e:
        return CardOutcome(sk.id, "budget", reason=str(e))
    except LLMOutputError as e:
        return CardOutcome(sk.id, "discarded", reason=f"the model never produced valid JSON: {e}")
    except LLMHTTPError as e:
        return CardOutcome(sk.id, "failed", reason=str(e))
    except LLMError as e:
        return CardOutcome(sk.id, "failed", reason=f"{type(e).__name__}: {e}")
    raise AssertionError("unreachable")  # pragma: no cover


# ============================================================================ the library

def _work_dir(out_dir: Path) -> Path:
    return out_dir.with_name(out_dir.name + ".work")


def _prepare_out(out_dir: Path, work: Path, resume: bool) -> None:
    if not out_dir.exists() or not any(out_dir.iterdir()):
        return
    report = work / REPORT_FILE
    if resume and report.exists():
        try:
            prev = json.loads(report.read_text())
            lib = load_library(out_dir)
        except (OSError, ValueError, LibraryError) as e:
            raise GenerationError(f"cannot resume: {out_dir} is not the partial library of {report}: {e}") from None
        if prev.get("partial") and prev.get("library_id") == lib.manifest.id:
            shutil.rmtree(out_dir)
            return
        raise GenerationError(f"{out_dir} holds a complete library; resume only replaces a partial one")
    raise GenerationError(f"{out_dir} already exists and is not empty (libraries are immutable); "
                          f"choose another --out, or --resume to replace a partial library")


def generate_library_with_report(catalogue: Catalogue, design: Design, seed: int, client, *,
                                 budget: Budget | None = None, out_dir, results_client=None,
                                 config: GenerationConfig | None = None, work_dir=None, resume: bool = False,
                                 progress: Callable[[CardOutcome, int, int], None] | None = None
                                 ) -> tuple[LibraryManifest, GenerationReport]:
    """Generate the cards of ``design`` and store them as a library in ``out_dir``. See the module docstring.

    ``budget`` replaces the client's own budget (and the results client's) when given. ``results_client``
    is G2's client when G2 uses another model or temperature (it should share the budget and log)."""
    cfg = config or GenerationConfig()
    out_dir = Path(out_dir)
    work = Path(work_dir) if work_dir else _work_dir(out_dir)
    work.mkdir(parents=True, exist_ok=True)
    _prepare_out(out_dir, work, resume)
    if budget is not None:
        client.budget = budget
        if results_client is not None:
            results_client.budget = budget
    authors = Authors(catalogue)
    t0 = time.monotonic()
    stop = threading.Event()
    lock = threading.Lock()
    state = {"fail_run": 0, "ok": 0, "done": 0, "stop_reason": None}

    def work_one(i: int) -> CardOutcome:
        sk = make_skeleton(catalogue, i, design, seed)
        if stop.is_set():
            return CardOutcome(sk.id, "not_started")
        out = generate_card(authors, sk, client, results_client, cfg)
        with lock:
            state["done"] += 1
            if out.status == "budget" and not stop.is_set():
                state["stop_reason"] = "budget"
                stop.set()
            if out.status == "failed":
                state["fail_run"] += 1
                if state["ok"] == 0 and state["fail_run"] >= cfg.abort_after_failures and not stop.is_set():
                    state["stop_reason"] = f"endpoint failing: {out.reason}"
                    stop.set()
            elif out.status == "accepted":
                state["ok"] += 1
                state["fail_run"] = 0
            n_done = state["done"]
        if progress:
            progress(out, n_done, design.n)
        return out

    with ThreadPoolExecutor(max_workers=max(1, cfg.concurrency)) as pool:
        outcomes = list(pool.map(work_one, range(design.n)))

    accepted = [o for o in outcomes if o.status == "accepted"]
    discards = [{"card_id": o.card_id, "status": o.status, "reason": o.reason, "repairs": o.repairs,
                 "problems": o.problems} for o in outcomes if o.status in ("discarded", "failed")]
    with open(work / DISCARD_FILE, "w", encoding="utf-8") as f:
        for d in discards:
            f.write(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n")
    hist: dict[str, int] = {}
    for o in accepted:
        hist[str(o.repairs)] = hist.get(str(o.repairs), 0) + 1
    not_completed = sum(1 for o in outcomes if o.status in ("budget", "not_started"))
    snap = client.budget.snapshot()
    models = client.model if results_client is None or results_client.model == client.model \
        else f"{client.model}+{results_client.model}"

    def report(library_id: str | None) -> GenerationReport:
        return GenerationReport(
            library_id=library_id, partial=not_completed > 0, stop_reason=state["stop_reason"], requested=design.n,
            accepted=len(accepted), discarded=sum(1 for o in outcomes if o.status == "discarded"),
            failed=sum(1 for o in outcomes if o.status == "failed"), not_completed=not_completed, repairs=hist,
            calls=snap["calls"], tokens=snap["tokens"], model=models, prompts=dict(PROMPT_VERSIONS), seed=seed,
            elapsed_s=round(time.monotonic() - t0, 1), discards=discards[:200])

    if not accepted:
        rep = report(None)
        (work / REPORT_FILE).write_text(json.dumps(rep.to_json(), indent=2, sort_keys=True) + "\n")
        raise GenerationError(f"no card was completed ({rep.discarded} discarded, {rep.failed} failed, "
                              f"{rep.not_completed} not completed; stop: {rep.stop_reason}); see {work}")
    manifest = write_library([o.card for o in accepted], catalogue, out_dir,
                             {"generator": "llm", "model": models, "prompts": dict(PROMPT_VERSIONS),
                              "error_source": "guided"})
    rep = report(manifest.id)
    (work / REPORT_FILE).write_text(json.dumps(rep.to_json(), indent=2, sort_keys=True) + "\n")
    return manifest, rep


def generate_library(catalogue: Catalogue, design: Design, seed: int, client, *, budget: Budget | None = None,
                     out_dir, **kw) -> LibraryManifest:
    """``generate_library_with_report`` returning only the manifest (the report is in ``<out_dir>.work``)."""
    return generate_library_with_report(catalogue, design, seed, client, budget=budget, out_dir=out_dir, **kw)[0]


# ============================================================================ offline stand-in for the model

_ID_RX = re.compile(r"Card id: (\S+)")
_STATE_RX = re.compile(r"State: (\S+)")


def reference_fake_client(catalogue: Catalogue, design: Design, seed: int, *,
                          transform: Callable[[str, str, dict, str], dict] | None = None, **client_kw) -> FakeLLMClient:
    """A ``FakeLLMClient`` that answers G1 and G2 from the reference generator, so the whole pipeline runs
    offline. The G1 answer is the reference card's findings, presenting and account of every state; G2 gets the same
    card's observations and GP note of the state in its prompt (they follow the plan G2's prompt carries, because the findings are
    the same). ``transform(role, card_id, answer)`` may change an answer (tests use it to break cards);
    ``role`` is ``g1`` or ``g2``; ``user`` is the prompt, in which a pipeline repair round contains
    ``"failed validation"``."""
    from .card import card_to_json
    cache: dict[int, dict] = {}
    lock = threading.Lock()

    def reference_json(card_id: str) -> dict:
        index = int(card_id.rsplit(":", 1)[1])
        with lock:
            if index not in cache:
                sk = make_skeleton(catalogue, index, design, seed, plan=False)
                cache[index] = card_to_json(generate_reference(catalogue, sk))
        return cache[index]

    def fn(system: str, user: str, schema: dict) -> dict:
        m = _ID_RX.search(user)
        if not m:
            raise LLMError("reference fake: no card id in the prompt")
        cid = m.group(1)
        c = reference_json(cid)
        if "states" in schema["properties"]:
            role = "g1"
            ans = {"states": {}}
            for i, st in enumerate(c["states"]):
                ans["states"][st] = {"findings": c["hidden"]["findings"][st], "presenting": c["presenting"][st],
                                     "account": {"text": c["notes"][2 * i]["text"], "mentions": c["notes"][2 * i]["mentions"]}}
        else:
            role = "g2"
            st = _STATE_RX.search(user).group(1)
            i = c["states"].index(st)
            ans = {"observations": c["observations"][st],
                   "gp_note": {"text": c["notes"][2 * i + 1]["text"], "mentions": c["notes"][2 * i + 1]["mentions"]}}
        ans = json.loads(json.dumps(ans))
        return transform(role, cid, ans, user) if transform else ans

    return FakeLLMClient(fn, **client_kw)


def estimate_cost(catalogue: Catalogue, design: Design, seed: int, sample: int = 30) -> dict:
    """Prompt and answer sizes for ``sample`` cards through the reference fake (no model call). Tokens are
    characters / 4. Answers of a real model are longer than the reference's template texts: count about
    1.5 times the output figure."""
    answers: list[int] = []
    fake = reference_fake_client(catalogue, design, seed, transform=lambda role, cid, ans, user: (
        answers.append(len(json.dumps(ans))) or ans))
    authors = Authors(catalogue)
    n = min(sample, design.n)
    for i in range(n):
        generate_card(authors, make_skeleton(catalogue, i, design, seed), fake)
    chars_in = sum(len(s) + len(u) for s, u in fake.calls)
    per_in = chars_in / 4 / n
    per_out = sum(answers) / 4 / n
    return {"sample_cards": n, "calls_per_card": len(fake.calls) / n, "input_tokens_per_card": round(per_in),
            "output_tokens_per_card_reference": round(per_out), "output_tokens_per_card_model": round(per_out * 1.5),
            "cards": design.n, "total_calls": round(design.n * len(fake.calls) / n),
            "total_input_tokens": round(per_in * design.n), "total_output_tokens": round(per_out * 1.5 * design.n)}
