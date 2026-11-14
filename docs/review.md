# Independent review (14 Nov 2026, before submission)

Reviewer: independent pass over code, results and pitch, as a skeptical engineer and a skeptical judge.
Branch `track/review`. Everything below was run in this worktree. Check scripts are in `docs/review_checks/`
(each runs in 10-60 s). New tests are in `tests/test_review_fixes.py`.

**Verdict in one paragraph.** The engine and the Norwegian check are solid. The bundle reproduces exactly
from code, critical-path accounting is exact, held-out reporting is real, and the proposal side never reads
hidden truth. The weak point is the **Finnish headline**. "18% to 61%" comes entirely from one assumed
parameter pair: the routine booking lead against the urgent booking lead. The "fast lane" gives priority to
every referred patient, so it is the same as shortening every booking lead for free, and the dashboard called
it "reordering". A judge who opens screen 5 sees two identical flowcharts. Fix the framing before 10:00. The
numbers can stay.

## What is strong (keep)

- **Reproducible.** `python3 demo/export.py --out /tmp/b.json` (9 min, 1 core) regenerates
  `demo/data/demo_bundle.json` with **0 differences** apart from `generated_at`.
- **Exact time accounting.** For every treated cancer patient, in Stokstad and in all Finnish flowcharts, the
  waiting plus service on the critical path equals the time to treatment (max difference 1e-14 d;
  `docs/review_checks/finland_waiting_decomposition.py`).
- **The proposal side is blind to hidden truth, as claimed.** `optimiser/analysis.py` reads only
  `RevealedPatient`. The new test `test_proposal_scores_ignore_hidden_truth` scrambles `condition`, `cancer`,
  `results` and `attributes` after a run and gets identical candidates, scores and validity.
- **The rest of the method holds up.** Common random numbers keyed by (seed, patient, test, attempt), two
  training cohorts plus held-out cohorts, and selection optimism reported. The acceptance step's use of truth
  is disclosed ("in real life a pilot").
- **No end-of-horizon bias.** Re-running Finland with arrivals continuing 150 days past the horizon changes
  the share by 0.0 pp and the median by under 0.7 d.
- **Honest negative results are kept.** These are good material for the Data quality criterion: the
  faster-PET over-prediction, the half-compute claim not reproduced, the decision model only tying the rule,
  and the equity caveats.
- **The checks pass.** `python3 -m pytest -q` passes (71 tests before, 76 now, about 32 s).
  `python3 -m pathway_sim demo --quick` runs (2 min 20 s). All 12 dashboard screens (both scenarios, 1-6)
  render with no "could not be drawn" fallback.

---

## Blockers

### B1. The Finnish headline is an assumed booking-lead gap, not a fast lane or a reorder
**Where:**
- `scenarios/finland_lung.yaml:74-80` (`urgent_lead_days` against `min_lead_days`, all `source: assumption`)
- `pathway_sim/engine.py:118-122`
- headline in `docs/pitch/filled/*.md`, dashboard screens 1, 3 and 4

**Evidence:** `python3 docs/review_checks/finland_fast_lane_is_booking_lead.py` (held-out cohorts 301 and 302,
the same as the bundle):
```
baseline                                       share 0.1754, median 102.31, missed 27.5
baseline, routine lead := urgent lead, NO FT   share 0.6147, median  80.01, missed 27.5   <- identical to the optimiser result
fast_track(triage), 100% of the lead gap       share 0.6147, median  80.01
fast_track(triage),  50% of the lead gap       share 0.4418, median  90.0
fast_track(triage),   0% of the lead gap       share 0.1754, median 102.31  <- no gain at all
```

**Why it matters:**
- Every patient who uses the clinic, CT, sampling, PET-CT and treatment slots has passed referral triage, so
  "priority after triage" means *everyone* is priority. Nobody is left to be crowded out, which is why the
  non-cancer and equity guardrails pass trivially.
- The Finnish resources have no `urgent_reserved_share`, so priority only swaps each booking lead for a shorter
  one: clinic 12 to 5 d, CT 4 to 1, bronchoscopy and needle biopsy 6 to 2, PET-CT 4 to 1, treatment 10 to 6.
  The gain is exactly the assumed lead gap, at no capacity cost. Utilisation moves by 1-3 points.
- In a real appointment book the lead *is* the backlog, so "everyone urgent" cannot be free. A clinical judge
  will say "if everyone is urgent, nobody is."
