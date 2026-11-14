# Simulation moodboard (for ElevenLabs)

The look of the dots animation in `video/dots/` (on `main`): one dot is one simulated patient on a black stage, piles grow where patients wait, and a single moment where the piles dissolve.
Image: [`simulation-moodboard.png`](simulation-moodboard.png) (1600 px wide). Source page: `source.html` (open it in a browser from this folder). The seven frames in `images/` were rendered from the animation on 14 Nov 2026 at 1920x1080.

## Colour
About 95 percent black. Colour only on dots, piles and a few numerals. One meaning per colour.

| Name | Hex | Role |
|---|---|---|
| Ink | `#050607` | The stage |
| Paper | `#e9efe6` | Dots in a queue, labels, numerals |
| Dim | `#7d877c` | Captions, axes, hairlines |
| Amber | `#ffb347` | Waiting; piles glow amber the longer they wait |
| Mint | `#b8ffcf` | Treated within the target |
| Pink | `#f373b5` | Vague symptoms |
| Cyan | `#96ebff` | The fast lane, our change |
| Red | `#f24239` | Cancer missed, sent home |
| Grey | `#3a3f3c` | Treated later than the target |

Ink, paper, dim, amber and mint are read from the page source; pink, cyan, red and grey are sampled from the rendered frames.

## Type
Giant monospaced numerals for the percentages and the day counter (the source sets them in DotGothic16), tracked monospaced capitals for the stage labels (DETECTION, REFERRAL, DIAGNOSIS, TREATMENT START), small dim Courier Prime for captions. The frames here show the fallback monospace because the web fonts did not load when they were rendered.

## Motion grammar
- **Dots:** every dot is a simulated patient, the same cohort in every view. They travel left to right through the four stages (or climb a flowchart), and treated patients land on the right as a mint block.
- **Piles:** a slow step collects dots into a pile; piles grow while time runs and turn amber the longer patients wait.
- **The drop:** one keypress applies the change to the same patients on the same day; the piles dissolve and the dots flow through.

## Frames
1. `01-day30-pile-appears.png`: day 30, today's pathway, the tall amber column at detection.
2. `02-day100-by-symptoms.png`: day 100, coloured by symptom group.
3. `03-day100-today-vs-change.png`: day 100, today (17%) against the animation's fast-track variant (61%). **Caution:** in the current demo bundle the 61% is the conditional urgent-booking scenario, which depends on assumed booking times; the Finnish headline is 18% to 33% (reorder only). Re-export `video/dots/dots_data.js` before using it as a result.
4. `04-norway-check.png`: the Norwegian pathway (Stokstad et al. 2019), partway through the run.
5. `05-flow-swarm.png` and 6. `06-flow-today-vs-solution.png`: the flowchart scene. The "our solution" side (53%, 79%, median 80 days) rests on assumed fast-lane booking times.
7. `07-patient-race.png`: eight patients as large dots moving through the named steps.

## Lean into / steer away from
Lean into: black stage and round dots, time as distance and pile height, one number per moment, today beside the change with the same patients, sparse monospaced labels, amber glow only where someone waits.
Steer away from: faces and hospital stock imagery, bright backgrounds, gradients, glossy 3D, old computers or terminal windows, rainbow palettes, anything that blames clinicians, neural-network cliches.

The trailer moves from the film world (see `../video-mood-board/`) to this look when the solution explanation starts.
