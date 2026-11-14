# WP-C8-1: Encounter loop in the simulator

| | |
|---|---|
| Component | C8 `docs/plan/components/C8-encounter-loop.md` (read it first: behaviour and rules) |
| Size | M–L (one long wave) · Model: Opus |
| Needs | merged on `overnight/sim`: `patient_engine` (cards, cohorts, `RevealHandle`, `record.py`, `care.py`), `catalogue/lung-primary-care`, the hospital flowchart in `scenarios/finland_lung.yaml` |
| Provides | `pathway_sim.encounter` runtime; a runnable Finnish encounter scenario; per-patient record and outcomes in the run log; the encounter decision-table format |
| Owned paths | `pathway_sim/encounter.py` (new), `pathway_sim/engine.py` (hooks only), `pathway_sim/policy.py` (add an optional `record` to `PatientView`, nothing else), `pathway_sim/documents.py` / scenario loading only if a new node kind needs it, `pathway_sim/__main__.py` (a flag), `scenarios/finland_encounter.yaml` (new), `scenarios/finland_encounter_policy.yaml` (new; you publish the format, WP-C8-3 fills numbers later), `tests/test_encounter*.py`, `docs/encounter_loop.md` (new) |
| Do not edit | `patient_engine/` (WP-C8-2 owns reveal/reference; ask on the channel), `catalogue/` (WP-C8-3), `jev/` (WP-C8-4), existing scenarios |
| Review required | yes: I1 (information boundary), golden checks |

## Outcome

`python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 2000 --seed 1`
runs patients drawn from a reference-generated library of `catalogue/lung-primary-care` through the
encounter loop (C8 "Behaviour") and, after referral, the existing Finnish hospital steps; prints
outcomes (share treated within the target, time to referral/diagnosis/treatment, encounters per
patient by role, tests and cost per patient, treatments matching or not, undiagnosed at horizon) and
the same by patient group. Each patient's `record/1` is in the run log.

## Acceptance

- [x] **Contract first (T1, within ~45 min):** the decision-table format for `nurse_encounter` /
      `gp_encounter` decisions committed with a small example in `scenarios/finland_encounter_policy.yaml`
      and posted as STATUS (WP-C8-3 fills its numbers). Lean: reuse the existing stub-table /
      `decision_policy.points` machinery (`jev/stub.py`, `pathway_sim/policy.py`) with conditions
      written as safe expressions (`pathway_sim/expr.py`) over record facts such as
      `found.cough_3wk`, `last.chest_xray.abnormal`, `episode`, `encounters`, `age`.
- [x] **I1:** the policy receives a `PatientView` whose new `record` is a `patient_engine.record.Record`;
      a test asserts nothing hidden reaches the policy (spy policy walks what it receives for condition
      ids, `caused_by`, card ids; same idea as `tests/test_pe_reveal.py`).
- [x] **Loop:** a scripted policy that always orders a test already done shows repeated attempts with
      fresh results (beyond `max_attempts` too, once WP-C8-2 lands; until then cap and mark the test xfail);
      the patient keeps looping until the horizon; outcome `undiagnosed_at_horizon` (test).
- [x] **Treatment follows truth:** with a policy that always treats with antibiotics, pneumonia-only
      patients resolve and leave; cancer patients return (test on a small library).
- [x] **Hand-over:** `refer_*` enters the hospital flowchart's referral node; time to treatment is
      measured from first contact; hospital results appear in the record.
- [x] **Determinism (I2) and same results across policies (I3)** (tests).
- [x] **Golden checks unchanged:** `scripts/gate.sh` passes (Norway and Finnish headline untouched).
- [x] Fast tests under 30 s; a full 2 000-patient run under 60 s (measure and report).

## Things to weigh

- Where the loop lives: a new node kind inside the flowchart engine (resources and queues shared with
  the hospital part) vs a separate pre-phase that hands patients to `simulate` at referral. The first is
  more faithful (GP and X-ray capacity are real queues); the second is simpler. Decide, record why.
- Resources: nurse, gp, lab, xray, the definitive-test resources. Capacities and costs will come from
  WP-C8-3 (`catalogue/lung-primary-care/care.yaml` and a resources fragment it writes,
  `scenarios/finland_encounter_resources.yaml`); start with clearly marked placeholders.
