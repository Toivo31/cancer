# Lane handoff files

Each UI lane writes **one file here**, `docs/plan/ui-revamp/handoff/<lane>.md` (for example `L1-simulator.md`; L0's is
`L0.md`), on its own branch, before it posts RELEASE. A lane without a filled handoff file is not merged. The
integrator assembles `docs/plan/ui-revamp/HANDOFF.md` from these files at the end; lanes do not edit that file or
another lane's file.

How to fill it:

1. Copy the template below (it is the one in [../08-pause-and-handoff.md](../08-pause-and-handoff.md), section 4).
2. Be specific under **Removed**, **Renamed or moved** and **Do not recreate**: name the class, element id, URL
   parameter, section or bundle field. Later agents grep their diffs against these lists.
3. Nothing is deleted silently: text that left the top of a page says where it went (below DETAILS, or the doc it
   came from).
4. Put presenter lines (what to click, what to say) under **Presenter notes**; the integrator moves them into
   `docs/demo_path.md`.
5. Screenshots: run `scripts/ui_shots.sh /tmp/ui_shots/<lane> <url-list>` and give the path and the console result.

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
Short bullets a later agent can check a diff against.

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
Lines the integrator should put into docs/demo_path.md.

## Open issues and judgement calls
Design calls made and why; what Tuomas should look at; known rough edges.
```
