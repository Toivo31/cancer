# Recommendation: faster lung cancer diagnosis, equally across Finland (E3)

**For:** Goal 3 of the National Cancer Strategy 2026-2035, indicator "patients reach treatment within target times".
**Basis:** [evidence brief](evidence_brief.md), [equity note](equity.md). Synthetic simulator, clinician decides every case.

## The problem in three sentences

Finland has the longest lung cancer waits in the Nordics at the first steps, with a primary-care appointment taking about 14 days and a specialist consultation 2-4 weeks after the first GP visit ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)). In Norway, one study found only 40% of early-stage lung cancer patients started treatment within 42 days, and that adding scanner capacity alone barely changed this while reordering the steps would have reached 80% ([Stokstad 2019](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944)). Finnish lung cancer five-year survival is 17% for men against 27-30% in Denmark, Norway and Sweden ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)).

## Five actions

| # | Action | Who acts | Tested by our simulator? | Evidence |
|---|---|---|---|---|
| 1 | **At the first specialist visit, order PET-CT, exercise test and the tumour-board slot together**, and take tissue samples while treatment is booked. | Hospital districts' lung units within each wellbeing services county (hyvinvointialue); county medical directors | **Yes.** Validated against the Norwegian pathway; we then test the same reordering on a Finnish scenario. | [Stokstad 2019](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944), [NHS England timed pathway](https://www.england.nhs.uk/long-read/implementing-a-timed-lung-cancer-diagnostic-pathway/), [Scotland](https://rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/lung-cancer) |
| 2 | **Direct CT access from primary care**, including for nurse-led first contact, with a shared protocol for when to order. | Wellbeing services counties (primary care and imaging); THL and the specialised-care collaborative areas (YTA) for shared protocols | **Partly.** Scenario compares a nurse-first path with and without direct CT; it uses assumed capacity. | [IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf) (<10% of units perform CT), [Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa) (40-60% nurse first). **Caution:** faster CT alone did not shorten time to treatment decision in an English cohort ([ERJ 2023](https://publications.ersnet.org/content/erj/62/suppl67/pa1123)); pair it with action 1. |
| 3 | **Fast track for non-specific symptoms**, with a guardrail: publish waits for all other patients using the same scanners and clinics, and review if they rise. | Wellbeing services counties; YTA areas for sharing a service across small counties | **Partly.** A fast-track lane is a search option; waits for non-cancer patients are reported as a guardrail. | [Sewell 2020](https://cronfa.swan.ac.uk/Record/cronfa53256) (works only at about 80%+ utilisation), [Scotland RCDS](https://www.rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/rapid-cancer-diagnostic-services-rcdss/data-and-impact) (8.4% cancer conversion), [Delilovic 2019](https://doaj.org/article/ebf8fe6bd4b642e8b7ca902f004b468d) (crowd-out) |
| 4 | **Monitor time-to-treatment per pathway step, by county, nationally**, published annually and split by presentation route. | THL with the Finnish Cancer Registry; counties supply data. The strategy proposes a national cancer care quality register with 90% coverage ([Strategy p. 36](https://www.iccp-portal.org/sites/default/files/2026-02/National_Cancer_Strategy_2026-2035_Finland.pdf)) | **No.** Rests on cited evidence only. Our simulator shows what such a monitor would look at. | Strategy sub-objectives 3.1-3.2; Sweden and Denmark already monitor lung outcomes at hospital level, Finland does not ([Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa)) |
| 5 | **Run each change as a monitored pilot in one county first**, measuring before and after on the monitor in action 4. | One or two counties volunteering; THL evaluates | **No.** This is the step that turns our simulated proposal into evidence. | Our own data-transparency note |

## What we are not saying

- The simulator is synthetic. It ranks pathway changes under stated assumptions; it does not estimate lives saved in Finland.
- Action 3 can make others wait longer if capacity is thin. It should start where utilisation will stay high.
- A Norwegian 42-day target is our benchmark; the Finnish statutory limits are 21 days to assessment and 180 days to treatment ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)).

## Gain claimed (fill from final run)

Share treated within target time in the Finnish scenario: `[[finland_share_base]]` today to `[[finland_share_opt]]` with action 1 and 2 together, on held-out patients. Gap between non-specific and site-specific presenters: `[[equity_gap_before_pp]]` to `[[equity_gap_after_pp]]` percentage points.

## Note on named actors

Wellbeing services counties and THL are named in the strategy's sub-objectives (counties for 3.2-3.4; 3.1 names none). The strategy text we could read does not mention the collaborative areas (YTA), and the ministry says a roadmap due in 2026 will set responsible parties ([STM](https://stm.fi/en/national-cancer-strategy)). Naming YTA areas here is our proposal, not a quote.
