# Theme: 80s paper, ink, and two broken colours

**In one line:** warm off-white paper, near-black ink, greys for nearly everything. Mustard and brick appear
only where patients wait or something goes wrong. Inter (caps for headings) and Courier Prime (labels, stamps,
commands), both vendored for offline use. One tokens file per surface.

## Where it comes from

| Source | What it shows |
|---|---|
| Reference frames (`reference/01`–`06`) | Off-white background (around `#f8f8f6`), near-black text; bold grotesque caps headings ("EQUAL CARE PATHWAYS", "1 DEFINE"); grey body; white cards with a 1 px dark outline and generous padding; pale grey inset panels; a rotated outlined stamp; a small black terminal chip (`> read referral note --patient 214_`); a typewriter title on black; pathway as thin grey lines with black/grey dot piles and light-grey labels; a big `DAY 021`; almost no colour |
| Video code `video/dots/index.html` | `--bg #fbf9ef; --ink #2d2d2a; --dim #6b6b66; --hot #c87d00; --ok #1e8755; --honey #e8c56a`; fonts Inter and Courier Prime (`show.js`, `zoom.js`); red `#ff3b2f` only for the "87 DAYS" wait |
| `live_demo/` (Eemeli) | `--bg #fdfcf8; --ink #1f1f1d; --dim #6b6a65; --line #dcd9d0; --card #fff`; Inter; canvas forced greyscale |
| Tuomas | Clean, white, minimal; a little retro and paper-like with a slight yellow tint ("80s paper"); broken colours used rarely, maybe brown and mustard; "Walter White: old, outdated, not saying much" |

The proposal sits between the video's `#fbf9ef` (yellow) and the frames' `#f8f8f6` (neutral), a little warmer than
both, as he asked. The accents are the video's own honey/ochre, broken (greyed) a step further.

## Palette (contrast measured, WCAG 2.1)

