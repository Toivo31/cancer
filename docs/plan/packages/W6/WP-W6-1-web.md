# WP-W6-1: web app fixes, optimise loop, minimal editor

Lane `w6/web`. Files: `web/src/**` only (no service changes, no new dependencies).

## 1. Dots travelling off the drawn connections

Cause. `preparePatients` sorted the segments of all of a patient's visits by start time across nodes. Steps that run in
parallel have overlapping recorded times, so segments of two steps interleaved (for example second_look wait,
gp_referral wait, second_look served). `stateAt` took "the previous different node in the list" as where the dot comes
from, so a dot could be sent from a later step back to an earlier one (gp_referral to second_look) and, where no directed
path exists, `PlaybackLayer.routeBetween` fell back to a straight line between the boxes. On the seeded Finnish baseline run
that was 4 of 837 distinct transitions before the fix; the sampled run of the team lead shows more.

Fix. Visits are laid out in chain order with times that never go backwards (`playback.ts`), so "from" is always the step the
patient really came from. When no path exists in the drawn graph (it can happen for a pair like bronchoscopy to needle biopsy),
the dot fades out at the old step and in at the new one (`fadeAlpha`) instead of flying across. The route is always the
shortest path over drawn connections of every type, dotted ones included. Tests: `playback.test.ts` (overlapping visits never
produce a transition without a path; fade).

## 2. Moving and resizing boxes

- Boxes can be dragged outside edit mode. Positions and sizes are a view-only layout in `localStorage`
  (`pathway:view-layout:<project>/<flowchart>`, in try/catch), "Reset layout" clears it. `graph/viewLayout.ts` (+ test).
- Edges that touch a moved step are drawn directly; dots follow because the playback layer receives the live boxes and routes.
- Box height now follows the label (`nodeSize`/`wrapLines` in `layout.ts`, wraps to 2 to 3+ lines); the text clamp is removed.
  The "fits a laptop canvas" layout test threshold went from 0.5 to 0.45 because taller boxes make the Norway layouts a little larger.
- A selected box can be resized (React Flow `NodeResizer`, rendered outside the clipped box so the handles are reachable).
- Tooltip shows the full label and the count line; the side panel already shows the full label and counts for a selected step.

## 3. Optimise loop (M4-1, M4-2, M4-4)

"Optimise" tab in the side panel (`screens/OptimisePanel.tsx`): patients and max changes, start, progress with cancel, earlier
searches, held-out before/after (on time, median days), the selection-optimism line and the honesty text, the suggested
changes with kind, records reading, predicted days saved, search-patient and unseen-patient numbers, linked changes tick
together (`lib/optimise.ts`), blocked changes, "Apply N as a new version and rerun" (subset via `accept`), progress of the two
held-out reruns, then a before/after table from `POST /compare` (headline plus on-time by group), and buttons to open the new
or old version with its run. API methods added to `api/client.ts`; the mock API answers "needs the real service".
Not done: the side-by-side graph diff (M4-3) and M4-5.

## 4. Minimal editor (M5-1 subset)

"Edit" button on the canvas: label, test (from the world's tests), guard, add or remove a non-option connection, live validator
problems (click to select the step), "Save as new version" blocked while there are errors. Decision options are left to the
Decisions table. No add/delete step, no drag-to-create, no undo.

## Screenshots (in /tmp, not committed)

`/tmp/w6shots/b-dragged.png`, `d-resized.png`, `h-opt-result.png`, `i-opt-compare.png`, `k-edit-invalid.png`, `l-edit-added.png`, `m-edit-saved.png`.
