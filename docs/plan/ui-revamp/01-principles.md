# Principles, and what each one changes here

**In one line:** two kinds of screen need two rule sets. Info pages follow the inverted pyramid. The simulator
follows "overview first, details on demand". Both follow one visual hierarchy and spend colour only where it means something.

| Principle | Source | What it changes in our app |
|---|---|---|
| **Inverted pyramid** (conclusion first, then support, then background) | journalism; Nielsen Norman Group on web writing | Every info page opens with one sentence plus one infographic that is enough on its own. Methods, ranges, caveats, commands and file paths go below a visible "Details" rule. Today the start page puts 1,340 words above and around six buttons |
| **F-pattern / layer-cake scanning** (people read headings and the first words of lines) | NN/g eyetracking studies | Headings say the finding ("Reordering beats a faster scanner in all 184 settings"), not the topic ("Why we trust the engine"). Paragraphs start with the point |
| **Overview first, zoom and filter, details on demand** | Shneiderman's visual information-seeking mantra (1996) | Simulator default: the whole graph, the day, three numbers. The patient trace, per-step time lost, layers, the Norway table and counters each sit one click away. Today all of them are open at once beside the graph |
| **Progressive disclosure** | Nielsen; Apple HIG | One "Details" menu in the simulator instead of 14 controls in the header and footer. In the React app, one Optimise entry instead of two (toolbar button and side tab) |
| **Visual hierarchy: one primary action per screen** | Gestalt; Material/HIG "primary button" | Simulator: Optimise is the only filled button. Overview: the only filled button is "Open the simulator" |
| **Data-ink ratio, no chartjunk** | Tufte, *The Visual Display of Quantitative Information* | Charts: no background grids (today the pages draw a blue grid on every page body), direct labels instead of legends, thin range bars, grey for "today" and ink for "after". Colour only for the one thing the chart is about |
| **Pre-attentive attributes used sparingly** | Ware, *Information Visualization*; Healey | If colour is rare, a mustard node pops without explanation. That only works when nothing else on screen is coloured. Today mint, coral, amber, blue and red all compete |
| **Recognition rather than recall; consistency and standards** | Nielsen's heuristics 6 and 4 | One nav bar with the same five items on every page; the same word for the same thing everywhere ("today" / "after the change", never "left/right", "baseline", "observed" and "before" for one idea) |
| **Visibility of system status** | Nielsen heuristic 1 | The day counter is large; play/pause state is unambiguous; "saved example" / "live" / "saved optimiser run" are stamped on what they label |
| **Match between system and the real world** | Nielsen heuristic 2; master plan section 8 "plain words" | No "node", "variant", "pp", "layer" in default views. "Step", "pathway", "points" |
| **Aesthetic and minimalist design** | Nielsen heuristic 8 | Each sentence on a default view has to earn its place against the three numbers. The honesty text does not disappear; it moves to a fixed short strip plus the details section |
| **Accessible contrast and non-colour cues** | WCAG 2.1 AA (4.5:1 text, 3:1 large text and UI parts) | Palette checked in 05-theme.md. Queue state also shown as border weight and a "24 waiting" label, not by colour alone. Light-grey graph labels as in the video fail AA, so labels use the darker muted ink |
| **Explorable explanation** | Bret Victor; "Explorable Explanations" | The patients page lets the reader hide and reveal one patient's truth, instead of describing it in prose |

What these principles do **not** decide: which numbers count as the result. Those come from
`docs/pitch/filled/numbers_sheet.md` and the bundles. The UI only chooses where they sit and how big they are.
