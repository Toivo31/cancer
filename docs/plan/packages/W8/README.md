# Wave 8 packages and ticket index (14 Nov night, toward the 04:00 UTC freeze and after the submission)

Written by the spec lane `w8/specs` (documents only) at 21:15 to 22:00 UTC, against `overnight/sim` at `4019b15`
(decisions up to D64). Each package file is self-contained for a builder with no memory of this conversation; rules for
builders: `docs/plan/02-execution-strategy.md`. Leans are leans: where a row says "Tuomas's call", the options are in the file.

Not duplicated here (active or merged lanes; reference them): `w8/g2blind` (blind results prompt `g2@3`, leak rule, histology;
not yet merged at 21:15), `w8/catalogue-check` (D59, merged), `w8/norway-paper` (`docs/norway_case_study.md`, merged),
`w8/ui-plan` (UI WP1 to WP4 lane briefs, in `docs/plan/ui-revamp/`). D61 pauses other lanes while UI WP1 and WP2 run:
"before freeze" below means "when the coordinator frees a lane".

## Package map

| WP | Outcome | Size | Needs | Owner | Track |
|----|---------|------|-------|-------|-------|
| [WP-W8-1](WP-W8-1-jev-install.md) | JEV install: checkpoint 2350 reachable from `jev.birch`, `jev.walk`, encounter runs and the demo page; documented | M | – | agent; T5 JEV owner | before freeze |
| [WP-W8-2](WP-W8-2-jev-gp-node.md) | JEV decides at GP nodes (24 actions vs 16 per node; options A to E, lean two-stage by kind) | M | W8-1 T2 for the live check | agent; option is Tuomas's call | before freeze if a lane is free |
| [WP-W8-3](WP-W8-3-jev-demo-and-owner.md) | JEV page: recorded outputs for 4 live-only presets, HF link, owner's model-card answers, model vs table run | S to M | gateway up; W8-1, W8-2 for T4 | agent; T3 JEV owner | T1 before freeze; T4 after |
| [WP-W8-4](WP-W8-4-card-run-runbook.md) | Runbook after the Gemini card run: audit, merge, training sets, pitch refill | M | `w8/g2blind` merged | Tuomas runs; agent the rest | before freeze |
| [WP-W8-5](WP-W8-5-fi-evidence-followups.md) | Optimiser rerun inside the Finland evidence worlds; the unrun items | M | – | agent | after submission |
| [WP-W8-6](WP-W8-6-deploy-and-ci.md) | CI green (it runs and fails today); deployment to a real host | S, M | host for T4 to T6 | agent; T4 to T6 human with a host | T1 to T3 before freeze |
| [WP-W8-7](WP-W8-7-clinician-review.md) | Clinician review of the catalogue: reading order, sheet, how corrections flow back | S, M | a clinician | agent + clinician | after submission |
| [WP-W8-8](WP-W8-8-ui-after-submission.md) | Tickets pointing to UI revamp WP5 to WP9 | per plan | UI WP1 | agent; WP8 human | after submission (WP5 stretch) |
| [WP-W8-9](WP-W8-9-human-decisions.md) | Items waiting for a human, with options | S | – | humans | marked per row |
| [WP-W8-10](WP-W8-10-review-followups.md) | Review w8 and Known-problems leftovers (audit checks, retry, labels) | S | `w8/g2blind` merged | agent | T1 before freeze if free; rest after |

```
W8-JI-T1 ─► W8-JI-T2 ─┬─► W8-JI-T3 ─► W8-JI-T4
                      └─► W8-JG-T4 ◄── W8-JG-T2 ◄── W8-JG-T1 ─► W8-JG-T3
W8-JG-T2 + W8-JI-T5 ─► W8-JD-T4 ;  W8-JG-T2 ─► W8-RF-T8
w8/g2blind merge ─► W8-RB-T1 ─► T2 (Tuomas) ─► T3 ─► T4 ─► T5 ─► T6 ─► T7 ─► T8
W8-DP-T1, T2, T3 ─► W8-H3 (merge PR #2) ;  W8-DP-T1..T3 + host ─► W8-DP-T4 ─► T5, T6
W8-CR-T1 ─► T2 (Tuomas) ─► T3 (clinician) ─► T4 ─► T5
```

