# Gemini libraries that fail the audit (kept for the record, not used)

Five libraries of 500 cards each (2,495 accepted cards; seeds 3 to 7), written on 14 Nov 2026 by
gemini-3.8-flash with patient prompt `g1@1` and results prompt `g2@1`, about 150 M tokens in total.
They sit one level below `libraries/` on purpose: `scripts/build_training_set.py`, `demo/export_cards.py`
and `docs/pitch/fill_numbers.py` only scan `libraries/*/`, so nothing picks these up automatically.

Each folder has its `audit.md`. All five fail the same 13 of 40 checks:

- `report_wording`: the report text gives away which results are wrong (review B1; fixed by `g2@2`, D52).
- `background_realism`: ages and pack-years from the old background step (fixed by the population model, D53).
- `findings.*` for all 11 conditions: the presentations are far more textbook than the catalogue's
  frequencies (e.g. asthma wheeze 100% vs 70%, pneumonia fever 100% vs 53%), and unrelated labs
  (calcium, ALP, LDH) sit below the reference median in nearly every card. Root cause under
  investigation on branch `w8/g1skew`; a fresh run with `g2@2` alone would not fix this part.

Use: pipeline testing and as a contrast to the audited libraries. Not for training, the demo or pitch numbers.
