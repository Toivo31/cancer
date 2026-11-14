# Recommendation: faster lung cancer diagnosis, equally across Finland (E3)

**For:** Goal 3 of the National Cancer Strategy 2026-2035, indicator "patients reach treatment within target times".
**Basis:** [evidence brief](evidence_brief.md), [equity note](equity.md). Synthetic simulator (numbers below are from the Finnish synthetic county, held-out patients, provisional 90-day target), clinician decides every case.

## The problem in three sentences

Finland has the longest lung cancer waits in the Nordics at the first steps, with a primary-care appointment taking about 14 days and a specialist consultation 2-4 weeks after the first GP visit ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)). In Norway, one study found only 40% of early-stage lung cancer patients started treatment within 42 days, and that adding scanner capacity alone barely changed this while reordering the steps would have reached 80% ([Stokstad 2019](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944)). Finnish lung cancer five-year survival is 17% for men against 27-30% in Denmark, Norway and Sweden ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)).

## Five actions

| # | Action | Who acts | Tested by our simulator? | Evidence |
|---|---|---|---|---|
| 1 | **At the first specialist visit, order PET-CT, exercise test and the tumour-board slot together**, and take tissue samples while treatment is booked. | Hospital districts' lung units within each wellbeing services county (hyvinvointialue); county medical directors | **Yes, in the synthetic county.** The engine reproduces the Norwegian pathway; the same reordering in our Finnish scenario takes the share within 90 days from 18% to 54% (needs 3 PET-CT slots). The same extra capacity without reordering reaches 31%. | [Stokstad 2019](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944), [NHS England timed pathway](https://www.england.nhs.uk/long-read/implementing-a-timed-lung-cancer-diagnostic-pathway/), [Scotland](https://rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/lung-cancer) |
| 2 | **Direct CT access from primary care**, including for nurse-led first contact, with a shared protocol for when to order. | Wellbeing services counties (primary care and imaging); THL and the specialised-care collaborative areas (YTA) for shared protocols | **Yes, and alone it does little.** Direct CT gives 20% (baseline 18%) and needs several times the baseline CT slots. Pair it with action 1. Assumed capacity. | [IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf) (<10% of units perform CT), [Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa) (40-60% nurse first). **Caution:** faster CT alone did not shorten time to treatment decision in an English cohort ([ERJ 2023](https://publications.ersnet.org/content/erj/62/suppl67/pa1123)); pair it with action 1. |
| 3 | **Fast track for non-specific symptoms**, with a guardrail: publish waits for all other patients using the same scanners and clinics, and review if they rise. | Wellbeing services counties; YTA areas for sharing a service across small counties | **Yes.** A fast lane for vague symptoms gives 37%; the optimiser's own suggestion also marks referred patients as priority after hospital referral handling. Waits for non-cancer patients are reported as a guardrail (16.8 to 16.8 days median with the suggested change). | [Sewell 2020](https://cronfa.swan.ac.uk/Record/cronfa53256) (works only at about 80%+ utilisation), [Scotland RCDS](https://www.rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/rapid-cancer-diagnostic-services-rcdss/data-and-impact) (8.4% cancer conversion), [Delilovic 2019](https://doaj.org/article/ebf8fe6bd4b642e8b7ca902f004b468d) (crowd-out) |
| 4 | **Monitor time-to-treatment per pathway step, by county, nationally**, published annually and split by presentation route. | THL with the Finnish Cancer Registry; counties supply data. The strategy proposes a national cancer care quality register with 90% coverage ([Strategy p. 36](https://www.iccp-portal.org/sites/default/files/2026-02/National_Cancer_Strategy_2026-2035_Finland.pdf)) | **No.** Rests on cited evidence only. Our simulator shows what such a monitor would look at. | Strategy sub-objectives 3.1-3.2; Sweden and Denmark already monitor lung outcomes at hospital level, Finland does not ([Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa)) |
| 5 | **Run each change as a monitored pilot in one county first**, measuring before and after on the monitor in action 4. | One or two counties volunteering; THL evaluates | **No.** This is the step that turns our simulated proposal into evidence. | Our own data-transparency note |

## What we are not saying

- The simulator is synthetic. It ranks pathway changes under stated assumptions; it does not estimate lives saved in Finland.
- Action 3 can make others wait longer if capacity is thin. It should start where utilisation will stay high.
- The Norwegian check uses 42 days; the Finnish scenario uses a provisional 90 days from first contact. Neither is a Finnish legal limit; the Finnish statutory limits are 21 days to assessment and 180 days to treatment ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)).

## Gain claimed (from the run of 2026-11-14)

In our synthetic county, on held-out patients: the optimiser's suggested change (Fast lane: once the hospital has handled a referral, give that patient priority in every later queue) takes the share treated within 90 days from 18% to 61% and the median from 102 to 80 days. The hand-written "order together" flowchart reaches 54%. Missed cancers go from 27.5 to 27.5 per cohort and tests per patient from 0.41 to 0.41.

Equity: 13% to 54% for vague-symptom patients and 27% to 79% for alarm-symptom patients. The gap in points widens (13.6 to 25.9); the gap in median days narrows (11.2 to 9.7). Both groups gain; we do not claim the gap closes.

Status of the target: 90 days is our provisional choice (D20). At the Norwegian 42 days every Finnish flowchart is at 0%.

## Note on named actors

Wellbeing services counties and THL are named in the strategy's sub-objectives (counties for 3.2-3.4; 3.1 names none). The strategy text we could read does not mention the collaborative areas (YTA), and the ministry says a roadmap due in 2026 will set responsible parties ([STM](https://stm.fi/en/national-cancer-strategy)). Naming YTA areas here is our proposal, not a quote.
