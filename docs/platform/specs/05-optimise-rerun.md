# Spec 05: Optimise and rerun

Milestones M2 (API), M4 (browser). Depends on specs 01 to 03. Open fork: F7.

## Purpose

Expose the existing optimiser (`optimiser/`) through the service so a user can ask for suggested
changes, see why each was suggested, accept some, and rerun. The method does not change:

1. Run the current flowchart on training patients.
2. Score candidate changes from what the records revealed (timestamps, results, choices; never
   the hidden condition).
3. Rerun the same patients with the best candidates; accept a change only if it is faster in every
   training cohort and passes the safety checks.
4. Report before and after on patients the search never saw.

## What exists and what is added

| Exists (`overnight/sim`) | Added |
|---|---|
| `search(scenario, start, Config)` returning accepted changes with evidence, train and held-out metrics, changes blocked by safety checks, the new flowchart | A job wrapper with progress per step |
| Change kinds: `detach`, `relax`, `standardise`, `fast_track` | Settings exposed in the API; kinds can be switched off |
| Safety checks: missed and untreated cancers, tissue-confirmed diagnoses, tests and invasive procedures per patient, waits for patients without cancer, no group worse off | Thresholds exposed as settings with today's defaults |
| Whole result or nothing | `apply_changes(world, flowchart, changes, accept=[…])`: apply a chosen subset in order, revalidate, return the new version or the problems |
| Plain-language label per change (`demo/export.py`) | Label generation moves into `optimiser/` so the API returns it |

## API

```json
POST /api/projects/{p}/optimisations
{"flowchart": {"id": "baseline", "version": 3},
 "allow": ["detach", "relax"],
 "n": 18800, "train_seeds": [101, 102], "heldout_seeds": [301, 302],
 "max_changes": 6,
 "safety": {"tests_tolerance": 0.02, "equity": true}}
→ 202 {"optimisation_id": "o_17", "job_id": "j_52"}

GET /api/projects/{p}/optimisations/o_17
{"status": "succeeded",
 "changes": [{"index": 0, "kind": "relax", "label": "Book the specialist visit as soon as the referral arrives…",
              "records_reading": "In the records, the step … was held back by …: on average 6.1 days per patient",
              "train": {"on_time_before": 0.18, "on_time_after": 0.23},
              "heldout_after_this_change": {"on_time": 0.24}}],
 "blocked": [{"label": "…", "gain_pp": 2.6, "blocked_by": ["more missed cancers"]}],
 "heldout": {"before": {…metrics…}, "after": {…metrics…}},
 "selection_optimism_pp": 0.4,
 "proposed_flowchart": {…document…}}

POST /api/projects/{p}/optimisations/o_17/apply  {"accept": [0], "rerun": true}
→ {"flowchart": {"id": "baseline", "version": 4}, "run_id": "r_9a01"}
```

Accepting a subset can invalidate a later change that depended on an earlier one (two changes
accepted together by the lookahead). `apply` then returns `409` with the dependency, and the UI
keeps those two switches linked.

## Behaviour with JEV attached

- The training runs, the acceptance reruns and the held-out runs all use the flowchart's decision
  policy unchanged. With `mode: sample` the common-random-number draw keeps each patient's choices
  identical across variants wherever the probabilities are identical, so a measured gain comes from
  the structural change.
- If a structural change alters what JEV sees at a decision (for example the decision now happens
  before a result is known), JEV's probabilities change too. That is a real effect of the change,
  and it is reported: each change lists the decision points whose average probabilities moved.
- `standardise` ("always choose X here") overrides a decision point. With hardcoded probabilities
  that is a legitimate suggestion ("stop the variation"). With a JEV model attached it competes
  with the model. Fork F7; lean: off by default when any decision point uses a non-stub source.
- `fast_track` applied to every patient only swaps booking times for the assumed urgent ones
  (review finding B1). It stays available but is reported as a conditional finding, not as a
  suggested change, unless the world reserves urgent slots.

## The rerun and the comparison

"Rerun" means: the new version on held-out seeds, next to the parent version on the same seeds.
The comparison shows the headline (on-time share, median days), the safety numbers (missed
cancers, tests per patient), each patient group, and where the waiting moved. It states how many
patients and seeds it is based on.

Honesty line shown with every optimisation result, as on the dashboard today: suggestions come from
what a clinic's records would show; acceptance reruns the same simulated patients, which in real
life is a pilot; the numbers shown are from patients the search never saw.

## Build order

1. `apply_changes` with subset and linked changes; tests (M2-7).
2. Change labels and `records_reading` returned by the library (M2-7).
3. Job wrapper, API, settings (M2-7).
4. Decision-probability movement per change; `standardise` rule under JEV (M4-5).
5. Browser: suggestions, blocked list, diff, apply and rerun (M4-1..4).

## Not in this spec

Suggesting capacity changes ("one more slot here"): the capacity probe exists in `demo/export.py`
and moves into the platform in M8. Optimising JEV itself (retraining to improve outcomes) is
spec 06 and decision D25.
