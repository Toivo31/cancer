# Junction 2026 master plan: decision model and pathway optimiser for cancer diagnostics

Exported from the Claude doc on 14 Nov 2026 · Tuomas. Figures from the original doc are described in text.

## 1. Goal and idea

**Goal:** Shorten the time from a patient's first contact to diagnosis and the start of treatment (National cancer strategy Goal 3). We also allow testing of fast-track lanes and early detection (Goal 2), and fast diffusion of new diagnostic tools and tests (Goal 4).

**Idea:** A decision model with our own JEV architecture proposes the next step at every node of a configurable flowchart of the diagnostic pathway. An optimiser then tests whether a different flowchart would be faster.

**Three core advantages that are unlocked** (figure in the original doc), all resting on a shared flowchart that standardises care, so quality depends less on which doctor a patient meets:

| Use | What it does |
|---|---|
| Second opinion | Shows the doctor what the model would recommend, catching outliers and outdated practice |
| Automation framework | Interprets a step's result once the step itself, such as sampling, is automated |
| Pathway optimisation | Tests whether another order of steps or a fast track shortens time to treatment |

## 2. The challenge and the evidence

**Brief:** AstraZeneca asks for an AI system that identifies a gap in cancer care, locates it in the pathway and recommends what to do. It requires a source for every claim, at least one Goal 3 indicator, actionable proposals and a working demo.

The national cancer strategy has four main goals, and our project touches three of them. Goal 3, equal and effective care, is the required one and our primary target. Its indicators are that survival in poor-prognosis cancers reaches the Nordic level, which for lung cancer means more than 14 percentage points, that cancer mortality falls by 10 percent, and that patients reach treatment within target times. We measure the last one directly. Goal 2, prevention and early detection, is an additional target, through testing of fast-track lanes and earlier diagnosis. Goal 4, we target by standardizing the care decisions, as our model can recommend a novel treatment, test, or diagnostic for a doctor that he was unaware of. We can also to some effect simulate addition of new solutions to the network.

**Evidence on time gap:** Finland takes longer than the other Nordic countries to diagnose cancer. Lung cancer is the clearest case, and it is also where Finnish survival lags furthest behind. In Finland, 40 to 60 percent of patients with lung symptoms first see a nurse, while elsewhere in the Nordics they see a doctor. Fewer than 10 percent of Finnish primary care units could perform CT scanning, against about 90 to 100 percent elsewhere in the Nordics (IHE 2026; *corrected 14 Nov: the source says 'perform', not 'order directly'; we found no source on direct ordering*).

The delay does not always arise in the same place. In one study from Satakunta, the referral took about two weeks, but the diagnosis took almost two more months, so most of the delay was in specialist care.

**Why reordering helps:** Changing the order of steps in the pathway is one of the easiest ways to cut these times, because it needs no new equipment or staff. A better order eases queues at scarce tests. Fast tracks get the most urgent cases through first. And catching outlier decisions prevents the worst missed or late diagnoses. A Norwegian study supports this: reordering the tests alone would have doubled the share of patients treated on time, from 40 to 80 percent.

**Finland is slower at most steps of the lung cancer pathway** (*14 Nov: at the diagnosis step Sweden equals Finland; the figures are survey modes, not measured waits*) (typical waiting time in days; IHE Cancer Dashboard Finland 2026, citing Khalife et al. 2025):

| Step | Finland | Denmark, Norway, Sweden |
|---|---|---|
| Health centre appointment | 14 days | 2 to 7 days |
| Specialist consultation after GP | 14 to 28 days | 7 to 14 days |
| Diagnosis after specialist | 28 days | 14 to 28 days |

**Reordering doubles on-time treatment; a faster PET scan alone barely helps** (early-stage lung cancer patients starting treatment within 42 days, one Norwegian centre; Stokstad et al. 2019):

| Scenario | Share within 42 days |
|---|---|
| Observed pathway | 40% |
| Faster PET scan only (7 days) | 48% (not statistically significant) |
| Reordered steps, faster PET | 80% |

**Capacity versus order:** The same Norwegian study separates the two levers. During the study the median time from PET-CT referral to report was 20.5 days, and a new scanner later cut that wait to 7 days or less. Re-timing the patients with only the shorter PET wait raised the share treated on time from 40 to 48 percent, a gain that was not statistically significant. Changing the order of the steps, with the same shorter PET wait, raised it to 80 percent. Adding capacity at one bottleneck barely helped, while reordering doubled the result without new equipment or staff.

