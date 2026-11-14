# Video script, 2 minutes (E4)

Placeholders in `[[ ]]` are filled from the final run before recording. Voice-over word count is stated at the bottom. Screens refer to `demo/index.html`; adjust names to the final UI.

| Time | Screen | Voice-over |
|---|---|---|
| 0:00-0:15 | **Headline number**, large type: `[[finland_share_base]]%` against `[[finland_share_opt]]%` treated on time | Today, `[[finland_share_base]]` percent of simulated Finnish lung cancer patients start treatment within the target time. With one change to the order of steps, `[[finland_share_opt]]` percent. |
| 0:15-0:35 | **Where time is lost**: four stage bars (detection, referral, diagnosis, treatment start), waiting vs service time | The problem is waiting, not testing. Finland waits about fourteen days for a first appointment, and the longest queue sits between referral and diagnosis. Almost half of patients first see a nurse, and few health centres can scan. |
| 0:35-1:00 | **The change**: flowchart before and after, PET-CT, exercise test and tumour board moving to the first visit | Our optimiser searched for a faster order, knowing only what each test had revealed. It proposed what one Norwegian study suggested: order the scan, the fitness test and the tumour board together, and take samples while treatment is booked. Same patients, same capacity, no new equipment or staff. |
| 1:00-1:25 | **Validation**: our run of the Norwegian pathway vs the published 40% and 80% | We checked the machine against reality first. Rebuilt from the Norwegian study, our model reproduces forty percent on time, finds a similar reordering on its own, and lands near eighty. Adding scanner capacity alone barely helped. Order did. |
| 1:25-1:45 | **Equity split**: two bars, site-specific vs non-specific symptoms, before and after | Not everyone waits equally. Patients with vague symptoms and those who see a nurse first wait longest. We show each group, and we check that the change does not make other patients wait more. A change that helps one group and hurts another would show up immediately. |
| 1:45-2:00 | **Recommendation card**: five actions, owners | Our proposal for the national cancer strategy: order together at the first visit, give primary care direct scan access, fast-track vague symptoms with safeguards, and publish waiting times by county. Then pilot it. The data is synthetic, every number has a published source, and a doctor decides every case. |

## Spoken text only

Today, [[finland_share_base]] percent of simulated Finnish lung cancer patients start treatment within the target time. With one change to the order of steps, [[finland_share_opt]] percent.

The problem is waiting, not testing. Finland waits about fourteen days for a first appointment, and the longest queue sits between referral and diagnosis. Almost half of patients first see a nurse, and few health centres can scan.

Our optimiser searched for a faster order, knowing only what each test had revealed. It proposed what one Norwegian study suggested: order the scan, the fitness test and the tumour board together, and take samples while treatment is booked. Same patients, same capacity, no new equipment or staff.

We checked the machine against reality first. Rebuilt from the Norwegian study, our model reproduces forty percent on time, finds a similar reordering on its own, and lands near eighty. Adding scanner capacity alone barely helped. Order did.

Not everyone waits equally. Patients with vague symptoms and those who see a nurse first wait longest. We show each group, and we check that the change does not make other patients wait more. A change that helps one group and hurts another would show up immediately.

Our proposal for the national cancer strategy: order together at the first visit, give primary care direct scan access, fast-track vague symptoms with safeguards, and publish waiting times by county. Then pilot it. The data is synthetic, every number has a published source, and a doctor decides every case.

## Claims to check before recording

- "Almost half see a nurse": source says 40-60% ([Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa)); "about fourteen days": [IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf).
- "Few health centres can scan": fewer than 10% of primary-care units could perform CT (IHE).
- "Longest queue sits between referral and diagnosis": a statement about our model output, to be confirmed from the run; Satakunta thesis agrees for one region ([Mattila](https://www.utupub.fi/handle/10024/180618)).
- "Wait longest" for vague symptoms and nurse-first: **not directly sourced for Finland** (see equity note). Soften to "are most at risk of waiting" if the final run does not show it.
- "Lands near eighty" and "finds a similar reordering": only if the validation run does. Otherwise say what happened.
