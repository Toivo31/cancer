# The video: script, how it is made, how to change it

Submission video for Equal Care Pathways (AstraZeneca challenge, Junction 2026): about 84 s, 1920×1080, warm white paper and dark ink. Link: see the top of the main [README](../README.md).

## Narration script (current)

Times are when each line starts in the cut; the last slide is deliberately not narrated.

| Start | Line | On screen |
|---|---|---|
| 0:00 | Two people, the same cancer. One waits months longer for treatment. | "Same lymphoma": **123 days** (occupational or private care) vs **207 days** (public health centre), counted up on the spoken numbers; then the scanner clip |
| 0:07 | Doctors either trust AI too little and check everything, or too much and check nothing. | "Trust AI too little, / Trust it too much," (approved wording and timing, locked) |
| 0:14 | In our framework, clinicians define each pipeline, the system runs it, and when the model is unsure, a doctor reviews the case. | Three numbered lines, each on its words |
| 0:24 | We propose a framework where an expert defines a standardized care plan. From initial symptoms to post-cure screening, this can largely be automated by our decision model, specialized in medical data. | The pathway animation: the chart builds, dots flow, a thin blue fast track from the GP |
| 0:38 | We believe that although much of medicine can't be automated, we could free doctors from repeating tasks to concentrate on difficult cases. Whether it's scheduling visits, routing patients to the correct specialists, or identifying symptoms. | "What we believe", three points on their words |
| 0:54 | For example, our decision model can read the patient history automatically and select from a predefined set of actions whether urgent care is needed. | The note-reader scene (synthetic example) |
| 1:03 | *(no voice)* | Credit: AstraZeneca challenge; Decision model: NVIDIA Nemotron; Served on: Modal; Note reader: Verda |
| 1:07 | Our suggestion: pilot one clinician-validated pipeline in North Savo, tracking treatment within target times. More time for hard cases and the human encounter. | The suggestion, line by line |
| 1:18 | *(no voice, a beat of silence)* | "Waiting is a decision nobody made." with a low hit, then the repo link |

The script lives in `generated/script_v3.json` (text and phrase splits). The sequence above is the 123 / 207 figure from Kuitunen et al., *Cancer Medicine* 2026;15:e71920 (DLBCL, lymphoma, not lung; days from symptom onset to treatment).

## How it is made

1. **Voice.** `generated/tts.py` generates each line with Gemini text-to-speech (`gemini-2.5-pro-preview-tts`, voice Orus, a style prompt for a natural presenter). This is a placeholder voice: a recording of the team's own voice replaces it (see below).
2. **Timing.** `generated/build_timeline.py` measures where every phrase and word starts in each recording (faster-whisper word timestamps, aligned to the script; a pause-based fallback), and schedules every scene, every on-screen line, the chimes and the clock ticks from those times. It writes `dots/trailer_assets/cues.json` and `timeline.json`.
3. **Picture.** `dots/trailer2.js` draws the whole video on a canvas in the browser, cued from `timeline.json`: statements cut in on the spoken word, the pathway animation (`dots/flow.js`), the note-reader scene (`dots/zoom.js`), TV-style captions only where the voice says something the screen doesn't. Open `dots/index.html?trailer` through the local server (`python -m note_reader.server`, then http://127.0.0.1:8770/dots/index.html?trailer). `&mute` runs silent, `&from=40` starts at 40 s, `&nocap` hides captions.
4. **Sound.** The low "brrr" at the start is a music sample (fades in, fades out before the first slide, ducked under the voice); the chime, the ticks and the final hit are synthesized in code.
5. **Render.** `render_trailer.py` plays the page on a fake clock, one frame at a time in Chrome (Playwright), mixes the same sound from the same files and times, normalises loudness to -14 LUFS (two-pass EBU R128), and encodes mp4 with ffmpeg.

```bash
# one-time setup (a scratch virtualenv is enough)
pip install playwright imageio-ffmpeg numpy scipy faster-whisper
# regenerate a changed line's voice, then re-sync everything
python video/generated/tts.py --lines script_v3.json --voice Orus --line n5
python video/generated/build_timeline.py
python video/render_trailer.py --out video/generated/out/trailer.mp4
```

## Using your own voice

Record one file per line, named `n1, n2, n3, n4a, n4b, n5, n7` (any audio format), in one folder, with a natural pause between phrases. Then:

```bash
python video/generated/build_timeline.py --from-dir ~/recordings --rate 1.0
python video/render_trailer.py
```

Every cut, caption, tick and chime re-syncs to the recording. The line `n2` ("Doctors either trust…") is locked to its approved recording and timing; skip it to keep it.

## What is not in git

The generated voice files, the music sample, the scanner clip frames and the rendered mp4 are git-ignored (`dots/trailer_assets/`, `generated/out/`).
- The scanner clip is 2 s from a film scene, extracted with ffmpeg (24 fps JPEG frames into `trailer_assets/scanclip/`). It is short and used for illustration; it is not ours, so check usage rights before a public release.
- The music sample is a short clip of a third-party track (CYMATICS).

## Other files here

- `deck/`: source of the presentation deck built from the video's scenes (see its README).
- `dots/trailer.js`: the earlier, longer cut, kept for reference. `dots/trailer_final.js`: an earlier script from the team.
- `generated/script_v2.json`, `vo_*.json`, `stills.py`, `veo.py`: earlier scripts and the first-draft image and video generation (Gemini images; Veo was not available).
- `../docs/submission_tech_challenges.md`: how Gemini, Nemotron, Modal and Verda are used, honestly.