**More evidence:** The Norwegian result is not an isolated case. In England, a hospital cut the wait from an abnormal chest X-ray to CT from 15 days to 3, yet the time to a treatment decision stayed at 66 versus 65 days, because the later diagnostic and staging steps were unchanged. A review of radiotherapy simulations makes the same point: more machine capacity does not help if an earlier step limits the flow. Where the whole pathway was redesigned, times fell. A Norwegian county hospital cut time to treatment by about 8 days with a local diagnostic algorithm and by about 15 days with national pathways. A Toronto clinic that ordered tests before the first visit cut referral to diagnosis from 39.9 to 28.1 days. The Royal Free in London cut referral to treatment from 66 to 29 days, and a Welsh simulation found that a first visit within 7 days would remove about 10 to 12 days, and that combining it with daily testing and next-day reporting would remove about 20 to 22 days (England et al.; *corrected 14 Nov, the earlier 'about 11 days' mixed scenarios; the PubMed link below may point to a different paper*).

**Limits of reordering:** Some tests are genuinely undersized, as a London study found for imaging and endoscopy, and no reordering fixes that. Fast tracks can also lengthen waits for other patients who need the same resources, a concern raised in Sweden. The simulator therefore reports waits for all patients, not only those with cancer, and treats more waiting for others as a guardrail.

**Where queues build up:** The core insight we want the demo to show is that time is lost mostly in queues, not in the tests themselves. A queue forms wherever patients arrive faster than a step can serve them, and a late or out-of-order referral makes it worse. To answer the brief directly, every flowchart node belongs to one of the brief's four stages: detection in primary care, referral to specialist care, diagnosis, and treatment start. For each stage the simulator separates waiting time from service time and shows which stage, and which step within it, holds most of the waiting. This locates the gap the way the brief asks, and it shows which change shortens it.

## 3. The decision model

A Jev-type model takes a state and a typed question and returns a probability for every option in one pass. It is not a language model. In a plain dot-product design each option is scored separately. Our correction model, a trained transformer, sees all options and adds a correction vector to the context embedding at each layer before the dot product.

**Claims to demonstrate:** A second question on the same context costs about half the compute, and the model can compare options with each other. Both need a plain dot-product baseline, ideally on a public benchmark.

**In this project:** The context is the patient's history plus the newest piece of information, which may be a test result, a sample result, a doctor's note or a nurse's description of symptoms. The options are the next steps the flowchart allows at that node.

Architecture (figure in the original doc): patient context → context embedding → correction model (sees every option, adds a correction vector at each layer) → dot product against the allowed next steps → proposed next step with a probability for every option; a doctor decides. A second question on the same context reuses the embedding, at about half the compute.

## 4. Flowchart, model and optimiser

The three parts have separate jobs, which lets us say what each one contributed. The flowchart holds the steps, the allowed orders and the time limits. Each node is one step in the diagnostic process, such as a first visit, a test, a sample or a consultation. A person configures the flowchart, so the process stays under human control.

The decision model picks the next step at each node from the options the flowchart allows, and it does not change the flowchart. The optimiser reads a finished run and proposes a changed flowchart, such as a different order of tests or a new fast-track route, and the same patients run again.

System loop (figure in the original doc): synthetic patients → flowchart ⇄ decision model → run log (what each step revealed, waiting times, queues) → four metrics, and run log → optimiser → variant flowchart to rerun.

## 5. Data

All data is synthetic. There is no real patient or decision data. Each patient is generated from a true condition: cancer, a non-cancer condition commonly confused with cancer, or nothing serious. Symptoms and the results of every possible test are drawn from that condition using each test's sensitivity and specificity. Cancer is kept realistically rare, because otherwise every aggressive pathway looks good and false positives cost nothing.

A patient card holds the starting information, the truth about cancer, and all test results as hidden variables. Most results are negative and unrelated to cancer, and a few point towards cancer when the patient has it. Some cancers are quick to diagnose and others need many alternatives ruled out first. Because every result exists in advance, a rerun can reveal different results in a different order for the same patient. Error rates, waiting times and capacities are to come from published figures. To avoid overfitting we generate test and training datasets with the synthetic data.

