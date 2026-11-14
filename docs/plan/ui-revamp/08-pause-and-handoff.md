# Pause protocol and handoff

**In one line:** before the revamp, freeze the data and every other lane at a tagged, gated, screenshotted commit.
During it, the UI lanes own `demo/` (and optionally `web/src/`). After it, one `HANDOFF.md` tells every resumed agent
what was removed, renamed or moved, and what it must not bring back. `CLAUDE.md` and the agent channel point to it.

## 1. Pause (the coordinator, about 20 minutes)

1. **Announce.** On the channel:
   `python scripts/comms.py post --as claude-code@tuomas/architect --type DECIDED "UI revamp starts <time>. All lanes pause: commit WIP on your own branch, do not merge, post RELEASE with branch and state. demo/, web/src/, docs/demo_path.md, README.md, demo/README.md are owned by the ui/* lanes until the HANDOFF post."`
2. **Decide per running lane.** Let it finish if it is within about 15 minutes of done **and** touches no file in the
   revamp's set (`demo/**`, `web/src/**`, `docs/demo_path.md`, `README.md`, `demo/README.md`, `tests/test_demo_*`). Merge it
   before the snapshot. Stop all others: WIP commit on their branch, unmerged, with a RELEASE note saying what is half done.
   Jobs that run outside the repo can continue but are not merged until after the handoff. Example: Gemini library
   generation on Tuomas's Mac.
3. **Refresh data once, then freeze it.** If any merged data lane changed results: `python demo/export_all.py`, then
   `python docs/pitch/fill_numbers.py`, commit. From here no bundle changes except L4's `start_bundle.js` (additive).
4. **Gate.** `scripts/gate.sh` (and `--slow` if there is time); save the summary lines.
5. **Snapshot.**
   - `git tag ui-revamp-base` on `overnight/sim`; push the tag.
   - Screenshots of the current pages: `scripts/ui_shots.sh` does not exist yet (L0 writes it), so use the commands in
     06-execution-plan.md WP2 acceptance, into `runs/ui_shots/base/` (or `/tmp` if `runs/` should stay clean). These are
     the "before" set and the visual fallback reference.
   - Record in `docs/plan/04-status.md`: base commit, gate summary, which lanes were paused at which branch/commit.
6. **Create `ui/main`** from the tag; start L0. Post a CLAIM listing the lanes and their owned files (the table in 07-parallel-lanes.md).

**Rollback point:** the tag `ui-revamp-base`. `overnight/sim` does not move during the revamp, except for an urgent
non-UI fix, which the integrator merges into `ui/main` too. At the end, `ui/main` goes into `overnight/sim` as one
`--no-ff` merge, so rolling back the whole revamp is `git revert -m 1 <that merge>`. Rolling back one lane is
reverting that lane's merge in `ui/main` before the final merge.

## 2. During the revamp

- Lanes post CLAIM at start, FYI when blocked, RELEASE when done (with branch, commit, and the path of their handoff file).
- The integrator answers blocks within minutes. A lane never edits another lane's files to unblock itself.
- If a number looks wrong on a page, the lane reports it and does not fix data. The integrator decides whether
  that is a post-revamp data task.

## 3. Handoff: the rule

Each UI lane fills in **its own file** `docs/plan/ui-revamp/handoff/<lane>.md` from the template below, in the same
branch as its work, before it posts RELEASE. A lane without a filled handoff file is not merged.

At the end, the integrator assembles **`docs/plan/ui-revamp/HANDOFF.md`**: a short summary at the top ("what the
site is now"), a combined "Do not recreate" list, then the lane files appended or linked. Then:
- `CLAUDE.md` (project context, under "Project context") gets one line:
  `- UI revamp (15 Nov): before touching demo/, web/src/ or the presenter script, read docs/plan/ui-revamp/HANDOFF.md, especially "Do not recreate".`
- Channel: `DECIDED` post "UI revamp merged at <commit>. Paused agents: merge overnight/sim into your branch, read docs/plan/ui-revamp/HANDOFF.md, check your diff against its Do-not-recreate list before you merge."
- `docs/plan/04-status.md` and one line in `docs/master_plan.md` section 8 (Clarity), per the CLAUDE.md rule that a
  changed decision is recorded there.

### What a resumed agent does (goes at the top of HANDOFF.md)

1. Merge `overnight/sim` into your branch. Expect conflicts only if you edited a file listed under "Owned by the revamp".
2. Read "Do not recreate" and "Renamed and moved".
3. Before merging, grep your diff for removed names (classes, URL parameters, element ids, page names) listed there.
4. New UI elements: use the tokens and shared classes in `demo/theme.css`; add a page to the nav only through `demo/site.js`; keep
   detail below the DETAILS rule; numbers bound from bundles.
5. If your work needs something the revamp removed, ask on the channel. Do not put it back on your own.

## 4. Template for a lane's handoff file

```markdown
# Handoff: <lane id and name>

Branch / merge commit: <ui/lN-…> / <sha>   Agent: <name>   Finished: <UTC time>

## Summary (3 lines)
What this page or area is now, in plain words.

## Removed
| What (page / section / element / URL parameter / CSS class / element id / bundle field / test) | Where it was | Why | Replacement, if any |
|---|---|---|---|

## Renamed or moved
| Old | New | Notes (for example "old URL still works and maps to …") |
|---|---|---|

## Added
| What | Where | Contract or page-local |
|---|---|---|

## Do not recreate
Short bullets a later agent can check a diff against. Example: "No counter row above the graph: counts live in
Details → Counts now." "No second Optimise button." "No colour outside the tokens."

## URL parameters
| Parameter | Still works? | Behaviour now |
|---|---|---|

## Data and bundles
Fields read, fields no longer read, any additive export change (L4 only), "none" otherwise.

## Tests
New tests; existing tests run and passing (names); anything skipped and why.

## Screenshots
Path of the 1440×900 and 1920×1080 set from scripts/ui_shots.sh; console errors: none / list.

## Presenter notes
Lines the integrator should put into docs/demo_path.md (what to click, what to say).

## Open issues and judgement calls
Design calls made and why; what Tuomas should look at; known rough edges.
```