- The sensitivity analysis never varies this change. The tornado shown under it was for `bundled_workup` (see M6).

**Fix:**
- Keep the result, but present it as what it is. Something like: "Book every referred suspected-lung-cancer
  patient on the urgent track (as Nordic cancer pathways do). *If* urgent booking leads of 5/1/2/1/6 days can be
  held without extra slots, the 90-day share goes from 18% to 61%. Half that lead reduction gives 44%."
- Show the dose-response line from the script above.
- Alternatively, lead with the capacity-controlled reorder: `bundled_workup` 54% against
  `baseline_plus_capacity` 31%, the same extra capacity. That one is a real order effect, although sensitivity
  shows it needs the PET-CT capacity.
- Either way, add `*.urgent_lead_days` for all six servers to the sensitivity shortlist with the optimiser's
  change as comparison B. Rename the "Fast lane" label (`demo/export.py` POLISHED, `fast_track/triage`).

### B2. The dashboard said "Reordering the steps gains 44 points" for a change that reorders nothing (fixed in code)
**Where:**
- `demo/index.html` `screenCap` (headline and lede)
- `demo/export.py::capacity_vs_order` (hard-coded bar label "Suggested change: new order and a fast lane, no
  new capacity")
- screen 5 shows identical before and after flowcharts, because `display_flowchart` does not show `fast_track`

**Evidence:** headless screenshot `#finland_lung/4` showed "Reordering the steps gains 44 points; more capacity
gains 13", next to a bar labelled "new order and a fast lane". The only accepted step is
`fast_track(triage)` (bundle `scenarios[1].optimiser.steps`).

**Fixed:**
- `export.py` builds the bar label from the accepted step kinds (`suggested_change_label`). It now reads
  "Suggested change: a fast lane (priority booking), same order, no new capacity".
- `screenCap` says "The suggested change gains ..." when no reordering edit was accepted, and its lede states
  that the gain rests on the assumed routine and urgent booking times.
- Stokstad is unchanged, because its suggestion really is a reorder.
- Tests: `test_suggested_change_label_matches_accepted_kinds`.

**Still to do:** mark fast-tracked steps on screen 5, for example an outline on the triage node, so that
"Before and after" shows something.

---

## Major

### M1. "87% of the time is waiting in queues" is mostly assumed fixed delays, not queues
**Where:** dashboard screen 2 ("waiting in queues", "The longest queue is at one step: Waiting for treatment
slot"), deck slide 3, `docs/master_plan.md` §2 "Where queues build up".

**Evidence:** `docs/review_checks/finland_waiting_decomposition.py` splits the mean critical-path waiting per
treated cancer (baseline):

| Part of the waiting | Days |
|---|---|
| Fixed booking leads (`min_lead_days`, tuned to hit the published waits) | 57.0 |
| Assumed `extra_wait` (incl. the 14-day "comes back if it persists" interval and the 4-day pre-treatment work-up) | 13.5 |
| Referral paperwork and the weekly board | 9.9 |
| **Capacity queueing** | **9.4** |

The "longest queue", the treatment slot (16.5 d), sits at a resource that screen 4 itself shows as 36% busy.
The 14.8-day "Re-presents to GP" bar is the assumed safety-net interval.

**Fix:**
- Relabel as "waiting (booking time and queues)".
- Or split the bars into "booking lead" and "queue": the engine knows both, at `_Server._slot`.
- Say in the pitch that per-step waits are calibrated to published Finnish waits rather than emerging from
  capacity.

### M2. "131 parameters, 113 sourced, 18 assumptions" overstates source coverage
**Where:**
- deck slide 10, qa #1, submission "Limitations", `data_transparency.md:14`
- `demo/export.py::assumptions` reads `params/*.yaml`

**Evidence:**
- Most of the 113 "sourced" rows are calibration *targets* or background, not simulator inputs. Examples: MOT
  intervals, survival 17%, GLOBOCAN counts, the Welsh RDC days.
- The scenario the headline runs on, `scenarios/finland_lung.yaml`, has 45 `source: assumption` tags. They
  cover every server capacity, every booking lead, every urgent lead, the nurse, GP and specialist
  decision probabilities, the safety net, and five of the seven prevalences.
- `docs/sensitivity.md` itself says Finland has "roughly 100 assumption parameters".

**Fix:** count from the scenario files the engine reads, for example: "Finnish scenario: N inputs, K sourced;
all capacities and booking leads are assumptions calibrated to published waits". Keep the params table as
"evidence and calibration targets".

### M3. The "predicted, not fitted" 80% depends on a calibrated parameter that flows into the authors' pathway
**Where:**
- `scenarios/stokstad.yaml:240` and `:293`: the `&pet_triage_mix` anchor is shared by `observed`,
  `faster_pet` and `optimal`
- the calibration sets it to 1.0, at the grid edge
- the claim is in the README table, submission, deck slide 6 and qa #3

**Evidence:** `docs/review_checks/stokstad_authors_pathway_vs_pet_triage.py`:
```
observed and optimal share one mix object: True
authors' pathway, PET-CT ordered at triage for 100%: 0.801
                                                50%: 0.728
                                                 0%: 0.661   (PET ordered at the first visit, as the paper describes)
```

The calibration also lands on the grid edge for 3 of 5 parameters: bronchoscopy wait 3 (minimum),
post-board wait 6/10.5 (minimum), PET triage 1.0 (maximum).

**Fix:** keep "predicted", but add one line: "the calibrated observed practice (PET-CT ordered when the referral
is triaged) is carried into the authors' pathway. If PET-CT were ordered only at the first visit, the
simulated authors' pathway would give 66%." This is a disclosure, not a reason to drop the claim. The grid-edge
fit is already in `docs/validation.md` and should be said aloud.

### M4. The tissue-confirmed guardrail is switched off in the Finnish scenario
**Where:** `optimiser/search.py:87` skips the check when `base["confirmed_cancers"]` is 0. No Finnish test has
`confirms_diagnosis: true`. The claim is in README, master plan §10, qa #11 and D14.

**Evidence:** the bundle has `confirmed_cancers = 0.0` for every Finnish variant. The guardrail that "blocks
faster by skipping tissue sampling" therefore does not exist for the Finnish search.

**Fix:**
- Add `confirms_diagnosis: true` to `bronchoscopy` and `ttnb` (and the `_fast` copies) in
  `finland_lung.yaml` and rerun. The accepted change does not touch sampling, so it should survive.
- At minimum, log a warning when a guardrail is inactive, and stop claiming it for Finland.

(I did not change scenario parameters, per instructions.)

### M5. "Rejected GP-first because more cancers were missed" is noise
**Where:** video script 0:38, master plan §10 ("it gives more missed cancers"), the missed-cancer guardrail at
`optimiser/search.py:85` (zero tolerance on 2-cohort means).

**Evidence:** `docs/review_checks/finland_gp_first_rejection.py`:
```
train:    share 0.559 -> 0.585, missed 24.0 -> 24.5 (of ~264)  -> blocked: more missed / untreated
held-out: share 0.615 -> 0.638, missed 27.5 -> 25.0 (of ~261)  -> fewer missed; trips the equity guardrail instead
```

The trip is half a cancer per cohort: one patient in one of two cohorts. The equity guardrail (1 pp, about 80
site-specific cancers per cohort) is equally noise-driven.

**Fix:**
- Say "GP-first did not pass our safety checks on the training patients (one extra missed cancer in one
  cohort); on unseen patients it looked neutral to positive, so it needs a proper test." That is a better
  story anyway.