- Hidden side: the engine may read the `Card` (via `Cohort.card(i)`) to apply treatment effects and
  decide whether symptoms persist; only the policy side is restricted.
- Card states: until WP-C8-2 lands, reference cards have one state; implement the transition with a
  function you call (`next_state(card, resolved)`) and a test that is skipped until multi-state cards exist.
- Clinician notes in `Entry.note`: short templates ("CXR clear, treated as infection, review 2 wk").
- Keep the old `finland_lung.yaml` flowcharts byte-for-byte working.

## Tickets

| | ID | Ticket | Done when |
|---|---|---|---|
| [x] | C8-1-T1 | Decision-table format + example, STATUS posted | committed, posted |
| [x] | C8-1-T2 | Runtime: arrival, encounters, gathers, decisions, record entries | loop test |
| [x] | C8-1-T3 | Orders with resources and result arrival; review encounters | test |
| [x] | C8-1-T4 | Treatment, discharge, return, give-up, horizon | treatment test |
| [x] | C8-1-T5 | Hand-over to hospital flowchart; outcomes and per-group report; CLI | end-to-end command |
| [x] | C8-1-T6 | `docs/encounter_loop.md`: how it works, what is assumed, how to run | file |

## Report (builder fills in)

Builder: claude-code@tuomas/c8-engine, branch `w3/c8-engine`, commits a8ac898 (T1 format) .. HEAD; merged
`overnight/sim` at 0badc5f (D49). Gate PASS (fast 1067 passed, contracts 49, golden 5).

**How to run**

```
python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 2000 --seed 1 [--out runs/enc.json]
python -m pytest -q tests/test_encounter.py          # 14 fast tests ~5 s; 1 slow (CLI, ~5 s)
```

How it works: `docs/encounter_loop.md`.

**Timings** (this machine, other agents running): 2 000 patients 4.3-7.5 s end to end (library of 600
reference cards generated once per process ~1 s); fast encounter tests ~5 s.

**Decisions**

1. *Where the loop lives:* inside the flowchart engine's event loop, as a subclass
   `EncounterSimulation(Simulation)` with three hooks added to `engine.py` (`new_run`, `on_arrive`,
   `on_event`; default behaviour unchanged). Primary care and hospital share one heap and the same
   `server` resources, so GP, X-ray and CT are real queues for both. Chosen over a pre-phase because it is
   no more code than a pre-phase plus a hand-over, and queues are shared for free.
2. *Hospital part:* the `baseline` flowchart of `finland_lung.yaml` is cut at `referral_in`
   (`hospital_subflowchart`): that node and its descendants, foreign dependencies dropped, entry guard
   removed. Old flowcharts and scenarios untouched.
3. *Hospital results:* CT and PET-CT read the card (attempt numbering continues from primary care, I3);
   other hospital steps keep finland_lung's per-condition probabilities via `condition_map` (lung cancer
   with haemoptysis -> `lung_cancer_site`). Every hospital step is a `hospital` record entry. A hospital
   discharge returns the patient to primary care as a discharge with advice.