## 6. Simulator and optimiser

**Simulator:** Each step reveals some hidden variables with an error rate, takes time and uses a resource. Capacity is fixed and queues form dynamically. Scarce final diagnostic tests and treatment lanes sit behind intermediate steps that filter out healthy patients and sort the rest. The number of tests, lanes and their capacities are configurable; an example configuration might have about ten final tests and two treatment lanes. Capacities start as rough values and are calibrated later. There is one flowchart, one region and no simulated doctors.

**Optimiser:** It uses revealed information only. The typical question is whether test D should have come first when A, B and C were negative and D gave the diagnosis. Answered patient by patient, this misleads. D was only run on patients who had failed A to C, those negatives may be what kept D's queue short, and D may be slow, scarce or invasive.

The optimiser therefore works on patient groups and estimates which test is expected to yield most for a given context. Steps that resolve non-cancer patients count as value. If nine of ten patients are resolved at the first test, that step was a good call whatever happened to the tenth. A change is kept only if a full rerun shortens time to treatment. The proposed guardrails, not yet decided, are no more missed cancers and no tests beyond capacity.

## 7. Demo and validation

**Demo:** Generate patients, run a starting flowchart, let the optimiser propose a change, rerun the same patients, re-run with unseen test dataset, and compare the numbers: time to treatment, share within target, cancers missed and tests per patient.

**Validation:** An improvement inside our own simulator proves little, so we check the optimiser against a published case. A Norwegian study of 100 early-stage lung cancer patients reports the observed pathway step by step. We rebuild that pathway as a flowchart (CT, first hospital visit, bronchoscopy or needle biopsy, PET-CT, exercise test, weekly tumour board, treatment) and set its waiting times from the paper, for example a median of 20.5 days from PET-CT referral to report and 4.5 days from sampling to pathology report. We then generate about 100 matching patients and check that the run reproduces the observed result: only 40 percent started treatment within the 42-day target, with a median of 46.5 days. That is the calibration step. (*42 days is the Norwegian target; Finnish targets in IHE 2026 are assessment within 21 days of referral. We use 42 days for comparability and say so.*)

Next the optimiser searches without being told the authors' solution. It passes if it finds a similar reordering, with PET-CT and the exercise test ordered at the first visit, a tumour board straight after them, and sampling done while treatment is booked, and if it lands near the authors' 80 percent. The paper gives most of the inputs. Its 80 percent is itself a model estimate rather than an observed result, and all of its patients already had cancer, so the check covers specialist care but not primary care filtering.

**Deadline:** Sunday 15 November at 10:00, with a working demo, a two-minute video and a pitch deck.

## 8. Judging criteria and how we fit them

### Actionability (30%)

Optimiser. The platform suggests how to reduce time-to-diagnosis or time-to-treatment through process changes. These could be new pathway lines (for example a fast track), different decision heuristics and a new order of steps, and simulates each change.

### Insight (25%)

Dynamic simulation. It shows where queues build up across the brief's four stages (detection, referral, diagnosis, treatment start), lets us test different ways to relieve them, and points to the hidden bottlenecks where a targeted capacity increase would help most.

### Data quality and transparency (20%)

**OPEN, needs thinking.** Our data is synthetic, and we say so. The system is built to run on real data, and calibrating against the Norwegian study shows it can reproduce a real, published pathway.

### Execution (15%)

A strong point. A cinematic intro video with a retro-recon-renaissance aesthetic and a flowchart command-centre look, then a live demo of the flowchart platform, the optimiser, and a full simulation run on synthetic patients.

### Clarity (10%)

To be refined in a dedicated UI session. Basic principles:

- **One message per screen:** the first screen answers "what should we change, and what does it gain".
- **Number first:** share treated on time today against with the change, in large type.
- **Plain words:** no internal terms such as node, optimiser or embedding.
- **Show where, then what:** the stage where time is lost, then the change that fixes it.
- **Test it:** walk a non-technical person through it in under two minutes before judging.

## 9. Open questions

The first two block a first run or the pitch.

