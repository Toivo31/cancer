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

- [ ] **Contract first (T1, within ~45 min):** the decision-table format for `nurse_encounter` /
      `gp_encounter` decisions committed with a small example in `scenarios/finland_encounter_policy.yaml`
      and posted as STATUS (WP-C8-3 fills its numbers). Lean: reuse the existing stub-table /
      `decision_policy.points` machinery (`jev/stub.py`, `pathway_sim/policy.py`) with conditions
      written as safe expressions (`pathway_sim/expr.py`) over record facts such as
      `found.cough_3wk`, `last.chest_xray.abnormal`, `episode`, `encounters`, `age`.
- [ ] **I1:** the policy receives a `PatientView` whose new `record` is a `patient_engine.record.Record`;
      a test asserts nothing hidden reaches the policy (spy policy walks what it receives for condition
      ids, `caused_by`, card ids; same idea as `tests/test_pe_reveal.py`).
- [ ] **Loop:** a scripted policy that always orders a test already done shows repeated attempts with
      fresh results (beyond `max_attempts` too, once WP-C8-2 lands; until then cap and mark the test xfail);
      the patient keeps looping until the horizon; outcome `undiagnosed_at_horizon` (test).
- [ ] **Treatment follows truth:** with a policy that always treats with antibiotics, pneumonia-only
      patients resolve and leave; cancer patients return (test on a small library).
- [ ] **Hand-over:** `refer_*` enters the hospital flowchart's referral node; time to treatment is
      measured from first contact; hospital results appear in the record.
- [ ] **Determinism (I2) and same results across policies (I3)** (tests).
- [ ] **Golden checks unchanged:** `scripts/gate.sh` passes (Norway and Finnish headline untouched).
- [ ] Fast tests under 30 s; a full 2 000-patient run under 60 s (measure and report).

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
| [ ] | C8-1-T1 | Decision-table format + example, STATUS posted | committed, posted |
| [ ] | C8-1-T2 | Runtime: arrival, encounters, gathers, decisions, record entries | loop test |
| [ ] | C8-1-T3 | Orders with resources and result arrival; review encounters | test |
| [ ] | C8-1-T4 | Treatment, discharge, return, give-up, horizon | treatment test |
| [ ] | C8-1-T5 | Hand-over to hospital flowchart; outcomes and per-group report; CLI | end-to-end command |
| [ ] | C8-1-T6 | `docs/encounter_loop.md`: how it works, what is assumed, how to run | file |

## Report (builder fills in)