4. *Decision-table format* `encounter_policy/1` = the stub-table shape; conditions over record names with
   dots (`found.cough`, `last.chest_xray.abnormal`, `attempts.chest_xray`, `reason`, ...). `pathway_sim.expr`
   has no attribute access, so dots are rewritten to `__` before parsing (outside quotes).
   `record_names(record)` is a pure function of the `Record` (I1); `reason` is derived from the record
   (prior encounter's action kind / entries since). Optional `working_diagnosis` per row (added for D49).
5. *Policy sees:* `PatientView` with `record` = record so far + this encounter (action None); `group`,
   `attributes`, `history` empty; `patient_id` the cohort index; `record.patient_id` the handle's `P000042`.
6. *D49:* `choose_with_note(policy, view, options)` helper and `NotingPolicy` protocol in `policy.py`; the
   engine appends an `assessment` (author `<role>_encounter/<backend>`) after the encounter entry. The table
   policy returns `{plan: "{action}", working_diagnosis?}` and a note naming the rule; the engine fills
   `{action}` with the chosen action's label (the policy returns probabilities, so only the engine knows it).
7. *Draws:* action ~ probabilities with `uniform(seed, patient, "enc", encounter_count)`; treatment success
   and timing keyed by (treatment, condition, times given); natural course keyed per condition; return,
   give-up and delay keyed per episode. Same seed -> byte-identical log (test).
8. *Timing (Tuomas via architect):* gathers are inside the visit (take the role's slot); every order books
   the test's resource (`Test.resource_kind`) with its lead and queue, then catalogue service and report
   time; reveal at end of service; result entry; review encounter booked with the urgent lead
   (`encounters.review_urgency`).
9. *Natural course:* care/1 has no field for illnesses ending by themselves (without it, viral coughs never
   end). Added a world block `natural_course` (placeholder) incl. `unexplained` for symptoms no condition
   causes. Persisting symptoms are computed by the engine from first-state findings and `caused_by`.
10. *Outcomes:* `treatment`, `left_resolved`, `left_with_symptoms`, `undiagnosed_at_horizon`; patients in
    the hospital chain are not cut at the horizon. Per-group report: age band, sex, smoking, region.
11. *Library:* reference cards generated per condition (`library: {per_condition: 60, seed: 1}`), written
    with `write_library` to a temp dir (real content-hash id, reported) or `library: {path}` for a stored one.
12. *Placeholder care model* in `scenarios/finland_encounter_care/care.yaml`, used only while the catalogue
    has no `care.yaml`.
13. *Shared tests:* `tests/test_documents.py`, `tests/test_validate.py`, `tests/test_expr.py` treated every
    `scenarios/**/*.yaml` as a flowchart scenario; changed to skip YAML without `flowcharts` (FYI posted).
    Outside my owned paths; necessary for the encounter files in `scenarios/`.

**Outcomes, one run** (`--n 2000 --seed 1`, placeholder tables and care, before WP-C8-2):
26 cancers: treated 62%, within 90 d 23%; median days to referral 36, diagnosis 72, treatment 98; 10
cancers left with symptoms (missed). Per patient: nurse 0.9, GP 2.9 encounters, 1.8 episodes, 0.9 tests,
321 EUR; treatments 0.4 per patient, 4.5% matching the truth; 24% referred (465 non-cancer). Outcomes:
left_resolved 1121, left_with_symptoms 827, treatment 16, undiagnosed_at_horizon 36. With w3/c8-cards
merged (trial, not committed) the run has 0 fallback reveals and the xfail test passes.

**Placeholder** (WP-C8-3 to replace): care model, decision-table numbers, encounter resources and
capacities (gp_appt 160/day, nurse 60, lab 200, pathology, mri), visit costs, natural course, review
urgency, no-advice return factor.

**Depends on other lanes**

* WP-C8-2 (`w3/c8-cards`): already used when present: `states.next_state` (import-guarded) and
  `RevealHandle(card, catalogue=)` (TypeError-guarded). Until merged: single-state fallback, xfail test,
  skipped resolved-state test. Trial merge: all 17 encounter tests pass.
* WP-C8-3: `catalogue/lung-primary-care/care.yaml` (picked up automatically; its action ids must match the
  table or the world refuses to load with a list of problems), `scenarios/finland_encounter_resources.yaml`
  (merged over the world's `resources`, top-level `resources:` or a flat mapping), table numbers,
  `natural_course` numbers.
* WP-C8-4: a JEV `BackendPolicy` with `choose_with_note` can be passed as `run_encounter(policy=...)`; the
  CLI `--jev` flags are refused for encounter worlds (not wired).

**Known weaknesses**

* Residual truth-conditioned hospital steps (specialist visit, bronchoscopy, needle biopsy, board).
* One action per encounter; reviews are full visits with the urgent lead.
* No warm-up: queues start empty; utilisation is over the arrival window (45 days at n = 2 000), so the
  hospital resources look idle.
* About 26 cancers per 2 000 patients at catalogue prevalence: cancer numbers are noisy; use larger n or a
  `prevalence:` override in the world.
* Hospital entries for non-card steps carry `{"result": true/false}` only.
* A stale hospital `done` event after a hospital discharge is ignored only while the patient is back in
  primary care (a re-referral in the same instant could in theory see it; not observed).

