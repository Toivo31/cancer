# Evidence brief (E1)

Status: every claim below was checked against the page named in the link, on 14 Nov 2026, unless marked **[not verified]**. Numbers are paraphrased from what the source states. Where a host was unreachable from our environment it says so.

## 1. The problem

Finland has the weakest lung cancer outcomes in the Nordics, and part of the gap is time before treatment.

- Five-year relative survival in lung cancer (NORDCAN, 2019-2023): men 17% in Finland against 27-30% in Denmark, Norway and Sweden; women 29% against 35-37%. [IHE Cancer Dashboard Finland 2026](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf), survival section.
- Lung cancer is Finland's third most common cancer but causes the most cancer deaths. [University of Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa).
- Delay costs lives in general: across cancers, a four-week treatment delay is associated with higher mortality (hazard ratio about 1.06-1.08 for surgery). This meta-analysis is not lung-specific. [Hanna et al., BMJ 2020](https://www.bmj.com/content/371/bmj.m4087.abstract).

## 2. The indicator we measure

National Cancer Strategy 2026-2035, Goal 3 (equal and effective care), has three indicators: five-year survival in poor-prognosis cancers reaches the Nordic level; cancer mortality falls 10% (now 13,300 deaths a year); patients reach treatment within target times. The footnote puts the lung cancer survival gain needed at more than 14 percentage points from the 2023 NORDCAN level, with "Nordic level" defined as the Sweden-Norway average. [Strategy PDF, p. 5](https://www.iccp-portal.org/sites/default/files/2026-02/National_Cancer_Strategy_2026-2035_Finland.pdf).

We measure the third: **share of patients treated within target time**, and the days between first contact and treatment start.

Which target time? Three exist and they should not be mixed up:

| Target | Value | Source |
|---|---|---|
| Finnish statutory access | treatment need assessed within 21 days of referral arriving; treatment within 180 days of that assessment | [IHE dashboard](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf), waiting-times section |
| Observed Finnish practice | median 36-38 days from diagnosis to treatment start, 2018-2022 | same |
| Our simulator target | 42 days from referral, taken from the Norwegian study | [Stokstad et al. 2019](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944) |

The strategy points to THL monitoring guidance (Ohjaus 21/2016) for the official definition; we did not read that document. Our 42-day target is a benchmark borrowed from Norway, not a Finnish legal limit. The demo must say so.

## 3. Where the gap sits in the lung pathway

**Step by step, Finland against Denmark, Norway, Sweden** (typical waits, [IHE dashboard](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf) citing Khalife et al. 2025; we could not read the Khalife paper itself):

| Step | Finland | Denmark / Norway / Sweden |
|---|---|---|
| Health-centre appointment, symptomatic patient | 14 days | 2-7 days |
| Specialist consultation after first GP visit | 2-4 weeks | 1-2 weeks |
| Diagnosis after specialist consultation | 4 weeks | 2-4 weeks (Sweden 4) |

So the Finnish gap is clearest at the first two steps. At the diagnosis step Finland equals Sweden and sits at the top of the Danish and Norwegian range. The report states Finland had the longest waits in the Nordics in this comparison.

**Nurse-first contact.** 40-60% of Finnish patients with lung symptoms meet a nurse first; elsewhere in the Nordics they usually see a doctor. [University of Helsinki](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa). The same page puts the primary-care appointment wait at about two weeks in Finland against about one week elsewhere.

**CT access.** Fewer than 10% of Finnish primary-care units could perform CT scanning, against about 90-100% in the other Nordic countries. [IHE dashboard](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf), diagnostic imaging section. Note the wording: *perform*, not *order directly*. Direct-order access is a related but different thing; we found no source quantifying it.

**Satakunta.** In 131 patients diagnosed in 2021-2022, about two weeks passed from first primary-care visit to referral and about two months from referral to diagnosis; the author concludes the largest delay was in specialist care. [Mattila 2025, University of Turku thesis](https://www.utupub.fi/handle/10024/180618). Caveats: one region, a master's-level thesis, and the pandemic period.

**Quality of the diagnostic work-up.** In 2019-2023 only 27% of Finnish lung cancer patients were directed to curative treatment, staging information was missing for almost half, and the Finnish Cancer Societies' registry report found clear differences between wellbeing services counties. [Verkkouutiset on the Syöpäjärjestöt report](https://www.verkkouutiset.fi/a/keuhkosyopa-todetaan-usein-liian-myohaan-vain-joka-neljas-saa-parantavaa-hoitoa/). This is a news report of the study; we did not read the report itself.

**Reading.** Time is lost before the specialist (nurse first, slow appointment, no direct CT) and again inside specialist care (referral to diagnosis). The two stages need different fixes. Our simulator addresses the second directly and the first only through scenario settings.

## 4. Why reorder instead of adding capacity

The strongest piece is one Norwegian study that separates the two levers.

**Stokstad et al. 2019** reviewed 100 patients with stage I-II lung cancer treated with curative intent in Norway. Only 40% started treatment within 42 days. Median wait from PET-CT referral to report was 20.5 days. Re-timing patients with a PET-CT wait of 7 days or less lifted the share to 48%, not statistically significant (p = 0.254). Ordering PET-CT and the exercise test right after the first CT, an early tumour board, and tissue sampling while treatment is arranged would have given 80% (p < 0.001) and 16% fewer sampling procedures. The 80% is a model estimate, not an observed result. [BMC Health Serv Res 2019, abstract via DOAJ](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944); DOI [10.1186/s12913-019-4517-z](https://doi.org/10.1186/s12913-019-4517-z) (Springer full text blocked here).

Consistent evidence from elsewhere:

| Evidence | What happened | Link |
|---|---|---|
| English rapid-CT cohort, ERJ 2023 conference abstract | Wait from abnormal chest X-ray to CT fell from a median 15 to 3 days, but time to treatment decision stayed 66 vs 65 days. The authors say other diagnostic and staging delays remain. Abstract page was readable only through the ERS media viewer. | [ERJ abstract](https://publications.ersnet.org/content/erj/62/suppl67/pa1123), [viewer](https://channel.ersnet.org/container-detail-media-viewer.php?id=161387) |
| Norwegian county hospital, Laerum et al. 2020 (780 NSCLC patients, 2007-2016) | Time from referral to treatment fell about 7.8 days after a local diagnostic algorithm and about 14.9 days after national cancer pathways. Curative-intent patients: median 64 to 43 days. Mean number of procedures rose slightly (3.5 to 3.9). | [Laerum 2020](https://doaj.org/article/99ecb231f07d4b9f9b88e2fccb12a075) |
| Royal Free, London (Pulse, citing trust board papers) | Referral to treatment averaged 66 days before and 29 after, a recent monthly average. The first step changed from an outpatient clinic to a CT scan. Not peer reviewed. | [Pulse](https://pulsetoday.co.uk/?p=30344) |
| Wales, simulation, England et al. 2021 | A first outpatient visit within 7 days removes roughly 10-12 days; daily instead of weekly testing about 10 days; next-day reporting 8-10 days; the three together about 20-22 days. The authors note substantial investment would be needed. | [TLCR 2021](https://tlcr.amegroups.org/article/view/50482/html) |
| Toronto clinic (39.9 to 28.1 days referral to diagnosis, tests ordered before first visit) | **[not verified]**: PubMed and PMC pages were not reachable here. Cite only after checking. | [PMC7564135](https://pmc.ncbi.nlm.nih.gov/articles/PMC7564135) |
| Radiotherapy pathway simulation review | **[not verified]**: host unreachable. | [Salford repository](https://salford-repository.worktribe.com/OutputFile/2660286) |

National reference designs already exist: England's timed lung pathway has a test bundle requested at the first outpatient appointment (PET-CT, spirometry and others), MDT discussion at day 21 and a follow-up clinic to discuss treatment at day 28 ([NHS England](https://www.england.nhs.uk/long-read/implementing-a-timed-lung-cancer-diagnostic-pathway/)); Scotland's optimal pathway bundles PET-CT and other fitness tests in week 2 (ideally the same day), targets all tests completed by day 14 and a treatment plan agreed by day 21 ([Right Decisions Scotland](https://rightdecisions.scot.nhs.uk/optimal-cancer-diagnostic-pathways/lung-cancer)).

## 5. Limits

- **Real shortages exist.** A discrete-event simulation with particle-swarm optimisation at the Royal Free found a capacity-demand mismatch, mainly imaging and endoscopy, though adding resource in one place alone does not fully solve it. It covers cancer diagnosis in general against the 28-day Faster Diagnosis Standard, not lung only. [Cooke et al. 2022](https://doaj.org/article/cccf45af7f814425b2411efb70814d28). Reordering raises the use of scarce tests at the front (e.g. PET-CT earlier), so it can shift queues rather than remove them. The simulator keeps capacity fixed and reports queues for this reason.
- **Crowd-out.** Standardised cancer pathways in Sweden's largest region were reported by 58 interviewed professionals to risk longer waits for other patients using the same resources. [Delilovic et al. 2019](https://doaj.org/article/ebf8fe6bd4b642e8b7ca902f004b468d). Our guardrail: report waits for non-cancer patients and reject changes that worsen them beyond a set margin.
- **Fast-track utilisation.** A Welsh rapid diagnostic centre for vague symptoms was cost-effective only at roughly 80% capacity utilisation or more. [Sewell et al. 2020](https://cronfa.swan.ac.uk/Record/cronfa53256).
- **Transfer.** All reordering evidence is from curative-intent or specialist-stage pathways in Norway, England and Wales. None is Finnish. Finnish effect sizes are an inference, not a finding.
