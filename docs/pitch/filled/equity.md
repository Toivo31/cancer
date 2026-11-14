# Equity: who waits longer and why (E2)

Same verification rule as the evidence brief: claims are from pages read on 14 Nov 2026; **[gap]** marks what we looked for and could not source.

## 1. The equity claim in one line

Strategy Goal 3 asks for *equal* as well as effective care, and includes an indicator on knowing regional and socioeconomic differences, with a sub-objective on reliable information about regional differences in diagnostic and treatment practice ([Strategy PDF](https://www.iccp-portal.org/sites/default/files/2026-02/National_Cancer_Strategy_2026-2035_Finland.pdf), p. 5 and p. 36). The ministry page states diagnostics and treatment must be available equally and without delay across the country ([STM](https://stm.fi/en/national-cancer-strategy)). Our contribution is to show *who* falls behind in a pathway and which changes reach them.

## 2. Groups that wait longer, with evidence

### Patients with non-specific symptoms
- At a Welsh rapid diagnostic centre for vague symptoms, mean time to diagnosis fell from 84.2 days under usual care to 5.9 days when diagnosis was made at the clinic, or 40.8 days when further tests were booked during the visit. [Sewell et al., Br J Gen Pract 2020](https://cronfa.swan.ac.uk/Record/cronfa53256). This is a cost-effectiveness model on routine data from one hospital, not a trial, and it holds only at about 80% utilisation or better.
- Scotland's Rapid Cancer Diagnostic Services (2025 data, six services): 4,439 referrals, 72.7% presenting with unexplained weight loss, 239 cancers among 2,389 completed pathways (8.4%), median 17 days from referral to cancer diagnosis; lung was the most frequent diagnosis (20.5%). [Right Decisions Scotland](https://www.rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/rapid-cancer-diagnostic-services-rcdss/data-and-impact). The 8.4% conversion rate shows the crowd-out risk: more than nine in ten are not cancer.
- **[gap]** We did not find a source that quantifies the delay for non-specific presenters specifically in Finland, and did not verify the claim that this group waits longer than site-specific presenters in a like-for-like comparison. The Welsh figure compares a rapid service against usual care for the same group. The simulator's group split is therefore a modelling choice (D9), not a finding.

### Patients who see a nurse first
- 40-60% of Finnish patients with lung symptoms first meet a nurse, where elsewhere in the Nordics they usually see a doctor; a primary-care appointment takes about two weeks against about one. [University of Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa).
- **[gap]** No source gives the delay attributable to nurse-first contact, nor whether the share differs between counties. The simulator can test an assumption (nurse can order CT) but not measure the effect.

### Regions: CT access and diagnostics
- Nationally: fewer than 10% of Finnish primary-care units could perform CT, against about 90-100% elsewhere in the Nordics. [IHE dashboard](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf).
- Within Finland: the Finnish Cancer Societies' quality report on lung cancer found clear regional differences in how lung cancer is diagnosed, compared across wellbeing services counties, and differences in treatment quality (only 27% directed to curative treatment nationally). [Verkkouutiset](https://www.verkkouutiset.fi/a/keuhkosyopa-todetaan-usein-liian-myohaan-vain-joka-neljas-saa-parantavaa-hoitoa/).
- **[gap]** We found no source on direct-CT-access *by county*. The county-level report exists but we could only read a news summary; it should be the first thing to obtain. Satakunta ([Mattila 2025](https://www.utupub.fi/handle/10024/180618)) shows the delay inside one region, not a comparison between regions.
- Reassurance with a caveat: a Finnish Cancer Registry study reported that survival variation between municipalities within hospital districts fell 18% between 1997-2006 and 2007-2016 across eleven common cancers, with more variation inside than between hospital districts ([MTV Uutiset](https://www.mtvuutiset.fi/artikkeli/syoparekisterin-tutkimus-suomen-alueelliset-erot-syovasta-selviytymisessa-ovat-kavenneet/7854820), news summary). This is about survival, not waiting time, and predates the 2023 wellbeing-county reform.

### Education and income
- A register study of everyone aged 30+ diagnosed 2000-2020 (Finnish Cancer Registry, Population Register) found higher education linked to a 10-16% higher chance of early-stage diagnosis, 12-18% higher chance of surgery and about 20% lower mortality across cancers. Lung cancer behaves differently: in women, higher education was linked to *lower* odds of early-stage diagnosis (OR 0.79), while higher education raised the odds of surgery (men OR 1.18, women 1.48). [MPIDR working paper WP 2025-016](https://www.demogr.mpg.de/papers/working/wp-2025-016.pdf), a preprint; the abstract and tables differ on case count (377,986 against 384,441).
- Age-standardised cancer mortality 2015-2019: men 442 per 100,000 with primary education against 272 with tertiary; women 308 against 213; the gradient is steepest for women mainly because of lung cancer. [EU CanIneq Finland factsheet](https://cancer-inequalities.jrc.ec.europa.eu/sites/default/files/docs/factsheets/canineq/2025/EU-CanIneq-fs-Finland.pdf). The factsheet reports no regional breakdown within Finland and no waiting-time data.
- **[gap]** Education and income gradients are in stage, treatment and mortality. We found no Finnish source for *waiting time* by education, income or age. The brief should not claim that low-income patients wait longer; it can say they present later or get less surgery.
- 684 cancer patients surveyed around the turn of 2024-2025: just under a third felt their diagnosis was delayed; no breakdown by region or age was reported. [Syöpäpotilaat via STT](https://www.sttinfo.fi/tiedote/70972938/kyselyselvitys-joka-kolmas-syopapotilas-kokee-diagnoosin-viivastyneen?publisherId=69820264).

## 3. What the simulator shows

In our synthetic Finnish county (about 16 177 chest-symptom presenters per held-out cohort, 1.6% with lung cancer, 15% presenting with alarm symptoms), each patient has a presentation group: `site_specific` (alarm symptoms) or `non_specific` (vague symptoms). The groups differ only in how likely the detection step is to send them on, so the gap at baseline follows from our assumption (D9), not from Finnish data.

**Baseline.** Share treated within 90 days (provisional target, D20): 16% for vague-symptom patients against 31% for alarm-symptom patients, a gap of 14.9 points; median days 107 against 94. Share of cancers never diagnosed in the episode: 13.6% against 7.7%.

**With the suggested change** (held-out): 60% against 78% within 90 days. Both groups gain (vague symptoms 44 points, alarm symptoms 47). The gap in percentage points widens (14.9 to 18.6) because the alarm group starts closer to the threshold; the gap in median days narrows (13.6 to 7.3 days). We report both because they point in different directions, and we do not claim the change closes the gap in shares. Missed cancers among vague-symptom patients go from 13.6% to 10.8% of that group (we have not separated which of the two steps drives this; one plausible route is that GP-first visits image more patients in the model).

| Flowchart | Vague (non-specific) symptoms: within target | Alarm (site-specific) symptoms: within target | Gap, pp | Gap in median days |
|---|---|---|---|---|
| Baseline | 16% | 31% | 14.9 | 13.6 |
| Suggested change | 60% | 78% | 18.6 | 7.3 |
| GPs order CT directly | 14% | 44% | 29.4 | 16.9 |
| Order together | 41% | 78% | 37.3 | 17.1 |
| Fast lane for vague symptoms | 33% | 42% | 9.4 | 8.6 |
| Capacity-only control | 22% | 45% | 23.3 | 12.7 |

Reading the table: the hand-written flowcharts reach the two groups differently. Ordering CT directly helps mainly the alarm group and widens the gap in median days (13.6 to 16.9); the fast lane for vague symptoms is the one that most narrows the gap in shares (9.4 points) but gains less overall (37% against 64%). Which of these is "more equal" depends on the measure, and that is a choice for the team and, in practice, for clinicians.

The demo also reports waits for non-cancer patients as the crowd-out guardrail: median days to leave the pathway 16.8 at baseline and 13.8 with the suggested change.

## 4. What it cannot show

- **Single region, one capacity profile.** It cannot show differences between counties or YTA areas, or between a county with and one without direct CT.
- **Synthetic groups.** The size and the delay of the non-specific group come from scenario assumptions anchored on the sources above, not from Finnish data (see [gap] items). The result "the non-specific group benefits less or more" is a consequence of our assumptions.
- **No age, income or education.** Patients carry age but it does not drive timing in the model; no socioeconomic variable exists.
- **No patient behaviour.** Delay before first contact, missed appointments and travel distance are not modelled.
- **Proof of effect.** The simulator tests whether a change helps *if* the parameters hold. It does not show that Finnish patients are being treated unequally; the cited registry studies do that.

## 5. Suggested wording for judges

"We show where in the pathway time is lost and which change shortens it, split by how the patient first presents. The national evidence on regional and social gaps is cited; our simulator tests the pathway change, not the size of the inequality."
