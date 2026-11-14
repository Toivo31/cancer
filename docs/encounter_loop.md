# The primary-care encounter loop (C8, WP-C8-1)

Finnish primary care in the simulator is no longer a fixed chain of yes/no steps whose probabilities
depend on the patient's true condition. Nurses and GPs now hold **encounters**: they find things out,
write them into the patient's record, and choose an action using only that record. What happens to the
illness (does the antibiotic work, does the cough go away) follows the hidden truth on the patient's card.
A referral hands the patient to the existing, calibrated hospital part of `scenarios/finland_lung.yaml`.

```
python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 2000 --seed 1 [--out runs/enc.json]
```

Prints the outcomes (cancers treated, within the target, days to referral / diagnosis / treatment, encounters
per patient by role, episodes, tests and cost per patient, treatments matching the truth, outcomes) overall and
by patient group (age band, sex, smoking, region). `--out` writes the run log with every patient's `record/1`.
About 8 s for 2 000 patients.

## Files

| File | What |
|---|---|
| `pathway_sim/encounter.py` | the runtime: world loading, library and cohort, `EncounterSimulation`, decision tables, record names, outcomes, CLI |
| `scenarios/finland_encounter.yaml` | the world (`encounter_world/1`): catalogue, care model, decision tables, hospital hand-over, placeholder resources, natural course |
| `scenarios/finland_encounter_policy.yaml` | decision tables (`encounter_policy/1`), format in the file header |
| `scenarios/finland_encounter_care/care.yaml` | PLACEHOLDER care model, used only while `catalogue/lung-primary-care/care.yaml` is absent (WP-C8-3) |
| `scenarios/finland_encounter_resources.yaml` | capacities from WP-C8-3; merged over the world's `resources` when present |
| `tests/test_encounter.py` | information boundary, loop, treatment, hand-over, I2, I3, CLI |

Engine hooks (`pathway_sim/engine.py`): `new_run`, `on_arrive`, `on_event`. They keep the old behaviour
exactly (the golden checks pass); the encounter simulation is a subclass of `Simulation`.

## How a patient moves

1. **Arrival** = first contact (the clock starts). Nurse or GP by `behaviour.first_contact`, booked on the
   role's resource (`care.yaml roles[].resource`, a `server` in the world). The booking lead and the queue
   are the wait.
2. **Encounter.** The visit takes the role's slot. Every test in the role's `gathers` (history, examination)
   is done inside the visit: its next attempt is revealed and only the role's outputs reach the record
   (`found`, plus the observation with `positive`). The patient's own complaints (presenting `reported`,
   still present) are listed in `reported`.
3. **Decision** at point `<role>_encounter`: the policy gets a `PatientView` whose `record` is the record so
   far plus this encounter with `action` still None (`attributes`, `history` and `group` are empty). The
   policy may answer with `choose_with_note` (probabilities, a note, an assessment, D49) or `choose`. The
   action is drawn from the probabilities with `uniform(seed, patient, "enc", n)`, n = the patient's
   encounter count. The engine appends the encounter (mechanical log, author `engine`) and, if the policy
   gave words, an `assessment` entry authored `<point>/<backend>`. The table policy writes a template
   (`working_diagnosis` when the rule has one, `plan` = the chosen action).
4. **Action** (`care.yaml actions[].kind`):
   * `order`: the test is booked on its resource (`Test.resource_kind`) with that resource's lead and
     queue, then takes the catalogue's `service_days` and `report_days`. The result is revealed at the end
     of service, arrives as a `result` entry, and opens a review encounter with the ordering role.
     Ordering a test already done gives its next attempt.
   * `treat`: a `treatment` entry; hidden side, each true condition the treatment `resolves` ends with p
     after days (keyed draws). Review encounter after `review_days`.
   * `book` (other role, routine or urgent lead), `follow_up` (same role after `days`).
   * `refer`: `referral` entry, hand-over (below).
   * `discharge`: the episode ends. The patient returns as a new episode (`return` entry, first contact
     again) if a symptom persists at the time they would return (`return_delay_days`), with probability
     `return_if_persisting` (times `no_advice_return_factor` for a discharge without advice), unless they
     gave up (`give_up_per_episode`). Otherwise they leave.
