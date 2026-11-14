# WP-W8-2: JEV at the GP node: 24 offered actions against a 16-action limit

| | |
|---|---|
| Component | C4 decision layer, C8 encounter loop (D44, D51) |
| Status | not started |
| Size | M |
| Needs | WP-W8-1 T2 (checkpoint 2350 defaults) for the live check; offline tickets can start now |
| Provides | `BirchPolicy` that can decide at every encounter node, with the reduction recorded in the run log |
| Owned paths | `jev/birch.py` (request building and response mapping), `jev/adapter.py` only if the reduction belongs there, `tests/test_jev_birch.py`, new `tests/test_jev_gp_node.py`, `docs/platform/jev-birch.md` (one section) |
| Do not edit | `catalogue/lung-primary-care/care.yaml` (calibrated loop; see option E), `pathway_sim/encounter.py`, `decision_api/` |
| Review required | yes: I1, and the reduction changes what the model can choose (D51) |
| Track | submission if a lane is free before freeze (Tuomas's call); otherwise first after submission |

## Outcome

`python -m jev.walk --pick random --auto-accept` (and an encounter run with `--jev birch`) gets a model proposal at every GP
visit instead of a refusal. Every GP decision in the run log records how the offered list was reduced and which calls were made.

## Why

`care.yaml` gives the GP 24 actions (2 discharge, 1 follow-up, 15 order, 4 treat, 2 refer: the `kind` field of each action).
The pathway contract allows 16 actions per node natively (`inference_schema.py` `Node.actions max_length=16`); the gateway's
`/score` allows 8 choices per question. `BirchBackend._decide_one` sends every offered option, so a live GP call is refused
(found by `w8/jev-demo`; the demo page works around it with a hand-picked 8 in `demo/export_jev.py` `GP_SUBSET`).
The nurse node (3 actions) is unaffected.

## Options (weigh; the lean is mine, the call is Tuomas's because it touches D51)

| | Option | Calls per GP visit | For | Against |
|---|---|---|---|---|
| A | **Shortlist by the placeholder table**: keep every action the table weighs at this visit, fill to 16 with common next steps (as the demo page does, to 8) | 1 | Simplest; one call; works tonight | The placeholder decides the menu, so the model cannot choose what the table ruled out; weakens "only the JEV decides" (D51); a hidden dependency on the table's quality |
| B | **Two-stage by action kind**, using the pathway contract's own graph: root node "what kind of next step" (discharge, follow-up, order a test, treat, refer: 5 actions), then a node per kind with its actions (largest: 15 tests, under 16); second call carries the first choice in `history` | 2 (1 when the kind has one action) | The model chooses everything; uses the API as designed (workflow graph, history); no content change; kinds already exist in `care.yaml` | Twice the calls (with 120 calls an hour this halves throughput); the probability of an action is P(kind) x P(action given kind), and only the chosen kind is scored in argmax mode; "order a test" gets 15 options at once |
| C | **Record-aware feasibility filter** first (drop orders already pending, a test just resulted, treatments already given), then A or B if still over 16 | 1 or 2 | Removes options a clinician would not consider; cheap rules from the record | Rules are ours, not sourced; rarely gets 24 under 16 on its own; must not use hidden truth |
| D | **Several questions in one `/score` call** (e.g. 3 questions of 8) and compare winners | 1 to 2 | One context encoding | Scores are relative within a question (softmax over its choices), so winners of different questions are not comparable; `/score` is not the pathway contract `jev.birch` uses |
| E | **Fewer GP actions in `care.yaml`** (merge near-duplicates such as `order_crp` and `order_crp_lab`) | 1 | No adapter logic | Changes care content and the tuned loop (8 of 8 seeds) and the catalogue-side review; not before freeze |

**Lean:** B, with A behind a flag (`--gp-shortlist table`) as the fallback if B is not ready or too slow tonight. Both must
record the reduction in the run log and the walk output. C only as a later refinement. D and E not now.

## Acceptance

- [ ] Offline (mock): at a GP node with 24 offered actions, B sends two requests, each with at most 16 actions; the second
      request's `history` holds the first choice; the returned `probs` cover all 24 offered ids (non-chosen kinds get 0 in
      argmax mode, as documented) and sum to 1 (test).
- [ ] A under the flag: the request holds at most 16 actions, every action with table weight above 0 is kept, and the run
      log entry lists dropped ids (test). If the table weighs more than 16, the call fails loudly (edge test).
- [ ] I1: neither stage's payload contains a condition id or hidden field (reuse `check_visible`) (test).
- [ ] Sample mode: kind sampled from stage 1 scores, action from stage 2; with a fixed seed the choice is reproducible (test).
- [ ] Nurse node still makes exactly one call (test).
- [ ] Live: one `jev.walk` through a GP visit on the hosted gateway completes (manual, recorded in the doc).

## Out of scope

Changing `care.yaml`; training the model on two-stage questions; the demo page's preset (it stays at 8 via `/score` until a
later ticket aligns it).

## Things to look at and weigh

- `jev/birch.py:205-236` `map_request` builds one node with all options and terminal `after-*` nodes; B needs a two-level
  workflow and a history entry. Read the pathway contract (`PathwayRequest`, `CompletedStep`) in
  `decision_api/runtime/decision_model/inference_schema.py` on `origin/main` to see what `history` must contain.
- The cache key is the payload hash, so each stage caches on its own: good for reruns.
- The engine draws from the returned `probs` (`pathway_sim/encounter.py:764-787`); any option missing from `probs` gets 0.
- Where the reduction lives: in `BirchPolicy` (knows the care kinds) or in `jev.adapter` (generic, would serve any backend
  with a limit). Consider which other backends will have a limit.
- Explanation text: the run log's `choices` entry should say "two-stage: kind X (score), then action Y (score)".

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | W8-JG-T1 | Read action kinds from the care document into the request builder and check the limits before sending (16 per node; clear error naming the limit) | S | – | over-limit request raises before any network call (test) |
| [ ] | W8-JG-T2 | Two-stage GP decision by kind (option B), argmax and sample modes | M | T1 | acceptance items 1, 3, 4, 5 |
| [ ] | W8-JG-T3 | Table shortlist behind `--gp-shortlist table` (option A) with dropped ids logged | S | T1 | acceptance item 2 |
| [ ] | W8-JG-T4 | Live check on the gateway and a section "Nodes with many actions" in `docs/platform/jev-birch.md` (calls per visit, effect on throughput at 120 calls an hour) | S | T2, WP-W8-1 T2 | walk output saved; doc section merged |
