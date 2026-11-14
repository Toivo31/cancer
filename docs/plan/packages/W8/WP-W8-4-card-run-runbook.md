# WP-W8-4: After tonight's Gemini card run: audit, merge, training sets, pitch refill (runbook)

| | |
|---|---|
| Component | C1 patient engine (D52 to D54, D58, D59, D60 `g2@3`), C6 training data, pitch (D57) |
| Status | not started; waits for the run |
| Size | M in total; each ticket S. Wall clock: run 60 to 90 min, the rest about 60 min |
| Needs | `w8/g2blind` merged (result author `g2@3` default; **5 commits not yet on `overnight/sim` at 21:15 UTC**), `w8/catalogue-check` merged (yes: catalogue hash `436ff728b717`), gate green |
| Owned paths | `libraries/gemini_v2_*` (new), `libraries/<name>.md` (new handoff notes), `libraries/README.md`, `libraries/ref500.md` (caveat line), `docs/platform/jev-training-data.md` (numbers), `docs/pitch/filled/**` (only via `fill_numbers.py`), `runs/` |
| Do not edit | `patient_engine/`, `catalogue/`, `docs/pitch/*.md` templates (pitch lane), `docs/plan/04-status.md` (integrator: hand over the lines instead) |
| Review required | yes: numbers said aloud (D57) and libraries used for training (I1) |
| Track | before freeze (04:00 UTC) |

Written so whoever does it at 2 a.m. can follow it top to bottom. Every step says what to look at and when to stop.
Run from the repository root with `.venv` active. Synthetic data only.

## Step 0: preconditions (agent, 5 min) — W8-RB-T1

```bash
git log --oneline -1 && git status --short              # on the integration branch, clean
grep -n "results_prompt\|PROMPT_VERSIONS" patient_engine/authors.py | head    # g2@3 is the default (D60)
python -m patient_engine library-info libraries/ref500  # catalogue hash 436ff728b717...
bash scripts/gate.sh                                     # fast tier green (known: see WP-W8-6 T1 for the test_expr guard)
```

Stop if `g2@3` is not the default: the run would make `g2@2` text, which review w8 B1 showed is not blind.
`ref500`: `w8/g2blind` changes histology for non-cancer cards (review w8 M2), so `ref500` must be **regenerated after that
merge** (its id changes again; `w8/catalogue-check` regenerated it before). Check `libraries/ref500.md` names the current id.

## Step 1: trial and full run (Tuomas, the key holder) — W8-RB-T2

```bash
export LLM_API_KEY="..."                         # never in a file
bash scripts/generate_gemini.sh trial            # 30 cards, ~5 min; prints the audit lines
bash scripts/generate_gemini.sh full             # 5 x 500 in the background (seeds 13 to 17), 60 to 90 min
bash scripts/generate_gemini.sh status           # until every seed says "done"; PARTIAL or WITH FAILED CARDS: see below
bash scripts/generate_gemini.sh resume           # restarts stopped runs; for failed cards follow its printed advice
```

Go from trial to full only if, in the trial's audit: `report_wording` and `leak` pass, `background_realism` passes, and the
`presenting` check passes. Findings cells are too few at n 30 to judge. Consider `CONC=10` if the trial hit rate limits
(review w8 M3).

## Step 2: audit each library (agent, 20 min) — W8-RB-T3

```bash
for s in 13 14 15 16 17; do
  python -m patient_engine audit libraries/gemini_v2_s${s}_500 --catalogue catalogue/lung-primary-care \
    --out runs/audit/gemini_v2_s${s}_500 | tail -25
done
```

For each library write down: checks passed of 40, which failed; accepted, discarded, failed cards
(`libraries/gemini_v2_s<seed>_500.work/generation_report.json`); accepted cards per condition against the design counts in
`manifest.json` (the audit does not check this; review w8 Q7 "design_coverage": flag any condition more than 5 points off).
Read 20 result reports from `runs/gen_cache/g2_bank` and 10 patient accounts by eye for condition words (review w8 Q7).

**Stop rule (a judgement for Tuomas; options):** (a) use only libraries that pass every check; (b) use libraries whose only
failures are in cells with too few cards, listed in the handoff note; (c) if all fail on findings: keep them outside the
scanned folder like `libraries/g2v1_audit_fail/` and train on `ref500` only (D54 fallback; V11: headline numbers stay on the calibrated generator anyway). Lean: (b),
with the failures named in the note and in the pitch's data-transparency sheet.

## Step 3: handoff notes and commit (agent, 10 min) — W8-RB-T4