5. **Reviews** after a result, a treatment or a follow-up are booked with the urgent lead
   (`encounters.review_urgency`, placeholder).
6. **Ends**: `treatment` (hospital chain), `left_resolved` (no persisting symptom), `left_with_symptoms`
   (did not return or gave up; for a cancer this is a missed cancer), `undiagnosed_at_horizon` (still in
   primary care at `horizon_days` after first contact). Patients in the hospital chain are not cut at the
   horizon.

## Hidden side

* **State.** Conditions end by treatment or by their `natural_course` (world block, placeholder: care/1 has
  no field for it). The state at time t is `patient_engine.states.next_state(card, resolved)` (WP-C8-2).
  `unexplained` in `natural_course` ends symptoms that no condition causes.
* **Persisting symptoms**: symptom variables whose finding is true and not caused only by resolved
  conditions (uncaused ones persist until `unexplained` resolves).
* **Results**: attempt k of a test in state s is `RevealHandle(card, catalogue=...).reveal(test, k, s)`, a
  pure function of the card (I3): the same patient gets the same result for the same (test, attempt, state)
  under every policy. Before WP-C8-2 a refused request (state not served, attempt beyond `max_attempts`)
  falls back to the last stored attempt of the first state with resolved findings read as absent, and the
  run reports how often (`fallback_reveals`).

## Hand-over to the hospital

`hospital.flowchart` (`baseline` of `finland_lung.yaml`) is cut at `hospital.entry` (`referral_in`): that
node and everything downstream are kept, dependencies on primary-care nodes removed. Hospital and primary
care share one event loop and the same resources (X-ray, CT, ...). An urgent referral fast-tracks the
patient (`urgent_referral_priority`). Hospital steps whose test maps to a catalogue test (`card_tests`: CT,
PET-CT) read the card through the handle, continuing the attempt count from primary care; the others keep
`finland_lung`'s condition-dependent probabilities, with the catalogue condition mapped by `condition_map`
(lung cancer with haemoptysis -> `lung_cancer_site`). Every hospital step is appended to the record as a
`hospital` entry. A hospital discharge sends the patient back to primary care as a discharge with advice.
Time to referral, diagnosis (the flowchart's `diagnosis` milestone) and treatment count from first contact.

## Decision tables

`scenarios/finland_encounter_policy.yaml`, format in its header: per point a `default` row and `rules`
(`when`, `probs`, `source`, `note`, optional `working_diagnosis`); same shape as the stub tables. Conditions
are `pathway_sim.expr` expressions over the names `record_names(record)` builds from the record alone
(`found.cough`, `last.chest_xray.abnormal`, `attempts.chest_xray`, `reason`, `episode`, ...; dots are
rewritten to `__` before parsing). `EncounterTablePolicy.problems(care)` checks every action against the
role's actions; the world refuses to load otherwise.

## Assumptions and weaknesses

* Placeholders everywhere (WP-C8-3 replaces): the care model, decision-table numbers, encounter
  capacities and costs, natural course, review urgency, no-advice return factor.
* Residual truth-conditioned hospital steps: specialist visit, bronchoscopy, needle biopsy, board and the
  admin steps still draw from `finland_lung`'s per-condition probabilities.
* One action per encounter (a GP cannot order X-ray and bloods together); reviews are full visits.
* Queues start empty and there is no warm-up cut (2 000 patients at 44 a day is 45 days of arrivals), so
  waits are optimistic; utilisation is over the arrival window.
* The cohort follows the catalogue's prevalence: about 1.3% lung cancer, i.e. ~26 cancers in 2 000
  patients. Cancer numbers from one 2 000-patient run are noisy.
* JEV flags (`--jev`) are not wired for encounter worlds yet; a JEV-backed policy can be passed to
  `run_encounter(policy=...)` (it reads `view.record`; WP-C8-4).
