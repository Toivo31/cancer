# The team's decision model (checkpoint 2350, "Birch") in the encounter loop

WP-W5-1, WP-W8-1. Code: `jev/birch.py` (backend and policy), `jev/walk.py` (step-through tool), `jev/birch_mock.py`
(local mock of the API, tests and offline demo), registered in `jev/factory.py`. Tests: `tests/test_jev_birch.py`,
`tests/test_jev_install.py`. The model owner's kit is `decision_api/` (brought from `origin/main` e921d3c unchanged; we do
not edit it). Live calls go through the owner's bridge `decision_api/jev_bridge.py`, which accepts only checkpoint 2350
with weight SHA256 `22570c20...a7323e8` (the gateway URL still says 1138: trust the response, not the URL).

## Install and run (5 minutes)

Needs: Python 3.11+, this repo on `overnight/sim` (or `w9/jev-install` until it is merged), plain internet access to
`*.modal.run` (a laptop is fine; the Claude Code cloud workspace is not: its proxy refuses `*.modal.run`). No key, no
Modal account: with no `BIRCH_API_KEY` the local proxy forwards to the owner's hosted gateway and waits for its jobs.

```bash
python3 -m pytest tests/test_jev_install.py -q             # offline, about 15 s: the pin, the limits, I1
python3 -m decision_api.agent --saved                      # reachability check on a recorded answer: no GPU, no submission slot

# terminal 1: the local proxy on 127.0.0.1:8771 (no key: hosted gateway; no GPU starts until a call)
python3 -m decision_api.server
# terminal 2: one walk, unattended, a few calls; prints "birch step 2350 sha 22570c201a9e" per answered decision
python3 -m jev.walk --pick random --pick-seed 7 --auto-accept --max-calls 6
```

The walk saves `runs/walks/*.json`; each step holds the response's `backend` (`step`, `checkpoint_sha256`) and
`latency_ms`. **Expect the walk to stop at the first GP visit** ("offers 24 actions; the model takes at most 16 per
node (WP-W8-2); nothing was sent"): the nurse decisions before it are real 2350 answers; the GP node needs WP-W8-2. The
stopped walk is saved as `runs/walks/walk_stopped_*.json`. The first call after the model has been idle can take
minutes (cold start); the backend waits up to 660 s.

Demo page, live: `python3 demo/serve_jev.py`, open http://127.0.0.1:8772/jev.html, choose "This server's
/api/decision" and score a preset (the same proxy code, on one origin). From code:

```python
from pathway_sim.encounter import load_world
from jev.birch import policy_for_world                    # the pinned bridge, paced 10 s between live calls
pol = policy_for_world(load_world("scenarios/finland_encounter.yaml"), max_calls=20)
```

`jev.prepare(..., backend="birch")` and `--jev birch` on encounter runs also resolve to the bridge. `--jev mock` (walk)
or `allow_non_model` (factory) keep the plain backend against a local mock, with no pin, pacing or action limit.

**Limits that bind us** (gateway `decision_api/hosted.py`, native `runtime/decision_model/inference_schema.py`), all
checked before sending, so an over-limit request costs no slot:

| Limit | Value | Here |
|---|---|---|
| Submissions | 6 a minute, 120 an hour per gateway process, shared by everyone (demo page, teammates), reset on restart | live calls paced 10 s apart (`--min-interval`, `min_interval`); use 30 for runs longer than 20 minutes |
| Outstanding jobs | 3 accepted, one GPU, concurrency 1 | concurrency 1 |
| Body | 32,000 bytes as `json.dumps` (ASCII escaped) | `check_limits`, error names the limit; nothing trimmed (no silent change) |
| Context | 12,000 characters | `check_limits` |
| Actions per node | 16 (natively) | `check_limits` on the pinned backend; GP node has 24: WP-W8-2 |
| Wait | cold start minutes; 660 s overall; no replay of a POST | timeout 660 s, no retry, stop after 2 failures in a row |

D64 (no budget limit) settles cost only; it does not lift the rate limit or the owner's rules (visible information
only, a person reviews, no bulk cohort inference, no health polling). `--max-calls` stays as a loop guard: `0` sends
nothing (it is not "unlimited"); for a long run pass a number above the expected calls.

