# Simulation

Run the simulation and watch patients move through a lung cancer pathway in a hospital, from the moment a referral arrives to the start of treatment. Each dot is a patient. Steps with limited capacity build queues, and the colour of each step shows how long patients wait there. The target is to start treatment within 42 days.

The pathway runs through a CT scan, a first hospital visit, tissue sampling, a PET-CT scan, an exercise test for patients with reduced lung function, a weekly tumour board meeting and finally surgery or radiotherapy. It is rebuilt from a published study of a real hospital and tuned so that it reproduces that hospital's observed result. How this was done is described in the [Appendix](04-appendix.md).

## Before and after optimisation

You can run the pathway as it is today or as the optimiser proposes it. Both runs use exactly the same patients, so any difference comes from the pathway and not from luck. The optimiser only uses information a clinic would actually have, and it adds no new equipment or staff. It keeps a change only if patients get to treatment faster without more tests than the hospital can run.

Today, about 40 percent of patients start treatment within 42 days. The optimised pathway raises this to about two thirds. The main changes are to order the PET-CT scan and the exercise test at the right time, and to hold the tumour board meeting without waiting for every sample to come back.

## What you can explore

The main number is the share of patients treated within 42 days. Next to it is the median number of days to treatment. The Details menu holds the rest, including a step-by-step view of where patients wait, so you can see where the pathway loses most of its time.

---

**Infographic:** none beyond the simulation itself: the live flowchart with a before/after toggle and a small stats panel.
