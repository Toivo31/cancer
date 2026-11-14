# Video script, 2 minutes

Numbers in double square brackets are filled from `demo/data/demo_bundle.json` by `fill_numbers.py`; record from `filled/video_script.md`. Screens refer to `demo/index.html` (keys 1-6). Two team decisions affect the opening: D20 (Finnish target is a provisional [[f_target]] days; alternative is to open on "[[f_median_gain]] days faster") and D17 (Norwegian headline with or without the faster scanner; both numbers are spoken below).

| Time | Screen | Voice-over |
|---|---|---|
| 0:00-0:18 | Screen 1, headline number: [[f_share_base]]% to [[f_share_opt]]%, label "synthetic data" | In our synthetic Finnish county, [[f_share_base]] percent of lung cancer patients start treatment within [[f_target]] days of first contact. With two reorders of the steps and no new equipment, [[f_share_opt]] percent. All patients are simulated, and we say so. |
| 0:18-0:38 | Screen 2, four stage bars, waiting vs service | Most of the delay is waiting, not testing: [[f_wait_share]] percent of the days, mostly booking time calibrated to published waits. The biggest block is in primary care, about [[f_wait_detection]] days before a referral. |
| 0:38-1:00 | Screen 5, flowchart before and after | Our optimiser proposes changes using only what each step revealed. We report on patients it never saw. It suggests two reorders: reserve the treatment slot when the case goes to the tumour board, and book the specialist visit as soon as the referral arrives. Urgent booking for every referral would give [[f_cond_share_100]] percent, but only if booking times we assumed hold. That is conditional, not our result. |
| 1:00-1:30 | Screen 5, validation: our run vs published 40 / 48 / 80 | We checked it against a real Norwegian hospital. Fitted only to the observed pathway, it reproduces [[s_obs_share]] percent and predicts [[s_auth_share]] for the authors' pathway; they published [[s_pub_opt]]. With PET-CT ordered only at the first visit it would say [[s_auth_pet_first_visit]]. It overshoots on a faster scanner alone: [[s_fast_share]] against [[s_pub_fast]]. Searching a menu of about [[s_candidates]] single changes, not told which the authors made, it finds their three plus one, and with no new equipment reaches [[s_noeq_share]] percent. |
| 1:30-1:48 | Screen 6, two groups before and after | Under our assumptions both groups gain: vague symptoms from [[f_ns_share_base]] to [[f_ns_share_opt]] percent, alarm symptoms from [[f_ss_share_base]] to [[f_ss_share_opt]]. The gap in days [[f_gap_days_narrows]], [[f_gap_days_base]] to [[f_gap_days_opt]]; in percentage points it [[f_gap_pp_widens]], [[equity_gap_base_pp]] to [[equity_gap_opt_pp]]. The gap itself is our assumption. |
| 1:48-2:00 | Recommendation card | Our proposal: make the two reorders in one county, monitor waits by county, and collect real booking data before any urgent track. A doctor decides every case. |

## Spoken text only

In our synthetic Finnish county, [[f_share_base]] percent of lung cancer patients start treatment within [[f_target]] days of first contact. With two reorders of the steps and no new equipment, [[f_share_opt]] percent. All patients are simulated, and we say so.

Most of the delay is waiting, not testing: [[f_wait_share]] percent of the days, mostly booking time calibrated to published waits. The biggest block is in primary care, about [[f_wait_detection]] days before a referral.

Our optimiser proposes changes using only what each step revealed. We report on patients it never saw. It suggests two reorders: reserve the treatment slot when the case goes to the tumour board, and book the specialist visit as soon as the referral arrives. Urgent booking for every referral would give [[f_cond_share_100]] percent, but only if booking times we assumed hold. That is conditional, not our result.

We checked it against a real Norwegian hospital. Fitted only to the observed pathway, it reproduces [[s_obs_share]] percent and predicts [[s_auth_share]] for the authors' pathway; they published [[s_pub_opt]]. With PET-CT ordered only at the first visit it would say [[s_auth_pet_first_visit]]. It overshoots on a faster scanner alone: [[s_fast_share]] against [[s_pub_fast]]. Searching a menu of about [[s_candidates]] single changes, not told which the authors made, it finds their three plus one, and with no new equipment reaches [[s_noeq_share]] percent.

Under our assumptions both groups gain: vague symptoms from [[f_ns_share_base]] to [[f_ns_share_opt]] percent, alarm symptoms from [[f_ss_share_base]] to [[f_ss_share_opt]]. The gap in days [[f_gap_days_narrows]], [[f_gap_days_base]] to [[f_gap_days_opt]]; in percentage points it [[f_gap_pp_widens]], [[equity_gap_base_pp]] to [[equity_gap_opt_pp]]. The gap itself is our assumption.

Our proposal: make the two reorders in one county, monitor waits by county, and collect real booking data before any urgent track. A doctor decides every case.

## Claims to check before recording

- "Missed cancers do not rise": held-out [[f_missed_base]] to [[f_missed_opt]] per cohort in the current bundle (Finland only; in the Norwegian check every patient has cancer, so the check is vacuous there and the script does not claim it); recheck after any rerun.
- "Biggest block in primary care": the largest stage in the current bundle is [[f_top_stage]] at [[f_top_stage_wait]] days; if a rerun changes this, change the sentence. (An earlier draft said the longest queue sat between referral and diagnosis; the run does not show that.)
- "Gap in days / gap in points": [[f_gap_days_narrows]] and [[f_gap_pp_widens]] in this bundle; flip the wording if a rerun reverses either.
- "Finds the authors' three changes plus one": the fourth plans tissue sampling at referral triage, before a specialist has seen the patient, which needs a clinical check (D18); drop "plus one" if the team removes it.
- Word count of spoken text is about [[spoken_words]]; trim the validation paragraph first if the read runs over two minutes (about 150 words a minute).