1. **First run:** what produces the starting flowchart and the first logs, given no simulated doctors?
2. **Equity gap:** remember to tie the theme also to reducing inequality in treatment.
3. **Training signal:** what is the decision model trained on in the demo?
4. **Long-run capacity:** do we allow adding capacity to a test to solve a queue?
5. **Expected value:** how is a test's expected yield estimated from revealed data only? How does the optimization work?
6. **Invasive and costly tests:** how is their cost represented?
7. **Non-cancer patients:** how are steps that resolve healthy patients credited?
8. **Hindsight bias:** how do we avoid judging a late test by patients who already failed earlier ones?
9. **Guardrails:** what are the limits for missed cancers and tests, and what is the target time?
10. **Treatment before diagnosis:** early treatment, or a reserved slot while tests finish?
11. **Preventive care:** in basic healthcare, can we generate risk scores that might accelerate high-risk patients to specialist care or cancer diagnostics faster?
12. **Architecture proof:** which node shows that comparing options matters, and against which baseline?
13. **Parameter sources:** which published figures feed the simulator?
14. **Scope:** lung cancer only, or several cancers?

## 10. Build status and decisions taken (overnight 14 to 15 Nov)

Code is on branch `overnight/sim`; how to run it is in `README.md`. Provisional decisions, each easy to change, are listed in `docs/decisions.md` (D1 to D13). Items marked *provisional* need a team call.

- **Flowchart format** (*provisional*): a DAG with required, any-of and optional prerequisites, guards on revealed results, choice nodes and exits. A linear sequence cannot express the Norwegian optimal pathway, which is mostly parallel ordering. See `docs/architecture.md`.
- **Resources** (*provisional*): `server` for capacity queues (Finland), `delay` for published wait distributions (the Stokstad check, as the authors re-timed patients), and `batch` for the weekly tumour board.
- **Open question 1, first run** (*provisional*): a hand-written starting flowchart plus a rule policy. Observed practice variation in the Stokstad data (late PET referral and similar) is reproduced as a "mix" at choice nodes.
- **Open questions 5, 7 and 8, optimiser** (*provisional*):
  - Proposals are scored from revealed timestamps only: which prerequisite held each step back, and by how many days.
  - Proposals are accepted only if a rerun of the same patients, with common random numbers, is faster.
  - Results are reported on held-out patients.
  - Proposals can be biased (hindsight, selection), but acceptance is an exact counterfactual on the same patients. In real life that acceptance step is a pilot.
- **Open question 9, guardrails** (*provisional*): no more missed or untreated cancers, at most 2 percent more tests or invasive procedures, at most 2 percent fewer tissue-confirmed diagnoses, and no longer exit times for patients without cancer.
  - The tissue-confirmed guardrail was added after the optimiser tried "skip tissue sampling" to save time.
  - The scenario also lists clinical needs, for example "the tumour board needs PET-CT", that no change may break.
  - *Update 14 Nov, review:* the tissue-confirmed guardrail is now active in Finland too (bronchoscopy and needle biopsy are marked as confirming). In the Norwegian check the missed-cancer guardrail is vacuous, because every patient has cancer and there is no discharge exit.
- **Validation result** (`docs/validation.md`):
  - Calibrating only the observed pathway reproduces the observed 40 percent. It then *predicts* 78 to 86 percent for the authors' pathway (published 80 percent) and their 16 percent drop in sampling procedures.
  - It over-predicts "faster PET only": 55 to 67 percent against the published 48 percent.
  - The blind optimiser, given the faster scanner as the authors were, finds their three changes:
    1. the tumour board before sampling;
    2. PET-CT always ordered on time;
    3. the exercise test ordered early.
  - It also finds a fourth change: planning tissue sampling when the referral is triaged, before the first hospital visit (before a specialist has seen the patient). That needs a clinical check.
  - This reaches 88 percent on held-out patients. Without new equipment it reaches 67 percent.
  - *Disclosures (review M3, M7):* the 80 percent "prediction" carries the calibrated observed practice of ordering PET-CT at referral triage into the authors' pathway; with PET-CT ordered only at the first visit the simulated authors' pathway gives 66 percent. The search chose from a menu of about 70 single changes that included each of the authors' changes as one edit, and was not told which ones the authors made.
