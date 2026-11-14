# WP-W8-5: Finland evidence worlds: rerun the optimiser inside them, and the items not run

| | |
|---|---|
| Component | C5 optimiser, C7 evidence; follows `w8/fi-sens` (merged): `scripts/fi_evidence_sensitivity.py`, `docs/evidence_sensitivity.md` |
| Status | not started |
| Size | M (T1, T2), S to M each for T3 to T6 |
| Needs | nothing; uses the generated worlds `scenarios/experiments/finland_evidence_*.yaml` |
| Owned paths | `scripts/fi_evidence_sensitivity.py`, new `scripts/fi_evidence_optimise.py`, `scenarios/experiments/finland_evidence_*.yaml`, `docs/evidence_sensitivity.md` (new sections and the "What this does not cover" list), `docs/review_checks/fi_evidence_*.json` |
| Do not edit | `params/`, `scenarios/finland_lung.yaml`, `optimiser/`, `pathway_sim/`, pitch files (hand corrected sentences to the pitch lane, as `w8/fi-sens` did) |
| Review required | yes if any sentence for the pitch changes |
| Track | after submission (the pitch already says the gains are slightly pessimistic; nothing here is needed for Sunday) |

## Outcome

`docs/evidence_sensitivity.md` answers, for each alternative world: what does the optimiser find **when searched inside that
world**, and is the gain larger than when the world-A flowchart is carried over? Plus four items that were listed as not run.

## Why

`docs/evidence_sensitivity.md` "Not done" and "What this does not cover": the optimiser's flowchart was found in world A and
evaluated unchanged elsewhere (gains "slightly pessimistic"); X1 breaks because capacity was not recalibrated; the extra delay
was put only at treatment booking; symptom odds ratios, EBUS and CT-biopsy accuracy were not run.

## Acceptance (each ticket adds a section with a table and a one-paragraph verdict)

- [ ] Same held-out cohorts (seeds 301 to 304) and common random numbers as the existing tables; search cohorts separate
      from evaluation cohorts (the optimiser must not see 301 to 304).
- [ ] Every world's guardrails are reported (the optimiser's `guardrails()`), and any world where the found flowchart fails
      them says so.
- [ ] Edge: a world where the optimiser finds nothing acceptable reports "no change accepted", not an error.
- [ ] A rerun of `python scripts/fi_evidence_sensitivity.py --quick` still reproduces the current world-A numbers (regression).

## Things to look at and weigh

- Cost: one optimiser search on the Finnish scenario at the size of `runs/opt_fi_noft.json`; find its command in
  `docs/commands.md` section 2 and in `demo/export_flow.py:111`. Eight worlds times one search may take hours on the shared
  machine; consider starting with L67, X2 and ALT (the lung-specific worlds) and adding others only if they differ.
- Keep the D27 constraint (reorder and standardise edits only; no fast track) in every search, or the comparison is not like
  for like.
- For "delay placed earlier": which step is defensible (specialist booking lead, board cycle)? Read
  `docs/booking_vs_queue.md` first: the reorders save overlapping waiting, so where the delay sits may matter.
- X1 recalibration: the aim is a world where the pooled primary-care X-ray accuracy holds **and** utilisation is like world A.
  Weigh scaling clinic and CT capacity against changing the referral threshold; say which and why.
- Symptom odds ratios and EBUS / CT-biopsy accuracy are not inputs of the chain scenario today
  (`docs/evidence_sensitivity.md` last list). First check whether they can be inputs at all; if not, the honest output is a
  short note "not an input; would need X", not a forced world.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | W8-FS-T1 | Optimiser search inside L67, X2 and ALT (D27 edit set), evaluated on held-out cohorts | M | – | table: world, accepted edits, gain in points and days for found vs carried-over flowchart, guardrails; JSON in `docs/review_checks/fi_evidence_optimise.json` |
| [ ] | W8-FS-T2 | Same for N37, L92, P (only if T1 shows a different edit set anywhere) | M | T1 | as T1, or a one-line "not run because T1 found the same edits" |
| [ ] | W8-FS-T3 | Recalibrate capacity in X1 to world-A utilisation and rerun | M | – | utilisation of clinic and CT within 5 points of world A; gain and ranking reported |
| [ ] | W8-FS-T4 | Place the extra diagnosis-to-treatment delay earlier (one defensible step) for L67 | S | – | section comparing gain against L67 as built |
| [ ] | W8-FS-T5 | Symptom odds ratios: can they enter the chain scenario? Run if yes, else a scoped note | S | – | section or note with the reason |
| [ ] | W8-FS-T6 | EBUS and CT-guided biopsy accuracy (`docs/evidence_research.md` lines 41 to 43): same check as T5 | S | – | section or note |
