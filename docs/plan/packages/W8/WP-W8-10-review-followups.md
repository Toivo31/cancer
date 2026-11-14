# WP-W8-10: Leftovers from review w8 and 04-status "Known problems" that had no ticket

| | |
|---|---|
| Component | C1 patient engine (audit, pipeline, population), C4 decision layer |
| Status | not started |
| Size | S each, except T4 (M) |
| Needs | `w8/g2blind` merged (it fixed review w8 B1, M1, M2 and touches `authors.py`, `pipeline.py`, `validate.py`, `reveal.py`, `skeleton.py`) |
| Owned paths | `patient_engine/audit.py`, `catalogue/lung-primary-care/audit_tolerances.yaml` (not hashed), `patient_engine/pipeline.py` (T4 only), `populations/lung_primary_care.yaml` (T5 only), `jev/stub.py`, `pathway_sim/policy.py` (T7 only), tests for each |
| Do not edit | `catalogue/lung-primary-care/` hashed files, prompts |
| Review required | T5 and T6 yes (labels and numbers) |
| Track | T1 before freeze if a lane is free (it helps WP-W8-4 step 2); the rest after submission |

Source: `docs/review_w8_fixes.md` (on `w8/g2blind`; merged with it) sections M3, Minor 1 and 2, Q7; `docs/plan/04-status.md`
"Known problems". Items fixed by `w8/g2blind` (B1, M1, M2) and by `w8/verify` (M3 script part, M4) are not repeated.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | W8-RF-T1 | Audit check `design_coverage`: accepted cards per primary condition against the manifest's design counts, plus discards and failures by condition from `generation_report.json` (review w8 Q7 c) | S | – | fails when a condition is more than the tolerance (start at 5 points, in `audit_tolerances.yaml`) off; test with a library missing half of one condition; passes on `ref500` |
| [ ] | W8-RF-T2 | Audit check `report_condition_words`: naive Bayes on report words against value-only text, label = primary condition, within test and output (same code path as `report_wording`) (review w8 Q7 a) | S | – | test with a fake library whose reports name the condition fails; `ref500` passes |
| [ ] | W8-RF-T3 | Audit check `null_truth_values`: no reported value where the measured variable is null unless the output's `only_if` holds (review w8 Q7 b; guards M2 from coming back) | S | – | count must be 0 on `ref500` after `w8/g2blind`; a planted phantom value fails (test) |
| [ ] | W8-RF-T4 | Pipeline: a resumed run retries cards that failed on endpoint errors (from the cache) instead of only the partial library (review w8 M3, pipeline part; the script only warns today) | M | – | test with a fake client that fails 10% of calls once: after `--resume` the library has every designed card; answered calls are not re-sent |
| [ ] | W8-RF-T5 | Population file labels: `lung_cancer` age ratios and `tuberculosis` entries marked `source: assumption` (cited sources support incidence and notification, not age) (review w8 Minor 1) | S | – | labels changed; population hash pin and its tests updated in the same commit; note which library ids change, if any |
| [ ] | W8-RF-T6 | Sex has no effect except through smoking (lung cancer 49% male vs about 60% in Finland) (review w8 Minor 2) | S | a source for the sex ratio by condition | either a sourced sex ratio in the population model with the check in `background_realism`, or a documented "not modelled" line |
| [ ] | W8-RF-T7 | When a standardised option is not on offer, rule and stub policies differ (first option against uniform) (04-status Known problems) | S | – | one documented behaviour, the same in both, with a test that offers a list without the standard option |
| [ ] | W8-RF-T8 | Align the JEV demo's GP preset with the simulator's GP reduction once WP-W8-2 lands (today it is a hand-picked 8 in `demo/export_jev.py` `GP_SUBSET`) | S | W8-JG-T2 | preset request equals what `BirchPolicy` sends at that visit (test) |
| [ ] | W8-RF-T9 | Agent decisions from first-wave reports are only partly in `docs/decisions.md` (04-status Known problems) | S | – | integrator: one pass over `docs/platform/tickets.md` reports; missing decisions added or listed as "not a decision" |
