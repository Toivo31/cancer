# Video script, 2 minutes

Numbers in double square brackets are filled from `demo/data/demo_bundle.json` by `fill_numbers.py`; record from `filled/video_script.md`. Screens refer to `demo/index.html` (keys 1-4). Two team decisions affect the opening: D20 (Finnish target is a provisional [[f_target]] days; alternative is to open on "[[f_median_gain]] days faster") and D17 (Norwegian headline with or without the faster scanner; both numbers are spoken below).

| Time | Screen | Voice-over |
|---|---|---|
| 0:00-0:18 | Screen 1, headline number: [[f_share_base]]% to [[f_share_opt]]%, label "synthetic data" | In our synthetic Finnish county, [[f_share_base]] percent of lung cancer patients start treatment within [[f_target]] days of first contact. With two changes to the pathway, [[f_share_opt]] percent. All patients are simulated, and we say so. |
| 0:18-0:38 | Screen 2, four stage bars, waiting vs service | Most of the delay is waiting, not testing: [[f_wait_share]] percent of the days. The biggest block is in primary care, about [[f_wait_detection]] days before a referral. |
| 0:38-1:00 | Screen 3, flowchart before and after | Our optimiser proposes changes using only what each step revealed. It reruns the same patients to accept a change, and we report on patients it never saw. It suggests two: fast-track patients once the hospital has handled the referral, and send nurse-first patients to a GP appointment. Missed cancers do not rise. |
| 1:00-1:30 | Screen 3, validation: our run vs published 40 / 48 / 80 | We checked it against a real Norwegian hospital first. Fitted only to the observed pathway, it reproduces [[s_obs_share]] percent on time, and predicts [[s_auth_share]] percent for the authors' pathway. They published [[s_pub_opt]]. It overshoots on a faster scanner alone: [[s_fast_share]] against [[s_pub_fast]]. Searching blind, it finds the authors' three changes plus one, and with no new equipment reaches [[s_noeq_share]] percent. Order beats capacity. |
| 1:30-1:48 | Screen 4, two groups before and after | Both groups gain: vague symptoms from [[f_ns_share_base]] to [[f_ns_share_opt]] percent, alarm symptoms from [[f_ss_share_base]] to [[f_ss_share_opt]]. The gap in days narrows, the gap in shares does not. How big that gap is, is our assumption. |
| 1:48-2:00 | Recommendation card | Our proposal: order tests together at the first specialist visit, pair direct scans with it, fast-track vague symptoms with published safeguards, monitor waits by county, and pilot in one county first. A doctor decides every case. |

## Spoken text only

In our synthetic Finnish county, [[f_share_base]] percent of lung cancer patients start treatment within [[f_target]] days of first contact. With two changes to the pathway, [[f_share_opt]] percent. All patients are simulated, and we say so.

Most of the delay is waiting, not testing: [[f_wait_share]] percent of the days. The biggest block is in primary care, about [[f_wait_detection]] days before a referral.

Our optimiser proposes changes using only what each step revealed. It reruns the same patients to accept a change, and we report on patients it never saw. It suggests two: fast-track patients once the hospital has handled the referral, and send nurse-first patients to a GP appointment. Missed cancers do not rise.

We checked it against a real Norwegian hospital first. Fitted only to the observed pathway, it reproduces [[s_obs_share]] percent on time, and predicts [[s_auth_share]] percent for the authors' pathway. They published [[s_pub_opt]]. It overshoots on a faster scanner alone: [[s_fast_share]] against [[s_pub_fast]]. Searching blind, it finds the authors' three changes plus one, and with no new equipment reaches [[s_noeq_share]] percent. Order beats capacity.

Both groups gain: vague symptoms from [[f_ns_share_base]] to [[f_ns_share_opt]] percent, alarm symptoms from [[f_ss_share_base]] to [[f_ss_share_opt]]. The gap in days narrows, the gap in shares does not. How big that gap is, is our assumption.

Our proposal: order tests together at the first specialist visit, pair direct scans with it, fast-track vague symptoms with published safeguards, monitor waits by county, and pilot in one county first. A doctor decides every case.

## Claims to check before recording

- "Missed cancers do not rise": held-out [[f_missed_base]] to [[f_missed_opt]] per cohort in the current bundle; recheck after any rerun.
- "Biggest block in primary care": the largest stage in the current bundle is [[f_top_stage]] at [[f_top_stage_wait]] days; if a rerun changes this, change the sentence. (An earlier draft said the longest queue sat between referral and diagnosis; the run does not show that.)
- "The gap in days narrows, in shares does not": [[f_gap_days_narrows]] and [[f_gap_pp_widens]] in this bundle; flip the wording if a rerun reverses either.
- "Finds the authors' three changes plus one": the fourth is booking tissue sampling at the first visit, which needs a clinical check (D18); drop "plus one" if the team removes it.
- Word count of spoken text is about 250; trim the validation paragraph first if the read runs over two minutes.
