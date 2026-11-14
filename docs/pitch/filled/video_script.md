# Video script, 2 minutes

Numbers in double square brackets are filled from `demo/data/demo_bundle.json` by `fill_numbers.py`; record from `filled/video_script.md`. Screens refer to `demo/index.html` (keys 1-6). Two team decisions affect the opening: D20 (Finnish target is a provisional 90 days; alternative is to open on "8 days faster") and D17 (Norwegian headline with or without the faster scanner; both numbers are spoken below).

| Time | Screen | Voice-over |
|---|---|---|
| 0:00-0:18 | Screen 1, headline number: 18% to 33%, label "synthetic data" | In our synthetic Finnish county, 18 percent of lung cancer patients start treatment within 90 days of first contact. With two reorders of the steps and no new equipment, 33 percent. All patients are simulated, and we say so. |
| 0:18-0:38 | Screen 2, four stage bars, waiting vs service | Most of the delay is waiting, not testing: 87 percent of the days, mostly booking time calibrated to published waits. The biggest block is in primary care, about 30 days before a referral. |
| 0:38-1:00 | Screen 5, flowchart before and after | Our optimiser proposes changes using only what each step revealed. We report on patients it never saw. It suggests two reorders: reserve the treatment slot when the case goes to the tumour board, and book the specialist visit as soon as the referral arrives. Urgent booking for every referral would give 61 percent, but only if booking times we assumed hold. That is conditional, not our result. |
| 1:00-1:30 | Screen 5, validation: our run vs published 40 / 48 / 80 | We checked it against a real Norwegian hospital. Fitted only to the observed pathway, it reproduces 40 percent and predicts 80 for the authors' pathway; they published 80. With PET-CT ordered only at the first visit it would say 66. It overshoots on a faster scanner alone: 60 against 48. Searching a menu of about 69 single changes, not told which the authors made, it finds their three plus one, and with no new equipment reaches 67 percent. |
| 1:30-1:48 | Screen 6, two groups before and after | Under our assumptions both groups gain: vague symptoms from 13 to 26 percent, alarm symptoms from 27 to 50. The gap in days narrows, 11.2 to 9.9; in percentage points it widens, 13.6 to 24.6. The gap itself is our assumption. |
| 1:48-2:00 | Recommendation card | Our proposal: make the two reorders in one county, monitor waits by county, and collect real booking data before any urgent track. A doctor decides every case. |

## Spoken text only

In our synthetic Finnish county, 18 percent of lung cancer patients start treatment within 90 days of first contact. With two reorders of the steps and no new equipment, 33 percent. All patients are simulated, and we say so.

Most of the delay is waiting, not testing: 87 percent of the days, mostly booking time calibrated to published waits. The biggest block is in primary care, about 30 days before a referral.

Our optimiser proposes changes using only what each step revealed. We report on patients it never saw. It suggests two reorders: reserve the treatment slot when the case goes to the tumour board, and book the specialist visit as soon as the referral arrives. Urgent booking for every referral would give 61 percent, but only if booking times we assumed hold. That is conditional, not our result.

We checked it against a real Norwegian hospital. Fitted only to the observed pathway, it reproduces 40 percent and predicts 80 for the authors' pathway; they published 80. With PET-CT ordered only at the first visit it would say 66. It overshoots on a faster scanner alone: 60 against 48. Searching a menu of about 69 single changes, not told which the authors made, it finds their three plus one, and with no new equipment reaches 67 percent.

Under our assumptions both groups gain: vague symptoms from 13 to 26 percent, alarm symptoms from 27 to 50. The gap in days narrows, 11.2 to 9.9; in percentage points it widens, 13.6 to 24.6. The gap itself is our assumption.

Our proposal: make the two reorders in one county, monitor waits by county, and collect real booking data before any urgent track. A doctor decides every case.

## Claims to check before recording

- "Missed cancers do not rise": held-out 27.5 to 27.5 per cohort in the current bundle (Finland only; in the Norwegian check every patient has cancer, so the check is vacuous there and the script does not claim it); recheck after any rerun.
- "Biggest block in primary care": the largest stage in the current bundle is detection at 30 days; if a rerun changes this, change the sentence. (An earlier draft said the longest queue sat between referral and diagnosis; the run does not show that.)
- "Gap in days / gap in points": narrows and widens in this bundle; flip the wording if a rerun reverses either.
- "Finds the authors' three changes plus one": the fourth plans tissue sampling at referral triage, before a specialist has seen the patient, which needs a clinical check (D18); drop "plus one" if the team removes it.
- Word count of spoken text is about 280; trim the validation paragraph first if the read runs over two minutes (about 150 words a minute).
