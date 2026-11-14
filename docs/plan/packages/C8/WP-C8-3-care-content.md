# WP-C8-3: Care content: roles, definitive tests, costs, turnaround, capacity, worried well

| | |
|---|---|
| Component | C8 (rules 4, 5), C2; decisions D46, D47 |
| Size | M · Model: Sonnet (with web research) |
| Needs | merged `patient_engine/care.py` (format `care/1`, example `catalogue/_examples/tiny/care.yaml`), `catalogue/lung-primary-care` |
| Provides | `catalogue/lung-primary-care/care.yaml`; definitive tests and `dx_<condition>` markers; a worried-well condition; costs and turnaround on every test; `scenarios/finland_encounter_resources.yaml` (resource capacities); first decision-table numbers in `scenarios/finland_encounter_policy.yaml` once WP-C8-1 has published its format |
| Owned paths | `catalogue/lung-primary-care/`, `params/sources.yaml` (append only), `scenarios/finland_encounter_resources.yaml` (new), `scenarios/finland_encounter_policy.yaml` (numbers only, after WP-C8-1 T1), `docs/research/catalogue/care_practice.md` (new), `tests/test_catalogue_lung.py` |
| Review required | yes: medical content |

## What to build

1. **Research** (`docs/research/catalogue/care_practice.md`, every number from a page you opened):
   - Finnish primary care: what a nurse may do on their own (health-centre nurse clinics, limited
     prescribing for listed conditions, whether nurses order labs or X-rays under standing orders),
     what a GP does; typical booking leads for nurse and GP (THL access-to-care statistics).
   - Rates to start decision tables: how often GPs order a chest X-ray for cough, prescribe
     antibiotics for acute bronchitis or cough (Finnish data exist), refer.
   - Costs in euros (Finnish price lists of wellbeing counties or labs such as HUS/Fimlab/Kela fees):
     visits, blood tests, CRP, chest X-ray, CT, PET-CT, bronchoscopy, biopsy, histology, culture, echo,
     spirometry. Turnaround: same day, days, weeks (culture), very slow (histology with markers).
   - Capacity: what can be sourced about Finnish scanner, endoscopy and lab capacity per region; else
     derive from the existing `scenarios/finland_lung.yaml` resources and mark `assumption`.
2. **Definitive tests (D46):** for each condition a confirming test (lung cancer: histology report;
   tuberculosis: sputum culture; heart failure: echocardiography; asthma/COPD: spirometry with
   reversibility; pneumonia: chest X-ray with clinical picture; reflux: pH monitoring or trial of
   treatment; benign nodule: CT follow-up). Express each as a test output measuring a binary hidden
   variable `dx_<condition>` (`given: {<condition>: {p: 1}, default: {p: 0}}`), sensitivity and
   specificity sourced, slow, expensive, scarce. A visible `cost_scale` factor (lean 1.0 to 1.5) in
   `care.yaml` notes, applied by the engine.
3. **Worried well (D47):** condition `worried_well`, share among presenters as an assumption with
   reasoning (and any source on medically unexplained symptoms in primary care), symptoms independent
   with moderate probabilities, no objective findings.
4. **`care.yaml`** for `lung-primary-care`: roles nurse and GP (and specialist only if WP-C8-1 needs it),
   gathers (nurse sees a subset of history outputs; GP history and examination), actions per role
   matching the table in the C8 doc, treatments (antibiotics, inhaler/bronchodilator, PPI for reflux,
   diuretic for heart failure) with what each resolves, behaviour (first contact share from
   KHALIFE2025, return, give-up, horizon).
5. **Resources fragment** `scenarios/finland_encounter_resources.yaml`: nurse, gp, lab, xray, ct,
   definitive-test resources with `capacity_per_day`, lead days, source or assumption.
6. **Decision-table numbers** once WP-C8-1 posts its format: a first plausible set for nurse and GP
   from the research, each row with a source or `assumption`.

## Acceptance

- [ ] `load_catalogue` and `load_care` load `lung-primary-care` with no errors (test in `tests/test_catalogue_lung.py`).
- [ ] Every new number has a source or `assumption` with reasoning; `python scripts/catalogue_stats.py catalogue/lung-primary-care` shows the counts.
- [ ] Every condition has exactly one definitive test (test).
- [ ] `tests/test_params.py` passes.
- [ ] Report lists the costs and turnaround table, which numbers are sourced, and what a clinician should check.

## Report (builder fills in)
