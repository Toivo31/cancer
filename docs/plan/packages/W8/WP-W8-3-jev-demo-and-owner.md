# WP-W8-3: JEV demo page: real outputs for the live-only presets, the model card's open facts, a model-policy run

| | |
|---|---|
| Component | C4; demo page `demo/jev.html` (lane `w8/jev-demo`, merged); D63, D64 |
| Status | not started |
| Size | S (T1, T2), owner's answers (T3), M (T4) |
| Needs | T1: the hosted gateway up (no key needed); T4: WP-W8-1 T2 and WP-W8-2 T2 |
| Owned paths | `demo/data/jev_preset_outputs.json` (new, written by the script), `demo/data/jev_bundle.js` (regenerated), `demo/jev.js` (the `HF_URL` line and model-card fact strings only), `docs/platform/jev-birch.md` (results section), new `docs/jev_policy_run.md`, `runs/` |
| Do not edit | `decision_api/`, `demo/export_jev.py` logic (only run it), `docs/plan/ui-revamp/` |
| Review required | yes for T4 (a result that may be quoted) |
| Track | T1, T2 before freeze; T3 whenever the owner answers; T4 after submission unless started by about 23:30 UTC |

## Outcome

`demo/jev.html` opened from disk shows a real recorded output (label "Recorded · deployed model", checkpoint 2350) on all
five presets, not only "reasoning"; the Hugging Face fact links to a real page or stays a labelled placeholder (D63); and
there is one honest comparison of the model policy against the placeholder tables on the same patients.

## Why

Today only the reasoning preset has a recorded model output; `gp_visit`, `triage`, `screening` and `compare` say "no answer"
until someone presses a live button with an endpoint. Judges open the page offline (D60). D63 keeps the page's wording and
leaves training data and the HF link to the owner.

## Acceptance

- [ ] `python demo/export_jev.py --record https://cancer123--birch-decision-1138-demo.us-east.modal.run/api/decision`
      writes `demo/data/jev_preset_outputs.json` with four new entries whose `backend.mode == "model"` and `backend.step == 2350`;
      `python demo/export_jev.py` then bundles them; `pytest tests/test_demo_jev.py` green.
- [ ] Page check (headless browser, 1440x900): every preset card shows a recorded output with its label and timestamp; no
      console errors; nothing scored offline.
- [ ] Edge: a preset whose live call fails stays "no answer" with the error, and the script exits non-zero (no fixture kept
      unless `--allow-non-model`).
- [ ] `HF_URL` is either a URL the owner gave, or empty (placeholder text unchanged). Not guessed from repository names.

## Things to look at and weigh

- The gateway allows 6 submissions a minute; four presets fit. The `gp_visit` preset sends 8 actions (`GP_SUBSET`), within limits.
- Recording against 2350 while `demo/data/jev_recorded.json` (the owner's recordings) is also 2350: check both show the
  same checkpoint and hash on the page; if not, refresh with `--refresh-recorded origin/main` first.
- T4 sizing: about 4 decisions per patient, 1 or 2 calls each (WP-W8-2), 120 calls an hour: 30 patients is about 1 to 2 hours,
  100 patients about 4 to 7 hours. Weigh n against what the result can claim (it is a policy comparison on synthetic
  patients, not a validation); use common random numbers and the same patients for both policies.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | W8-JD-T1 | Record live outputs for `gp_visit`, `triage`, `screening`, `compare` on the hosted gateway and rebundle | S | gateway up | acceptance 1 to 3; posted FYI with the checkpoint and hash recorded |
| [ ] | W8-JD-T2 | Fill `HF_URL` in `demo/jev.js` once the owner gives a public page | S | T3 (a) | link opens; `test_demo_jev.py` green. If no answer by freeze: leave empty (D63) |
| [ ] | W8-JD-T3 | **JEV owner**: answer the model-card questions (post on the channel; record answers in `docs/platform/jev-birch.md`) | S | – | answers to: (a) public Hugging Face page for checkpoint 2350, or none; (b) training data of checkpoint 2350 (datasets, whether any of our synthetic encounter rows were used); (c) the "correction from the whole answer set": confirm the page's wording (D63 keeps it unless the owner corrects it); (d) head size actually deployed (layers, width; the page says 2 layers from `head_layers_default`) and the adapter rank and the 7 adapted blocks |
| [ ] | W8-JD-T4 | Model policy against placeholder tables on the same patients (the run asked for in channel 1114-162540; D64 settles cost) | M | WP-W8-1 T2, WP-W8-2 T2, WP-W8-1 T5 (a) | `docs/jev_policy_run.md`: n, seeds, calls, cache hits, time; per policy the encounter metrics (`scripts/encounter_report.py`), referrals, time to referral for cancers, tests per patient; labelled "model policy, n = N, synthetic"; no number goes into the pitch without D57's sheet |
