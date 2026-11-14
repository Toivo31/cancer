# Pathway dots (video animation)

One dot = one simulated lung cancer patient. Every patient starts at day 0 (first contact) and moves through the four stages of the brief: detection, referral, diagnosis, treatment start. A dot waiting for a step sits in the pile above that step; piles turn orange the longer the patients in them have waited. On the right, patients who reached treatment within the target time (bright) and later (grey); red = cancer not diagnosed.

The patients are the same held-out cohorts the dashboard uses, so the percentages match `demo/data/demo_bundle.json` exactly (checked by the export script):

| Scenario | Pathway | Within target |
|---|---|---|
| Finland (synthetic, 90 days) | Today's pathway | 17.5% |
| | Optimiser's change (priority after the hospital handles the referral) | 61.5% |
| | CT and PET-CT ordered together at the specialist visit | 53.7% |
| Norway (Stokstad et al. 2019, 42 days) | Observed pathway | 40.1% |
| | Authors' reordered pathway, simulated | 80.1% |
| | Optimiser, found blind, with the faster PET-CT | 88.2% |

## Open

Open `index.html` in Chrome (works from the file; fonts load from Google Fonts when online). Make the window 1920x1080 or full screen.

Keys: space play/pause, r restart, → / ← switch pathway on the same patients and the same day (the "drop" moment: piles dissolve), 1 2 3 pick pathway, s split view, n Finland / Norway, g colour by symptom group, l labels for the three biggest piles, + / − speed, h hide help for recording.

URL options, for repeatable takes: `?s=norway`, `?v=optimiser`, `?split=baseline,optimiser`, `?speed=10` (days per second), `?day=45`, `?end=180`, `?paused`, `?clean` (no help box), `?labels`, `?groups`.

Takes for the video plan (`docs/video_plan_draft.md`):

- 0:20-0:35, where it emerges: `index.html?clean&labels&speed=8`
- 0:35-0:55, the experiment: `index.html?clean&speed=8`, press → at the music drop (switches to the optimiser's change on the same patients). Or `?clean&split=baseline,optimiser`.
- 0:55-1:10, Norway check: `index.html?clean&s=norway&split=observed,authors&speed=4`

Record with Cmd+Shift+5 (record selected portion) or OBS at 1920x1080.

## Regenerate the data

Needs a checkout of branch `overnight/sim` (the simulator):

    git worktree add ../cancer-sim origin/overnight/sim
    .venv/bin/python video/dots/export_dots.py --sim ../cancer-sim

Rerun after any simulator or bundle change, and check that the printed shares match the dashboard.

## Music-synced sample (`?show`)

Plays the 2:00 music excerpt and drives the animation from it: title, the 123 vs 207 gap card, the flow scene (0:14-1:04: two flowcharts side by side, today vs with the fast lane; day 120 lands on the drop at 0:49.8), the Norway split, the three implementation cards and the end card, with subtitles.

1. Put the excerpt at `audio/excerpt.wav` (that folder is git-ignored; the music is not committed).
2. Serve the folder and open the page (the audio needs a click to start):

       cd video/dots && python3 -m http.server 8765
       open "http://127.0.0.1:8765/index.html?show"

Options: `&mute` runs on a silent clock (picture only, for testing or recording without sound), `&from=46` starts at 0:46 (works with `&mute`; the simple Python server cannot seek in audio).

## Patient race (`?race`)

Eight simulated patients as large dots moving through the named steps (health centre, chest X-ray, referral, specialist, CT, biopsy, PET-CT, tumour board, treatment slot, treatment). Top lane: today's pathway. Bottom lane: the same patients with the optimiser's fast track (priority once the hospital has handled the referral). Dots glow orange while waiting; green with the day number when treated within 90 days, grey when later. The eight are chosen evenly by today's time to treatment (quantiles), not hand-picked. Space plays, r restarts, `&speed=4` sets days per second.

## Flow scene (`?flow`)

Two vertical flowcharts side by side: left today's pathway, right the optimiser's change (fast lane: suspected cancer gets priority in every queue once the hospital has handled the referral). Each ball is one of the same 521 simulated patients; balls start at the bottom (first contact) and climb towards "treatment starts" at the top. Waiting balls swarm around the step they wait for (orange the longer they wait, cyan on the fast lane); a ball sent home with the cancer missed turns red and drops out. Edge thickness = how many patients take that route. Counters: share treated within 90 days and missed cancers. Real numbers: median 103 days today vs 80 with the fast lane; 95% treated by day 142 vs 118; 55 missed on both sides.
