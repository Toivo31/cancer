# Demo page moodboard (for ElevenLabs)

The look of the working demo dashboard (`demo/index.html`): a calm night-shift control room where the numbers are the picture.
Live version: https://claude.ai/artifact/9aW6uHLcy8C2h3rcUckTQ2
Screenshots in `images/` were taken 14 Nov 2026; colour values are read from the page's stylesheet.

## Colour
Almost everything is night. Colour appears only where it carries meaning. Roughly nine parts dark neutrals to one part accent, on numbers, bars and outlines, never as large flat fills behind text.

| Name | Hex | Role |
|---|---|---|
| Night | `#0A0F14` | Page ground, under the grid and scan lines |
| Panel | `#111A24` to `#16222F` | Cards, fading slightly from top to bottom |
| Hairline | `#2C3F52` | Every border and divider, one pixel |
| Text | `#EAF1F8` | Headlines and key figures |
| Muted | `#A8B8C9` | Labels, captions, body copy |
| Coral | `#FF9A7A` | Today, the observed pathway, the before |
| Mint | `#55E3B0` | After the change, good results, section eyebrows |
| Amber | `#FFC04D` | Waiting: booking time and queues |
| Blue | `#62B0FF` | Being served, links, the blueprint grid |

**The colour rule:** coral is today, mint is after the change, amber is waiting, blue is being served. A colour never changes its meaning from one screen to the next.

## Type
- **Numerals:** system monospace (SF Mono or Menlo on a Mac), weight 800, tight tracking (-0.04em), the percent sign at 38% size.
- **Headlines and body:** system sans, bold at about 1.08 line height, slightly negative tracking. Body in muted blue-grey.
- **Labels:** monospace, uppercase, wide tracking (0.12 to 0.2em), small. Section eyebrows in mint with a number.

## Surface and texture
- **Blueprint grid:** 48px square grid, blue lines at about 5% opacity.
- **Scan lines:** horizontal dark lines every few pixels (about 10% black) over everything.
- **Panels:** 4px radius, 1px hairline, slight top-to-bottom gradient, mint tick marks at two opposite corners.
- **Bars:** flat colour with a fine horizontal stripe, square ends, no gradients or shadows.
- **Badges:** small outlined mono uppercase tags, mint for SOURCED, amber for ASSUMPTION.

## The six screens

| Screenshot | What to borrow |
|---|---|
| [01 · Headline](images/01-headline.png) | Two giant mono numbers with an arrow between them, coral before and mint after, with a small outlined delta chip. One finding and nothing competing with it. |
| [02 · Where time is lost](images/02-where-time-is-lost.png) | Stacked horizontal bars: amber for waiting, blue for being served, today above after. The stage with the most waiting gets a thin amber outline. |
| [03 · Why these changes](images/03-why-these-changes.png) | A staircase of bars rising from coral through blue to mint, with the big mono value over each bar. Evidence cards use a mint step number and tiny mono sub-labels. |
| [04 · Capacity or order](images/04-capacity-or-order.png) | Plain horizontal bars on a quiet panel. Labels right-aligned in sans, values in mono beside each bar. Coral today, amber more capacity, mint the suggested change. |
| [05 · Before and after](images/05-before-and-after.png) | The flowchart as dark rounded boxes joined by pale hairline arrows. Only the steps the change touches get a mint outline and a green-tinted fill. |
| [06 · Who waits longest](images/06-who-waits-longest.png) | Data as calm rows: mono values, underlined blue source links, outlined badges. Transparency is part of the look. |

## Composition and tone
**Lean into:** left-aligned sentence headlines that state the result; number, arrow, number (today left, after right); generous dark space in a few hairline panels; flowcharts as dark rounded boxes with pale thin arrows; small outlined mono status badges; plain, factual, slightly dry language.

**Steer away from:** white or pastel backgrounds, glossy gradients, drop shadows; stock photography and hospital clichés; emoji, rounded pill buttons, playful illustration; old computers, CRT monitors or terminal windows (the scan lines are a texture, not a screen); rainbow palettes; anything that points at clinicians, because the subject is the queue.

**Note for the trailer.** The trailer script describes cream and paper tones with film grain for its opening beats. The product screens are the dark look on this board. When the trailer cuts to the product (flowchart, architecture and results beats), match this board.
