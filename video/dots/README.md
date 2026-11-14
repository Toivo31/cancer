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

## Inequality evidence on the left (sourced, not simulated)

The flow scene cycles these facts in a "Who falls behind" box. The simulator has no income or region variable, so these are cited, not modelled:

- Income / work route: same lymphoma, 123 days to treatment via occupational or private care vs 207 via a public health centre. Kuitunen et al., Cancer Medicine 2026;15:e71920 (AstraZeneca briefing).
- Low income: upfront fees for several cancer services can be a barrier. OECD/EU Country Cancer Profile Finland 2025, p. 3.
- Education: lung cancer incidence more than double among the least educated (OECD/EU 2025, p. 5); higher education goes with more lung cancer surgery (women OR 1.48, men OR 1.18) and income shows similar patterns (Zai et al. 2025, MPIDR WP 2025-016, doi:10.4054/MPIDR-WP-2025-016).
- Eastern Finland: most life years lost to premature death among men in Kainuu, Kymenlaakso, Etelä-Savo and Pohjois-Karjala; low income more common in Eastern and Northern Finland. THL press release 13.9.2022, all causes, 2017-2019. Note: cancer incidence is actually lowest in Etelä-Savo (women) and Pohjois-Savo (men) (OECD/EU 2025), and we found no published county-level cancer waiting times.

## Document zoom (`?doc`, and 0:31-0:46 in `?show`)

Zooms into one pink patient at "Back to GP" and opens her synthetic note. The note reader flags three spans (weight loss = red flag, "Visit 3" + "post-viral" = anchoring, a negative X-ray = check). The decision model panel shows:

- Next test: chest X-ray finds 77-80% of lung cancers (Bradley et al. 2019 systematic review; shown as 77%); direct CT 97% (simulator assumption, no direct source).
- Central tumour, which biopsy: bronchoscopy 94% diagnostic in about 14 days vs needle biopsy 68% in about 22 days, measured in our simulator (161 + 150 synthetic exploration cases, runs/model_in_loop.json on overnight/sim).
- Route stamp: fast lane, urgent CT; a clinician confirms every step.

The note reader and decision model are prototypes; the on-screen footer says so.

## Fast lane vs regular route, and the slow-motion popup

- In the simulator, the optimiser's change gives priority to every suspected-cancer referral once the hospital has handled it, and it helped all 466 treated patients (by 14 days or more; median 23). To show both routes, the right panel draws on the fast lane the 271 patients whose priority moved them ahead by 21+ days (`FAST_GAIN` in flow.js) and the other 195 on the regular route. All counters and percentages are unchanged simulator results.
- In `?show`, 0:31-0:46 is slow motion (0.15 days per second). A full-page popup grows out of one ringed patient on the right (a vague-symptom patient on the fast lane whose referral is handled around day 57) and shows her referral note being read (the document scene). After the popup the clock fast-forwards so that day 120 still lands on the drop.

## Light theme and evidence pictures (current version)

- Theme follows the National Cancer Strategy cover: cream background (#efebe2), dark grey text, honey-yellow accents (#e8c56a), Inter font. Magenta = vague symptoms, dark grey = alarm symptoms, green = treated within 90 days, blue = fast lane.
- The flow scene shows only our solution's flowchart (right). Today's pathway is shown as grey markers on the group bars and in the median ("today 103"). The left half holds the strategy cover (Goal 3) and three article cards (Bradley 2019, Stokstad 2019, Zai 2025), plus the cycling "Who falls behind" facts. See "Sources checked" below.
- Pictures live in `img/`. `scanner.webp` and `accountable.png` are git-ignored (unclear licence); copy them in locally. Strategy PDF: https://valtioneuvosto.fi/documents/1271139/1329769/Kansallinen_syopastrategia_2026_2035.pdf

## Sources checked (14 Nov)

| Claim on screen | Source | How checked |
|---|---|---|
| Chest X-ray finds 77-80% of lung cancers in symptomatic patients | Bradley SH, Abraham S, Callister MEJ, et al. Br J Gen Pract 2019;69(689):e827-e835, doi:10.3399/bjgp19X706853 | PMC abstract (PMC6805164): 76.8% and 79.3% in primary care, 79.7% in secondary care |
| 40% treated within 42 days → 80% with the reordered pathway (model estimate) | Stokstad T, et al. BMC Health Serv Res 2019;19:679, doi:10.1186/s12913-019-4517-z | Team's full-text read (params/sources.yaml on overnight/sim); 80% CI 72-87% |
| Lung cancer surgery OR 1.48 (women, high vs low education), similar by income | Zai X, Li P, Dei Bardi L, et al. MPIDR WP 2025-016, doi:10.4054/MPIDR-WP-2025-016 | Full text read (p. 8) |
| 123 vs 207 days, DLBCL, occupational/private vs public route | Kuitunen et al. Cancer Medicine 2026;15:e71920 | AstraZeneca briefing slide (rendered table) |
| Goal 3 "Varmistetaan yhdenvertainen ja vaikuttava syövänhoito"; indicator 3.1 "Potilaat pääsevät hoitoon tavoiteaikojen puitteissa" | Kansallinen syöpästrategia 2026-2035, Sosiaali- ja terveysministeriö | Full PDF read (14 Nov): Goal 3 title p. 32; indicator under 3.1 p. 33; p. 33 also says the lack of national coordination "ylläpitää alueellista eriarvoisuutta"; responsible for 3.1: FICAN, national cancer groups, Duodecim, STM, Palko (p. 34) |
| CT finds 97% | none | Simulator assumption; labelled as such |

Changed: the earlier 75% X-ray figure (Bradley et al. 2021, 86/114) could not be checked (PubMed and BJGP pages did not load), so the video and the note reader now use the 2019 systematic review. The simulator itself still uses 0.754.

## Greyscale version (current)

Everything drawn on the canvas is greyscale (CSS `filter: grayscale(1)` on the canvas); only the page background keeps a faint warm white (#fdfcf8). Grey levels: vague symptoms black, alarm symptoms mid grey, treated later light grey; the fast lane is a dashed line and its balls a darker grey.

## Simpler version with ink (current)

- Strategy picture and article cards are off (`SHOW_DOCS = false` in flow.js); their sources stay in the "Sources checked" table. The flowchart is centred; the clock is top left; the "Who falls behind" facts stay in a small box on the left.
- Old-printer ink: an SVG filter (`#ink` in index.html) roughens edges with noise, spreads the ink slightly (dilate) and softens it (blur), before the greyscale filter. Tune `scale`, `radius` and `stdDeviation` there.
