# Prompts of the model-written card pipeline (WP-C1-5)

One file per role and version: `<role>.v<N>.system.md` and `<role>.v<N>.user.md`. `$name` in a file is
filled from the card's skeleton and the catalogue (`string.Template`; write `$$` for a literal dollar).
A change of wording is a new version (`g1_patient.v2.*`) and a new entry in
`patient_engine/authors.py:PROMPT_VERSIONS`; the version is stored in every card's `provenance.prompts`
and in the library manifest, so libraries made with different wording stay distinguishable.

| Role | Version id | Files | Writes |
|---|---|---|---|
| G1 patient author | `g1@1` | `g1_patient.v1.*` | findings with causes, what the patient reports, the patient's account |
| G2 result author | `g2@1` | `g2_results.v1.*` | every test result (status, values, report) following the error plan, and a GP note |
| G2 result author | `g2@2` (default) | `g2_results.v2.*` | report wording only, for values the engine decided, and a GP note |

`g2@2` (review w7 B1). A prompt whose text reaches the revealed side may hold only what a reader of that text has.
`g2@1` told the model the hidden findings and each attempt's planned outcome, and the wording gave the plan away
(half of false alarms hedged). `g2@2` is built by `authors.results_user` from public inputs only (age, sex, smoking,
reported symptoms, each attempt's status and values); it is in `reveal.SAFE_RESULTS_PROMPTS`. A new result-author
version joins that set only when it keeps this property and the audit's `report_wording` check passes on a library
made with it. `g2@1` stays selectable (`Authors(cat, "g2@1")`, `results_prompt=` in the pipeline) for comparison;
its reports never reach a decider.

Rules both prompts follow: English text, synthetic patients only, no real names or places (the region
field is the only place), notes and reports do not name the hidden diagnosis.