- Longer term: a paired comparison or more cohorts before treating a guardrail breach as real.

### M6. The tornado showed the optimiser's gain against bars for a different comparison (fixed in code)
**Where:** `demo/index.html` `tornado()`. The rows come from `docs/sensitivity_*.json`:
- Stokstad: "optimal vs observed", base +40.7
- Finland: "bundled_workup vs baseline", base +43.0

The dashed "central estimate" line was the optimiser's cumulative gain (+48 and +44). The two Finnish numbers
are close by coincidence, which makes it look like the suggested change was stress-tested. It was not (see B1).

**Fixed:** the central line now uses the rows' own `base_gain_pp`. The lede names the comparison, adding
"(not the suggested change above)".

### M7. "Found without seeing the authors' answer" needs its menu disclosed; the fourth change was mislabelled (label fixed)
**Where:** README, submission, deck slide 6, dashboard screen 1.

**Evidence:**
- The candidate menu contains each of the authors' changes as a single edit. "Late PET" and "late exercise
  test" are explicit choice options with an `extra_wait`, so `standardise(pet_timing → pet_on_time)` simply
  removes a modelled delay. `optimiser.needs` in `stokstad.yaml` was hand-written.
- The fourth change, `relax(sample_plan, visit)`, makes `sample_plan` depend only on the baseline CT, which is
  at referral receipt. So sampling is planned **at referral triage, before any hospital visit**. The dashboard
  and submission said "at the first hospital visit".

