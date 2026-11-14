# WP-W4-3: Library audit (G4)

| | |
|---|---|
| Component | C1 P7 ("Generation pipeline" G4), C2 K8 |
| Size | M · Model: Sonnet |
| Needs | merged `patient_engine` (library, catalogue, reference generator, states) |
| Owned paths | `patient_engine/audit.py`, `patient_engine/commands/audit.py`, `tests/test_pe_audit*.py`, `catalogue/lung-primary-care/audit_tolerances.yaml` (new) |

## Outcome

`python -m patient_engine audit <library> --catalogue catalogue/lung-primary-care` writes
`audit.json` and `audit.md` next to the library and prints pass/fail per check:
frequencies of each finding by condition vs the catalogue's reference (with a binomial interval
for the library's size), realised sensitivity and specificity of every binary test output vs the
catalogue (computed from observations vs findings, per state), share of non-diagnostic attempts,
continuous value distributions vs reference median/p90, diversity (near-duplicate cards: identical
findings and background), presenting complaints that are not true symptoms, and the share of notes
flagged by the validator's leak rule. Tolerances per check in `audit_tolerances.yaml` (each with a
reason; lean: fail when outside the 99% binomial interval and more than 5 percentage points off).

## Acceptance

- [ ] A reference-generated library of 1 000 lung cards passes (it is the baseline; if it does not, the tolerance or the generator is wrong: report which).
- [ ] A deliberately skewed library (copy and flip 30% of one test's results) fails exactly that check (test).
- [ ] Runs in under 30 s for 1 000 cards; `scripts/gate.sh` green.

## Report (builder fills in)

**Built.** `patient_engine/audit.py`, `patient_engine/commands/audit.py`, `catalogue/lung-primary-care/audit_tolerances.yaml`, `tests/test_pe_audit.py` (fast) and `tests/test_pe_audit_1000.py` (slow list).

Command: `python -m patient_engine audit LIBRARY --catalogue catalogue/lung-primary-care [--tolerances F] [--out DIR] [--json]`. Writes `audit.json` and `audit.md` into the library directory (they are not part of the library hash) and prints pass or fail per check; exit 0 pass, 1 fail, 2 error.

**Method.** The reference for each cell is the catalogue leaf resolved with that card's own background, attributes, findings and active conditions, so the expected value of a group is the mean over its cards. Interval: exact binomial for the group size at the mean probability. A cell fails outside the interval and more than `pp` points off; fewer than `min_n` cases is `skipped`, never pass.

**Checks (38 on the lung catalogue, about 750 cells).**
- `findings.<condition>`: single-illness cards, state `all_active`. Binary findings, categorical levels, and for measured findings the share below the card's reference median and p90 (the expected share is read from the card's own reference distribution, so rounding, clamping and discrete distributions do not bias it).
- `accuracy.<test>`: realised sensitivity and specificity per binary output, accuracy per categorical output, from observations against the same state's findings, per state group (`all_active`, and every resolved state pooled).
- `non_diagnostic`: per test and state group, against the catalogue's rate (expected 0 where the test has none).
- `state_consistency` (resolved states: no symptom appears, no resolved cause remains), `presenting` (complaints that are not true symptoms), `diversity` (cards equal to an earlier card), `leak` (the validator's rule 8, run alone, over notes).

**States.** Every state of every card enters accuracy, non-diagnostic and consistency. Frequencies are audited only in `all_active` on cards with one condition: in resolved states and with a co-existing illness the catalogue gives no single reference number (a mixture of causes), so those are not compared to a reference frequency (listed in `not_audited` in the report).

**Tolerances and a deviation from the lean.** The lean was 99% per cell and 5 points. On three 1 000-card reference libraries (seeds 1 to 3, generator `--fake`, which writes the reference generator's numbers) that fails 2, 1 and 3 cells by chance, all inside what about 750 independent cells give at 99%. The generator is right, the per-cell level was wrong, so `z` is 4.2 (99% for the whole report) with the 5-point floor kept (7.5 for measured findings, 2 for non-diagnostic). All three seeds then pass. A 30% flip of one test's results fails exactly `accuracy.<test>`.

**Not done.** Measurement error of continuous outputs against `error_sd`; frequencies in resolved states and for co-existing illness; correlation between repeated attempts on one card (treated as independent, so a model library with over-consistent repeats gets intervals that are too narrow); free mode has not been run against a real model, so the tolerances are untested against model drift (only against skews made by hand). Library size matters: with fewer than about 300 cards many cells are skipped.
