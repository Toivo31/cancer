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

Rules both prompts follow: English text, synthetic patients only, no real names or places (the region
field is the only place), notes and reports do not name the hidden diagnosis.
