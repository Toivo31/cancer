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

## Limitations

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
python -m pytest -q tests/test_decision_model.py
```
Policy: `ModelPolicy(model).train_on_runlog(runlog_json_or_path, {"sample": ["bronch", "ttnb"]})`, then `policy.choose(view, options)`.
