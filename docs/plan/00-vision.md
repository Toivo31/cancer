# L0 Vision

Source: Tuomas's direction on 14 Nov 2026 (three messages: the platform loop, "the flowchart
simulation is the main thing", and the synthetic patient engine). Where this file interprets
instead of quoting, it says so under "Assumptions to confirm".

## One sentence

A platform where a care pathway is drawn as a flowchart, realistic synthetic patients flow through
it, a decision model sits at every decision point, and an optimiser finds a better pathway and
better decision criteria, using only what the pathway itself revealed about each patient.

## The loop

```
   ┌──────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
   │ 1 PATIENTS   │     │ 2 PATHWAY    │     │ 3 DECISIONS   │     │ 4 SIMULATE   │
   │ synthetic    │────►│ flowchart of │────►│ at each node: │────►│ patients     │
   │ cards with   │     │ steps that   │     │ probabilities,│     │ advance;     │
   │ hidden truth │     │ REVEAL facts │     │ matrix, JEV   │     │ facts are    │
   └──────────────┘     └──────────────┘     └───────────────┘     │ revealed     │
          ▲                                                         └──────┬───────┘
          │              ┌──────────────┐     ┌───────────────┐            │
          └──────────────│ 6 RERUN on   │◄────│ 5 OPTIMISE    │◄───────────┘
            same cards   │ same patients│     │ order + rules │   run log: what was
                         └──────────────┘     └───────────────┘   revealed, when, waits
```

1. **Patients.** Each synthetic patient has a hidden primary condition (a cancer, another common or
   uncommon illness, or healthy), background information, and hidden variables derived from the
   condition: symptoms, findings, and the result every available test would give for this patient.
   Together this is the **patient card**.
2. **Pathway.** A flowchart whose nodes are real healthcare steps: a visit, bloodwork, a scan, a
   tissue sample, a board meeting. A step that performs a test **reveals** one or more hidden
   variables, with realistic accuracy (true and false positives, measurement noise, failed samples).
3. **Decisions.** At a decision node something chooses the next step. For the MVP: fixed
   probabilities or a simple decision matrix over revealed facts. Later: JEV, the team's decision
   model, behind the same interface.
4. **Simulate.** Patients arrive, queue for limited resources, and advance. Only what has been
   revealed so far can influence any decision.
5. **Optimise.** Change the order of steps and the decision criteria at each node so that patients
   reach the right treatment sooner, without missing more cancers, within capacity.
6. **Rerun** on the same patients, then on patients the optimiser never saw, and compare.

## Principles (these outrank convenience)

1. **The information boundary is sacred.** Hidden truth never reaches a decision, the decision
   model, the optimiser's proposals, or any text a decision-maker reads. It is used only to
   generate observations and to score outcomes afterwards. Tests enforce this.
2. **Numbers come from sources, text comes from the language model.** Every probability, accuracy
   and timing is in a catalogue with a source or the word `assumption`. A language model may write
   a patient's story and may draft catalogue entries for human review. It never sets a number that
   the simulation uses without that number being recorded and graded like any other.
3. **Same patients, different pathway.** Every comparison reruns identical patients with identical
   random draws, so a difference is caused by the change and not by luck.
4. **Reproducible from a few values.** A cohort is fully described by (catalogue version,
   generator version, settings, seed, size). A run by (cohort, flowchart version, decision policy,
   seeds).
5. **Honest about what is simulated.** Synthetic data only. Simulated results are labelled.
   Negative results are kept.
6. **The flowchart simulation is the product's main screen** (decision D31). Reports are secondary.
7. **Contracts before code.** Components talk through written, versioned contracts with tests.
   Anything behind a contract can be replaced (stub by JEV, template text by a language model).

## Who it is for

- Now: the Junction 2026 judges (AstraZeneca challenge "Equal Care Across Finland"), who score
  actionability 30, insight 25, data quality and transparency 20, execution 15, clarity 10.
- After: people who plan care pathways (a wellbeing services county, a hospital district) and the
  team's own research on the JEV decision architecture.

## Two horizons

| Horizon | Deadline | What counts |
|---|---|---|
| **Submission** | Sun 15 Nov 2026 10:00 Helsinki | A working demo (the flowchart simulation, offline-safe), the video, the pitch. Only what is green and frozen in time goes in |
| **Platform** | after the hackathon | The full loop above, with the patient engine, the decision layer and the optimiser in their general form |

The patient engine described in `components/C1` and `C2` is a platform-horizon component. It can
enter the submission only if it passes its validation gate before the freeze
(`02-execution-strategy.md`, "Two tracks").

## Non-goals (for now)

- Real patient data in any form.
- Clinical advice. The system proposes changes to a pathway for people to evaluate; it does not
  treat anyone.
- Modelling treatment outcomes or survival. The clock stops at the start of treatment.
- More than one disease area at once. Lung-symptom presentations first; the catalogue format must
  not prevent others.
- Training the real JEV. It arrives as an API from its owner.

## Assumptions to confirm (Tuomas)

These are my readings of the direction. Each is used as written until corrected. Answer on the
agent channel with type `DECIDED`, or tell the architect session.

| # | Assumption | If wrong, what changes |
|---|---|---|
| V1 | One primary condition per patient. Other illnesses appear as background (comorbidities), not as a second primary | C1 sampler and C2 catalogue get a joint-condition model |
| V2 | The first catalogue covers adults presenting to primary care with chest or general symptoms where lung cancer is one possibility among common illnesses and healthy people | C2 scope |
| V3 | The language model writes text (history, nurse note, referral letter) from already-sampled structured facts, and can draft catalogue entries for review. It does not sample conditions, symptoms or results | C1 generation pipeline |
| V4 | Clinician judgements that are modelled today as noisy "tests" (nurse assessment, GP decision to image) become real decision nodes with a decision matrix over revealed facts. This settles fork F1 as option (b) | C3, C4 and the Finnish scenario |
| V5 | The optimiser's goal is time from first contact to start of treatment for patients who have cancer, under guardrails: no more missed cancers, capacity respected, no group worse off. Cost and harm of tests are reported and can be made constraints | C5 objective |
| V6 | Disease state does not change while a patient waits in version 1 (a result is the same whenever the test is done). The design must allow progression later | C1 observation model |
| V7 | The patient engine is built on the platform track and does not block the Sunday submission | Execution strategy |
| V8 | The language model is reached the way Eemeli's classifier already does it: any OpenAI-compatible endpoint through `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | C1 narrative adapter |
