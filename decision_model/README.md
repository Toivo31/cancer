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
The "+ queue lead" variants add, per option, the days to the next free slot in that option's booking system at the moment
of the decision (what a clinic sees in its appointment book; read-only probe of the engine's booking state).

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
| dot-product + queue lead | 20.2% | -0.8 pp (s.e. 1.0) | 101.4 | 1.07 | 415 / 491 | 93.6% | 14.5 | 73% |
| correction (2 layers) + queue lead | 22.4% | +1.4 pp (s.e. 1.0) | 100.8 | 1.09 | 415 / 491 | 93.4% | 14.1 | 71% |

What happened:
- **Without queue information the learned policy breaks the pathway.** Under random exploration, peripheral bronchoscopy
  (with its needle-biopsy fallback) scored about the same as a needle biopsy (+0.22 vs +0.21), because the bronchoscopy book had the shorter lead (7.6 vs 16 d).
  The models therefore sent about 80 % of peripheral lesions to bronchoscopy. That overloaded the 1 slot/day bronchoscopy server: days from choice to
  sampling done rose from 15 to 52-63, and on-time fell from 21 % to 1-3 %. The per-patient reward cannot see that one choice lengthens
  the queue for everyone else, and the exploration log was collected under a different load than the learned policy creates.
  Unstable as well: with model seed 1 the correction model got 10.8 % (dot-product 1.2 %). The peripheral values are a near-tie,
  so small estimation differences reroute the whole group, and the queue amplifies the effect.
- **With the next-free-slot lead as an option feature, both models load-balance by queue state.** Central lesions go to
  bronchoscopy. Peripheral lesions go mostly to needle biopsy, switching to bronchoscopy when its book is shorter.
  They match the rule on on-time (paired -0.8 / +1.4 pp, s.e. 1.0; model seed 1: -1.0 / -0.2 pp), use about 5 % fewer sampling procedures
  (1.07-1.09 vs 1.14 per patient) and confirm about the same number of cancers (415 vs 416). This is not a significant improvement over the rule;
  it is a learned policy that is as good as the rule and was trained only on information the clinic has.
- Dot-product vs correction: no reliable difference in either scenario (the order flips with the model seed).

### Is this the comparison-dependent case (open question 12)? Not yet, honestly
In this set-up the value of an option depends on the context and on that option's own features (location, its own queue lead),
not on which other options are offered. The best choice is then the argmax of per-option values, which a dot-product model can
represent, so the correction model has nothing extra to exploit. These results are therefore an "in the loop, revealed-only, honest" proof, not
evidence for the correction architecture; that evidence is still only the synthetic set-relative task above. A comparison-dependent in-loop case
needs option sets that vary (an option unavailable on some days, or a fallback that only exists if another option is offered) at a node with 3+ options.
The engine cannot express that today (see requests below). We did not attempt step 4.

### Limitations (in-loop)
- One reward exchange rate (30 days per diagnostic sample), one training run per model per seed, and 2-3 held-out seeds.
  Stokstad patients do not interact (delay resources), so its seeds are independent. Finland patients share queues.
- Off-policy shift: the exploration log comes from a uniform-random policy. Under a different load (Finland) the learned values
  are biased; the queue-lead feature fixes this here, but a production version would retrain on-policy with epsilon exploration.
- The queue probe reads `Simulation.servers` and mirrors `_Server.book` (`_next_slot_days`; a test checks it equals a real booking).
  If the engine's booking logic changes, the mirror must change too. Fast-track priority is not visible to the policy, so the probe uses the normal lead.
- The model optimises the stated reward at one node, not the four headline metrics; on-time is a downstream check.
- Finland on-time uses the provisional 90-day target (decisions D20).

### Engine requests (not done; pathway_sim is out of scope for this track)
1. `PatientView.resources`: per resource, the next free slot / queue length at decision time, so policies do not reach into `Simulation`.
2. `PatientView.priority` (fast-track flag) and `PatientView.clock_start`, so a policy can compute leads the way the engine books them.
3. Option availability: per-option `available_when` (weekday, resource closed, capacity left), passed to `Policy.choose` as a smaller option set.
   That is what a comparison-dependent experiment needs.
4. A `simulate(..., on_start=callback)` hook (or returning the `Simulation`) so wrappers can attach to it without constructing `Simulation` directly.

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
python -m pytest -q tests/test_decision_model.py tests/test_decision_model_loop.py
python -m decision_model.in_loop             # model in the simulator loop, Stokstad optimal / method (~1 min)
```
Policy: `ModelPolicy(model).train_on_runlog(runlog_json_or_path, {"sample": ["bronch", "ttnb"]})`, then `policy.choose(view, options)`.