| Token | Hex | Use | Contrast on paper / card / inset |
|---|---|---|---|
| `--paper` | `#F4F0E4` | page background | |
| `--card` | `#FBF9F2` | cards, graph steps, drawers | |
| `--inset` | `#EAE5D6` | inset panels (the grey boxes inside the video's cards), code | |
| `--ink` | `#1E1D1A` | headings, numbers, card outlines, the primary button, "after" series | 14.8 / 16.0 / 13.4 |
| `--ink-2` | `#4F4B43` | body text | 7.6 / 8.2 / 6.9 |
| `--ink-3` | `#67625A` | secondary text, graph labels, captions | 5.3 / 5.7 / 4.8 |
| `--faint` | `#9C978C` | waiting dots, "today" series, decorative rules; **never text** | 2.6 / 2.8 / 2.3 |
| `--line` | `#CDC7B6` | hairlines, graph edges | 1.5 (decorative only) |
| `--mustard` | `#B8902F` | queue "building" outline, markers, the change highlight; not for text | 2.6 / 2.8 (3:1 not met; always paired with ink text or a 2 px outline) |
| `--mustard-ink` | `#7E5E12` | mustard text ("18 waiting") | 5.3 / 5.7 / 4.8 |
| `--mustard-tint` | `#F1E4BD` | queue "building" fill | ink on it 13.3 |
| `--brick` | `#9E3B2A` | queue "piled up", cancer missed, harm; text allowed | 5.9 / 6.4 / 5.4 |
| `--brick-tint` | `#E8CFC4` | queue "piled up" fill | ink on it 11.4 |
| `--brown` | `#6A4B30` | links and the rare second accent (e.g. the published-value ring in Evidence charts) | 6.9 / 7.5 / 6.3 |
| `--carbon` | `#161512` | the one dark element: terminal/command chips, a possible title card | card text on it 17.3 |

Rules: at most one accent per view besides ink; mustard and brick mean "waiting" and "wrong", never decoration;
"today" is grey and "after" is ink (as `live_demo` already does); no green anywhere (the video's `#1e8755` is the one
thing left out; "good" is simply ink). Mustard vs brick differ in lightness (2.3:1), so they stay apart for
red-green colour blindness, and the outline weight and "N waiting" text carry the meaning anyway.
The frames' very light graph labels fall below AA. The site uses `--ink-3` for labels; `--faint` stays for dots and lines.

Paper alternatives (D61 chose #F4F0E4): neutral like the frames `#F8F7F2`; video `#FBF9EF`; proposed `#F4F0E4`; stronger "80s"
`#EFE9D8` (ink-3 still 4.9:1 on it). The rest of the palette works on all four.

## Type

| Role | Face | Size / weight | Notes |
|---|---|---|---|
| Page title | Inter | 40 / 700, CAPS, tracking +0.01em | "EQUAL CARE PATHWAYS" |
| Section heading | Inter | 20 / 700, CAPS | "1 SIMULATE" |
| Finding heading (below DETAILS) | Inter | 18 / 600, sentence case | headings are sentences there |
| Body | Inter | 16 / 400, line-height 1.55, max 64ch, `--ink-2` | |
| Big numbers, `DAY 021` | Inter | 56–72 / 700, `font-variant-numeric: tabular-nums` | numbers stay in Inter, as in the video's DAY counter |
| Labels, eyebrows, legend, stamps, captions | Courier Prime | 12–13 / 400–700, CAPS for labels, tracking +0.06em | the typewriter |
| Commands, file paths | Courier Prime on `--carbon` | 13 | the terminal chip |

Fallback stacks (no network): `"Inter", "Helvetica Neue", Helvetica, Arial, system-ui, sans-serif` and
`"Courier Prime", "Courier New", Courier, monospace`. Vendor the fonts as `woff2` with `OFL.txt` (SIL Open Font
License 1.1 allows that): Inter 400/600/700 (or the variable file) and Courier Prime 400/700, about 0.4 MB in all,
under `demo/fonts/` and `web/public/fonts/`. Use `@font-face` with `local()` first and `font-display: swap`. If they
cannot be downloaded tonight, the stacks above still give the look (Helvetica/Arial + Courier New).

## Spacing, shape, elevation

- 4-px base scale: 4, 8, 12, 16, 24, 32, 48, 64, 96. Card padding 24–32; gap between top-of-page blocks 48; page
  side margin 64 at 1440.
- Cards: `--card` fill, 1 px `--ink` outline, radius 0 (at most 2), no shadow. Inset panels: `--inset`, no outline.
- Buttons: primary = `--ink` fill, `--card` text, Inter 600 caps 13; secondary = 1 px `--ink` outline; tertiary = text
  link in `--brown`. One primary per view.
- Stamp: Courier Prime 700 caps 12, 1.5 px outline, rotated −2°, ink or brick. Uses: "SYNTHETIC PATIENTS",
  "PREDICTED, NOT FITTED", "SAVED EXAMPLE" / "LIVE", "SAVED OPTIMISER RUN". Never "CLINICIAN-VALIDATED".
- No background grid, no gradients, no glow, no scanlines.

## Charts

- Data-ink first: no gridlines (or `--line` hairlines at round values only), no chart borders, axis labels in
  Courier Prime 12 `--ink-3`, direct labels at line ends instead of legends.
- Series: today/before = `--faint`; after/ours = `--ink`; published value = hollow `--brown` ring; range = 1.5 px
  `--ink` bar with end ticks; harm = `--brick`. At most one accent per chart.
- Graph (simulator): edges `--line`, width by patient count (as now); steps `--card` with a 1 px `--ink-3` outline;
  decision steps rounded; labels `--ink-3` 12 px Inter; the change highlight mustard.

## Applying it: tokens, one file per surface

| Surface | Tokens file | What reads it |
|---|---|---|
| `demo/` pages | **new `demo/theme.css`**: `@font-face`, `:root` tokens, base type, `.card .inset .stamp .chip .btn .num .nav` | every `demo/*.html` links it first; page CSS keeps layout only |
| `demo/*.js` canvas/SVG colours | same tokens, read once at start: `const C = tokens()` via `getComputedStyle(document.documentElement)` | replaces the literal `C = {...}` in `flow.js` (line 7) and the literals in `encounter.js` |
| `web/` | **new `web/src/theme.css`** (same names) imported by `styles.css`; `web/src/theme.ts` exports the values for TSX | replaces the 41 literals in `FlowCanvas.tsx`, `DiffView.tsx`, `layers.ts`, `PlaybackLayer.tsx` |
| `live_demo/` | Eemeli's; offer him `demo/theme.css` | |

Migration trick: `theme.css` also defines the **old variable names** as aliases (`--night: var(--paper)` (the old pages use `--night` as their background, so the new dark token is called `--carbon`),
`--text: var(--ink)`, `--mint: var(--ink)`, `--amber: var(--mustard)`, `--coral: var(--faint)`, `--red: var(--brick)`,
`--blue: var(--ink-2)`, and `--line` simply redefined …). It loads *after* each page's own `:root`. A page then changes theme by
adding one `<link>` and deleting its background-grid rule. A deeper clean-up (removing the per-page copies)
can come after the submission. `?theme=night` swaps the alias block back to the old values for a fallback during the night.

After the submission, generate both tokens files from one `design/tokens.json` with a ten-line script, so one file
changes the theme everywhere.