## Ticket index

Owner: **agent**, **human** (named), **JEV owner**. Size: S under an hour, M one wave.

### Before freeze (04:00 UTC)

| ID | Ticket | Size | Owner |
|---|---|---|---|
| W8-DP-T1 | Scenario guard test covers shipped scenarios only (fails on CI and locally since `w8/fi-sens`) | S | agent |
| W8-DP-T2 | Fix the Docker web build (fixtures outside the build context) | S | agent |
| W8-DP-T3 | Align `deploy/platform.env.example` with the hosted limits; time one Finnish optimisation through the service | S | agent |
| W8-RB-T1 | Card run preconditions: `g2@3` default, catalogue v2, `ref500` regenerated after g2blind, gate | S | agent |
| W8-RB-T2 | Run Gemini trial, then full (5 x 500) | S | human (Tuomas, key holder) |
| W8-RB-T3 | Audit the five libraries; Tuomas picks the stop-rule option | S | agent + Tuomas |
| W8-RB-T4 | Library handoff notes, README, `ref500.md` caveat; commit libraries | S | agent |
| W8-RB-T5 | Merge libraries without double counting | S | agent |
| W8-RB-T6 | Build training and held-out sets (realistic, balanced) | S | agent |
| W8-RB-T7 | Refill pitch and demo bundles; explain every changed number | S | agent (pitch lane OK) |
| W8-RB-T8 | Hand over: RELEASE post and 04-status lines | S | agent |
| W8-JI-T1 | Bring the owner's current `decision_api/` from `main` into the integration branch | S | agent (integrator OK) |
| W8-JI-T2 | `jev.birch` defaults to checkpoint 2350 (cache by checkpoint, 660 s, 32,000-byte gateway limit) | S | agent |
| W8-JI-T3 | Live smoke: walk two patients on the hosted gateway | S | agent |
| W8-JI-T4 | "Install and run" in `docs/platform/jev-birch.md` and the runbook | S | agent |
| W8-JD-T1 | Record live outputs for the 4 live-only JEV presets on the hosted gateway; rebundle | S | agent |
| W8-JG-T1 | Check node limits before sending, from care action kinds | S | agent |
| W8-JG-T2 | Two-stage GP decision by kind (lean; Tuomas's call vs table shortlist) | M | agent |
| W8-JG-T3 | Table shortlist behind a flag (fallback) | S | agent |
| W8-JG-T4 | Live GP check and doc section | S | agent |
| W8-RF-T1 | Audit check `design_coverage` (helps W8-RB-T3) | S | agent |
| W8-UI-T5 | UI WP5 patients page (stretch per the UI plan) | 2 to 3 h | agent |

### After submission

| ID | Ticket | Size | Owner |
|---|---|---|---|
| W8-JD-T4 | Model policy vs placeholder tables on the same patients (about 120 calls an hour) | M | agent (after W8-H12) |
| W8-FS-T1 | Optimiser search inside L67, X2, ALT | M | agent |
| W8-FS-T2 | Same for N37, L92, P if T1 differs | M | agent |
| W8-FS-T3 | Recalibrate capacity in X1 and rerun | M | agent |
| W8-FS-T4 | Extra delay placed earlier (L67) | S | agent |
| W8-FS-T5 | Symptom odds ratios: input or scoped note | S | agent |
| W8-FS-T6 | EBUS and CT-biopsy accuracy: input or scoped note | S | agent |
| W8-CR-T1 | Clinician reading guide and reviewer's sheet generated from the catalogue | S | agent |
| W8-CR-T4 | Apply clinician corrections: hash, pins, ref500, audit, loop report, pitch, decision | M | agent |
| W8-UI-T6 | UI WP6 evidence page and Norway paper page | 4 to 6 h | agent + review |
| W8-UI-T7 | UI WP7 web app theme and simplification | 1 h to 2 days | agent |
| W8-UI-T9 | UI WP9 `scripts/ui_shots.sh` | 1 to 2 h | agent |
| W8-RF-T2 | Audit check `report_condition_words` | S | agent |
| W8-RF-T3 | Audit check `null_truth_values` | S | agent |
| W8-RF-T4 | Resume retries failed cards from the cache | M | agent |
| W8-RF-T5 | Population labels to `assumption` (FILHA2026, ECDC_TB2024) | S | agent |
| W8-RF-T6 | Sex effect beyond smoking (needs a source) | S | agent |
| W8-RF-T7 | Rule vs stub when the standard option is not offered | S | agent |
| W8-RF-T8 | Align the JEV GP preset with the simulator's reduction | S | agent |
| W8-RF-T9 | Backfill first-wave agent decisions into the log | S | integrator |

### Needs a human

| ID | Ticket | Size | Owner | When |
|---|---|---|---|---|
| W8-H1 | Voice-over 320 to 300 words (lean: rewrite the Norway paragraph to D62) | S | Eemeli + pitch lane | before submission |
| W8-H2 | Stale 61% / 80% in Eemeli's video files | S | Eemeli | before submission |
| W8-H3 | Merge PR #3 and PR #2 into `main`, or name the submitted branch | S | Toivo or Tuomas | before submission |
| W8-H4 | No-disease-found presenters without symptoms (D59) | S | Tuomas | before the card run if (b) |
| W8-H7 | D18, D27 (spoken in the script); D20, D25 | S | Tuomas | D18, D27 before submission |
| W8-RB-T2 | Gemini trial and full run (also listed above) | S | Tuomas | before freeze |
| W8-JI-T5 | Questions to the JEV owner: bulk runs vs D64, rate limit, rationale, uptime | S | JEV owner | soon |
| W8-JD-T3 | Model-card facts: HF page, training data of 2350, correction wording, head size | S | JEV owner | soon |
| W8-JD-T2 | Fill `HF_URL` when the owner gives a page | S | agent after owner | any time |
| W8-H5 | D42 and vision assumptions V2 to V11 | S | Tuomas | after |
| W8-H6 | Booking split (1114-141641), D43 | S | Tuomas | after |
| W8-H8 | How training files reach the JEV owner | S | Tuomas + JEV owner | after the run |
| W8-H9 | Forks F2 to F7 | S | Tuomas | after |
| W8-H12 | Automated JEV runs vs the owner's no-bulk rule | S | Tuomas + JEV owner | before W8-JD-T4 |
| W8-DP-T4..T6 | First deploy, security settings, rollback test | M | human with a host (H10) | after |
| W8-CR-T2, T3, T5 | Find a clinician; review session; draft status wording | S, M | Tuomas, clinician (H11) | after |
| W8-UI-T8 | One simulator renderer or three | S | Tuomas and Eemeli | after |

## Found while speccing, not planned anywhere before

1. **CI runs and fails** on `overnight/sim` and PR #2 (04-status says it was never run): the scenario guard test (since
   `w8/fi-sens`) and the Docker web build. W8-DP-T1, T2.