- **Decision model** (`decision_model/README.md`):
  - On a task where the right answer depends on the set of options, the correction model beats a parameter-matched dot-product model: 84.5 against 79.0 percent accuracy (78.3 percent is the smaller d=32 dot-product model).
  - The "half the compute for a second question" claim was *not* reproduced at our model sizes. Only the context embedding is cached, so a second question costs 76 to 91 percent of the first.
  - *Update 14 Nov, wave 2:* the model now runs inside the simulator at the sampling-method choice. It is trained from a random-exploration log on revealed outcomes only (reward = usable result − days/30, a value judgement, D25).
    - On the Norwegian scenario it rediscovers the location rule (central → bronchoscopy, peripheral → needle biopsy) and ties with it.
    - On Finland it first sent most patients to the shortest-looking queue and overloaded it (on time 21% → 1–3%). Once it can see queue state, it matches the rule.
    - Insight for the pitch: a model that optimises each patient separately harms the shared system unless it can see the queues.
    - Dot-product and correction models show no difference yet, because no scenario varies which options are on offer. *Open question 12 result:* in a built case where an option's value depends on another option (a needle-biopsy rescue sharing a queue), the correction model learns the comparison with enough data (12k training patients) and the dot-product model cannot at any size. The gain is small (+0.02 reward, no on-time gain), and a dot-product model with a hand-written summary of the offer does about as well. The correction model's real advantage is that it needs no hand-written set features. Details are in `decision_model/README.md`.
- **Wave 2 optimiser** (D22 to D24):
  - A change must help in each of two training cohorts.
  - No presentation group may get slower or less often on time.
  - A two-step lookahead lets it accept pairs of changes that only help together.
  - Norway: the same four changes as before; held-out 60% → 88%, selection optimism 1.7 points.
  - Finland (after review B1, fast track excluded from the search): two reorders survive, "reserve the treatment slot when the case is sent to the tumour board" and "book the specialist visit as soon as the referral arrives". Held-out within 90 days 18% → 33%, median 102 → 94 days, no new equipment, missed cancers unchanged.
  - The earlier 61% ("urgent booking for every referred patient") is a **conditional finding**: it gives the same lead reduction to everyone, so the gain is exactly the assumed gap between routine and urgent booking leads. With 0 / 50 / 100% of the assumed reduction the share is 18 / 44 / 61%. Never present it as the headline or as a fast lane.
  - "GP first instead of nurse first" did not pass the safety checks on the training patients (half a missed cancer more per cohort, one patient in one cohort). On unseen patients it looked neutral to positive (fewer missed, but it trips the equity guardrail), so the rejection is noise-level and it needs a paired test with more cohorts.
- **Sensitivity** (`docs/sensitivity.md`):
  - Norway: reorder beats observed in 80 of 80 joint draws of the unsourced parameters, with a gain of +32 to +48 points.
  - Finland: the direction holds but the size is uncertain by about 10 points. These runs compare the hand-written order-together pathway, not the two accepted reorders or the urgent-booking variant.
  - Reordering alone, against a capacity-matched control, gives about +20 points. It turns negative if CT or PET-CT is one slot short.
  - The Finnish equity gap comes entirely from our detection assumptions, not from Finnish data. Claim it only as "in our synthetic county, under these assumptions".
- **External check** (`docs/external_checks.md`): the UK rapid-CT pattern is reproduced. Moving the CT earlier cut X-ray to CT result from 29 to 9 days, but X-ray to tumour board decision stayed at 61 days.
- **Evidence corrections** found by the pitch track are marked *corrected 14 Nov* in sections 2 and 7 above. The full list is in `docs/pitch/evidence_brief.md`.

## 11. Risks

**Missing the brief:** The output might need to read also as a sourced, national-level recommendation that names the equity gap, not only as a technology demo.

**Credibility:** An improvement in our own simulator proves little without the Norwegian check, and the architecture is invisible without a dot-product baseline at one node.

**Scope and wording:** Only the optimisation loop fits the time. The clinician approves every proposal, the data is synthetic, and a treatment slot is reserved while tests finish.

## 12. Platform direction (set by Tuomas, 14 Nov)

The end goal is an online platform, not only a hackathon demo: build your own flowchart, attach JEV to its decision points, train JEV on your dataset, run the simulation, optimise the flowchart and rerun.

