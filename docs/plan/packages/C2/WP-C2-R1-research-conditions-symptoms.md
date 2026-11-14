# WP-C2-R1: Research: conditions, prevalence among presenters, symptoms and signs by condition

| | |
|---|---|
| Component | C2 `components/C2-clinical-catalogue.md`, K3 and the symptom/sign half of K4 |
| Status | not started |
| Size | M |
| Needs | – (format is being fixed in parallel by WP-C1-1; write plain tables, WP-C2-1 converts) |
| Provides | `docs/research/catalogue/conditions_symptoms.md` |
| Owned paths | `docs/research/catalogue/conditions_symptoms.md` only |
| Review required | yes: medical content |
| Track | submission (feeds the first catalogue) |

## Outcome

A research note a converter agent can turn into `conditions.yaml` and the symptom/sign part of
`variables.yaml` without searching again: every number with its source (full citation, URL or
DOI, the population and setting it was measured in), a grade (A, B, C, `assumption`; definitions
in C2 "Rules of the format"), and a short note. Plus an explicit list of what could not be
sourced.

## Scope

Setting: **adults contacting primary care with chest or general symptoms** (Finland or Nordic
preferred, then UK primary care, then other). Read C2 "Scope of the first catalogue".

1. **Conditions** (8 to 12): lung cancer (with stage distribution at diagnosis, histology group
   shares NSCLC/SCLC, central vs peripheral location share); pneumonia; COPD exacerbation;
   asthma; heart failure; tuberculosis (rare in Finland, say so); benign nodule; reflux or
   post-infectious cough; self-limiting viral illness; no disease found. For each: share among
   presenters with such symptoms if published, otherwise incidence figures that let us derive it
   (show the derivation), and the current values in `scenarios/finland_lung.yaml` for comparison.
2. **Symptoms and signs by condition**: cough over 3 weeks, haemoptysis, breathlessness, chest
   pain, weight loss, fatigue, fever, hoarseness, recurrent chest infection, appetite loss, finger
   clubbing, abnormal chest sounds, enlarged neck nodes. For lung cancer: frequency among cases at
   presentation **and** positive predictive values in primary care (Hamilton et al. CAPER studies,
   NICE NG12 tables, Walter et al., Iyen-Omofoman). For the look-alikes: guideline or review
   figures, graded honestly.
3. **Smoking modifiers**: relative risk of lung cancer by current / former / never smoking, and
   the smoking-status distribution of Finnish adults (THL), for `prevalence.by`.
4. **Co-occurrence** (for D40, later): how often lung cancer first presents as, or alongside, a
   chest infection or pneumonia; how often COPD coexists with lung cancer. Two or three numbers
   are enough.

## Acceptance

- [ ] One table per section with columns: `entry` (proposed snake_case id), `value`, `low`,
      `high`, `unit`, `source` (citation + URL/DOI), `population/setting`, `grade`, `note`.
- [ ] Every value comes from a page you actually opened in this session (WebSearch/WebFetch).
      Never a number from memory. If you only have a number from memory, put it in the
      "could not source" list with that remark.
- [ ] A section "New sources" listing each source once with a proposed id in the style of
      `params/sources.yaml` (read it first; reuse existing ids where the source is already there).
- [ ] A section "Could not source" with what is missing and a suggested assumption plus reasoning,
      marked `assumption`.
- [ ] A section "Comparison with the current scenario": where your numbers differ from
      `scenarios/finland_lung.yaml` and `params/finland.yaml`, say by how much. Do not edit those files.

## Out of scope

Test accuracy and laboratory value distributions (WP-C2-R2). Writing YAML. Editing any file other
than the one you own.

## Rules

- Quote at most a short phrase from any source; paraphrase and give the number.
- Prefer systematic reviews and large primary-care cohorts (grade A); single studies are B;
  guidelines and derived numbers C.
- Stop at about 75 minutes of work: a complete table with honest gaps beats a perfect half table.

## Tickets

| | ID | Ticket | Done when |
|---|---|---|---|
| [ ] | R1-T1 | Read `params/sources.yaml`, `scenarios/finland_lung.yaml`, `docs/parameters.md`; list what exists | note has a "Starting point" section |
| [ ] | R1-T2 | Conditions and prevalence table | table filled or gaps listed |
| [ ] | R1-T3 | Lung cancer symptoms: frequency and PPV in primary care | table filled |
| [ ] | R1-T4 | Look-alike conditions: symptom and sign frequencies | table filled or gaps listed |
| [ ] | R1-T5 | Smoking modifiers, co-occurrence, comparison, new sources, could-not-source | all sections present |

## Report (builder fills in at the end)