One `libraries/gemini_v2_s<seed>_500.md` per library (copy the shape of `libraries/ref500.md`): id, catalogue hash, prompts
(`g1@2`, `g2@3`), model, counts, audit result, failures, intended use (train or held out). Update `libraries/README.md`
(the paragraph on `gemini_*`; `gemini_trial` and `gemini_s2_30` no longer match the catalogue) and the stale caveat in
`libraries/ref500.md` line 59 ("177 of about 260" assumptions: take the current count from
`python scripts/catalogue_stats.py`). Check sizes before committing (`du -sh libraries/gemini_v2_*`); commit only
`manifest.json` + `cards.jsonl.gz`, never `.work/`.

## Step 4: merge (agent, 5 min) — W8-RB-T5

Options: (a) **no merge for training**: the builder takes every `gemini_*` library of the world's catalogue and holds out the
highest seed; (b) merge seeds 13 to 16 into `libraries/gemini_v2_train_2000` for one id to quote, keep seed 17 separate;
(c) merge all five for the demo's card counts. Lean: (b) only if one id is needed in the pitch or demo, else (a).
**Trap with (b) or (c):** the builder would then read the merged library **and** its sources (same cards twice). Move the
sources out of `libraries/` or pass `--exclude` for each. Command:
`python -m patient_engine merge libraries/gemini_v2_s1{3,4,5,6}_500 --out libraries/gemini_v2_train_2000 --catalogue catalogue/lung-primary-care`
then `python -m patient_engine library-info libraries/gemini_v2_train_2000` (lists sources).

## Step 5: training and held-out sets (agent, 15 min) — W8-RB-T6

```bash
python scripts/build_training_set.py --dry-run                       # read the list: which libraries, which is held out
python scripts/build_training_set.py --holdout libraries/gemini_v2_s17_500
python scripts/build_training_set.py --holdout libraries/gemini_v2_s17_500 --mix balanced
```

Check in the dry run: held out is `gemini_v2_s17_500` (pattern fixed by review w8 M4); no `g2@1` library and no library of
the old catalogue hash in the list (the script warns on `g2@1`); no library counted twice (step 4 trap). Read
`runs/training/build_summary.json`: row counts, label balance, checks. Copy the counts into
`docs/platform/jev-training-data.md`. Say where the files are for the JEV owner (they are git-ignored; how they reach the owner
is a human question: see WP-W8-9 H8).

## Step 6: refill the pitch and demo bundles (agent with the pitch lane's OK, 15 min) — W8-RB-T7

```bash
python docs/pitch/fill_numbers.py --strict          # exits 1 on any unfilled placeholder
git diff --stat docs/pitch/filled
pytest -q tests -k "pitch_templates_fill"           # the golden check
python demo/export_all.py                           # bundles that read libraries (cards, start, jev)
```

Read the diff of `docs/pitch/filled/numbers_sheet.md` line by line: every changed number must be explained by the new
libraries (E-section card counts and ids) or by the catalogue v2 counts. Anything else changed: stop and ask the pitch lane.

## Step 7: hand over (agent, 5 min) — W8-RB-T8

Post RELEASE on the channel with: library ids, audit results, what is held out, training row counts, pitch diff summary.
Give the integrator the lines for `docs/plan/04-status.md` ("Model-written cards" paragraph and "Next" rows 1 and 2) rather
than editing it.

## Tickets

| | ID | Ticket | Size | Owner | Needs | Done when |
|---|---|---|---|---|---|---|
| [ ] | W8-RB-T1 | Check preconditions (g2@3 default, catalogue v2, ref500 regenerated after g2blind, gate) | S | agent | g2blind merged | step 0 commands as described; any failure posted as PROBLEM |
| [ ] | W8-RB-T2 | Run trial, then full, to completion | S | **human (key holder)** | T1 | `status` says done for seeds 13 to 17 |
| [ ] | W8-RB-T3 | Audit the five libraries and record per-library results; Tuomas picks the stop-rule option | S | agent + human decision | T2 | table of results in the handoff notes; option chosen |
| [ ] | W8-RB-T4 | Handoff notes, README, ref500 caveat; commit the libraries | S | agent | T3 | notes exist; `library-info` verifies each committed library |
| [ ] | W8-RB-T5 | Merge (option chosen in step 4) without double counting | S | agent | T4 | dry run of step 5 lists each card once |
| [ ] | W8-RB-T6 | Build training and held-out sets (realistic and balanced) | S | agent | T5 | `build_summary.json` checks pass; counts in `jev-training-data.md` |
| [ ] | W8-RB-T7 | Refill pitch and demo bundles; explain every changed number | S | agent (pitch lane OK) | T6 | `fill_numbers.py --strict` exit 0; golden check green; diff explained in the RELEASE post |
| [ ] | W8-RB-T8 | Hand over: channel RELEASE and 04-status lines for the integrator | S | agent | T7 | posted |
