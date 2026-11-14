# UI revamp plan (start here)

**In one line:** one quiet paper-coloured site with five pages, and a simulator whose default view shows the
graph, a day counter, three numbers and one Optimise button. It is built by six page lanes in parallel on a shared
contract, with everything else paused, and closed with a handoff that paused agents read before resuming.

Status: plan only, merged into `overnight/sim` (21:40 UTC); no product code changed. Reviewed 21:45 UTC: ready once the pre-pause data steps in 08 section 1 are done (see "Before the pause" below).
Submission Sun 10:00 Helsinki; code freeze 04:00 UTC. Tuomas's choices are recorded as D60 to D63 in `docs/decisions.md`.

| Document | What it holds |
|---|---|
| [01-principles.md](01-principles.md) | UI principles and the concrete change each one makes here |
| [02-audit.md](02-audit.md) | Every surface as it is today (screenshots in `current/`), clutter, duplication |
| [03-information-architecture.md](03-information-architecture.md) | The five pages: message, top infographic, what goes below DETAILS; site maps weighed |
| [04-sim-view.md](04-sim-view.md) | Simulator: default vs hidden, three numbers, Optimise flip, queue colours, speed |
| [05-theme.md](05-theme.md) | Palette (contrast checked), type, spacing, charts, tokens; based on `reference/` frames |
| [06-execution-plan.md](06-execution-plan.md) | File map, test guards, couplings, work packages, rollback |
| [07-parallel-lanes.md](07-parallel-lanes.md) | **Lanes, the shared contract, ownership, merge order, critical path, what fits** |
| [08-pause-and-handoff.md](08-pause-and-handoff.md) | **Pause protocol, rollback point, handoff rule and template** |
| [../content-revamp/README.md](../content-revamp/README.md) | **What the pages say** (claim labels, Norway framing, research page, how content can change on the fly); runs beside this plan |
| [lanes/](lanes/) | **One self-contained brief per lane**, ready for a fresh agent |

## Decided (D60, D61; D62 and D63 shape two lanes)

| Question | Decision |
|---|---|
| What judges see | The offline `demo/` site (`start.html`, simulator `flow.html`), also the main submission page; `live_demo/` is the hosted secondary; the React app stays off the judges' path |
| Pages | Five: Overview, Simulator, Patients, Evidence, Decision model |
| Before/after | A flip on one layout and clock; side by side optional |
| Optimise offline | Labelled a saved run, results on held-out patients |
| Queue colour | By pile size (mustard, then brick) |
| Speed | Default 2 days/s, slowest 0.5 |
| Look | Paper `#F4F0E4` (check on the projector); the video's three-card look, not its words; no "clinician-validated" stamp |
| White paper | Printable page after the submission; tonight the Evidence page links `docs/norway_case_study.md` |
| React app | Not restyled for Sunday (lane L7 waits) |
| Norway framing (D62) | Plausibility framing of `docs/norway_case_study.md`; ranges always; never "beats the authors" |
| JEV page wording (D63) | Kept as built; restructure and restyle only |
| Dashboard "Before and after" (D66) | `index.html` screen 5 kept as built, re-themed only (script colours may change); linked from the Simulator's Optimise result (`index.html#<scenario>/5`) |
| Simulator graph (D67) | Less by default: edge thickness only, node names only, numbers on hover/click; keep the coloured "return" path and the dashed group boxes; a Details switch for the dense view |

## Lanes, critical path, cut line

