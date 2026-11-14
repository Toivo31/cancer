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
