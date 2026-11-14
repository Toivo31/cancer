# C8 Encounter loop (primary care)

| | |
|---|---|
| Decided | D44 to D48, Tuomas, 14 Nov evening |
| Code | `pathway_sim/encounter.py` (new), hooks in `pathway_sim/engine.py`; contracts in `patient_engine/record.py` (`record/1`) and `patient_engine/care.py` (`care/1`) |
| Depends on | C1 cards, cohorts and the reveal handle; C2 catalogue plus `care.yaml`; C4 policy interface; the existing hospital flowchart |
| Track | Sunday submission (there is no later track, D45) |
| Readable overview | the doc "How the pathway simulation works" (section "Primary care") |

## Why

The current Finnish primary-care chain answers yes or no with probabilities that depend on the
patient's true condition, so clinicians effectively see the hidden diagnosis; it has no record, no
role differences and no loop. The evidence on inequality points at primary care (vague symptoms
explained by an ordinary illness), so this is where the model must be realistic.

## Behaviour

```
arrival (first contact: nurse or GP, behaviour.first_contact)
  └► ENCOUNTER(role)
       1. gather: every test in role.gathers is done now; its next attempt is revealed,
          only role's outputs are written to the record (`found`, plus the observation)
       2. decide: decision point "<role>_encounter", options = role.actions; the policy sees
          the record only; one action is chosen
       3. act:
          order      → the test is booked on its resource; its result arrives after
                       service + report time as a `result` entry, then a review
                       ENCOUNTER with the ordering role
          treat      → `treatment` entry; hidden side: each condition the treatment resolves
                       goes to its resolved state with p after days; review ENCOUNTER after review_days
          book       → ENCOUNTER with that role after the role's booking lead (urgent or routine)
          follow_up  → ENCOUNTER with the same role after days
          refer      → `referral` entry; the patient enters the hospital flowchart at its
                       referral node; hospital results are appended as `hospital` entries
          discharge  → `discharge` entry; episode ends. If any symptom persists in the patient's
                       current (hidden) state: return with p return_if_persisting after
                       return_delay_days, as a new episode (`return` entry, first contact again);
                       else the patient leaves. give_up_per_episode ends the loop at any discharge.
  stops at: tissue/definitive diagnosis and treatment start (hospital chain), leaving
  (no persisting symptoms, or gave up), or horizon_days (outcome `undiagnosed_at_horizon`)
```

Rules:

1. **Information boundary (I1).** Decision nodes, the JEV request and any text shown before scoring
   are built from `Record` only. `RevealHandle.truth_for_scoring` is called only from scoring code.
2. **Repeated tests.** Attempt k of a test is attempt k on the card. Beyond the card's `max_attempts`
   the reveal handle draws a fresh result from the catalogue's accuracy with a keyed random number
   (seed, patient, test, attempt, state), so a patient can loop indefinitely and results stay
   reproducible (I2, I3).
3. **States.** A card has one state per combination of resolved co-existing illnesses (C1, D40).
   Treatment changes the state (hidden). Findings caused only by a resolved condition disappear;
   gathers and tests then reveal the new state's values.
4. **Definitive tests (D46).** Each condition has one test whose output measures that condition's
   own hidden marker (`dx_<condition>`): slow, scarce, expensive. Cost, turnaround and capacity come
   from the catalogue and the world; a world setting `cost_scale` multiplies costs (visible).
5. **Worried well (D47).** A catalogue condition with independent symptom probabilities and no
   objective findings.
6. **The hospital part stays as it is** (Norway check untouched); hospital steps whose test maps
   to a catalogue test read the card through the handle, others keep their current behaviour, and
   the residual truth-conditioned steps there are listed as a known weakness.
7. **Outputs per patient**: time to referral, to diagnosis, to treatment; number of encounters by
   role; tests ordered and their cost; treatments given and whether they matched the truth; episodes;
   outcome. Aggregated by patient group (age band, sex, smoking, region).

## Work packages (wave 3, in `docs/plan/packages/C8/`)

| WP | What | Model |
|---|---|---|
| WP-C8-1 | Engine: encounter runtime, record writing, orders, treatments, returns, horizon, hand-over, run outputs | Opus |
| WP-C8-2 | Cards: states for treatment, fresh attempts beyond `max_attempts`, gather of an output subset, definitive markers, worried well in the reference generator | Sonnet |
| WP-C8-3 | Care content: `catalogue/lung-primary-care/care.yaml`, definitive tests, worried-well condition, costs, turnaround, capacities, first decision tables, with research | Sonnet |
| WP-C8-4 | Record to JEV request and record view: `jev` context from a `Record`, contract test; record text for the flow page | Sonnet |
| WP-C1-5 | Model-written cards (authors G1, G2), offline with the fake client | Sonnet |

Wave 4: tune decision tables to plausible Finnish primary-care rates and report; results page and
patient record in the demo; audit (WP-C1-7); pitch numbers.
