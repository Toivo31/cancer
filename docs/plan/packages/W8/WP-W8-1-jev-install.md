# WP-W8-1: JEV install: run the team's decision model so the simulator and the demo page can call it

| | |
|---|---|
| Component | C4 decision layer (D41, D49, D51, D63, D64); owner's kit `decision_api/` |
| Status | not started |
| Size | M (T1 to T4 about one wave; T5 is the owner's) |
| Needs | nothing to start T1; T3 needs T1 |
| Provides | a documented, tested way to reach checkpoint 2350 from `jev.birch`, `jev.walk`, encounter runs (`--jev`) and `demo/jev.html` |
| Owned paths | `docs/platform/jev-birch.md`, `docs/platform/runbook.md` (JEV section only), `jev/birch.py` (constants and constructor defaults only), `jev/factory.py` (spec parsing only), `tests/test_jev_birch.py`, new `tests/test_jev_install.py` |
| Do not edit | `decision_api/**` (JEV owner's code: bring it in by merge, never by hand edits), `pathway_sim/` |
| Review required | yes: network, I1 (visible information only) |
| Track | submission (T1 to T4 before freeze if a lane is free; otherwise right after) |

## Outcome

On a fresh checkout of `overnight/sim`: `python -m decision_api.server` (no key) plus `python -m jev.walk --pick random --auto-accept`
reaches the deployed checkpoint 2350 through the hosted gateway, the walk prints the checkpoint step and weight hash from the
response, and `demo/jev.html` with "This server's /api/decision" (via `python demo/serve_jev.py`) scores a preset live.
`docs/platform/jev-birch.md` says exactly how, with the limits below, and lists what is still unknown.

## Why

D51: only the JEV decides at decision nodes; D64: no budget limit. Today `overnight/sim` has an **older copy** of
`decision_api/` (no `hosted.py`, `jev_bridge.py`, `agent.py`, `modal_inference.py`, `HOSTED_API.md`; 50 files differ from
`origin/main`), and `jev/birch.py` is pinned to checkpoint 1138 (`CHECKPOINT = 1138`, timeout 160 s, cache `runs/jev_cache`
not split by checkpoint). The owner documented the path for 2350 on `main` (PR 6, `decision_api/HOSTED_API.md` section
"Existing simulator Birch adapter"; `decision_api/validation/README.md` says this chain was smoke-tested end to end).

## What the documentation says (read on `origin/main`: `git show origin/main:decision_api/HOSTED_API.md`)

- **Hosted gateway, no key:** `https://cancer123--birch-decision-1138-demo.us-east.modal.run` (name still says 1138; the live
  checkpoint is 2350, weight SHA256 `22570c20...a7323e8`; trust response provenance, not the URL). Routes under `/api/decision`:
  `/score`, `/pathway`, `/reason`, `/examples`, `/jobs/{id}`, `/decisions/{id}`, `/decisions/{id}/review`, `/health`.
- **Local proxy:** `python -m decision_api.server` on `127.0.0.1:8771`; with no `BIRCH_API_KEY` it forwards to the hosted
  gateway and waits for 202 jobs, so `jev.birch` can keep its synchronous localhost URL. `jev.birch` refuses raw Modal URLs on purpose.
- **Bridge:** `decision_api/jev_bridge.py` `backend()` / `policy(world)`: subclass of `BirchBackend` pinned to step 2350 and the
  hash, timeout 660 s, cache `runs/jev_cache/checkpoint-2350-<hash12>`, rejects a response or cache entry of another model.
- **Limits that bind us** (gateway, `decision_api/hosted.py`; native, `runtime/decision_model/inference_schema.py`):
  one GPU, concurrency 1, at most 3 accepted jobs outstanding; **6 submissions per minute, 120 per hour per gateway process**;
  request JSON at most 32,000 bytes, context at most 12,000 characters, at most 4 questions and 8 choices per question on
  `/score`; natively 16 choices per question, **16 actions per pathway node**, 128 evidence items. Cold start: minutes;
  allow 660 s. No automatic replay of a POST.
- **Owner's rules:** visible information only; a person reviews proposals; no bulk cohort inference; no health polling.
  D64 (no budget limit) settles cost, not these rules or the rate limit (see T5).
- **Direct authenticated endpoint** (`BIRCH_API_URL`, owner's key out of band) has no gateway limits beyond the native schema.

## Acceptance

- [ ] `git diff origin/main -- decision_api` is empty on the lane branch after T1 (the owner's code arrives unchanged).
- [ ] `pytest tests/test_jev_install.py tests/test_jev_birch.py` green offline (mock): constructor default is 2350; a response
      with another step or hash is refused; a 1138 cache entry is not reused; a body over 32,000 bytes fails before sending
      with a message naming the gateway limit (edge).
- [ ] I1: the existing visibility test still passes with the bridge in place (`check_visible`).
- [ ] Live smoke (one person, a few calls, not in CI): `python -m jev.walk --pick random --auto-accept --max-calls 6` ends
      with an outcome and every response's `backend.step == 2350`; output saved under `runs/walks/`.
- [ ] `docs/platform/jev-birch.md` has a "Install and run" section a teammate can follow in under 5 minutes.

## Out of scope

GP nodes with more than 16 actions (WP-W8-2); recording demo outputs (WP-W8-3); any change to `decision_api/`; training.

## Things to look at and weigh

- **How to bring `decision_api/` in.** Merging `origin/main` into `overnight/sim` is what PR #2 needs anyway, but it also
  brings Eemeli's other `main` changes; checking out only `decision_api/` from `main` is narrower but forks history. Look at
  `git diff --stat overnight/sim origin/main` first and weigh which is safer two hours before freeze; ask the integrator.
- **Bridge vs editing `jev/birch.py`.** The owner wrote the bridge so `jev/` stays untouched. Changing the defaults in
  `birch.py` (checkpoint 2350, timeout 660, checkpoint-keyed cache) gives one code path; using the bridge keeps the owner's
  pin and hash check. Consider doing both: defaults in `birch.py`, `factory` spec `birch` resolving to the bridge.
- **Body size.** `MAX_BODY_BYTES` in `birch.py` is 480 KiB (the old proxy's limit); through the gateway it is 32,000 bytes.
  A long record (many encounters, `MAX_EVIDENCE_CHARS` 3,000 each) can pass the first and fail the second. Weigh trimming
  oldest evidence against failing loudly; failing loudly is the house rule (no silent fallback).
- **Rate limit as throughput.** 120 calls an hour means a 100-patient encounter run (about 4 decisions each) takes about
  3.5 hours. Note it in the doc next to D64.

## Decisions for the builder (leans)

- Prefer the owner's bridge for the pin; change only constants in `birch.py`.
- Keep the walk's default `--max-calls` (a guard against loops, not a budget), but document `--max-calls 0` or a large value
  for D64 runs if the code treats 0 as unlimited; otherwise a large number.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | W8-JI-T1 | Bring the owner's current `decision_api/` from `origin/main` into the integration branch | S | integrator OK | `git diff origin/main -- decision_api` empty; `pytest decision_api/tests -q` passes or its failures are listed as needing the owner |
| [ ] | W8-JI-T2 | Point `jev.birch` at checkpoint 2350 (defaults, checkpoint-keyed cache, 660 s timeout, gateway body limit) | S | T1 | tests above (2350 default, other identity refused, 1138 cache ignored, 32,000-byte edge) |
| [ ] | W8-JI-T3 | Live smoke: walk two patients through the loop on the hosted gateway; record step, hash, latency | S | T2 | `runs/walks/*.json` with `backend.step == 2350`; latency and any 202/cold-start behaviour noted in the doc |
| [ ] | W8-JI-T4 | Write "Install and run" in `docs/platform/jev-birch.md` (proxy, gateway, bridge, limits, owner's rules, D64) and a JEV line in `docs/platform/runbook.md` | S | T3 | a teammate follows it and scores `demo/jev.html` live through `demo/serve_jev.py` |
| [ ] | W8-JI-T5 | Questions for the JEV owner (post as one QUESTION on the channel; owner: JEV owner) | S | – | answers recorded in `jev-birch.md`: (a) does D64's unlimited use conflict with "no bulk cohort inference", and may a 100 to 400-patient automated run go through the gateway or must it use the authenticated endpoint; (b) can the rate limit be raised for a named run; (c) is a rationale (`record_note`, D49) available from `/reason` for pathway requests, and at what cost in seconds; (d) will the endpoint stay up after submission, and until when |
