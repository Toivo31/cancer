# WP-W8-9: Items waiting for a human, as tickets with options

| | |
|---|---|
| Component | across; source: `docs/plan/04-status.md` "Waiting for a human", the agent channel's open NEEDS-DECISION entries, `docs/decisions.md` |
| Status | open |
| Size | each S for the human; the agent follow-up is named per row |
| Owned paths | none (decisions go into `docs/decisions.md` through the integrator; agents act after the decision) |
| Track | marked per row: **before submission** or after |

Settled since 04-status was written, so **not ticketed**: which page is the main page (D60: `demo/start.html`, offline);
D17 Norway headline (D62); JEV page wording, training-data line and HF placeholder (D63; owner's answers are W8-JD-T3);
JEV budget (D64); "who owns JEV, does an API exist" (yes: the hosted gateway documented on `main`, PRs 4 to 6; see WP-W8-1);
"a language-model endpoint and budget for generating patients" (Tuomas runs `scripts/generate_gemini.sh` with his own key; WP-W8-4).

## Tickets

| | ID | Decision or action | Who | When | Options and lean | Agent follow-up |
|---|---|---|---|---|---|---|
| [ ] | W8-H1 | **Video voice-over: trim about 320 to about 300 words** (`docs/pitch/video_script.md`, spoken text; filled copy is what is recorded) | Eemeli (records), pitch lane edits the template | before submission | (a) **rewrite the Norway paragraph to D62's framing** ("from the hospital's structure at 40%, the optimiser found the authors' three changes; 62 to 86 across settings") and drop the 69-change menu and overshoot sentences: about 25 to 35 words, and it brings the script in line with D62 (the template still says D17 is open); (b) drop the conditional urgent-booking sentence ("Urgent booking ... not our result"): about 25 words, but it is the honesty clause for D27; (c) drop the gap-in-days sentence of the groups paragraph: about 20 words, loses the narrows/widens nuance. Lean: (a); the script's own note says trim the validation paragraph first | pitch lane: edit template, `python docs/pitch/fill_numbers.py`, check the spoken word count it prints |
| [ ] | W8-H2 | **Stale numbers in Eemeli's video files** | Eemeli | before submission | `video/dots/README.md:10` (61.5% as the optimiser's change; it is 33%, 61% is conditional); `docs/video_plan_draft.md` lines 38, 53, 78, 83, 94 ("18 to 61"); `video/dots/trailer.js:306` (80% with 88/67: D62 asks for ranges and the plausibility framing). Options: fix now; or mark the files as superseded by `docs/pitch/filled/video_script.md`. Lean: fix `trailer.js` if the trailer is shown; mark the two drafts superseded | none (Eemeli's files) |
| [ ] | W8-H3 | **Merge PR #3 and PR #2 into `main`** (or say which branch is submitted) | Toivo or Tuomas | before submission | D60 makes `demo/` the judges' page, and it exists only on `overnight/sim`. Options: (a) merge PR #2 after the freeze gate; (b) submit `overnight/sim` as the branch; (c) tag a commit. Lean: (a), after WP-W8-6 T1 and T2 make CI green; note that `main` also holds the newer `decision_api/` (WP-W8-1 T1) | integrator: gate, merge, tag |
| [ ] | W8-H4 | **No-disease-found presenters without symptoms** (D59 "needs Tuomas"): about 37% of the 20% have no symptom | Tuomas | before the card run if (b); else after | (a) **leave as is for Sunday and say so** in the data-transparency sheet; (b) give them their own symptoms plus a `care.yaml` rule that resolves the condition (tried in D59: moved the pinned loop run out of range: GP visits 4.25 to 5.8, cost 491 to 657 EUR; needs retuning); (c) drop the condition. Lean: (a) now, (b) after submission as a loop-tuning ticket | if (b): a WP for care rule + loop retune |
| [ ] | W8-H5 | **D42 and the vision assumptions** V2, V5, V6, V8 to V11 (above all V10, `guided` error rates) | Tuomas | after (built on them already) | confirm as written, or name the one to change. Lean: confirm; V10 is how every library is made | integrator: mark D42 settled |
| [ ] | W8-H6 | **Booking split** (channel 1114-141641) and D43 (booking leads stay fixed inputs) | Tuomas | after | (a) **keep wording; say plainly that leads are inputs** (the reorder gain rests on paper delays, not booking leads); (b) split booking lead from queue in the stage bars (display change, fits UI WP7 or WP6); (c) emergent leads (C3 S12, platform spike). Lean: (a) now, (b) with the UI work | if (b): one row in WP-W8-8 |
| [ ] | W8-H7 | **Older pending decisions** D18, D20, D25, D27 | Tuomas | D18 and D27 before submission (they are in the spoken script); D20, D25 after | D18 (optimiser's 4th change "tissue sampling at referral triage"): keep with "needs a clinical check" as spoken, or forbid it (`optimiser.needs`); lean keep, labelled. D20 (90-day Finnish target): keep 90 labelled provisional, or open on "8 days faster"; lean keep (and see `docs/evidence_sensitivity.md` reading S). D25 (reward days/30): keep. D27 (Finnish headline reorder-only, urgent booking conditional): keep; it matches the script | integrator: decisions rows |
| [ ] | W8-H8 | **How the training files reach the JEV owner** (`runs/training/` is git-ignored) | Tuomas and the JEV owner | after the card run | (a) a release asset or shared drive; (b) commit the gzip files to a separate branch; (c) the owner rebuilds with `scripts/build_training_set.py` from the committed libraries (deterministic: "same inputs, same bytes"). Lean: (c), with the exact command and `build_summary.json` hash | WP-W8-4 T6 writes the command |
| [ ] | W8-H9 | **Forks F2 to F7** (`docs/platform/README.md` section 5), built on the leans | Tuomas | after | confirm the leans (F2 sample, F3 our contract, F4 React, F7 off under a model) or reopen one | none unless reopened |
| [ ] | W8-H10 | A host for deployment (fork F5) | Tuomas | after | see WP-W8-6 T4 to T6 | WP-W8-6 |
| [ ] | W8-H11 | A clinician to read the catalogue | Tuomas | after | see WP-W8-7 T2 | WP-W8-7 |
| [ ] | W8-H12 | Automated JEV runs and the owner's "no bulk cohort inference" rule (D64 settles cost only) | Tuomas and the JEV owner | before W8-JD-T4 | see W8-JI-T5 (a), (b) | WP-W8-3 T4 |
