# Junction 2026 trailer: script and generation prompt

Target length 1:58, hard cap 2:00. Draft v2, 14 Nov 2026 (v2: real Breaking Bad scene and the supplied track are in, clearance handled by Tuomas).

## Calls made in this draft (worth a quick look before generating)

1. **Cold open: the real diagnosis scene from Breaking Bad.** Used as the first 8 to 10 seconds, with no music. Only the stretch where the doctor's voice drops out and the focus drifts off him is needed. It is lung cancer too, which is our pathway, and it is recognised instantly, so the "waiting" line lands without any set-up. An original recreation of the same beat is kept as a fallback in beat 1.
2. **IBM slide comes at 0:24, not first.** The cold open earns the slide: first the feeling, then the thesis. The slide returns at the end with its second line retyped.
3. **Music.** I could not open the YouTube link, so the track's structure is unknown. The script gives rules for placing it (music enters on the slide, silence at the end), and the exact cut points need to be set by ear.
4. **No invented results.** Every `[RUN]` value must come from the real simulator run. If the optimiser lands below the Norwegian study's 80 percent, show the real number. That is still a good story, and judges reward transparency (20 percent data quality).

## The prompt

You are helping produce the 2-minute trailer for our Junction 2026 entry (AstraZeneca oncology challenge). The deadline is Sunday 15 Nov 2026 at 10:00, with a working demo, this video and a pitch deck. The full context is in `docs/master_plan.md` in repo toivo31/cancer, and the project docs (evidence-grounding-plan, capacity-vs-order-evidence, simulator-design-and-open-questions) are worth reading too.

### What the video is for

Judges score Actionability 30%, Insight 25%, Data quality and transparency 20%, Execution 15% and Clarity 10%. This video is our main Execution evidence and a Clarity test: a non-technical person should follow it in one watch, and it should be memorable. It has three jobs, each of which should be easy to point at on screen:

1. **The three core benefits**: a second opinion at every step, an automation framework (the model interprets a step's result once the step is automated), and pathway optimisation (would another order of steps, or a fast track, shorten time to treatment).
2. **The JEV decision architecture shown visually and in real detail**: patient context, one summary of it, a correction model that sees every option, a dot product against the allowed next steps, a probability for every option in one pass, a second question reusing the work, and a doctor who decides.
3. **How the node network is calibrated with real data, then analysed, then optimised**: the published Norwegian pathway rebuilt from the paper, about 100 synthetic patients reproducing 40% treated within 42 days, queues located by stage, then the optimiser reordering the steps and the same patients rerun.

### Ideas for making it effective (take, adapt or replace)

- **Follow one dot.** Patients are dots. One dot is amber from the first scene to the last, so the viewer always knows where they are in the system and the whole video reads as one patient's journey getting shorter.
- **A fixed visual grammar.** Amber means "the thing that matters" and nothing else. Time is horizontal distance. Queues are stacked dots. Waiting and service time are always different colours.
- **Number first, plain words.** Big numbers on screen, labels like "everything we know" and "compare every option at once", with the technical term in small mono type underneath for the judges who want it.
- **Watchable with sound off.** The visuals alone should carry the story, and the narration should add rather than describe.
- **Respect the doctors.** The target of the video is the queue, never the clinicians.

### Look and sound

Retro-renaissance-recon: an 80s public-information film that turns into a calm, precise product demo. Teal-black, grey-teal, cream and paper tones with one amber accent. Beats 1 to 3 have 16mm grain and slight VHS softness, and the supplied scene clip can be graded gently toward the same palette so it sits in the film. From beat 4 on the image gets cleaner, with the same palette, white hairlines and engraved-diagram details. No old computers, CRT monitors or terminals in anything we generate. The narrator is deadpan 80s (ElevenLabs). The music is the track from the supplied link starting at its 0:30 mark. Typed text, stamps, ticks and printer sounds work as percussion.

### Script

**Beat 1, 0:00 to 0:12, cold open: "The word".** No music.
- Visual (primary): the diagnosis scene from Breaking Bad, cut to the stretch of about 8 to 10 seconds where the doctor tells Walter White it is lung cancer, his voice drops out and the focus drifts away. Keep the clip's own sound (muffled voice, room tone) and let it end on the most silent moment. A slow cut or fade to black, then straight into beat 2. No on-screen text over the clip, other than a small credit line if needed.
- Visual (fallback, if the clip does not work in the edit): an original plain consultation room, 4:3, soft. A patient seen from behind, the doctor out of focus across the desk. The voice is muffled except two clear fragments ("... it's lung cancer ..." and "... first available slot is in six weeks"). During the second one the focus racks slowly to a wall calendar, which sharpens, and one square is circled in amber pen. A small "Dramatisation" tag sits in the corner.
- VO (0:09), over the silence after the clip: "Cancer is a word. Waiting is a number."

**Beat 2, 0:12 to 0:24, "Between the tests".** A clock tick turns into a stamp sound and carries the rhythm.
- Visual: a Recon-style montage of six to eight cuts of about 1.5 seconds: a stamp in macro, a ticket dispenser, a long corridor, a pneumatic tube, a form in a tray, a queue seen from behind, a clock. Then a flat Isotype pictogram wipes in with two rows of figures, Finland long and the Nordic neighbours short.
- On screen: "Health-centre appointment, lung cancer pathway. Finland 14 days. Denmark, Norway, Sweden 2 to 7 days." Source tag: IHE Cancer Dashboard Finland 2026.
- VO: "Much of the delay isn't in the tests. It's in the waiting between them. Fourteen days to a health-centre appointment. Our Nordic neighbours: two to seven."

**Beat 3, 0:24 to 0:33, "The slide".** The music enters here, with a downbeat on the first typed letter.
- Visual: a projected slide, typed letter by letter on cream and teal (typed text only, no monitor): A COMPUTER CAN NEVER BE HELD ACCOUNTABLE / THEREFORE A COMPUTER MUST NEVER MAKE A MANAGEMENT DECISION. A thin amber line draws under "management decision".
- VO: "In 1979, a slide at IBM said a computer can never be held accountable. We agree. So ours proposes, and a human decides."
- Note: the slide is commonly attributed to IBM in 1979. It is worth verifying the wording and origin before the on-screen caption claims it.

**Beat 4, 0:33 to 0:50, "One map, three jobs".**
- Visual: the slide dissolves into a hand-inked flowchart on cream paper that redraws itself as the clean teal-black node graph (primary care visit, referral, CT, specialist visit, biopsy, PET-CT, tumour board, treatment). Dots flow through it, and one is amber. Three callouts appear on the same graph, each with a small looping image: (1) a hint card appears beside a node, then a doctor's hand picks a different option; (2) a node changes from a person icon to a machine icon and the dots keep flowing; (3) two versions of the chart side by side, one with a shorter route.
- On screen: "Second opinion", "Automation framework", "Pathway optimisation". Final line: "One shared flowchart, so care depends less on which doctor you meet."
- VO: "One shared flowchart, set by people. Three jobs: a second opinion at every step. A framework for automation. And an optimiser that asks, would another order be faster? Same map for everyone."

**Beat 5, 0:50 to 1:12, "How it decides" (the JEV architecture).** Code-animated for accuracy, blueprint or engraving look.
- Visual, in order:
  1. Zoom into one node. Patient context cards stack in from the left (history, symptoms, a nurse's note, the newest result, which pulses amber). Label: "Everything we know".
  2. The cards compress into one tall bar of cells. Label: "One summary".
  3. The allowed next steps from the flowchart appear on the right as cards.
  4. Between the summary and the options sit thin translucent layers. Threads from every option cross every layer and nudge the cells of the summary. Label: "A correction model lets every option see the others". For two seconds a ghost version shows the plain approach: each option scored alone, no threads.
  5. Dot product: beams from the summary to each option, bars grow into probabilities that sum to 100%, the top option lights amber. Label: "A probability for every option, in one pass".
  6. A second question card slides in and reuses the same summary bar, which skips the first stages. A small meter ticks to a half. Show the half only if the baseline benchmark confirms it.
  7. A "Doctor decides" stamp lands on the top option.
- VO: "At each step, the model reads everything known about the patient. A correction model lets every option see the others. One pass gives each a probability. Ask a second question and it reuses the work. Then a doctor decides."

**Beat 6, 1:12 to 1:42, "Calibrate, analyse, optimise".** A progress rail at the top shows 1 CALIBRATE, 2 ANALYSE, 3 OPTIMISE, with an amber marker moving along it.
- 1:12 to 1:22, calibrate: a page of the Stokstad 2019 paper on cream paper with the pathway drawn on it (CT, first hospital visit, bronchoscopy or needle biopsy, PET-CT, exercise test, weekly tumour board, treatment). Numbers are circled in amber pen (median 20.5 days from PET-CT referral to report, 4.5 days from sampling to pathology report) and fly onto the node graph as dials. About 100 synthetic patients run through, and a histogram of days to treatment builds against a 42-day line. Two gauges meet and lock with a click: "Published 40% / Simulated [RUN]%". On screen: "Synthetic patients, published parameters."
- 1:22 to 1:30, analyse: a heat overlay on the nodes, with four stage bands (detection, referral, diagnosis, treatment start). Waiting time and service time are drawn as two bars per node. The PET-CT node swells with stacked dots. Callout: "Most of the time is waiting, not testing" with the real figure from the run.
- 1:30 to 1:42, optimise: an amber line reroutes edges: PET-CT and the exercise test move to the first visit, the tumour board follows straight after, sampling runs in parallel with treatment booking. The same 100 dots replay, the routes straighten, and the histogram slides left past the 42-day line while the gauge climbs from 40 to [RUN]%. Then two bars: "More capacity: 40 to 48% (not significant)" against "Better order: 40 to 80% (study estimate)", with our own run result beside them. A guardrail ticker runs underneath: no more missed cancers, waits for other patients not worse, tests within capacity.
- VO: "First, calibrate. We rebuild a published Norwegian pathway from the paper, and run a hundred synthetic patients through it. Forty percent treated on time, as in the study. Then, analyse. Where is the time lost? In the queues. Then, optimise. The same patients, a new order. [RUN] percent. More capacity barely moves it. Order doubles it."
- Fallback line if our run lands lower than the study: "The study's authors estimated eighty. Our run reaches [RUN]."

**Beat 7, 1:42 to 1:58, "Close".**
- Visual: a hand stamps "Approved by clinician" on a printed proposal. Then back to the hall from beat 2, now with the queue moving toward the open door, slow dolly. One second of silence. The IBM slide returns and the second line is retyped: THEREFORE A HUMAN DECIDES / WITH THE WHOLE SYSTEM IN VIEW. End card: product name [TBD], tagline "Waiting is a decision nobody made.", and small text "Synthetic data. Sources in the deck. Junction 2026."
- VO: "Every proposal is approved by a clinician. Every patient here is simulated. Every claim has a source. Waiting is a decision nobody made. Now someone can."

### Sound plan

Cold open is the clip's own sound and then silence. The music enters on the slide, from the track's 0:30 mark, on a downbeat. Beat 5 thins the music to a pulse with quantised mechanical sounds. Beat 6 builds, with the lift or drop landing on the reroute in the optimise step. One second of silence before the final slide, then only typewriter clicks and one low note.

### How to work

This is guidance on process, not a fixed recipe:

1. **Read and plan.** Read the master plan and project docs. Think about what already exists and what is still planned, and which on-screen numbers can come from real runs by the deadline. Consider several ways to build the video (code-rendered animation for the diagrams, AI stills with slow push-ins or image-to-video for the atmosphere, ElevenLabs for narration, ffmpeg or an editor to assemble) and weigh quality, time left and image credit cost. If the working demo UI exists, a short real screen recording could be stronger evidence than an animation, and it is worth looking into where it fits.
2. **Audit the script.** Check every number and claim against the master plan and its sources. Look at whether the 2-minute length holds at a natural narration pace, and where to cut if it does not.
3. **Build in layers.** The diagrams carry the clarity, so consider building those first (beats 4 to 6), then the atmosphere (beats 1 to 3 and 7), then narration, then music sync.
4. **Test and reflect.** Watch once with sound off and once with sound only. Time it. If someone non-technical is around, show them and ask them to say what the system does. Look for any place that feels generic and ask whether a more specific image would replace it. Think about what a judge will remember an hour later.
5. **Supplied material.** The Breaking Bad clip and the music track are supplied by Tuomas, who is handling the rights. The editor can treat them as given and focus on how they cut with the rest, including whether the clip's look sits well next to the generated material.