| Lane | Owns | Before the freeze |
|---|---|---|
| L0 Foundation | `theme.css`, fonts, `site.js` (nav), skeleton, page stubs, test helper, `ui_shots.sh` | yes, first (A: 30 min, then frozen; B: 45 min) |
| L1 Simulator | `demo/flow.*` | yes, **critical path** (3 to 3.5 h) |
| L2 Overview | `demo/start.*` | yes |
| L3 Patients | `demo/patients.*` (new) | yes |
| L4 Evidence | `demo/evidence.*` (new), additive `export_start.py` + `start_bundle.js` | yes (top + robustness) |
| L5 Decision model | `demo/jev.*` | yes |
| L6 Secondary | `demo/encounter.*`, CSS of `index.html` | yes |
| L7 Web tokens | `web/src/**` | no (after the submission) |
| L8 Integrator | merges, `docs/demo_path.md`, READMEs, `CLAUDE.md` pointer, `HANDOFF.md` | throughout |

**Critical path:** pause and snapshot (20 min) → L0-A (30 min) → L1 (3 to 3.5 h) → integration and rehearsal (1 h).
That is about 5 hours. **Everything from L0 to L6 fits before 04:00 UTC if the pause starts by about 22:00 UTC.** Each
half hour of delay comes out of the buffer first, then out of L1's last step. Cut order if late: L4's small multiples, then L3's
reveal interaction, then L1's Optimise animation (keep the plain toggle). L0, L1 steps 1 to 4 and L2 are not cut. At
03:15 UTC, whatever is merged into `ui/main` ships, as one merge into `overnight/sim`. Rollback point: tag `ui-revamp-base`.

Merges cannot conflict, because files are owned exclusively. Shared things go through one owner: nav in `site.js` (L0),
docs and READMEs (integrator), bundles frozen (except L4's additive one), new tests per lane, existing tests unchanged.
Each lane writes `handoff/<lane>.md`. The integrator assembles `HANDOFF.md` and points `CLAUDE.md` and the channel to it.

## Riskiest parts

1. **The simulator lane is long and has no browser CI.** Five separately mergeable commits, a screenshot and
   console-error pass each, URL parameters kept, and `?theme=night` as a colour fallback.
2. **Seven agents on a 2-core machine.** Lanes run only their own tests and shots; the full gate runs in the
   integrator. If the machine chokes, run L5 and L6 after L2 and L3 instead of beside them.
3. **The contract has to be right the first time.** L0-A is small and frozen within about 30 minutes. Later changes are additive only, through the integrator.
4. **Honesty drift in rewritten text**, above all on the new Patients and Evidence pages. Numbers bound from bundles,
   caveats moved down and not deleted, Norway framing per D62, and a human read of L3 and L4 text before they go into the nav.
5. **Guarded pages:** `start.html` and `jev.html` have tests forbidding typed digits and limiting JS numerals; design
   constants have to live in CSS or `data-*` attributes.

## Before the pause (architect, about 25 minutes)

1. Regenerate `libraries/ref500` with g2@3 (M2 and D65 change its content and id), audit it.
2. `demo/export_cards.py`: prefer libraries made with `g2@3`, not `g2@2` (g2@2 is no longer in the safe set).
3. `python demo/export_all.py`, `python docs/pitch/fill_numbers.py --strict`, gate, commit, then the snapshot and tag in 08 section 1.
4. The Gemini v2 card run (Tuomas's Mac) lands after the handoff: the Patients and Overview pages must show whatever `cards_bundle.js` holds when re-exported (no typed counts), so a later `export_all.py` updates them without UI work.

## Still for Tuomas

| # | Question | Lean |
|---|---|---|
| N1 | Go time for the pause, and whether the Gemini library run on his Mac continues (it is outside the repo; merged only after the handoff) | Pause at once when the briefs are accepted; let the Mac run continue |
| N2 | How many agents: seven (L0 to L6) plus the integrator, or fewer if the machine is slow | Seven; fall back to running L5 and L6 after L2 and L3 |
| N3 | The synthetic-patients card moves from the Overview to the Patients page | Yes |
| N4 | The JEV page's model card moves below DETAILS (wording unchanged, D63) | Yes |
| N5 | A 01:00 UTC look at the merged screenshots, to catch taste problems while there is time to fix them | Yes, 10 minutes |

Open item: compare the palette and type against the reference frames on the actual presentation screen.
