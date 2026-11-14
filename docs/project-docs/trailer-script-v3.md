# Junction 2026 trailer: script v3 (the note is the quote)

Target 1:58, hard cap 2:00. Draft v3, 14 Nov 2026. This replaces the beat structure of v2 (`trailer-script-and-prompt.md`); the look, sound and "how to work" parts of v2 still stand.

## What changed, and why it works

The film now has one object that carries the whole story: **the note**. A doctor hands Walter a slip. He thinks it holds his place in the queue. It is the IBM line about accountability. The slip fills the screen, its black ink becomes the black stage of our animation, and its letters become dots. After that, everything on screen is dots and numbers, until the same slip comes back at the end with its second line retyped.

- **Paper world → dot world.** The transition from the film world (cream paper, grain, waiting room) to the simulation world (black stage, dots, mono numerals) is the one big move of the video, and it happens on the note.
- **One grammar.** After the transition, one dot is one patient, a pile is waiting, amber is waiting longer, mint is treated in time. The viewer never has to learn a second visual language.
- **Explain in the order a judge asks.** Why does this matter (the wait) → how does it decide (the engine) → can we trust it (a real study) → what does it change (the drop, Finland).
- **The echo.** The waiting-room display says 87 days. Later the narrator says 87 percent of the days are waiting. The first is a dramatisation, the second is our simulation (current bundle). They rhyme on purpose; the dramatisation gets a small tag.

## Things to settle before rendering (these affect honesty)

1. **The animation's 61% is not our headline any more.** The dots animation shows Finland 17.5% → 61.5% with "priority after the hospital handles the referral". In the current bundle that figure is the conditional urgent-booking scenario, which depends on assumed booking times and is "not a result". The current Finnish headline is **18% → 33%** (two reorders, no new equipment). So for the drop moment this script uses the **Norwegian split**, whose numbers match the bundle and the published study (40.1% observed, 80.1% authors' reorder simulated, 88.2% optimiser blind with the faster scanner, 67% with no new equipment). If you want the Finnish drop on screen too, the data needs re-exporting with the reorder-only variant (`video/dots/export_dots.py`, README has the command). Until then show Finland as a number card (beat 8).
2. **The "OUR SOLUTION" half of the flow scene** (53% and 79%, "fast lane, median 80 days") rests on assumed fast-lane booking times. Use it only for the note-reader panel, not for those numbers.
3. **"87 DAYS" on the waiting-room display** is a dramatisation. Keep the corner tag "Dramatisation" while the display is on screen.
4. **The IBM line** is commonly attributed to a 1979 IBM slide. Worth verifying the wording and origin before the caption claims it.
5. **88 vs 67 vs 80.** 80 is the study authors' own modelled estimate. 88 includes the faster scanner. 67 needs no new equipment. The script says the optimiser "finds the reorder the authors found" and shows 80, then 88 and 67 as small numbers, matching the demo's headline screen.
6. **Walt's number.** The display shows a long wait, but we never claim a wait for any real person.

## Music map (the Cymatics excerpt, from the team's video plan)

Excerpt is 2:00 starting at song 0:30, tempo about 185 BPM (a beat every 0.325 s, a bar every 1.3 s). Key moments in the excerpt: quiet dip from 0:02, new layer at 0:14.3, long build, **drop at 0:49.8**, full energy to 1:51. In this script the excerpt starts about 26 seconds into the video, so video time = excerpt time + 26 s:

| Video time | Music | Picture |
|---|---|---|
| 0:00 to 0:27 | None. Clip sound, room tone, a clock | Walt clip, note, waiting room |
| 0:27 | Fades in from the quiet dip | The note unfolds, the push-in starts |
| 0:40.3 | New layer | The first dots, the piles start to grow |
| 0:48 to 1:15 | Long build | The engine, then Norway observed and the queues |
| **1:15.8** | **Drop** | **The piles dissolve** |
| 1:16 to 1:40 | Full energy, duck about 12 dB under the voice | Result, Finland card |
| 1:40 to 1:46 | Cut the music out with a hard stop on a bar line (do not use the excerpt's own ending) | Last numbers |
| 1:46 to 1:58 | Silence, typewriter clicks, one low note | The ending |

Cut on every 4th beat (1.3 s) where the picture allows.

## Script

**Beat 1, 0:00 to 0:12. The diagnosis (clip, supplied).**
- The Breaking Bad scene, cut to about 12 seconds ending where the doctor's voice drops out and the focus drifts. The clip's own sound. No music, no text. Hard cut at the quietest moment.

**Beat 2, 0:12 to 0:19. The note (generated).**
- A doctor's hand, no face, slides a small folded slip across the desk. Walt takes it. Cut to a corridor and a door marked WAITING ROOM. Room tone, a clock tick.

**Beat 3, 0:19 to 0:27. The number (generated, one establishing shot).**
- A crowded waiting room of plastic chairs seen from the door, Walt takes a seat among silhouettes. A dot-matrix display on the wall shows the wait: "87 DAYS" (overlay the text in the edit, since generators garble numerals). Tag: "Dramatisation".
- VO (0:21): "Cancer is a word. Waiting is a number."

**Beat 4, 0:27 to 0:36. The note is the quote (generated, then edit).**
- Walt unfolds the slip to check his number. Close on the paper: typed text, A COMPUTER CAN NEVER BE HELD ACCOUNTABLE / THEREFORE A COMPUTER MUST NEVER MAKE A MANAGEMENT DECISION. He frowns. Then the push-in: in the edit, scale the supplied IBM note image up until the text fills the screen, then keep going into the black of one letter until the screen is black. Music fades in at the start of the push.
- VO (0:29): "In 1979, a slide at IBM said a computer can never be held accountable. We agree."

**Beat 5, 0:36 to 0:48. The wait (animation).**
- From the black, the typed letters reappear as small dots, which scatter into the first frame of the animation: today's pathway, the day counter starts, the piles grow, labels name the three biggest ones. The new music layer arrives at 0:40.3 as the first pile rises.
- Take: `index.html?clean&labels&speed=8`.
- VO (0:37): "So ours never decides. Each dot is a simulated patient. Where they wait, they pile up. Eighty-seven percent of the days are waiting, not testing."

**Beat 6, 0:48 to 1:05. The engine (animation and code-built diagram).**
- The piles settle into a flowchart (the flow scene's left side, today's pathway). A clinical note card appears beside it, with the words "likely stress" and "lost 6 kg" highlighted (take from the flow scene's note panel, synthetic example text). Then the decision model, drawn in the dot style: the note's words stream into one tall bar of cells (the summary), the allowed next steps appear as cards, thin layers between them let each option see the others, bars grow into probabilities, the top option lights, a "Doctor decides" stamp lands. As each of the three jobs is spoken, its label lights in cyan: SECOND OPINION (the flag appears on the note), AUTOMATION FRAMEWORK (a node changes from a person to a machine and the dots keep flowing), PATHWAY OPTIMISATION (two versions of the flowchart side by side).
- VO: "The pathway is a flowchart people set. At each step, a decision model reads the patient's notes and results, compares every option at once, and proposes the next step. A second opinion. A framework for automation. An optimiser for the order."
- Show the "half the compute" meter only if the baseline benchmark confirms it.

**Beat 7a, 1:05 to 1:15.8. Calibrate and analyse (animation).**
- The Norwegian pathway, observed, with the source caption "Stokstad et al. 2019". The dots run, the amber piles rise (the tall pile is the PET-CT queue), and the number lands on 40% beside the published 40%. A two-gauge lock: "Published 40% / Ours 40%".
- Take: `index.html?clean&s=norway&split=observed,authors&speed=4`, recorded to just before the piles are switched.
- VO (1:05): "First, a real Norwegian pathway, rebuilt from the paper: forty percent treated on time, as published. Where does the time go? Into the queues."

**Beat 7b, 1:15.8 to 1:28. The drop (animation).**
- On the drop of the music, press → : the piles dissolve and the same patients flow through. The mint block jumps from 40% to 80%. Then small numbers appear beside it: 88% with the faster scanner, 67% with no new equipment. A second image: two bars, "More capacity: 40 → 48% (not significant)" against "Better order: 40 → 80%".
- VO (1:16): "Now the optimiser, told nothing, tries new orders on the same patients. It finds the reorder the authors found. Eighty percent. More capacity barely moves it. Order does."

**Beat 8, 1:28 to 1:40. Finland and equity (number card over the dots).**
- Dimmed dots behind. A big card: "Synthetic Finnish county, held-out patients, 90-day provisional target. Today 18%. Two reorders, no new equipment 33%." A second line: "Vague symptoms 13 → 26%. Alarm symptoms 27 → 50%. Both groups gain." Footer: "Simulated patients. Assumptions in the deck."
- VO (1:29): "In a synthetic Finnish county, eighteen percent are treated within ninety days. With two reorders and no new equipment, thirty-three."

**Beat 9, 1:40 to 1:58. The ending (generated, then edit).**
- The music cuts out on a bar line at 1:46. Back in the waiting room, the same wide shot. The dots of the display lift off and dissolve like the piles did. Walt unfolds the note again: the typed text has changed, THEREFORE A HUMAN DECIDES / WITH THE WHOLE SYSTEM IN VIEW. A door opens, a doctor seen from behind (no face) says nothing, only holds the door. Walt gets up. Cut to black. One second. End card: "Waiting is a decision nobody made." and small: "A doctor decides every case. All patients simulated. Demo and sources in the deck." plus team name and repo or demo link.
- VO (1:48): "A doctor decides every case. Waiting is a decision nobody made. Now someone can."
- Alternate ending, if the generated waiting room does not work: stay in the dot world. A single amber dot in the biggest pile, the drop, and its path climbs through the flowchart to treatment; the pile is the waiting room seen from above. Then black, the retyped note, the end card.

Spoken words: about 175. That leaves room to breathe, so no line has to be rushed.

## What to generate, what to record, what to build

| Beats | How | Notes |
|---|---|---|
| 1 | Supplied clip | Cut to about 12 s |
| 2, 3, 4 (up to the unfold), 9 | ElevenLabs, from the reference screencaptures, the mood boards (the video board 01 weighs most) and the audio | About 25 s of generated video in total. Generate the waiting room once and reuse it for the ending (change the display and the note in the edit) to save credits |
| 4 push-in, 5 letters to dots | Edit | Scale the supplied IBM note image, then a short particle or dissolve effect from letters to dots. Do not ask a generator to render the text |
| 5, 7a, 7b, the dots behind 8 | Screen recording of `video/dots` | 1920x1080, `?clean`, URL params above. Press → on the drop |
| 6 | Code-built diagram, in the dot style | Can be a canvas page like the dots one; build it from the master plan section 3 |
| Numerals, display text, captions, end card | Edit | Overlay real text everywhere; generators garble it |

## ElevenLabs prompts for the generated shots

Give each with the reference screencaptures of the character, the waiting-room images from video mood board 01, and the simulation board for the dot-display look.

1. **Beat 2, the slip.** "1980s documentary look, 16mm grain, soft teal-black and cream palette. Close shot across a wooden desk in a plain consultation room. A doctor's hand, no face visible, slides a small folded slip of paper toward the man in the reference images, who picks it up. Static camera, shallow focus, quiet. No computers or screens."
2. **Beat 3, the waiting room.** "Same look. A long municipal waiting room seen from the door, rows of plastic chairs, people as quiet silhouettes, tall frosted windows, cold teal light. The man from the reference images takes a seat. On the far wall a dot-matrix display with warm amber dots, left blank. Slow push-in, symmetrical one-point perspective. No computers, no faces besides the man."
3. **Beat 4, the unfold.** "Close on the man's hands unfolding a small slip of cream paper, then his eyes narrowing as he reads. The paper is a clean typed note, no legible text. Shallow focus, soft grain, teal-black background."
4. **Beat 9, the door.** "Same waiting room as before. The dots on the wall display lift off and drift away, leaving the wall blank. The man looks at a note in his hand, then a door at the side opens. A doctor seen from behind holds it open, no face. The man stands. Slow, calm, hopeful. Same grain and palette."

## Checks before recording

- [ ] Read the voice-over aloud with a timer. It should end by 1:54.
- [ ] Do the Norwegian numbers on screen match `demo/data/demo_bundle.json` (40.1, 80.1, 88.2, 67)?
- [ ] Is 18 → 33 and 13 → 26 / 27 → 50 still what the current bundle says after any rerun? (`docs/pitch/fill_numbers.py`)
- [ ] The corner tag "Dramatisation" while the 87 DAYS display is on screen.
- [ ] Watch once with sound off: does the story still read?
