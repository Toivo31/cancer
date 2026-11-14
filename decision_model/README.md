# decision_model: Jev-type correction model vs dot-product baseline

Pure numpy (torch could not be installed in the build environment), with a small
reverse-mode autograd in `autograd.py`, checked against finite differences in the tests.
Not a language model: it takes a patient context and a set of candidate next steps and
returns one probability per option in a single pass.

## What it is

- `DotProductModel`: `logit_i = <f(context), g(option_i)>`. Each option is scored alone.
- `CorrectionModel`: the same, but before the dot product the context embedding goes through
  L correction blocks. Each block is attention from the context embedding over the whole option set,
  residual-added to the context embedding (`c <- c + Wo * attn(c; options)`). The score of an option
  can therefore depend on the other options offered.
- `encode_context(ctx)` is a separate call that depends on the context only. A second question on
  the same context reuses its result (`predict_proba(c0, opts, mask)`); `ModelPolicy` caches it.
- `tasks.py`: synthetic comparison task and the RunLog adapter. `policy.py`: `ModelPolicy.choose(view, options)`
  per `docs/architecture.md`; reads group, age, history, t_now only (a test checks hidden fields are ignored).
  Optionally (`attr_vocab`, `option_vectors`, `elapsed="t_now"`) it also reads the view's *revealed* attributes
  and per-option features; that is how it runs inside the simulator (next section).

## What it shows (measured, `python -m decision_model.benchmark`, ~90 s, seed 0)

Comparison task: pick the next test by a context-dependent value (sensitivity before a positive finding, specificity after),
discounted by wait (more heavily the longer the patient has waited) and invasiveness (older / non-specific patients),
but only among options at least as informative (sens + spec) as the *average of the options offered*. The set-relative
rule changes the correct answer in about a third of cases. Control task: same without that rule.

| Task | Model | Params | Test accuracy | Test log-loss |
|---|---|---|---|---|
| comparison (set-relative rule) | Dot-product (d=32) | 5568 | 0.783 | 0.519 |
| comparison (set-relative rule) | Dot-product, wider (param-matched) | 19328 | 0.790 | 0.510 |
| comparison (set-relative rule) | Correction (2 layers) | 13760 | 0.845 | 0.375 |
| control (no set-relative rule) | Dot-product (d=32) | 5568 | 0.927 | 0.207 |
| control (no set-relative rule) | Correction (2 layers) | 13760 | 0.952 | 0.119 |

24000 train / 6000 test, random pick = 0.24, accuracy s.e. about 0.5 pp, one training seed per model.

1. Comparing options: on the comparison task the correction model beats both dot-product baselines
   (+5.5 pp over the parameter-matched one, clearly more than noise), and a wider baseline does not close the gap. That is consistent
   with the claim, since the baseline cannot compute the set average.
   Caveat: on the control task the correction model also wins (+2.5 pp), so part of its advantage is
   extra capacity / depth, not only set awareness. The gap is larger when the rule is set-relative (5.5 pp vs 2.5 pp), but we have not
   run a cleaner ablation (e.g. a deeper dot-product MLP).
2. Second question cost: only the context embedding is cached, so the saving is
   `context encoder cost / first-question cost`. Measured with 4 options, per example:

| Model | Context encoder | FLOPs 1st | FLOPs 2nd | 2nd/1st FLOPs | 2nd/1st wall time |
|---|---|---|---|---|---|
| Dot-product | default | 25216 | 19200 | 0.76 | 0.66 |
| Correction (2 layers) | default | 67200 | 61184 | 0.91 | 0.86 |
| Dot-product | heavy (hidden 512) | 67328 | 19200 | 0.29 | 0.57 |
| Correction (2 layers) | heavy (hidden 512) | 109312 | 61184 | 0.56 | 0.82 |

   **The "about half the compute" claim is not supported at the sizes we trained.** With our small context encoder the second question
   costs 76-91 % of the first. It reaches about half (0.56) only when we make the context encoder deliberately large,
   which is by construction. The honest statement: the second question skips context encoding, and the saving
   grows with how expensive the context (history) encoder is relative to the option side. Option encoding and the correction
   layers are recomputed per question, because they depend on the option set. Wall times are dominated by numpy call overhead.


## In the loop: the model makes a real choice in the simulator (W1 / D6)

