# Spec 04: Web app

Milestones M3 (run), M4 (optimise), M5 (build), M6 (data). Depends on spec 03's API description.
Open fork: F4 (stack).

## Purpose

The browser face of the loop: build, attach JEV, run, optimise, rerun. Plain words in everything
visible, as in the current dashboard: "step", "decision", "suggested change", never "node",
"optimiser" or "policy".

## Stack (lean, fork F4)

- `web/`: Vite + React + TypeScript.
- Graph canvas: React Flow (`@xyflow/react`), layout by `dagre` (left to right, parallel steps
  stacked).
- API types generated from the service's OpenAPI description.
- Built files are served by the service at `/`; in development Vite proxies `/api`.
- Results: the existing `demo/index.html` dashboard is embedded and pointed at
  `/api/projects/{p}/runs/{r}/bundle` (it needs one small change: accept a `?bundle=` address).
  Native charts replace it screen by screen later, if at all.

The alternative, a no-build page like the current dashboard, keeps the offline property but means
writing drag, connect, pan, zoom and undo by hand.

## Screens

### 1. Projects
List, "new from template" (Norway check, Finnish scenario), "blank" (M5). One project holds one
world, its flowcharts, runs, datasets and models.

### 2. Flowchart
Left: palette. Centre: canvas. Right: properties of the selected step or connection. Bottom:
problems.

| Element | M3 (read-only) | M5 (editor) |
|---|---|---|
| Canvas | Graph of the selected version, auto-layout, pan and zoom; step kinds and stages styled; decisions highlighted | Drag from palette, move, delete, connect; connection type chosen on the line (required / any of / only if it ran); undo and redo |
| Properties | Shown, not editable | Label, what happens (from the world's catalogue), stage, condition builder, retry, fast track |
| Decisions | Options and current probabilities shown on the node | Add and remove options, availability |
| Problems | – | Live problem list from `/validate`; clicking a problem selects the step |
| Versions | Version picker | "Save as new version"; versions that have runs are locked |

Condition builder (M5): rows of "result of [step] is [positive / negative / inconclusive]",
"[attribute] is [value]", "group is", "age at least", joined by all / any. An "advanced" text field
shows the generated expression.

### 3. Decisions (JEV)
One row per decision point, one column per option.

- Stub: editable probabilities that must sum to 100; "add a condition" opens a rule
  ("when tumour location is central: …"). This is the "hardcoded probabilities" editor, and the
  first editable thing in M3.
- Source selector per decision point or for all: hardcoded, JEV API (address and model), trained
  model from this project (M6).
- "Sample or most likely" switch (fork F2).
- "Try it": fill in a patient context, see the probabilities the current source returns.
- Shows where a run fell back to the stub because the API failed.

### 4. Run
Patients, seeds, which flowchart version, which decision source. Start, progress bar, cancel.
History table (label, version, on-time share, median days, missed cancers, when). Selecting a run
opens the results view. Selecting two opens the comparison: headline deltas, by-group table, and a
refusal with an explanation if the runs used different patients.

### 5. Optimise (M4, spec 05)
Settings (which kinds of change are allowed, safety checks). Start, progress by step.
Result: list of suggested changes, each with what the records said, what the rerun confirmed and a
switch to accept it; a second list of changes that were faster but blocked by a safety check, with
the reason. Graph diff: before and after side by side with changed connections highlighted.
"Apply and rerun" creates the new version, runs it on unseen patients and opens the comparison.

### 6. World (M5)
Three tables: who arrives (conditions, shares, groups), what can be done (tests: accuracy, time,
cost, invasive), what is scarce (resources: slots per day, booking time). Every number shows a
source chip or "assumption", from the same fields the YAML already carries.

### 7. Data and training (M6, spec 06)
Upload or "use the decisions from run X". Validation report. Train. Model list with evaluation.
"Use this model at these decisions".

## Build order

M3, thin first:
1. Scaffold, build, served by the service (M3-1); generated API client (M3-2).
2. Projects and templates (M3-3).
3. Read-only graph (M3-4).
4. Decisions table with editable stub probabilities; saving creates a new version (M3-5).
5. Run panel and history (M3-6); embedded results (M3-7); compare (M3-8).

M4: optimise panel, suggestions, diff, apply and rerun.
M5: editor, properties, condition builder, world tables, import and export.

## Checks

- A scripted browser pass (headless Chrome, as used for the dashboard): open template, change one
  probability, run with small `n`, wait for results, screenshot each screen (M3-9).
- The editor never lets the user save a version with errors; warnings are allowed.
- Works at 1920×1080 for the projector and at laptop width.

## Out of scope

Collaboration, comments, mobile layout, translations.