- **JEV arrives as an API attached to the graph.** At each decision point it gets the revealed context and the options on offer, and returns a probability per option. Until it exists, a stub with hardcoded probabilities per decision point stands in behind the same contract.
- **What exists becomes the engine.** `pathway_sim` and `optimiser` are reused as libraries. The lung scenarios become the first two templates. `decision_model/` becomes one optional backend, not the JEV itself.
- **Plan, specs and tickets** are in `docs/platform/` (`README.md`, `specs/01` to `07`, `tickets.md`). Milestone M1 (JEV in the graph) is built on branch `plat/jev`: the `jev/` package (contract, `BackendPolicy`, stub with probability tables, HTTP client and stub server, local and rule backends), engine decision modes, CLI flags `--jev`, `--decision-mode`, `--set`, and contract tests. See `docs/architecture.md` (Policy, JEV).
- **The simulator no longer always takes the most likely option.** The engine asks the policy for probabilities and, in `sample` mode (the platform default, fork F2 provisional), draws the choice with the common-random-number uniform `(seed, patient, "mix", node)`, so a patient makes the same choice in every flowchart variant; `argmax` is switchable per run. Rule-based policies return one-hot probabilities and are unaffected: every shipped scenario reproduces its previous metrics exactly through the stub.
- **Open forks F1 to F7** (what counts as a decision point, sample or most-likely, the JEV contract and its owner, web stack, hosting and data, the cut for Sunday, `standardise` under JEV) are listed with leans in `docs/platform/README.md` section 5 and need a team call.

## Sources

- [National Cancer Strategy 2026 to 2035, Finland](https://www.iccp-portal.org/sites/default/files/2026-02/National_Cancer_Strategy_2026-2035_Finland.pdf): Goal 3 indicators and targets.
- [IHE Cancer Dashboard Finland, 2026](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf): Nordic waiting times, CT access, stage data gaps, treatment uptake.
- [University of Helsinki on the Nordic lung cancer comparison](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa): first contact with a nurse, slower access.
- [Stokstad et al. 2019, BMC Health Services Research](https://link.springer.com/doi/10.1186/s12913-019-4517-z): the Norwegian pathway study used as the validation target.
- [Mattila 2025, diagnostic delay in Satakunta](https://www.utupub.fi/handle/10024/180618): where the delay arose in one Finnish region.
- [Hanna et al. 2020, BMJ](https://www.bmj.com/content/371/bmj.m4087.abstract): mortality per four weeks of treatment delay.
- [HSSIB report on lung cancer missed on chest X-ray](https://hssib.org.uk/patient-safety-investigations/missed-detection-of-lung-cancer-on-chest-x-rays-of-patients-being-seen-in-primary-care/investigation-report): about one in five missed.
- [Smith et al. 2022, British Journal of General Practice](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8714520/): share of urgent referrals that turn out to be cancer.
- [Scotland's optimal lung cancer diagnostic pathway](https://rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/lung-cancer): a national pathway built on bundled, parallel tests.
- [Jev Decision Index coverage](https://aiweekly.co/alerts/jev-decision-index-ranks-30-open-weight-decision-models): the public benchmark for decision models.
- [Rapid CT access under England's optimal lung pathway, ERJ 2023](https://publications.ersnet.org/content/erj/62/suppl67/pa1123): faster CT, unchanged time to treatment decision.
- [Laerum et al. 2020, Norwegian county hospital](https://core.ac.uk/download/479092742.pdf): local and national pathway redesign.
- [Standardised triage with pre-ordered tests, Toronto](https://pmc.ncbi.nlm.nih.gov/articles/PMC7564135): referral to diagnosis 39.9 to 28.1 days.
- [Royal Free lung pathway, Pulse](https://pulsetoday.co.uk/?p=30344): referral to treatment 66 to 29 days.
- [England et al., Welsh lung pathway simulation](https://www.pubmed.gov/36760877/): about 11 days removed.
- [Radiotherapy pathway simulation review](https://salford-repository.worktribe.com/OutputFile/2660286): capacity does not help behind a rate-limiting step.
- [Cooke et al. 2022, London simulation and optimisation](https://discovery.ucl.ac.uk/10165787/1/1-s2.0-S277244252200034X-main.pdf): real capacity shortages in imaging and endoscopy.
- [Swedish cancer pathways, staff interviews](https://link.springer.com/doi/10.1186/s12913-019-4413-6): risk of longer waits for other patients.