**Live smoke (T3), 14 Nov 23:00 UTC:** not run from the cloud workspace: its egress proxy answers 403 to CONNECT for
`cancer123--birch-decision-1138-demo.us-east.modal.run` (allowlist). The local chain was checked up to that point
(proxy starts with no key; the walk stops loudly with "HTTP 503 ... Tunnel connection failed: 403"). Step, hash and
latency are to be recorded here from the first laptop run.

## The owner's constraints, in plain words

* Send only what a clinician could see: visible information, the question and the allowed choices. Never a hidden
  diagnosis, a future result, a gold label or an earlier model score.
* No bulk cohort inference, no health polling, no keep-alive, no per-frame calls. The model costs money while its
  GPU is allocated. (14 Nov: the GPU runs nonstop while the demo is live, so live per-decision calls are fine then; the
  budget and the cache stay as guards.)
* The model proposes, a person decides. Its scores are relative to the offered list, not disease probabilities, test
  sensitivities or time estimates, and are never used as such.
* Warm scoring takes about 3.4 s on the GPU (owner's measurement, plus gateway and polling), a cold start minutes. A
  failure stays visible: no silent fallback to saved or invented answers. No automatic retry of a POST.
* With no key the proxy uses the hosted gateway (limits above). With the owner's key (`BIRCH_API_KEY` or
  `BIRCH_API_KEY_FILE`, out of band) it calls the authenticated endpoint, which has no gateway limits beyond the native
  schema; our code never sees the key.

## Start the proxy, walk a patient

```bash
# terminal 1: no key = hosted gateway; or the owner's key, shared out of band, never committed
python -m decision_api.server                                             # http://127.0.0.1:8771, no GPU starts until a call
# BIRCH_API_KEY_FILE=/private/path/to/key python -m decision_api.server  # authenticated endpoint
# terminal 2
python -m jev.walk                                # a random patient (same as --pick random); the seed is printed, repeat with --pick-seed N
python -m jev.walk --pick cancer                  # or pneumonia, worried_well; Enter accepts a proposal, or type an id or number
python -m jev.walk --pick cancer --placeholder    # also show the placeholder decision table's numbers
python -m jev.walk --pick pneumonia --auto-accept --max-calls 20
python -m jev.walk --library DIR --patient 3      # a patient of a stored library (index or card id)
python -m jev.walk --pick cancer --auto-accept --jev mock   # no model, no key: a local mock (about 2 s)
python -m jev.walk --pick cancer --jev table      # the placeholder tables only
```

