# Tech challenges: what we claim, what backs it, what is still open

Four entries: Modal, Nemotron, Gemini API, Verda. Everything below is from the repo (`decision_api/`, `note_reader/`, `technique_classifier/`, `video/`). Items marked **[VERIFY]** need a teammate to confirm before they go in the submission form; **[BUILD]** is work that would make the entry stronger.

Video: https://vimeo.com/1246915943/8fbe835297?share=copy

## One sentence for the judges

Equal Care Pathways is a transparent framework for automating cancer care: clinicians define each pipeline, a decision model runs it, and when the model is unsure a doctor reviews the case. The decision model is **NVIDIA Nemotron**, served on **Modal**; referral notes are read through **Verda**; the video's narration and pictures were made with **Gemini**.

## Modal (40% use of Modal, 25% technical ambition, 20% impact, 15% live demo)

**What we have** (`decision_api/modal_inference.py`, `HOSTED_API.md`)
- Native inference of a fine-tuned Nemotron 3.5 Super VL (120B, A12B) on one Modal GPU (RTX PRO 6000, 320 GB RAM), weights on a Modal Volume, GPU memory snapshots enabled for fast cold start.
- A public, credential-free gateway on Modal in front of it (job queue, polling, rate limits), so a judge can open one URL: `https://cancer123--birch-decision-1138-demo.us-east.modal.run/decision`.
- Measured on the live checkpoint (`validation/performance2350.json`): first score 3.4 s, cached score 0.2 s; a tool-using evidence summary about 22 s (84 tokens, one tool call); 78 GiB GPU memory.

**Honest gaps** (the criteria name Sandboxes, training and scaling out)
- One container, one request at a time (`max_containers=1`, `max_inputs=1`); scales to zero.
- No Modal Sandboxes, no parallel `.map` scale-out visible in the code. **[VERIFY]** whether training of checkpoint 2350 ran on Modal.

**To win**
- **[BUILD]** Keep the container warm for the judging window (`min_containers=1`) so the demo never waits for a cold start.
- **[BUILD]** One real scale-out use: run many patients or pathway variants in parallel with `.map` (for example the optimiser's variants), and report the speed-up.
- **[BUILD]** One Sandbox use that fits the story: run a clinician-defined pipeline rule in an isolated Sandbox, with its log as the audit trail.
- **[BUILD]** Host the main demo page on Modal too, so the judges open one live link.

## Nemotron (25% meaningful use, 25% technical execution, 25% quality of output, 25% creativity)

**What we have**
- Nemotron is the decision model: it scores every allowed answer at a pathway step; a human accepts or corrects. Fine-tuned (LoRA, checkpoint 2350, checksum pinned).
- Creative design: the original frozen Nemotron head writes a short evidence summary and asks for read-only tools; then the trained decision head scores the choices. Frozen weights are shared, so no second model is loaded.
- Execution: bounded tokens (default 128, max 512), validated and really executed tool calls, truncated output never appended, off by default, human review separate from the score.
- Quality evidence so far (`validation/README.md`): 5 of 6 label agreement on six reused questions (4 of 6 earlier). The docs say plainly that this is a smoke check, not a benchmark, and that summaries can overreach.

**To win**
- **[BUILD]** One visible evaluation on pathway questions with before and after numbers and the same honest caveats. This is the "quality of output" box.
- **[BUILD]** Say in the video, deck and form what Nemotron does and why it matters: it decides each pathway step; clinicians validate.
- Show latency and error handling on screen (3.4 s, 0.2 s cached, bounded generation).

## Gemini API (open challenge: problem, integration, what is innovative, why Gemini)

**What we have (honest)**
- Gemini made the video's narration (Gemini text-to-speech) and the still images. Google DeepMind confirmed in #google-deepmind that any use of Gemini counts.
- It is not part of the product itself.

**To win**
- **[BUILD]** Use Gemini inside the product, for example to generate the synthetic patient notes for the patient engine (the plan already has an LLM writing patient cards), and describe that pipeline.
- Otherwise enter with a short, factual paragraph and claim nothing more.

## Verda (25% ambition, 25% fit, 25% working prototype and documentation, 25% path to scale)

**What we have**
- The note reader and technique classifier call an LLM through Verda (`note_reader/server.py`, `technique_classifier/llm.py`), with stored fallback.
- **[VERIFY]** Whether any training or other heavy work ran on a Verda GPU.

**To win**
- State the ambition: what the compute allowed that we could not otherwise do.
- Path to scale: one pilot in one region, cost per decision from the measured numbers above, what real data and governance would be needed.
- Documentation: this repo's `decision_api/validation/` records and a short "how to run it" section.

## Order of work (about 9 hours to the submission deadline, Sunday 10:00)

1. Confirm the **[VERIFY]** items.
2. Warm, public Modal demo (one link).
3. One Nemotron evaluation shown on screen.
4. One real Modal scale-out or Sandbox use.
5. One real Gemini use in the product, or enter with the honest paragraph.
6. One short paragraph per challenge in the form, in the judges' own words.
