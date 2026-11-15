# Start here: ten minutes for a technical judge

The README says what this is. This page says what to read to check whether we are honest. Everything is synthetic; no real patient data is used.

## Ten-minute reading order

| Min | Open | What to look for |
|---|---|---|
| 0 to 2 | `README.md`, then the site in `website/` | What we built, the headline result with what it depends on, and the one command that reproduces it |
| 2 to 4 | `docs/pitch/filled/numbers_sheet.md` | Every number we say aloud, the one sentence it may be used in, its range, and a status: fitted, predicted, simulated, published or assumption. Row A11 lists a number we retired because it was the corner of a wider band. Rows E4, E4b and G2 list things we do not stand behind |
| 4 to 7 | `docs/validation.md`, section "Robustness" | The Norwegian check. We fitted only today's order. The prediction for the authors' reordering is a band over 184 settings, not a point. The faster-scanner prediction misses (we over-predict). The ranking is the part that holds in every setting |
| 7 to 9 | `docs/review_w7.md`, "Verdict" and "Ten questions a critical judge will ask" | An independent review written before the freeze, with its blockers: a wording leak in model-written test reports, no population model for patient backgrounds, stale demo numbers. Open findings are kept as expected-failing tests (`tests/test_review_w7_*.py`) |
| 9 to 10 | `docs/ledger.md` | Which inputs of the Finnish scenario cite a source and which are assumptions. Most are assumptions, including every capacity and booking lead |

## Three checks you can run yourself

1. **Does the decision side see the hidden truth?** The record a decider sees is built in `patient_engine/reveal.py` and `jev/record_context.py`. The review traced every path (`docs/review_w7.md`, "What was checked and found safe"). It found one leak, in model-written report text, and says where.
2. **Is the Finnish gain a fact about Finland?** No. Read `scenarios/finland_lung.yaml` and `docs/ranges.md`. The claim is narrower: two reorders with no new capacity help in every one of 12 simulated cohorts, under stated assumptions.
3. **Do the pages agree with the sheet?** `python -m pytest -q tests/test_demo_start.py` (about a second). Other commands: `docs/commands.md`.

## Terms

- **Flowchart:** an editable diagram of care steps, with prerequisites, waits and capacity.
- **Held-out:** patients the optimiser never used while searching. Results are reported on them.
- **Card:** one synthetic patient: hidden truth plus the pre-written result of every test.
- **JEV:** the team's decision model. It scores the offered options at a choice point; a person decides. Scores are relative, not probabilities. The headline numbers do not depend on it.

## Where else

`README.md` (summary and caveats), `docs/repo_map.md` (every folder), `docs/pitch/filled/deck.md` (the "safe to claim / do not claim" box), `docs/plan/04-status.md` (what is built and what is not).
