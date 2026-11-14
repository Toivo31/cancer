# Case study: Norway

An improvement inside our own simulator proves little on its own. To check whether the simulator and optimiser behave sensibly on a real hospital, we used a published case: Stokstad and colleagues' 2019 study of 100 patients with early-stage lung cancer at St Olavs Hospital in Trondheim. Only 40 percent of them started treatment within Norway's 42-day target. The authors then estimated that a faster PET-CT scanner would have raised this to 48 percent, and that a reordered pathway would have raised it to 80 percent.

## Rebuilding the hospital

We rebuilt the hospital's pathway as a flowchart from the paper: a CT scan, a first hospital visit, tissue sampling, PET-CT, an exercise test for patients with reduced lung function, a weekly tumour board, a wait for surgery or radiotherapy, and treatment. Waiting times were taken from the intervals the paper reports, such as a median of 20.5 days from PET-CT referral to report. We kept the variation the paper describes, for example the patients whose PET-CT was ordered late and those who needed a repeat bronchoscopy.

A few quantities the simulation needs are not reported in the paper, such as the wait for bronchoscopy. We tried many combinations of them and kept every one under which our virtual hospital reproduced the real result: about 40 percent treated within 42 days and a median of about 46 days. That is the only thing we tuned.

## Comparing with the paper

With the hospital calibrated, we ran the authors' two alternatives without tuning anything further. Their reordered pathway gave 80 percent at our best fit, the same as the paper. Across all the settings that fitted equally well, it ranged from 62 to 86 percent, so we treat the 80 percent as one point in a band rather than an exact match. The faster scanner alone gave 60 percent, higher than the paper's 48 percent, so our simulator overestimates that change. The ranking held in every setting: reordering beats a faster scanner, and a faster scanner beats today's pathway.

We then let our optimiser search from today's pathway on its own, with no new equipment and without being told the authors' answer. It arrived at the same three timing changes the authors proposed: order PET-CT on time, order the exercise test early, and hold the tumour board without waiting for the sample to finish. It added one more change, planning tissue sampling already at referral, which is not in the paper and would need clinical review. The optimised pathway treated 67 percent within target at the best fit, with a range of 48 to 77 percent, against about 40 percent today.

## What it shows

The optimiser rediscovered the direction that experienced clinicians found, and it did not improve on their redesign. The test supports the direction of its changes, not the exact size of its predictions. It covers specialist care only, since every patient in the study already had cancer.

---

**Infographic:** a bar chart with the paper's numbers next to ours for four pathways: today (40% / 40%), faster PET-CT (48% / 60%), authors' reordering (80% / 80%, band 62 to 86%) and our optimiser with no new equipment (not in paper / 67%, band 48 to 77%).