`python -m decision_model.in_loop --scenario scenarios/generated/stokstad_calibrated.yaml --flowchart optimal --node method`
(about 1 min) prints the tables below and merges them into `runs/model_in_loop.json` (key `scenario/flowchart/node`).
Finland: `python -m decision_model.in_loop --scenario scenarios/finland_lung.yaml --flowchart baseline --node sample_choice --n-train 18800 --train-seeds 1001 1002 --eval-seeds 1 2` (about 2 min).

**Training signal (revealed information only).**
1. Exploration log: training patients (seeds 1001, 1002) run through the flowchart with the rule policy everywhere
   except the target node, where `RandomPolicy` picks uniformly. At each decision the `PatientView` is kept: group, age,
   days since clock start, history, and the attributes revealed so far (tumour location from CT, etc.).
2. Outcome of each logged choice, from the run log's events: the invasive tests downstream of the choice
   (its options, retry fallbacks, later choices). `diagnostic` = one of them returned a result (positive or negative,
   not non-diagnostic). `days` = choice to the last of those results. Reward `r = diagnostic - days / 30`
   (a value judgement: one diagnostic sample is worth 30 days; `--days-per-diagnosis`).
3. Both models get the same data and loss: the logit of the option taken is regressed on `r` (direct-method contextual
   bandit, `train.fit_reward`). Under uniform exploration that estimates each option's expected reward in the context,
   and the policy picks the argmax. The "probabilities" ModelPolicy returns are a softmax over predicted rewards and only rank options.
   Weight decay is picked per model from {0, 0.1, 0.3, 1} by reward MSE on a separate exploration log (seed 999). It is never
   picked by agreement with the rule or by held-out results.
4. `patient.condition`, `patient.cancer`, `patient.results` and unrevealed attributes are never read in training or at run
   time. Cancer status is used only to score the evaluation table.

