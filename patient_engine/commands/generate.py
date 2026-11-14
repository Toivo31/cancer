"""``python -m patient_engine generate``: write a library of model-written cards (WP-C1-5).

::

    export LLM_BASE_URL=https://.../v1 LLM_MODEL=<model> LLM_API_KEY=<key>      # key optional for a local server
    python -m patient_engine generate --catalogue catalogue/lung-primary-care --n 300 --seed 1 --out runs/libraries/L1
    python -m patient_engine generate --catalogue catalogue/lung-primary-care --n 50 --seed 1 --out /tmp/L --fake
    python -m patient_engine generate --catalogue ... --n 300 --seed 1 --out runs/libraries/L1 --estimate

``--fake`` answers from the reference generator (no network, no key). ``--estimate`` prints calls and tokens per
card and in total from the real prompt sizes and generates nothing. Exit codes: 0 complete, 3 partial library
written (budget or endpoint stop; rerun with ``--resume``), 1 failure, 2 usage.

Environment: ``LLM_BASE_URL``, ``LLM_MODEL``, ``LLM_API_KEY`` (never printed or stored), and optionally
``LLM_MODEL_G2`` to let the result author use another model than the patient author.
Work files (cache, call log, discard log, report) go to ``<out>.work`` unless ``--work-dir`` is given.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

from ..authors import PATIENT_VERSIONS, PROMPT_VERSIONS, RESULTS_VERSIONS
from ..catalogue import CatalogueError, load_catalogue
from ..llm import Budget, LLMClient, LLMError
from ..pipeline import (GenerationConfig, GenerationError, estimate_cost, generate_library_with_report,
                        reference_fake_client)
from ..skeleton import default_counts, make_design, proportional_design
from .design import parse_counts, scale_counts


def register(subparsers) -> None:
    p = subparsers.add_parser("generate", help="generate a library of model-written patient cards",
                              description=__doc__.split("\n\n")[0])
    p.add_argument("--catalogue", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n", type=int, help="total cards (scales the default counts; default: the default design)")
    p.add_argument("--counts", help="cards per primary condition, e.g. lung_cancer=100,pneumonia=50")
    p.add_argument("--proportional", action="store_true", help="draw primary conditions by prevalence (needs --n)")
    p.add_argument("--coexisting-rate", type=float)
    p.add_argument("--out", required=True, help="library directory (must not exist, or be empty)")
    p.add_argument("--work-dir", help="cache, logs and report (default <out>.work)")
    p.add_argument("--fake", action="store_true", help="offline: answer from the reference generator")
    p.add_argument("--estimate", action="store_true", help="print calls and tokens and stop")
    p.add_argument("--resume", action="store_true", help="replace a partial library of an earlier run (same cache)")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--max-calls", type=int, help="stop cleanly after this many model calls")
    p.add_argument("--max-tokens", type=int, help="stop cleanly after this many tokens")
    p.add_argument("--max-repairs", type=int, default=2)
    p.add_argument("--g1-temperature", type=float)
    p.add_argument("--g2-temperature", type=float)
    p.add_argument("--results-prompt", choices=list(RESULTS_VERSIONS),
                   help=f"result-author version (default {PROMPT_VERSIONS['results']})")
    p.add_argument("--results-cache-dir",
                   help="cache of the result author's calls (default the work dir's cache). g2@3's report bank does "
                        "not depend on the card, so runs that share this directory ask each result pattern once")
    p.add_argument("--patient-prompt", choices=PATIENT_VERSIONS, default=None,
                   help="patient-author version: g1@2 (default) the engine draws the findings from the catalogue and the "
                        "model writes the complaint and account; g1@1 the model writes the findings too")
    p.set_defaults(func=run)


def _design(cat, args):
    if args.proportional:
        if not args.n:
            raise ValueError("--proportional needs --n")
        return proportional_design(args.n, args.coexisting_rate)
    base = parse_counts(args.counts) if args.counts else default_counts(cat)
    if args.n and not args.counts:
        base = scale_counts(base, args.n)
    return make_design(cat, base, args.coexisting_rate)


def run(args) -> int:
    try:
        cat = load_catalogue(args.catalogue)
        design = _design(cat, args)
    except (CatalogueError, ValueError, KeyError) as e:
        print(f"generate: {e}", file=sys.stderr)
        return 2
    if args.estimate:
        e = estimate_cost(cat, design, args.seed, results_prompt=args.results_prompt,
                          patient_prompt=args.patient_prompt)
        print(json.dumps(e, indent=2))
        return 0
    out = Path(args.out)
    work = Path(args.work_dir) if args.work_dir else out.with_name(out.name + ".work")
    budget = Budget(args.max_calls, args.max_tokens)
    kw = dict(budget=budget, cache_dir=work / "cache")
    g2 = None
    try:
        if args.fake:
            client = reference_fake_client(cat, design, args.seed, **kw)
        else:
            client = LLMClient.from_env(**kw)
            if os.environ.get("LLM_MODEL_G2"):
                g2 = copy.copy(client)
                g2.model = os.environ["LLM_MODEL_G2"]
        if args.results_cache_dir:
            g2 = copy.copy(g2 or client)
            g2.cache_dir = Path(args.results_cache_dir)
            g2.cache_dir.mkdir(parents=True, exist_ok=True)
        cfg = GenerationConfig(concurrency=args.concurrency, max_repairs=args.max_repairs,
                               g1_temperature=args.g1_temperature, g2_temperature=args.g2_temperature)

        def progress(o, done, total):
            if done % cfg.progress_every == 0 or done == total:
                print(f"generate: {done}/{total} cards processed (last {o.card_id}: {o.status})", file=sys.stderr)

        manifest, rep = generate_library_with_report(cat, design, args.seed, client, budget=budget, out_dir=out,
                                                     results_client=g2, config=cfg, work_dir=work,
                                                     resume=args.resume, progress=progress,
                                                     results_prompt=args.results_prompt,
                                                     patient_prompt=args.patient_prompt)
    except (LLMError, GenerationError) as e:
        print(f"generate: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"library {manifest.id}: {rep.accepted}/{rep.requested} cards, {rep.discarded} discarded, "
          f"{rep.failed} failed, {rep.calls} calls, {rep.tokens} tokens, repairs {rep.repairs}")
    print(f"written to {out}; report in {work / 'generation_report.json'}")
    if rep.partial:
        print(f"PARTIAL: {rep.not_completed} cards not completed (stop: {rep.stop_reason}); "
              f"rerun with --resume and the same --work-dir to continue", file=sys.stderr)
        return 3
    return 0
