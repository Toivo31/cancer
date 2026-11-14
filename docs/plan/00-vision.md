## Decided by Tuomas (14 Nov)

| # | Decision | Where it lands |
|---|---|---|
| D39 | The language model generates all patient card data and the results of tests | C1 (pipeline, libraries, audit), principle 2 |
| D40 | One primary condition per patient; a patient may also have an ordinary illness next to a cancer. After treatment some symptoms disappear; if others persist the patient returns to the start of the pathway | C1 (states, causes of findings), C3 (treatment step, episodes) |
| D41 | Clinician judgements are nodes, tests are nodes, and every point where a decision is made is a decision node modelled by JEV. Settles fork F1 as "every judgement is a decision point" | C3, C4 |
| D42 | The patient engine is part of the Sunday submission (my reading of "yes it does"; correct me if you meant the opposite) | C1 "Sunday slice", execution strategy |

## Assumptions to confirm (Tuomas)

Used as written until corrected.

| # | Assumption | If wrong, what changes |
|---|---|---|
| V2 | The first catalogue covers adults presenting to primary care with chest or general symptoms where lung cancer is one possibility among common illnesses and healthy people | C2 scope |
| V5 | The optimiser's goal is time from first contact to start of treatment for patients who have cancer, under guardrails: no more missed cancers, capacity respected, no group worse off. Cost and harm of tests are reported and can be made constraints | C5 objective |
| V6 | No disease progression while waiting in version 1. State changes only through treatment (D40) | C1 states |
| V8 | The language model is reached the way Eemeli's classifier does it: any OpenAI-compatible endpoint through `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | C1 client |
| V9 | The engine, not the model, decides which condition each patient has and how many of each (the cohort's design); the model writes everything that follows from it | C1 roles |
| V10 | Whether a single test result is a miss or a false alarm is drawn by the engine from the catalogue's rates and written up by the model (`guided`), because models do not draw calibrated random numbers. The alternative (`free`) is built too | C1 "Error rates" |
| V11 | Headline numbers stay on the calibrated generator until a model-written library passes its audit; model-written patients are shown as patients first | C1 "Honesty" |