**Fixed:** POLISHED label → "Plan tissue sampling when the referral is triaged, before the first hospital
visit". Test: `test_sampling_label_says_triage_not_first_visit`.

**Still to do:**
- Fix submission.md, which says "tissue sampling booked at the first visit".
- Say "it searched a menu of about 70 single changes and was not told which ones the authors made".
- Flag the fourth change as bronchoscopy before a specialist has seen the patient (D18).

### M8. The recommendation does not contain the change the headline is about
**Where:** `docs/pitch/filled/recommendation.md`, deck slide 9.

**Evidence:**
- The headline 61% is the optimiser's urgent-booking-for-all change. None of the five actions is that change;
  it only appears inside action 3 as an aside.
- Action 1, "order PET-CT, exercise test and the board together", is the hand-written `bundled_workup` (54%,
  needs 3× PET-CT). The Finnish flowchart has no exercise test at all.

**Fix:** make action 1 whatever the headline is, or make the headline action 1's number. Drop "exercise test"
from the Finnish claim, or say it comes from the Norwegian evidence.

### M9. Numbers that disagree across documents (a judge will catch these)

| Claim | Where | Bundle or truth |
|---|---|---|
| "With **two** changes to the pathway, 61 percent" | `video_script.md:7,16` | one change (the script itself says "It suggests one" two lines later) |
| Finland held-out "18% → **57%**" | `master_plan.md:181` | 61% |
| "**No sensitivity analysis yet**" | `submission.md:41` | `docs/sensitivity.md` exists and the dashboard draws it |
| Demo "about a minute" / "~1 min"; tests "~3 s"; "keys 1-4" | `submission.md:49`, `README.md:12-14` | full demo about 9 min (quick 2.3 min); tests about 32 s; 6 screens |
| Correction model "beats a **parameter-matched** dot-product model: 84.5 against **78.3**" | `master_plan.md:169` | parameter-matched is 79.0; 78.3 is the d=32 model (`decision_model/README.md`) |
| "Missed cancers ... (we have not separated which of the **two steps** drives this; ... GP-first visits ...)" | `equity.md:38` | stale text from an earlier two-change run; now one change and no change in missed |
| "the optimiser proposes a different **order** of steps" | `submission.md:11` | in Finland it proposes priority booking, not an order change |
| "No missed cancers ... in any accepted change" | README | trivially true for Norway (no discharge exit, all patients have cancer), and the Finnish tissue guardrail is off (M4) |

**Fix:** edit the templates (`docs/pitch/*.md`) and rerun `fill_numbers.py`, so the filled copies stay in step.

---

## Minor

1. **Engine: a forced retry fallback left its downstream steps skipped (fixed).** `pathway_sim/engine.py`
   `on_done`.
   - The bug: when an option skipped at a choice is later forced as a retry fallback, the steps that had been
     dead-skipped because of it stayed skipped. The patient ended up `stuck`, or mis-routed.
   - Fix: `Simulation.revive_descendants` resets them to pending. Options that a choice actually skipped stay
     skipped.
   - Test: `test_forced_fallback_runs_its_downstream_steps`, which fails before the fix and passes after.
   - **Results-neutral:** all flowcharts of all shipped and experiment scenarios, 2 seeds each, give
     byte-identical metrics before and after. No shipped flowchart has a strict dependant of a fallback.
2. **Contract contradicts the code.** `docs/architecture.md:104-106` says a guard-skipped node "counts as
   complete for downstream `after_any`". In the code, `after_any` needs at least one `done` and goes dead when
   all are skipped. Fix the doc, since the code's behaviour is the sensible one.
3. **Guards are not name-checked.** A typo in a `when:` evaluates to `None` silently (`_Names.__missing__`). A
   scan of both scenarios found no unknown names today. Suggestion: in `validate_flowchart`, reject names that
   are not node ids, attributes, `group`, `age` or `t`.
4. **The Norwegian "Cancers missed 0 → 0 UNCHANGED" safety tile is vacuous**, because every patient has cancer
   and there is no discharge exit. Show "n/a (all patients have cancer)".