A cold model can take minutes; the backend waits up to 660 s (the gateway's documented wait). If it still fails, retry
the command (answers already received are in the cache). After two failed calls in a
row the backend sends nothing more until a new run. The walk saves `runs/walks/walk_<pick>_<n>_<jev>.json`: every step
(record, scores, proposal, choice), the record, and, in a separate block marked for scoring only, the patient's hidden
condition. Treat that file as hidden-side data.

**Who is blind.** The model always is. The person at the keyboard is blind with `--pick random` (the default: a seeded random kind and card; the seed is printed and `--pick-seed N` repeats the patient) and with a `--library` patient they did not select by condition. With `--pick cancer`, `pneumonia` or `worried_well` the person chooses the condition before the walk, so they are not blind (the walk prints a note); use those for rehearsal and say so on stage if used in the "person decides" demo.

## What one request looks like

`POST /api/decision/pathway` (same as `decision_api/web/pathway.json`):

```json
{"case": {"case_id": "p0:gp_encounter",
          "context": "Patient in Finnish primary care (synthetic). Background: age 67, female, smoking status former. Reported at first contact: Cough for 3 weeks, Fever. Deciding now: GP, episode 1.",
          "step": 3,
          "evidence": [{"source_id": "record:1:encounter", "available_at_step": 1, "text": "Day 0 · Nurse · ... · Book a GP visit · note: ..."},
                       {"source_id": "record:2:result", "available_at_step": 2, "text": "Day 11 · result · Chest X-ray: ..."},
                       {"source_id": "record:3:encounter", "available_at_step": 3, "text": "Day 12 · GP · ..."}]},
 "workflow": {"id": "primary-care-encounter", "version": "1", "root": "gp_encounter",
              "nodes": {"gp_encounter": {"question": "What should the GP do next for this patient?", "protocol": "Synthetic primary-care encounter. ...",
                                          "actions": [{"id": "order_chest_xray", "description": "Chest X-ray", "next": "after-order_chest_xray"}, "..."]},
                        "after-order_chest_xray": {"terminal": true}, "...": "..."}},
 "node_id": "gp_encounter"}
```

* One evidence item per record entry, in order, rendered by `patient_engine/record_text.render`. The step of an item is its
  place in the record (1, 2, ...), the current step is the number of entries including the visit being decided.
  (The package text says "encounter number"; encounter numbers restart in each episode and results and hospital
  steps have none, so the entry's position is the only strictly increasing step.) Earlier assessments are left out unless
  `include_assessments` is set.
* Actions are the options the role is offered, described by the care model's labels. Next nodes are terminal.
* The answer's `questions[0].choices[].score` become `probs` over the offered ids (renormalised); the explanation
  carries the checkpoint, the margin and the latency. If the response has a `rationale` (or `explanation`) text, per question
  or per response, it becomes the record note (D49). Without one, `BirchPolicy` writes a labelled template note
  ("Decision model proposal ... no written rationale") and `plan`.

## Cost guards

| Guard | Where |
|---|---|
| Hard call budget, default 50 (`--max-calls`, `max_calls`). Failed calls count. Over budget: `BirchBudgetExceeded`, nothing sent | `BirchBackend` |
| Disk cache `runs/jev_cache/checkpoint-2350-22570c201a9e/<hash>.json`, key = hash of the request without the case id (the same record never costs twice, across runs). Only answers from the model itself are cached and served; the bridge also refuses a cached or live answer whose step or hash is not 2350's (old 1138 entries in `runs/jev_cache/` are never read); a `calls.jsonl` ledger lists live calls | `BirchBackend`, bridge |
| Gateway and native limits (32,000-byte body, 12,000-char context, 16 actions per node) checked before sending; live calls paced (10 s default) | `check_limits`, `min_interval` |
| Concurrency 1 (`--concurrency`, at most 4) | semaphore |
| No retry, no polling, no keep-alive; one connection per call; stops after 2 failed calls in a row | `BirchBackend` |
| One-option decisions are never sent | `BirchBackend` |
| Refuses a `*.modal.run` URL (we talk to the proxy) and any answer from a non-model backend (a `--fixture` proxy) | `BirchBackend` |
| I1: before every send the payload is checked: no hidden-side key, no evidence from a later step, no condition id in the text | `check_visible` |
| Summary of calls, cache hits, failures, latency (`policy.run_summary()`, printed by the walk) | `BirchBackend.summary` |

## A small cohort with a budget

Through the factory, wherever a JEV spec is accepted: `birch` (proxy on 127.0.0.1:8771) or `birch+http://host:port`.
Options: `max_calls`, `cache_dir`, `concurrency`, `include_assessments`, and `catalogue=`, `care=` (labels).

```python
from pathway_sim.encounter import load_world, run_encounter
from jev.birch import policy_for_world
world = load_world("scenarios/finland_encounter.yaml")
pol = policy_for_world(world, max_calls=600, min_interval=30)   # about 5 decisions per patient; needs WP-W8-2 for GP nodes
log = run_encounter(world, 100, seed=1, policy=pol)
print(pol.run_summary())
```

Label such a run "model policy, n=100 (budgeted), proposals not reviewed". The engine draws the action from the
scores (they are not sharpened), so the numbers describe a sampling policy; use the walk for reviewed decisions.

## Running the loop and the Norway check with the JEV deciding (estimate, 14 Nov)

Measured offline on this branch with the placeholder tables (same seeds, no model), counting decisions with more than
one option; hours = calls / 120 (the hourly limit binds before the 6 a minute one):

| Run | Decisions | Distinct requests (cache) | Calls | Hours at 120/h |
|---|---|---|---|---|
| Encounter loop, 100 patients (`finland_encounter.yaml`, seed 1) | 497: 96 nurse (3 actions), 401 GP (24 actions); median 4, p90 11, max 25 per patient | about all (each record differs) | 497 with W8-2 option A (shortlist); about 900 with option B (two calls per GP decision) | 4.1 (A) to 7.5 (B) |
| Same, nurse node only (GP stays on the table) | 96 | about 96 | 96 | 0.8 |
| Norway check, one pass of 100 patients: `observed` + `optimal` (`stokstad.yaml`) | 346 + 277 | 120 + 84 | about 204, then later seeds mostly from the cache | 1.7 |

The table policy's decision counts are a proxy: a JEV policy can make paths longer or shorter. A calibration grid or a
sensitivity sweep multiplies the Norway passes but not the distinct requests much (see below). Concurrency stays 1; the
GPU's own time (about 3.4 s warm) is not the limit, the gateway is. The gateway's 120 an hour is shared with the live
demo page, so a background run during judging would starve the demo.

What the numbers hide:

* **Norway with the JEV is weak evidence today.** The flowchart decisions reach the model with almost nothing visible:
  the request is "Patient in Finnish primary care (synthetic). Background: age 68." with no evidence items (the
  flowchart `PatientView` carries no record), so distinct requests are just (node, age) pairs and the framing is wrong
  for a Norwegian hospital pathway. The model would choose PET timing or a sampling route from age alone. A useful
  Norway-with-JEV run first needs the flowchart's visible attributes and history rendered as evidence, and its own
  case text; otherwise it measures the prompt, not the model.
* **The encounter loop is blocked at the GP node** (24 actions vs 16) until WP-W8-2. Option B doubles the calls.
* Encounter runs through `--jev birch` (`pathway_sim/training_export.py`) wrap the backend in a plain `BackendPolicy`,
  so the model gets the context-derived evidence, not the rendered record that `policy_for_world` / the walk send
  (`pathway_sim/` is not ours to change; flag for its owner).

**Most informative within the limits, for the pitch:** a paired encounter run on one cohort and seed, table vs JEV,
with the JEV at every node once WP-W8-2 lands: about 30 patients stratified towards lung cancer (about 150 calls with
option A, about 1.3 hours; about 2.5 hours with B), reporting days to referral for the cancer patients, tests ordered
and referrals of the worried well, each beside the table's number. It shows the model deciding on records, which is the
claim (D51), and fits one evening. Tonight, before W8-2, the nurse-only version (100 patients, about 96 calls, under 1
hour) is feasible but says little (3 options, first contact only). Skip Norway-with-JEV until its requests carry the
visible record. Whether any of these counts as "bulk cohort inference" is the owner's call (question (a) below); with
the owner's key the authenticated endpoint has no gateway limit.

## Questions for the JEV owner (WP-W8-1 T5, posted on the channel 14 Nov)

(a) Does D64's unlimited use conflict with "no bulk cohort inference": may a 100 to 400-patient automated run go through
the gateway, or must it use the authenticated endpoint? (b) Can the rate limit be raised for a named run? (c) Is a
rationale (`record_note`, D49) available from `/reason` for pathway requests, and at what cost in seconds? (d) Will the
endpoint stay up after submission, and until when? Answers: not yet.

## Not done / unclear in the API

* No rationale yet (the owner may add one inference-side; read if present, see above).
* Concurrency: the gateway runs one job at a time with at most 3 accepted; we send one at a time.
* The record text per visit repeats the findings (the "found" line and the structured history); about 1 KB per item.
  Leaving it as `record_text` renders it.
