# WP-W7: web app (graph diff, editor, layout, polish)

Lane `w7/web`. Files: `web/src/**` only; no service change, no new dependency.

## 1. Run highlight after a save (bug)
Cause: the run named in the address (`run=`) was kept when a version was saved or switched, so the run list highlighted a run of the
older version. Fix: `lib/runSelect.ts` `effectiveRun` only accepts a requested run that belongs to the shown flowchart and version,
otherwise the newest finished run of that version; saving and switching version also drop `run` from the address. Test: `runSelect.test.ts`.

## 2. Graph diff (M4-3)
`lib/graphDiff.ts` (diff of two versions: steps and connections added, removed, changed; decision probabilities; sentences),
`graph/DiffView.tsx` (two SVG drawings, one layout over the union of both versions so a step sits at the same place in both,
scroll and zoom shared, unchanged parts dimmed, changes coloured, a word list underneath), `screens/DiffDialog.tsx` (overlay, loads both versions).
Offered in two places: "Compare with..." in the bar above the canvas (any two versions of a flowchart) and "Show what changed" in the
Optimise result after applying changes (before and after). Tests: `graphDiff.test.ts`, `DiffView.test.tsx`, `OptimisePanel.test.tsx`.

## 3. Editor
Add a step (step, join or end point; connected after the selected step if wanted), delete a step with its connections (confirmation inside
the app), undo and redo (buttons, Ctrl/Cmd+Z, Shift for redo; typing in one field is one undo step), decision options added and removed in
the same panel (a new option starts at 0%, removing one rescales the others; shares are set in the Decisions table). The validator keeps
running (debounced) and Save is blocked while there are errors, while a check is running, and while the check result is older than the
document. A step without connections gets a local warning (the service does not flag it). Pure edits in `lib/graphEdit.ts`, history in
`lib/history.ts`. Tests: `graphEdit.test.ts`, `history.test.ts`, `EditPanel.test.tsx`.

## 4. Layout readability
`graph/layout.ts` now builds many candidates (dagre ranker, spacing, each row laid out on its own or the whole drawing at once, one to five
rows) and keeps the best by `scale / (1 + crossings / 12)` on a 1100 x 700 canvas (`LAPTOP_CANVAS`); results are cached.
`graph/layoutScore.ts`: crossing counter, lane assignment for connections that skip between rows (fewest crossings in each channel),
edge label placement clear of boxes and other labels. Lanes are 4 px apart (up to 10). The canvas leaves room for the legend at the bottom.
Stored user layouts: positions are stamped with `LAYOUT_VERSION`; a view saved on an older automatic layout keeps its box sizes and drops
positions (they referred to a grid that no longer exists), see `viewLayout.ts`. Tests: threshold on a 1240 x 700 canvas raised from 0.45
to 0.5 (worst template now 0.53), at most 16 crossings per template, every option percentage has a place, lane limits, versioned storage.

| template (1440 x 900, panel open) | scale before | scale after | crossings before | after |
|---|---|---|---|---|
| norway observed | 0.49 | 0.53 | 28 | 15 |
| finland direct_ct | 0.48 | 0.55 | 14 | 15 |
| finland baseline | 0.67 | 0.74 | 3 | 3 |

Layout takes a few hundred ms for the largest template (more under the shared CPUs tonight); the cache and a size-only dependency
(not every typed letter) keep editing smooth.

## 5. Polish (done) and list of what remains
Done: Optimise button on the canvas (and the side tab stays), hint when a version has no run, error pages with Try again, an error banner
instead of silent failures, loading texts, inline (not browser) confirmation for deleting a project, keyboard: Tab to a step and Enter or
Space selects it, focus rings, Space on run rows, long project and flowchart names truncate, the disabled "Report" tab is hidden.
Left: the first fit is still small text for the biggest graphs (zoom with the controls); the optimise tab has no inline diff preview of a
single suggestion before applying; mock API answers "needs the real service" for the optimiser; no automated browser test in `npm test`;
drag-to-create connections and a condition builder (M5) are not built.

## Verification
Browser (headless Chrome, 1440 x 900, own seeded service on port 8077): `/tmp/w7shots/` (not committed):
`diff-dialog.png` (v1 against v2), `edit-confirm-delete.png`, `edit-added-unconnected.png`, `edit-after-redo.png`, `save-before.png`,
`save-after.png` (no highlighted older run after saving), `norway-before.png`, `norway-after.png`, `norway-opt-after.png`,
`finland-directct-after.png`, `polish-no-run.png`, `polish-optimise-keyboard.png`, `polish-error.png`, `polish-projects-confirm.png`.
Scripts: `diff.mjs`, `edit.mjs`, `save.mjs`, `norway.mjs`, `polish.mjs` in the same folder.

## Service changes wanted
None required. Nice to have: the validator could warn about a step with no connections (the web warns locally).