2. **`decision_api/` on `overnight/sim` is older than `main`** (no hosted gateway client, no bridge, 50 files differ), and
   `jev/birch.py` is pinned to checkpoint 1138 while the live model is 2350. W8-JI-T1, T2.
3. **The gateway caps a request at 32,000 bytes and 12,000 context characters**; `jev/birch.py` allows 480 KiB, so long
   records will be refused. W8-JI-T2.
4. **Throughput, not budget, now limits JEV runs**: 120 submissions an hour per gateway process (D64 removed only the budget). W8-JI-T5, W8-JD-T4.
5. **For pathway requests the binding limit is 16 actions per node** (native schema); the 8-choice cap is on `/score` only.
   The GP node's 15 tests fit a two-stage split by the existing `kind` field. WP-W8-2.
6. **`deploy/platform.env.example` contradicts 04-status's hosted limits** (50,000 vs 20,000 patients, 900 vs 120 s, no
   `PATHWAY_MAX_SEEDS`). W8-DP-T3.
7. **Ordering trap for tonight**: `w8/g2blind` changes non-cancer histology, so `ref500` must be regenerated **after** it
   merges (catalogue-check regenerated it before); and a merged training library next to its sources is read twice by the
   training-set builder. W8-RB-T1, T5.
8. **`video_script.md` still says D17 is open**; D62 closed it, which is also the natural place to trim the voice-over. W8-H1.
