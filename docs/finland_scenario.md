# Finnish lung-cancer scenario (`scenarios/finland_lung.yaml`)

Track F. All data are synthetic. Every parameter carries `source:` (an id in `params/sources.yaml`) or `source: assumption` with a note; `tests/test_finland.py` enforces this. Numbers below are means over seeds 1-5 (18,800 patients per seed, the first 60 days discarded as warm-up, about one year measured), produced with `python3 -m pathway_sim compare scenarios/finland_lung.yaml --seeds 1-5`.

## 1. What it represents

One large wellbeing services county (about 500,000 people, Pirkanmaa-sized; see limitations), clock from **first contact in primary care** (nurse or GP) to **start of treatment**. 44 chest-symptom presenters arrive per day (Poisson), about 16,000 in the measured year, **1.6% of them have lung cancer** (about 260 a year). The rest are pneumonia (17%), COPD exacerbation (14%), benign nodule (3%), other benign chest conditions (30%) and self-limiting illness (34%).

- **Two presentation groups** (equity split): `site_specific` (alarm symptoms such as haemoptysis, 16% of presenters, 3.1% cancer, KOO2023) and `non_specific` (fatigue, weight loss, cough; 84%, 1.3% cancer, BRADLEY2021). 31% of cancers present site-specifically. Groups are drawn through `share_by_condition`; the scenario encodes the cancers as two conditions (`lung_cancer_site`, `lung_cancer_nonspec`) with different test accuracies.
- **Stages** (the brief's four): detection (nurse/GP, chest X-ray, GP review, safety net), referral (referral letter, hospital referral handling, specialist visit), diagnosis (CT, bronchoscopy or needle biopsy, PET-CT), treatment start (weekly tumour board, treatment slot).
- **Queues** are `server` resources booked by appointment: a wait = booking lead (`min_lead_days`, appointment books are filled days ahead) + overload queue. Capacities are slices of county capacity for this stream, not whole-county capacities.
- **Nurse first**: a choice node with a 50/50 `mix` (KHALIFE2025: 40-60%). The nurse rarely orders imaging herself, so most nurse-first patients need a second appointment.
- **Chest X-ray misses** about one in four cancers in the model (sensitivity 0.754, BRADLEY2021; HSSIB2021 "one in five"). A negative film leads to a GP second look (suspicion, lower for non-specific presenters). If the GP does not refer, a **safety net** applies: `symptoms_persist` (cancer symptoms persist, most non-cancer ones resolve), then re-presentation after about two weeks (`extra_wait` on the GP visit) and a referral. No referral and no return = discharged = **missed cancer**. About 41% of cancers reach the specialist through this safety net and 10% through the GP second look.
- `target_days: 42` is the **Norwegian** target, used for comparability with the Stokstad scenario. Finnish targets per IHE2026 are assessment within 21 days of referral, and the strategy goal is "treatment within target times". Finland starts far from 42 days from first contact, so the on-time share at 42 d is 0% for every flowchart; the table adds the share treated within 90 days, which moves.

## 2. Calibration (targets against simulation)

Medians, baseline flowchart, 5 seeds. "Main path" = cancers with a suspicious X-ray who did not use the safety net or the second look (130 of 264 in seed 3).

| Quantity | Finnish target | Source | Simulated |
|---|---|---|---|
| Wait for the first GP appointment | about 14 d | KHALIFE2025 | 13.6 d |
| GP referral to specialist visit | 14-28 d | KHALIFE2025 | 18.5 d |
| Specialist visit to diagnosis (tissue result) | about 28 d | KHALIFE2025 | 24.6 d (seeds 23.7-29.8) |
| Diagnosis to treatment start | 37 d (all cancers) | IHE2026 | 31.5 d |
| First contact to diagnosis, main path | 30-60 d (authors' estimate) | KHALIFE2025 | 61.5 d |
| First contact to GP referral, main path | Satakunta: first visit to referral about 14 d | MATTILA2025 | 21.5 d (includes the 13.6 d wait for the first visit) |
| GP referral to diagnosis, main path | Satakunta: just under 2 months | MATTILA2025 | about 40 d |
| First contact to treatment, all treated cancers | about 99 d (41 primary + 58 specialised; secondary, unpublished) | YLE_MOT2025 | **102.9 d** (mean 106.4) |
| Chest X-ray positive predictive value | 9% (UK self-referral cohort) | BRADLEY2021 | 13% |

How it was calibrated: arrival rate and capacities were set so that scarce diagnostics sit at 80-95% of capacity; booking leads (GP 12 d, clinic 12 d, CT 4 d, bronchoscopy/needle biopsy 6 d, PET-CT 4 d, treatment slot 10 d) were tuned until the per-step medians above were reached. The specialist-to-diagnosis step and the Satakunta referral-to-diagnosis figure come out below target; the total is on target. The overall median was not tuned to 99 d directly; it follows from the step waits and the safety-net assumptions.

**Utilisation and stability** (own count of booked slots over the measured year; the engine's reported `utilisation` is lower, see section 6). Mean wait in days by quarter of arrival, 5-seed mean, baseline:

| Resource | Slots a weekday | Demand a weekday | Utilisation (min-max over seeds) | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|---|---|---|
| GP appointments | 74 | 66.3 | 0.89-0.90 | 15.3 | 15.4 | 15.5 | 15.3 |
| Chest X-ray | 24 | 20.7 | 0.84-0.87 | 2.8 | 2.8 | 2.8 | 2.7 |
| Specialist clinic | 7 | 5.5 | 0.76-0.82 | 12.8 | 12.7 | 13.0 | 12.7 |
| CT | 3 | 2.6 | 0.82-0.88 | 6.2 | 5.8 | 6.3 | 6.6 |
| Bronchoscopy | 1 | 0.85 | 0.76-0.92 | 9.3 | 8.3 | 9.7 | 10.4 |
| Needle biopsy | 1 | 0.83 | 0.71-0.85 | 8.5 | 9.3 | 8.6 | 10.7 |
| PET-CT | 1 | 0.91 | 0.81-0.91 | 7.8 | 9.6 | 7.3 | 8.6 |
| Treatment slot | 2 | 0.89 | 0.36-0.41 | 15.9 | 16.3 | 16.4 | 16.2 |

No resource has a systematic upward trend in the baseline. Waits at the 1-slot resources (bronchoscopy, needle biopsy, PET-CT) wander by several days within a year (single seeds show quarters from 5 to 24 d), which is what a queue at 85-92% utilisation does; this is the main source of seed-to-seed variance (baseline median 101-107 d across seeds). Overloading without extra capacity does explode: direct CT with the baseline's 3 CT slots has a median CT wait of 354 d, and mean quarterly waits rise 169, 298, 418, 536 d; bundled PET with 1 slot has a median PET wait of 308 d (143, 262, 376, 468 by quarter), seed 1 (section 4).

Other checks: no stuck patients in any flowchart; missed cancers are discharged cancers (27.6 of 258 per seed, 10.7%: 13% of non-specific, 5% of site-specific cancers); false treatments about 2 per seed; non-cancer patients leave after a median of 16.8 d (mean 22 d).

## 3. Flowcharts compared

*The table below is from an earlier five-seed run and is kept for the per-flowchart reading; the headline held-out numbers (today 18% to 33% within 90 days with the optimiser's two reorders; urgent booking for everyone is a conditional finding) are in `demo/data/demo_bundle.json` and `docs/pitch/filled/`. The fast-track flowchart now uses `urgent_lead_days` rather than a negative `extra_wait` workaround.*

All four alternatives are **hand-written**; the optimiser track builds the automatic search. `baseline_plus_capacity` is a control. Same patients (common random numbers) in every row.

- `baseline`: nurse/GP -> chest X-ray -> GP review -> referral -> specialist visit -> CT -> sampling -> PET-CT -> tumour board -> treatment slot.
- `direct_ct`: GPs order CT directly (alarm-symptom presenters skip the X-ray, a suspicious film goes to CT before the referral). **Needs CT capacity 8** (demand 7-8 a weekday against 2.6): the flowchart carries `resource_overrides: ct_scanner 8`.
- `bundled_workup` (Stokstad-style): at the specialist visit CT and PET-CT are ordered together (PET for patients with a suspicious film), the tumour board meets before sampling, a treatment slot is booked while sampling runs, treatment starts when both are ready. **Needs PET-CT capacity 3** (demand 2.3 a weekday against 0.9); `resource_overrides: pet_scanner 3`.
- `fast_track_nonspecific`: `fast_track: true` for non-specific presenters with a suspicious film (priority in every server queue, `urgent_reserved_share` 0.14 on the clinic and 0.32 on CT) and shortened booking leads at every later step (now `urgent_lead_days` on the servers; see section 6).
- `baseline_plus_capacity`: baseline order with CT 8 and PET-CT 3. The difference between this row and `direct_ct` / `bundled_workup` is the effect of the order of steps.

| Flowchart | On-time (42 d) | Median days to treatment | Mean days | Treated within 90 d | Median days to tissue diagnosis | Missed cancers per seed (of 258) | Tests per patient | Cost per patient (EUR) | Non-cancer exit, median / mean d |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.0% | 102.9 | 106.4 | 17.7% | 69.9 | 27.6 | 0.420 | 75 | 16.8 / 22.1 |
| direct_ct (CT 8) | 0.0% | 101.2 | 105.0 | 21.2% | 68.2 | 27.0 | 0.435 | 93 | 16.8 / 22.2 |
| bundled_workup (PET-CT 3) | 0.0% | **83.7** | 87.6 | **53.6%** | 80.8 | 27.6 | 0.443 | 109 | 16.8 / 22.2 |
| fast_track_nonspecific | 0.0% | 97.1 | 98.2 | 35.3% | 65.6 | 27.2 | 0.420 | 75 | 16.8 / 21.9 |
| baseline_plus_capacity (CT 8, PET 3) | 0.0% | 97.4 | 100.9 | 29.8% | 68.3 | 27.6 | 0.420 | 75 | 16.8 / 22.1 |

Paired difference in median days to treatment against the baseline (same patients, five seeds): direct_ct -1.7 (range -3.4 to +0.6), bundled_workup **-19.2** (-14.6 to -22.4), fast_track_nonspecific -5.8 (-3.8 to -8.2), baseline_plus_capacity -5.4 (-3.2 to -8.1).

Reading:

- **Order beats capacity**: extra CT and PET capacity alone gains about 5 days. Bundling the work-up and moving the board before sampling gains about 19 days with the same extra PET capacity, i.e. about 14 days from order alone. This echoes the Stokstad finding but it is a result of our assumptions, not a validated one.
- **Direct CT gains nothing on its own** (-1.7 d against baseline, 4 d worse than the capacity-only control): the CT moves before the referral, but the 12-day wait for the specialist visit and the later steps still gate treatment. It helps site-specific presenters (92 d against 96 d) and does not help non-specific ones (107.5 d against 107.1 d). Unchanged CT capacity makes it much worse.
- **Missed cancers do not change** in any flowchart (27-28 per seed), because none of them changes the detection step where the cancers are lost (X-ray misses, no imaging at the first visit). `direct_ct` saves 0.6 site-specific cancers per seed by skipping the X-ray for them.
- **Tests per patient** rise 5% under bundling (more PET scans for patients who are later found to be benign); cost per patient rises 45% (EUR 75 to 109). Tests per patient counts only `kind: test` steps.
- **"Median days to tissue diagnosis" is not comparable** across flowcharts: in `bundled_workup` sampling comes after the board, so the tissue result arrives later (80.8 d) although treatment starts earlier. `diagnosis` is the sampling-finished milestone in all four.
- The 42-day on-time share is 0% everywhere; no hand-written flowchart comes close to a Norwegian-style target from first contact.

### Equity by presentation group (cancers; seeds 1-5)

| Flowchart | Group | Cancers per seed | Median days | Mean days | Treated within 90 d | Missed (share) | Median days to tissue diagnosis |
|---|---|---|---|---|---|---|---|
| baseline | site_specific | 78 | 96.4 | 98.5 | 28.8% | 4.2 (5.4%) | 63.3 |
| baseline | non_specific | 180 | 107.1 | 110.2 | 12.7% | 23.4 (13.0%) | 74.5 |
| direct_ct | site_specific | 78 | 91.5 | 92.4 | 43.1% | 3.6 (4.6%) | 58.5 |
| direct_ct | non_specific | 180 | 107.5 | 111.0 | 11.7% | 23.4 (13.0%) | 75.3 |
| bundled_workup | site_specific | 78 | 74.5 | 77.7 | 78.2% | 4.2 (5.4%) | 70.9 |
| bundled_workup | non_specific | 180 | 90.5 | 92.3 | 42.9% | 23.4 (13.0%) | 87.6 |
| fast_track_nonspecific | site_specific | 78 | 93.5 | 95.8 | 38.5% | 4.2 (5.4%) | 60.5 |
| fast_track_nonspecific | non_specific | 180 | 100.3 | 99.4 | 33.9% | 23.0 (12.8%) | 70.9 |
| baseline_plus_capacity | site_specific | 78 | 90.2 | 92.7 | 46.7% | 4.2 (5.4%) | 61.5 |
| baseline_plus_capacity | non_specific | 180 | 101.8 | 104.9 | 22.4% | 23.4 (13.0%) | 72.9 |

**The equity gap in the baseline**: non-specific cancers wait a median 10.7 days longer than site-specific ones to treatment and 11.2 days longer to tissue diagnosis; they are missed 2.4 times as often (13.0% against 5.4%); and 12.7% against 28.8% are treated within 90 days. `compute_metrics()["by_group"]` carries the median, share within target, diagnosis time and missed count per group. The gap arises in **detection** by construction (lower GP/nurse suspicion, lower second-look rate): downstream steps are identical for both groups. The size is an assumption, smaller than the 34 days from SEWELL2020 (UK, secondary citation).

What the alternatives do to the gap: `bundled_workup` shortens both groups by about 20 days, gap unchanged (16.0 d); `direct_ct` helps only the group it is aimed at and **widens the gap** (16.0 d); `fast_track_nonspecific` **narrows the gap** to 6.8 days in the median, because it targets the slower group, and lifts the non-specific share treated within 90 days from 12.7% to 33.9%.

**Crowd-out** (one-off analysis, not in the repo; seeds 1-3, patients outside the fast lane): at the reservations used in the flowchart (1 of 7 clinic slots, 1 of 3 CT slots; about 700 patients a year in the fast lane) other patients lose nothing, since clinic utilisation is about 80%. If the reservation is made large (30% of clinic slots, 50% of CT slots) the others pay: mean CT wait 6.2 to 71.7 d, median days to treatment for site-specific cancers outside the lane 95.6 to 150.6 d, overall median 102.3 to 149.6 d. Crowd-out is a function of how much of the scarce slot count is reserved relative to utilisation, which is a parameter, not a finding. Non-cancer exit times barely change (22.0 to 21.1 / 21.8 d).

## 4. Where time is lost

Mean days per treated cancer patient on the critical path (wait / service), stage breakdown from `compute_metrics`:

| Stage | baseline | direct_ct | bundled_workup | fast_track_nonspecific | baseline_plus_capacity |
|---|---|---|---|---|---|
| detection | 28.3 / 1.5 | 26.3 / 0.8 | 28.3 / 1.5 | 28.3 / 1.5 | 28.3 / 1.5 |
| referral | 17.8 / 0.1 | 17.5 / 0.1 | 17.8 / 0.1 | 15.7 / 0.1 | 17.8 / 0.1 |
| diagnosis | 25.4 / 12.0 | 27.1 / 12.0 | 17.5 / 9.0 | 22.0 / 12.1 | 19.7 / 12.0 |
| treatment_start | 20.8 / 0.5 | 20.7 / 0.5 | 13.0 / 0.5 | 18.1 / 0.5 | 21.1 / 0.5 |

Waiting is about 92 of the 106 mean baseline days of a treated cancer; service (including report turnaround) is about 14. Steps with the most waiting in the baseline (seed 1, critical path, mean days per treated cancer): treatment slot 16.8, re-presentation after the safety-net advice 13.5, specialist visit 12.8, PET-CT 9.5, first GP visit 6.7. Time is lost in **primary care** (waiting for the GP, no imaging at the first visit, the 41% who come back through the safety net) and in **booking leads at the specialist and treatment steps**, more than in queues at the scarce diagnostics. Diagnostics are the part that reordering can change.

Diagnostic runs with unchanged capacity (seed 1, overrides removed in memory): `direct_ct` with 3 CT slots has CT demand 7.5 a weekday, a median CT wait of 354 d and median days to treatment 430; `bundled_workup` with 1 PET slot has PET demand 2.3, a median PET wait of 308 d and median days to treatment 376 (20 cancers untreated at the end of the run). That is why those flowcharts carry capacity overrides, and why they are compared with `baseline_plus_capacity`.

## 5. Limitations

- **Synthetic and single-region.** No Finnish registry data. Per-step waits come from a 42-specialist survey (modal answers) and a secondary news report; they are modes, not distributions. The 14 and 28 d targets are survey answers.
- **County size.** 44 presenters a day gives about 260 cancers a year, twice the 130 of a 250,000-person county in `params/finland.yaml`. Capacities are whole numbers of slots a day, so the scarce resources only reach 80-95% utilisation at this size. Halving the stream with the same capacities would mean fewer, shorter queues.
- **Capacities are invented** (all `source: assumption`) and calibrated to the waits; the PET-CT wait is not Finnish data. A "wait" is mostly the booking lead, with the queue adding 1-4 days; the 1-slot resources are lumpy.
- **Equity gap is assumed.** The two groups differ only in detection probabilities (imaging at the first visit 97% against 45% of cancers, GP second look 55% against 10%, nurse imaging 45% against 15%). Those numbers are not Finnish and the UK 34 d figure is a secondary citation. About 41% of cancers coming back through the safety net is high and drives the long tail; run a sensitivity analysis before quoting it.
- **No patient behaviour or symptom-to-first-contact interval** (MOT puts the patient interval at over 50 d), no county differences, no age/income effects, no treatment type (surgery/radiotherapy/drug) and no staging; treatment start is a slot.
- **Result independence**: test results are drawn independently given the condition (engine simplification), so a cancer missed on the film is no more likely to be missed on CT.
- **Missed cancers are cancers never diagnosed in this episode**; in reality some would return later or present as emergencies. 10.7% is plausible but not sourced.
- **False positives** are crude (CT/PET false-positive rates assumed); chest X-ray PPV comes out at 13% against 9% in BRADLEY2021.
- **Fast track** reservations and shortened urgent leads are assumptions (`urgent_lead_days`); the optimiser search excludes fast track, and urgent booking for every referral is reported only as a conditional finding.

## 6. Engine bugs and feature requests (status after the 14 Nov review: items 1, 2 and 4 are now done)

1. **`utilisation` was understated (fixed).** The engine now computes utilisation over [warm-up, last arrival]. Original problem: `_Server.summary` averages over the weekdays from `warmup_days` to the *last exit*, which is 100+ days after the last arrival, so the draining tail dilutes it: the engine reports 62-78% for resources whose utilisation over the measured year is 76-92%. Suggested: use [warmup, last arrival].
2. **No urgent booking lead (fixed: `urgent_lead_days` exists on servers, used by the `*_fast` tests and the conditional urgent-booking variant).** The conditional urgent-booking result depends on those assumed leads (see `docs/review.md` B1). Original problem: Priority only lets a patient use reserved slots; the lead (`min_lead_days`) is the same, so `fast_track` barely helps when waits are mostly lead. Workaround: `*_fast` tests with a negative `extra_wait` (a fixed shift) that shorten the lead for the same server. Request: `urgent_lead_days` on servers.
3. **`capacity_per_day` must be an integer and `urgent_reserved_share` floors.** At 1-3 slots the utilisation and reservations are coarse (floor(3 x 0.68) = 2, i.e. a reservation of 1 slot needs a share just under 1/cap). Request: fractional capacity or `capacity_per_week`.
4. **`p_positive` could not depend on `group` (fixed: the engine now supports `p_positive` by group).** Original problem: `p_positive` could not depend on `group` (only on condition and attributes), so presentation groups had to be encoded as separate cancer conditions. Request: `{by: group, ...}`.
5. **Guards are evaluated once and a skipped node never re-runs**, and there are no loops. Re-presentation and the safety net are modelled as a zero-time `symptoms_persist` test plus a GP visit with a long `extra_wait`. Works, but that visit pre-books its slot at decision time, which makes it a booking in the future, not a queue entry at the later date.
6. **`milestone: diagnosis` semantics** differ between flowcharts when sampling moves; `median_days_to_diagnosis` is not comparable between `baseline` and `bundled_workup`. Consider an optional second milestone ("decision made" at the board).
7. `compare` regenerates the patients for every flowchart and shows only four numbers; on-time at 42 d is 0% for all Finnish flowcharts, so it shows no movement. A configurable secondary threshold would help.

## 7. Files

- `scenarios/finland_lung.yaml`: the scenario (5 flowcharts).
- `tests/test_finland.py`: loads, every parameter sourced, no stuck patients, queues, missed cancers, group split, all flowcharts run (about 4 s).
- Reproduce: `python3 -m pathway_sim run scenarios/finland_lung.yaml --flowchart baseline` (about 5 s) and `python3 -m pathway_sim compare scenarios/finland_lung.yaml --seeds 1-5` (about 2.5 min).