Context features = the old 15 + a one-hot block over the (attribute, value) pairs seen in training; an unrevealed attribute
or an unseen value is all zero. Option features = identity one-hot + public test metadata (invasive, cost, median wait).
The "+ queue lead" variants add, per option, the days to the earliest appointment in that option's booking system at the moment
of the decision (`PatientView.option_leads`, computed by the engine's own booking logic; what a clinic sees in its appointment book),
plus a has-queue flag. The "+ set summary" ablation (dot-product only) appends to the CONTEXT a fixed-size summary of the whole
offer: per option of the node, offered flag and lead. It is a hand-made set feature, so a per-option scorer can see the other options.
"Mean reward at node" is the training objective measured in the loop (realised outcome of the decision actually taken).

**Evaluation**: held-out patients (other seeds), the same patients and random numbers for every policy. Only the target node changes;
every other node uses the rule. "vs rule (paired)" is the mean per-patient difference in on-time on the same cancers.

### Stokstad optimal, node `method` (bronchoscopy vs needle biopsy); 3 x 1000 held-out patients, 2334 training choices, target 42 d

| Policy at node | On-time | vs rule (paired) | Median days to treatment | Sampling procs / patient at node | Tissue-confirmed cancers | Diagnostic sample at node | Days choice to sampling done | Agreement with rule |
|---|---|---|---|---|---|---|---|---|
| rule (hand-written: central -> bronch) | 80.5% | - | 31.1 | 1.03 | 2133 / 3000 | 90.0% | 12.8 | 100% |
| random | 78.2% | -2.3 pp (s.e. 0.4) | 31.3 | 1.13 | 1699 / 3000 | 71.7% | 13.3 | 52% |
| dot-product | 80.5% | +0.0 pp | 31.1 | 1.03 | 2133 / 3000 | 90.0% | 12.8 | 100% |
| correction (2 layers) | 80.3% | -0.1 pp (s.e. 0.1) | 31.1 | 1.03 | 2131 / 3000 | 89.9% | 12.8 | 99.5% |

What it learned (location x chosen option, held-out): dot-product central -> bronch1 719/719, peripheral -> ttnb1 1651/1651;
correction 707/719 and 1651/1651. Mean predicted reward, central: bronch1 +0.45 vs ttnb1 +0.13; peripheral: bronch1 +0.01 vs ttnb1 +0.42
(the exploration log's raw means: +0.48 / +0.10 and +0.00 / +0.43). **Both models rediscovered the hand-written location rule from
outcomes alone and matched it; they did not beat it.** That is expected: in this scenario the rule is the reward-optimal policy
(the yields that drive the outcome depend only on location). The correction model's 12 disagreements are in rare contexts
(CT inadequate, long waits): estimation noise, not a better rule. Without weight decay, the disagreements were 1-2 %. With only 234 training choices
(100 patients) the models agreed with the rule on just 87 % (dot) and 68 % (correction) of choices, so they need data.

### Finland baseline, node `sample_choice`; 2 x 18800 held-out presenters, 885 training choices, target 90 d (provisional)

| Policy at node | On-time | vs rule (paired) | Median days to treatment | Sampling procs / patient at node | Tissue-confirmed cancers | Diagnostic sample at node | Days choice to sampling done | Agreement with rule |
|---|---|---|---|---|---|---|---|---|
| rule (central -> bronch; peripheral 35/65 mix) | 21.0% | - | 102.8 | 1.14 | 416 / 491 | 94.3% | 15.5 | 100% |
| random | 14.1% | -6.9 pp (s.e. 1.4) | 106.0 | 1.18 | 392 / 491 | 89.2% | 18.0 | 51% |
| dot-product | 1.4% | -19.6 pp (s.e. 1.8) | 142.6 | 1.29 | 420 / 491 | 95.1% | 63.3 | 61% |
| correction (2 layers) | 3.3% | -17.7 pp (s.e. 1.8) | 131.9 | 1.27 | 418 / 491 | 94.7% | 52.0 | 61% |
| dot-product + queue lead | 20.4% | -0.6 pp (s.e. 1.0) | 101.3 | 1.06 | 414 / 491 | 93.1% | 14.8 | 72% |
| correction (2 layers) + queue lead | 12.4% | -8.6 pp (s.e. 1.6) | 112.6 | 1.19 | 405 / 491 | 90.8% | 29.5 | 59% |
| dot-product + queue lead + set summary | 17.3% | -3.7 pp (s.e. 1.1) | 102.8 | 1.12 | 416 / 491 | 93.6% | 14.8 | 68% |

(Current code: leads from `PatientView.option_leads` as [lead/30, has-queue]. An earlier run with a read-only probe of the booking state
and a single lead column gave the queue-lead rows 20.2 % / 22.4 % (paired -0.8 / +1.4 pp), and with model seed 1, 20.0 % / 20.8 %.)

What happened:
- **Without queue information the learned policy breaks the pathway.** Under random exploration, peripheral bronchoscopy
  (with its needle-biopsy fallback) scored about the same as a needle biopsy (+0.22 vs +0.21), because the bronchoscopy book had the shorter lead (7.6 vs 16 d).
  The models therefore sent about 80 % of peripheral lesions to bronchoscopy. That overloaded the 1 slot/day bronchoscopy server: days from choice to
  sampling done rose from 15 to 52-63, and on-time fell from 21 % to 1-3 %. The per-patient reward cannot see that one choice lengthens
  the queue for everyone else, and the exploration log was collected under a different load than the learned policy creates.
  Unstable as well: with model seed 1 the correction model got 10.8 % (dot-product 1.2 %). The peripheral values are a near-tie,
  so small estimation differences reroute the whole group, and the queue amplifies the effect.
- **With the queue lead as an option feature, the dot-product model load-balances by queue state.** Central lesions go to
  bronchoscopy. Peripheral lesions go mostly to needle biopsy, switching to bronchoscopy when its book is shorter.
  It matches the rule on on-time (paired -0.6 pp, s.e. 1.0, and -0.8 / -1.0 pp in two earlier runs) and uses about 7 % fewer sampling procedures
  (1.06 vs 1.14 per patient). It confirms about the same number of cancers (414 vs 416). This is not a significant improvement over the rule.
  It is a learned policy as good as the rule, trained only on information the clinic has.
- **The correction model is unstable here.** With 885 training choices, its queue-lead variant gave +1.4 and -0.2 pp in two earlier runs.
  It gave -8.6 pp in the current run, where it fits the validation log worse (reward MSE 0.169 vs 0.138 for the dot-product) and sends some central lesions to needle biopsy.
  With little data the extra attention layers hurt, consistent with the data-size result in the next section.

## Open question 12: does comparing options matter in the loop? (`python -m decision_model.comparison_experiment`, ~6 min)

**Why availability alone is not enough.** Suppose each option's expected outcome is the same whatever else is offered.
Then "pick the best available" is the argmax of per-option values, and a dot-product scorer represents it exactly: it
just scores the options on offer. Comparison only matters when an option's value depends on the other options, or on their features.
We tested both cases in `scenarios/experiments/stokstad_method_availability.yaml`, an experiment built from the calibrated Stokstad scenario
by `decision_model/make_experiment_scenario.py`. The yields, capacities and the other-referral load are assumptions, not calibrated.
- Node `method` (after the tumour board) offers bronchoscopy, radial EBUS and needle biopsy.
- A non-diagnostic bronchoscopy falls back to a needle biopsy.
- Bronchoscopy suits central lesions, needle biopsy suits peripheral ones, and EBUS is a middle option.
- Lesions are 50 % central and 50 % peripheral.
- Each option has a chance of not being on offer (engine `availability`).

Reference policy, **expected-value rule**: for each offered option, `P(diagnostic) - E[days]/30` from the scenario's published-style parameters
(non-diagnostic rates by revealed location, wait and report distributions) and the queue leads in the view. It knows what a clinic could read in the
literature, never a patient's hidden truth. It is a hand-built upper reference, not a learned model. The hand-written rule is
"central -> bronchoscopy, peripheral -> needle biopsy, otherwise EBUS", and it ignores queues.

### Flowchart `availability`: the best available option depends on the offer; values do not (3 x 3000 held-out patients, 3909 training choices)

| Policy at node | Mean reward at node | vs rule (paired) | On-time | vs rule (paired) | Tissue-confirmed | Agreement with EV rule |
|---|---|---|---|---|---|---|
| rule (hand-written) | +0.347 | - | 73.8% | - | 7021 / 8496 | 92% |
| random | +0.284 | -0.063 (s.e. 0.004) | 73.0% | -0.8 pp (s.e. 0.3) | 6664 | 58% |
| expected-value rule | +0.352 | +0.004 (s.e. 0.002) | 72.5% | -1.3 pp (s.e. 0.1) | 7190 | 100% |
| dot-product | +0.349 | +0.001 (s.e. 0.002) | 72.7% | -1.2 pp (s.e. 0.2) | 7161 | 95% |
| correction (2 layers) | +0.347 | -0.000 (s.e. 0.003) | 72.7% | -1.2 pp (s.e. 0.2) | 7149 | 92% |
| dot-product + set summary | +0.352 | +0.004 (s.e. 0.002) | 72.8% | -1.0 pp (s.e. 0.2) | 7179 | 95% |

The learned models picked the best available option (most common pick per location x offered set, in `runs/model_in_loop.json`).
They also found one improvement on the hand-written rule: for a peripheral lesion with bronchoscopy and EBUS on offer but no needle biopsy, they choose bronchoscopy, whose needle-biopsy rescue makes it better than EBUS (the rule picks EBUS).
That gains diagnoses (7161 vs 7021 tissue-confirmed) at slightly lower on-time (-1.2 pp), because the reward values a diagnosis at 30 days.
**Correction vs dot-product: -0.002 reward (s.e. 0.002), 0.0 pp on-time. No difference, as predicted.**

### Flowchart `rescue_queue`: bronchoscopy's value depends on ANOTHER option's queue (the comparison-dependent case)
Needle biopsy is booked on a capacity-limited list (2/day) shared with other biopsy referrals, each of which books 20 sessions at once.
That bursty load is independent of the policy, so the needle-biopsy lead varies (median about 8 days, 90th percentile about 35).
The needle-biopsy list is also bronchoscopy's rescue, so bronchoscopy's value falls as the needle-biopsy lead grows. For a central lesion with
bronchoscopy and EBUS both on offer, the expected-value rule switches from bronchoscopy (short needle-biopsy lead) to EBUS (long lead).
A dot-product model sees each option's own lead, but bronchoscopy has no queue of its own, so it cannot use the needle-biopsy lead when scoring bronchoscopy.
The correction model can, because it attends over the offered options.

3 x 3000 held-out patients. Rows marked 12k were trained on 11683 exploration choices (12000 patients); the others on 3909 (4000 patients).

| Policy at node | Mean reward at node | vs rule (paired) | On-time | vs rule (paired) | Tissue-confirmed | Days choice to sampling done |
|---|---|---|---|---|---|---|
| rule (hand-written, queue-blind) | +0.151 | - | 59.1% | - | 7223 / 8496 | 21.0 |
| random | +0.126 | -0.025 (s.e. 0.007) | 62.6% | +3.5 pp (s.e. 0.4) | 6621 | 19.6 |
| expected-value rule | +0.370 | +0.219 (s.e. 0.006) | 74.8% | +15.7 pp (s.e. 0.4) | 7035 | 13.7 |
| dot-product (no leads) | +0.279 | +0.128 (s.e. 0.006) | 69.1% | +10.0 pp (s.e. 0.4) | 6999 | 16.3 |
| correction (no leads) | +0.270 | +0.119 (s.e. 0.005) | 67.9% | +8.8 pp (s.e. 0.4) | 7063 | 16.8 |
| dot-product + queue lead | +0.351 | +0.200 (s.e. 0.006) | 74.3% | +15.2 pp (s.e. 0.4) | 6942 | 14.0 |
| correction + queue lead | +0.364 | +0.213 (s.e. 0.006) | 74.8% | +15.7 pp (s.e. 0.4) | 6984 | 13.7 |
| dot-product + queue lead + set summary | +0.369 | +0.217 (s.e. 0.006) | 74.7% | +15.6 pp (s.e. 0.4) | 7031 | 13.8 |
| dot-product + queue lead, 12k | +0.353 | +0.202 (s.e. 0.007) | 76.1% | +17.0 pp (s.e. 0.5) | 6804 | 13.4 |
| correction + queue lead, 12k | +0.373 | +0.222 (s.e. 0.006) | 75.2% | +16.1 pp (s.e. 0.4) | 7026 | 13.6 |
| dot-product + queue lead + set summary, 12k | +0.367 | +0.216 (s.e. 0.006) | 74.6% | +15.5 pp (s.e. 0.4) | 7028 | 13.8 |

The set-dependent cell (central lesion, bronchoscopy and EBUS both on offer, 2052 decisions): share choosing bronchoscopy by needle-biopsy lead,
and agreement with the expected-value rule in the cell.

| Policy | lead 0-7 d | lead 7-20 d | lead > 20 d | Agreement with EV rule in cell |
|---|---|---|---|---|
| expected-value rule | 100% | 50% | 0% | 100% |
| dot-product + queue lead | 18% | 24% | 20% | 37% |
| correction + queue lead | 73% | 27% | 4% | 71% |
| dot-product + queue lead + set summary | 95% | 6% | 0% | 83% |
| dot-product + queue lead, 12k | 0% | 0% | 0% | 30% |
| correction + queue lead, 12k | 100% | 35% | 0% | 92% |
| dot-product + queue lead + set summary, 12k | 99% | 24% | 0% | 90% |

Paired, same patients:

| Comparison | Reward at node | On-time |
|---|---|---|
| correction + lead vs dot-product + lead (4k) | +0.013 (s.e. 0.003) | +0.5 pp (s.e. 0.2) |
| same, model seed 1 (4k) | +0.006 (s.e. 0.002) | -0.2 pp (s.e. 0.1) |
| correction + lead vs dot-product + lead (12k) | +0.020 (s.e. 0.004) | -0.9 pp (s.e. 0.2) |
| correction + lead vs dot-product + lead + set summary (12k) | +0.006 (s.e. 0.001) | +0.6 pp (s.e. 0.1) |

Offline check of data needs (held-out exploration log, 923 cell decisions, agreement with the EV rule in the cell):
- **Dot-product + lead:** 0.37 (4k) and 0.31 (12k).
- **Dot-product + set summary:** 0.88 (4k) and 0.86 (12k).
- **Correction + lead:** 0.73 and 0.49 (4k, model seeds 0 and 1); 0.93 and 0.89 (12k).

**What this shows.**
1. **The comparison-dependent case exists in the simulator, and the correction model learns it, given enough data.** A per-option dot-product
   model cannot: its bronchoscopy choice does not respond to the needle-biopsy queue at any data size. With 12k training choices the
   correction model tracks the expected-value rule in that cell (92 %) and matches its reward (+0.373 vs +0.370).
   It beats the dot-product model with leads by +0.020 reward per decision (s.e. 0.004).
2. **The gain is small in headline terms.** Only about 16 % of decisions fall in the set-dependent cell. Even the expected-value rule is only
   +0.02 reward above dot-product + lead. On-time does not improve: the dot-product model sends those central lesions to EBUS, which is faster
   and gives fewer diagnoses, so it has +0.9 pp on-time and 222 fewer tissue-confirmed cancers out of 8496.
   The reward values a diagnosis at 30 days; on-time ignores diagnoses.
3. **A hand-made set summary in a dot-product's context does as well, and with less data.** When the option list is small and fixed, that summary is easy to write.
   The correction model's case is that it needs no such hand-written feature: the same model works for any option set and any option features.
   It did not beat the set-summary baseline on decisions here (+0.006 reward at 12k, about equal agreement).
4. **With less data the correction model is less reliable.** At 4k the model-seed spread is large (cell agreement 0.49-0.73). In Finland, with 885 choices, the correction model was unstable (see above).
5. Both learned policies beat the queue-blind hand-written rule by about 15 pp on-time here. That reflects how bad a queue-blind rule is on a congested list,
   not the architecture.

### Limitations (in-loop)
- One reward exchange rate (30 days per diagnostic sample), one training run per model per seed, and 2-3 held-out seeds.
  Stokstad patients do not interact (delay resources), so its seeds are independent. Finland patients share queues.
- Off-policy shift: the exploration log comes from a uniform-random policy. Under a different load (Finland) the learned values
  are biased; the queue-lead feature fixes this here, but a production version would retrain on-policy with epsilon exploration.
- Queue leads come from `PatientView.option_leads` (engine booking logic, the patient's priority). A lead is the state at decision time;
  the bronchoscopy rescue is booked days later, so the expected-value rule's use of the current lead is an approximation.
- The open-question-12 experiment is a constructed scenario: the effect exists because we built a rescue that shares a queue with another option.
  Whether real sampling decisions have comparison effects of this size is not shown.
- The model optimises the stated reward at one node, not the four headline metrics; on-time is a downstream check.
- Finland on-time uses the provisional 90-day target (decisions D20).

### Engine features used (added by the coordinator after the first in-loop run)
`PatientView.option_leads`, `PatientView.priority`, `PatientView.offered`, and choice-node `availability` (per option `p_available` / `weekdays`).
Still missing: availability that persists across nodes (e.g. "no needle-biopsy service this week" applying to the rescue too). The engine draws availability
independently per node and option, and a forced fallback ignores availability.

## Limitations (synthetic task and adapter)

- The comparison task is synthetic and its rule was written by us; accuracy shows the model can learn set-relative rules, not that real
  clinical choices follow one. No public benchmark has been run.
- The RunLog adapter learns imitation of whoever produced the log (by default the rule policy), so the model can at best reproduce
  that policy. The RunLog contract has no age, no option features and no flowchart, so the adapter takes `choice_nodes`
  and a test table; `DEFAULT_TEST_TABLE` values are illustrative assumptions, not sourced numbers.
- "Typed question" is not modelled: the question type is implicit in the option set. Context is a fixed-size feature vector, not a sequence.
- `ModelPolicy` needs the same days-elapsed definition at train and run time (`view.arrival` if present). A doctor decides; the output is a proposal.
- Single seed, tiny models, manual autograd (no GPU, ~1 minute training).

## Run

```
python -m decision_model.benchmark          # full table (~90 s); --quick for a few seconds
python -m pytest -q tests/test_decision_model.py tests/test_decision_model_loop.py tests/test_decision_model_comparison.py
python -m decision_model.in_loop             # model in the simulator loop, Stokstad optimal / method (~1 min)
python -m decision_model.comparison_experiment                 # open question 12, both flowcharts (~6 min)
python -m decision_model.comparison_experiment --flowchart rescue_queue --n-train 12000 --weight-decay 0.1 0.3 --lead-variants-only   # 12k rows (~2.5 min)
python -m decision_model.make_experiment_scenario              # regenerate scenarios/experiments/stokstad_method_availability.yaml
```
Policy: `ModelPolicy(model).train_on_runlog(runlog_json_or_path, {"sample": ["bronch", "ttnb"]})`, then `policy.choose(view, options)`.
