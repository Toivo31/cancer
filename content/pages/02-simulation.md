# Simulation

This is the heart of the project. Pick a preset, run it, and watch synthetic patients move through a lung cancer pathway. Each dot is a patient. Steps with limited capacity build queues, and the colour of each step shows how long patients wait there. When the run ends, you can open any patient and follow their journey step by step: what was known about them at each point, what was decided, and how long they waited.

## Presets

**Norway (Stokstad 2019).** A rebuild of the specialist lung cancer pathway at one Norwegian hospital, tuned to match the published result. Every patient has cancer, the clock runs from referral to treatment, and the target is 42 days.

**Finnish county (synthetic).** A synthetic Finnish pathway that starts in primary care. Patients arrive with cough, breathlessness or weight loss, most of them do not have cancer, and they are sorted through nurse and GP visits, X-ray and CT before the few likely cancers reach the specialist steps. The clock runs from first contact to treatment, with a provisional 90-day target.

## Before and after optimisation

Each preset can be run in two versions: the pathway as it is today, and the pathway the optimiser proposes. Both runs use exactly the same patients, so any difference comes from the pathway and not from luck. The optimiser only uses information a clinic would actually have, such as timestamps and test results that were revealed, and it keeps a change only if it helps without increasing missed cancers. The final numbers are reported on held-out patients that the optimiser never saw while searching.

## What the stats show

The main number is the share of patients treated within the target time. Next to it you will find the median days to treatment, the number of tests per patient, and missed cancers, which must not go up. A waiting-time breakdown splits the total time into the four stages of the national brief: detection in primary care, referral, diagnosis and treatment start. For each stage it separates time spent being tested from time spent waiting, which shows where the pathway loses most of its time.

As an example, in our synthetic Finnish county the optimiser found two changes that need no new equipment: book the specialist visit as soon as the referral arrives, and reserve the treatment slot as soon as the patient is sent to the tumour board. On held-out patients, the share treated within 90 days rose from 18 to 33 percent. This is a result inside our synthetic world, not a forecast for real Finnish patients.

---

**Infographic:** none beyond the simulation itself. The page is the live flowchart view with the before/after toggle and a small stats panel.
