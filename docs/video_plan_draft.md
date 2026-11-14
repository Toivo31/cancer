# Video plan (draft, AstraZeneca submission)

Draft by Eemeli. It builds on the team script `docs/pitch/video_script.md` and the actions in `docs/pitch/recommendation.md` (both on branch `overnight/sim`) and does not replace them. Nothing here is final until the open decisions below are settled.

**Length:** 2:00. **Deadline:** final submission Sun 15 Nov 10:00; aim to upload by 08:00.

## Who it is for and what it must do

- **Two audiences.** The full Junction audience (understand it with no background, remember one image) and the AZ judges (sources, a real gap, and above all a plan a county can carry out).
- **Weighting from the AZ criteria:** Actionability 30%, Insight 25%, Data quality and transparency 20%, Execution 15%, Clarity 10%. The brief also says a decision-maker must get the message "in less than two minutes", so the video is the clarity test itself.
- **So the time goes where the points are:** about 40 of the 120 seconds go to implementation (who does what, first step, how it is measured), more than any other part.
- **Science-backed, shown not told:** every number on screen carries its source, simulated numbers are labelled "synthetic", and the model is shown passing a blind test on a published study before we ask anyone to trust its proposal.

## Style reference

Nigel Stanford, "CYMATICS: Science Vs. Music" (https://www.youtube.com/watch?v=Q3oItpVa9fs). What we take from it:

- **Make the invisible visible.** In Cymatics, sound becomes patterns in sand and water. Here, waiting time becomes patients piling up in queues.
- **Each scene is an experiment.** Set it up, run it, see the result. That is also how the science part works: run the published pathway, then the changed one.
- **Cut on the beat, dark stage, one bright subject.** Black background, the moving dots are the only light.

What we cannot take: the music (copyrighted), and a pure music video with no words. The brief needs the gap, where it sits, the recommendation and sources, so we keep a short voice-over and captions on screen at all times.

**Music:** royalty-free electronic track with a clear build and drop, about 120 BPM (YouTube Audio Library, Pixabay Music, or similar). Note the licence in the submission.

**Core visual: the pathway as an instrument.** Each simulated patient is a dot travelling through the flowchart (primary care, referral, diagnosis, treatment). Where a step is slow, dots pile up into a glowing heap. When a change is applied, the heap dissolves and the dots flow through. Rendered from the simulator's event log as a canvas animation and screen-recorded.

## Music map (team choice: Cymatics excerpt, song 0:30-2:30)

Excerpt file kept outside the repo (`~/Downloads/cymatics_0m30_to_2m30_excerpt.wav`, 2:00 with a 1.5 s fade-out); beat times in `~/Downloads/cymatics_excerpt_beats.csv`. Tempo about 185 BPM (a beat every 0.325 s; cut on every 4th or 8th beat). Times below are in the excerpt (= video time).

| Video time | Music | Use |
|---|---|---|
| 0:00-0:02 | End of the intro hit | Title card in |
| 0:02-0:14 | Quiet dip | Gap scene (123 vs 207); voice-over is clear here |
| 0:14 | New layer starts (onset at 0:14.3) | Cut to the pathway: piles start growing |
| 0:14-0:49 | Long build | "Where it emerges" and the 18% |
| **0:49.8** | **Drop** (strongest hit) | Press → : the piles dissolve, 61% |
| 0:50-1:51 | Full energy, loud | Norway check and implementation cards; duck the music under the voice-over (about -12 dB) |
| 1:51 | Energy dips | End card |

Note: the track is copyrighted (Nigel Stanford). The team chose to use it; YouTube Content ID may mute or block the upload, so check the uploaded video before submitting.

## Shot list and voice-over

About 270 spoken words; read aloud with a timer and trim the science scene first if it runs over.

| Time | Scene | Picture | Voice-over / caption |
|---|---|---|---|
| 0:00-0:06 | Title | Black. Beat starts. One dot, then hundreds. Title card in the 70s printout style of the deck. | (music only) |
| 0:06-0:20 | **The gap** | Two dots race on two tracks; one reaches "treatment" at day 123, the other at day 207. Source caption. | "Two Finns with the same lymphoma. One enters through occupational or private care and starts treatment in 123 days. The other goes to a public health centre: 207 days. Goal 3 of the national cancer strategy promises equal care within target times." |
| 0:20-0:35 | **Where it emerges** | Lung pathway flowchart, four stages labelled; heaps grow at the waiting points, largest in primary care. | "Lung cancer in Finland has the longest early waits in the Nordics. In our simulation of the pathway, 87 percent of the days are spent waiting, not testing. The largest block is in primary care, before the referral." |
| 0:35-0:55 | **The experiment** | Music builds. Headline 18%. Drop: the change is applied, heaps dissolve, dots flow. Headline 61%. Dots in two colours, both groups faster. | "We let an optimiser try different pathways on the same simulated patients. In our synthetic county, 18 percent start treatment within 90 days. With its change, 61. Patients with vague symptoms gain too. It only accepts changes that miss no more cancers." |
| 0:55-1:10 | **Can you trust it?** | Same animation on the Norwegian pathway: 40% on time, blind search, 80%. Caption: Stokstad et al. 2019. | "Before trusting it, we tested it on a real Norwegian hospital study. It reproduced their 40 percent on time, and without being told the answer it found the same reordering that reached 80. The lesson: order beats capacity." |
| 1:10-1:50 | **What a county does** | Three implementation cards appear on the beat, each with owner, first step and measure (see table below). Dots flow through the matching part of the pathway behind each card. | "So, what does a wellbeing services county do? One: the lung unit books PET-CT, the exercise test and the tumour board at the first specialist visit, instead of one after another. Two: health centres get direct access to chest CT, with a shared rule for when to order it. Three: measure time to treatment at every step, by county, and publish it. Start with one county as a pilot, measured before and after." |
| 1:50-2:00 | **End** | End card: "A doctor decides every case. All patients simulated." Team name, demo link, repo. Music resolves. | "A doctor decides every case. Try the simulator yourself." |

## Implementation cards (Actionability, 30%)

The cards on screen at 1:10-1:50, and the same content in the demo and the deck. Owners and evidence are from `docs/pitch/recommendation.md`. Where it says [check], the item still has to be verified before it goes in.

| # | What changes | Who acts | First step | How it is measured | Evidence |
|---|---|---|---|---|---|
| 1 | Order PET-CT, the exercise test and the tumour-board slot together at the first specialist visit; take tissue samples while treatment is booked | Lung units of the hospital in each wellbeing services county; county medical director | Change the booking template for suspected lung cancer so all three are booked in one visit | Share starting treatment within target time; days from referral to treatment decision | Stokstad 2019 (40% to a modelled 80%); NHS England timed lung pathway; our simulator (synthetic) |
| 2 | Direct chest CT from primary care, also when the first contact is with a nurse, using a shared ordering rule | Wellbeing services counties (primary care and imaging); THL and YTA areas for the shared rule | Agree the ordering criteria with radiology and publish them to health centres | Days from first contact to CT; CT positive rate (guards against overuse) | IHE Cancer Dashboard Finland (few units perform CT); caution: faster CT alone did not speed up decisions in an English cohort (ERJ 2023), so pair with action 1 |
| 3 | Monitor time to treatment per pathway step, per county, published every year | THL with the Finnish Cancer Registry; counties supply data | Report the existing timestamps for one cancer (lung) per step | Goal 3 indicator: patients reach treatment within target times | National Cancer Strategy 2026-2035, sub-objectives 3.1-3.2 and the proposed quality register |
| Pilot | Run actions 1-2 as a monitored pilot in one county first | One volunteering county; THL evaluates | Baseline measurement, then switch | Before vs after on action 3's measures | Our proposal; matches AZ's stated aim of a follow-up project with a wellbeing services county |

To check: whether the implementation roadmap 2026-2031 (resource pack PDF) already lists matching actions. If it does, cite the roadmap item on each card, which makes the proposal "already planned, here is how" rather than "new idea".

The fast track for vague symptoms (action 3 in the team recommendation) is left out of the video to keep it to three cards; it stays in the demo and the deck.

## Sources for the spoken claims

- 123 vs 207 days: Kuitunen et al., *Cancer Medicine* 2026;15:e71920 (DLBCL, days from symptom onset to treatment start, private/occupational vs public primary care entry). This is lymphoma, not lung cancer; never present it as a lung figure.
- Longest early lung cancer waits in the Nordics: IHE Cancer Dashboard Finland (https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf).
- Norwegian 40% / 80%: Stokstad et al. 2019 (https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944). The 80% is the authors' model estimate, not an observed result.
- 87%, 18 -> 61, group gains: our simulator, synthetic data, from `demo/data/demo_bundle.json`. Refill with `docs/pitch/fill_numbers.py` after any rerun.

## Check before recording

- [ ] "Two changes" (team script opening) vs "it suggests one" (team script, screen 3): which is right in the current bundle?
- [ ] Does the optimiser's suggested change in the Finnish run match implementation card 1? If not, the 18 -> 61 scene and the cards tell different stories; either show the optimiser's change on the cards or use the "order together" flowchart's number.
- [ ] D20: is the Finnish target 90 days? (Tuomas)
- [ ] D17: Norwegian headline 80% / 88% with the faster scanner, or 67% without new equipment? (Tuomas)
- [ ] D18: keep or drop the optimiser's fourth change (clinical check).
- [ ] Missed cancers do not rise in the current bundle.
- [ ] Ask Kaisa Kaitila (AZ Medical Affairs, on site Saturday) whether the three cards are realistic for a county.
- [ ] Read the voice-over aloud with a timer: it must fit in 2:00 with the 6 s intro.

## Production steps

1. Build the dot animation from the simulator's event log (canvas page in `demo/`, one patient = one dot). Fallback if time runs out: dashboard screens only, cut on the beat.
2. Pick the music track and mark its beats (build at about 0:35, drop on the "61").
3. Record the voice-over first (quiet room, phone or laptop mic close to the mouth).
4. Screen-record the animation and `demo/index.html` (keys 1-4) at 1080p: Cmd+Shift+5 or OBS.
5. Edit in DaVinci Resolve, CapCut or iMovie: cut picture to the voice-over and beats, add captions, title, implementation cards and end card.
6. Upload to YouTube as unlisted, test the link in a private window, put it in the submission.

## Owners (to fill)

| Task | Who |
|---|---|
| Dot animation | |
| Music and edit | |
| Voice-over | |
| Number and source check | |
| Ask AZ mentor about the cards | |