5. **Small fractions displayed as 0% or 1% (fixed in export).** For example "lung cancer risk after negative
   cxr: 0%" (true value 0.35%). `fmt_fraction` now shows 0.35%. Test: `test_small_fractions_are_not_shown_as_zero`.
6. **Odd wording when selection optimism is negative.** Screen 3 says "flatters the result by about -1.4
   points". It also says "(together with the ones above)" when there is only one change.
7. **Fractional counts.** "27.5 cancers missed ... out of 260.5 cancers" is a 2-cohort mean. Label it "per
   cohort (average of 2)".
8. **No uncertainty on the headline numbers.** Finnish cohorts have about 260 cancers. The held-out baseline is
   20.5% in cohort 301 and 14.6% in cohort 302, and `docs/sensitivity.md` reports a single-seed sd of 7 pp on
   the bundled gain. Show the per-cohort range next to 18% → 61%; the gain itself is stable at about 43-44 pp
   in both cohorts.
9. **`docs/finland_scenario.md` §6 is stale.** Utilisation is already computed over [warm-up, last arrival],
   and `urgent_lead_days` exists. §3 still describes the negative-`extra_wait` workaround.
10. **The submission does not mention the in-loop decision-model result.** The model matched the hand-written
    rule, and "a model that optimises each patient separately overloads the shared queue unless it sees queue
    state" is a genuine insight (master plan §10). Add one line; it supports Insight and honesty at once.
11. **`median_days_to_diagnosis` is not comparable across flowcharts** (already noted in
    `finland_scenario.md`). It should not be shown side by side without that caveat.

---

## Fixes made in this branch

| Fix | Files | Test |
|---|---|---|
| Forced retry fallback revives its dead-skipped descendants (results-neutral on shipped scenarios) | `pathway_sim/engine.py` | `test_forced_fallback_runs_its_downstream_steps` |
| Capacity-vs-order bar label built from the accepted step kinds | `demo/export.py` | `test_suggested_change_label_matches_accepted_kinds` |
| Stokstad fourth change labelled "at referral triage, before the first hospital visit" | `demo/export.py` | `test_sampling_label_says_triage_not_first_visit` |
| Small fractions in the sources table no longer rounded to 0% | `demo/export.py` | `test_small_fractions_are_not_shown_as_zero` |
| Screen 4 headline says "reordering" only when the change reorders | `demo/index.html` (JS) | headless screenshot |
| Tornado central line and lede use the sensitivity's own comparison | `demo/index.html` (JS) | headless screenshot |
| Proposal side checked blind to hidden truth (no code change) | — | `test_proposal_scores_ignore_hidden_truth` |

**Bundle regenerated** with the fixed code (`python3 demo/export.py`, 8.5 min, then `python3 demo/embed_bundle.py`).
The structural diff against the previous bundle has 13 differences, all labels or display strings: 6 percentage
strings in the sources table, 6 occurrences of the sampling label, and 1 capacity-vs-order bar label. **No
number changed**, which confirms that the engine fix is results-neutral on the shipped runs. Re-run
`fill_numbers.py` only if the team edits the templates; no filled number moved.

## Top 5 fixes before submission

1. **Reframe the Finnish headline (B1).** State that the 61% is "urgent booking for every referred patient,
   *if* the assumed urgent booking times hold without extra slots". Show the 0/50/100% dose-response, or lead
   with the capacity-controlled reorder (54% against 31%). Add urgent leads to the sensitivity analysis.
2. **Make the numbers agree everywhere (M9).**
   - video "two changes" → one
   - master plan 57% → 61%
   - drop "No sensitivity analysis yet"
   - demo time and screen count
   - 78.3 against 79.0
   - the stale equity sentence
   - the "first visit" wording in the submission

   Then refill the pitch copies.
3. **Replace "131 parameters, 18 assumptions" with counts from the scenario files (M2),** and say plainly
   that every Finnish capacity and booking time is an assumption calibrated to published waits.
4. **Disclose the two Norwegian caveats (M3, M7).** The 80% "prediction" carries the calibrated
   PET-at-triage practice (66% without it). The blind search chose from a menu that contained the authors'
   changes.
5. **Fix the safety story (M4, M5).**
   - Turn on the tissue-confirmed guardrail in Finland, or stop claiming it there.
   - Reword the GP-first rejection as "did not pass on training patients by one cancer; neutral to positive on
     unseen patients".
