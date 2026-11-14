# The team's decision model (checkpoint 1138, "Birch") in the encounter loop

WP-W5-1. Code: `jev/birch.py` (backend and policy), `jev/walk.py` (step-through tool), `jev/birch_mock.py`
(local mock of the API, tests and offline demo), registered in `jev/factory.py`. Tests: `tests/test_jev_birch.py`.
The model's owner's kit is `decision_api/` (we do not edit it).

## The owner's constraints, in plain words

* Send only what a clinician could see: visible information, the question and the allowed choices. Never a hidden
  diagnosis, a future result, a gold label or an earlier model score.
* No bulk cohort inference, no health polling, no keep-alive, no per-frame calls. The model costs money while its
  GPU is allocated. (14 Nov: the GPU runs nonstop while the demo is live, so live per-decision calls are fine then; the
  budget and the cache stay as guards.)
* The model proposes, a person decides. Its scores are relative to the offered list, not disease probabilities, test
  sensitivities or time estimates, and are never used as such.
* Warm calls take about 5-7 s, a cold start about 6 minutes. A failure stays visible: no silent fallback to saved or
  invented answers. No automatic retry of a POST.
* The key stays on the proxy (`BIRCH_API_KEY` or `BIRCH_API_KEY_FILE`); our code never sees it.

## Start the proxy, walk a patient

```bash
# terminal 1 (the owner shares the key out of band; never commit it)
BIRCH_API_KEY_FILE=/private/path/to/key python -m decision_api.server     # http://127.0.0.1:8771, no GPU starts until a call
# terminal 2
python -m jev.walk                                # a random patient (same as --pick random); the seed is printed, repeat with --pick-seed N
python -m jev.walk --pick cancer                  # or pneumonia, worried_well; Enter accepts a proposal, or type an id or number
python -m jev.walk --pick cancer --placeholder    # also show the placeholder decision table's numbers
python -m jev.walk --pick pneumonia --auto-accept --max-calls 20
python -m jev.walk --library DIR --patient 3      # a patient of a stored library (index or card id)
python -m jev.walk --pick cancer --auto-accept --jev mock   # no model, no key: a local mock (about 2 s)
python -m jev.walk --pick cancer --jev table      # the placeholder tables only
```

A cold model can take 6 minutes: the first call fails after the proxy's 145 s with "Model may still be starting"; the
walk stops with that message. Retry the command (answers already received are in the cache). After two failed calls in a
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
| Disk cache `runs/jev_cache/<hash>.json`, key = hash of the request without the case id (the same record never costs twice, across runs). Only answers from the model itself are cached and served; a `calls.jsonl` ledger lists live calls | `BirchBackend` |
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
pol = policy_for_world(world, max_calls=400)            # about 4 calls per patient: 100 patients
log = run_encounter(world, 100, seed=1, policy=pol)
print(pol.run_summary())
```

Label such a run "model policy, n=100 (budgeted), proposals not reviewed". The engine draws the action from the
scores (they are not sharpened), so the numbers describe a sampling policy; use the walk for reviewed decisions.

## Not done / unclear in the API

* No rationale yet (the owner may add one inference-side; read if present, see above).
* Concurrency limit of the endpoint is unknown (default 1, at most 4).
* The record text per visit repeats the findings (the "found" line and the structured history); about 1 KB per item.
  Leaving it as `record_text` renders it.
