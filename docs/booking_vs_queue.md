# Booking time versus queueing (review item, M8-6)

Script: `docs/evidence_checks/booking_vs_queue.py` (extends `docs/review_checks/finland_waiting_decomposition.py` to both held-out cohorts, 301 and 302, and to the accepted flowchart). Mean over treated cancers of the days on each patient's critical path, by kind of wait. Waiting plus service on the critical path equals time to treatment exactly (largest difference 0 d).

| Kind of wait (days per treated cancer) | Today | Suggested | Change |
|---|---|---|---|
| booking lead | 56.9 | 57.5 | +0.6 |
| assumed extra_wait | 14.6 | 14.6 | +0.0 |
| capacity queue | 11.7 | 11.0 | -0.6 |
| paper / weekly board | 9.6 | 2.5 | -7.1 |
| **Mean days to treatment** | 106.5 | 98.8 | -7.7 |

- **Most of the waiting is booking lead, not queueing.** Today 57 of 93 waiting days (61%) are the fixed booking lead (`min_lead_days`, tuned to published waits), 12 (13%) are capacity queueing. The dashboard and deck therefore say "waiting (booking time and queues)".
- **The accepted reorders remove paperwork and board time from the critical path, not booking or queue time.** The change in the table is -7.1 d in referral paperwork and board waiting and -0.6 d in capacity queueing; booking leads change by +0.6 d. Mechanism: the specialist visit is booked while the referral is being handled, and the treatment slot is reserved while the case waits for the board, so those waits overlap instead of adding up.
- **What the gain rests on.** The paperwork steps are `referral_triage` (sourced to the Pirkanmaa pathway document: handling 1 to 2 working days, invitation letter 3 to 4), `gp_referral_letter`, `gp_second_look` and the weekly board (all `assumption`). The size of the 8-day gain is therefore as good as those assumed delays; the direction does not depend on booking leads.
- **Model change?** None made. The split suggests the dashboard's stage bars could show booking lead and queue separately (the engine knows both), but that is a display change owned by the dashboard track. See the channel entry.
