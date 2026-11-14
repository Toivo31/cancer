# C4 Decision layer

| | |
|---|---|
| Package | `jev/` |
| State | Built: the decision contract, the adapter to the engine, stub tables, an HTTP backend with a stub server, a local numpy backend, dataset rows, a frequency trainer. Detailed spec: `docs/platform/specs/02-jev-interface.md` and `06-datasets-training.md` |
| Depends on | C3 (context from the revealed record) |
| Used by | C3 (every decision node), C5 (the optimiser edits its tables), C6 (editor, training) |
| Track | The ladder below is platform track |

## Purpose

Answer one question at every decision node: given what has been revealed about this patient and
the options on offer, how likely is each option to be chosen next? The answer always comes
through the same contract, whatever sits behind it. In the end that is JEV, the team's decision
model. Until then, and next to it for comparison, simpler policies do the job.

## The ladder of policies (all behind the one contract)

| Level | Policy | What it is | State |
|---|---|---|---|
| 0 | **Fixed probabilities** | One row per decision: 70% option A, 30% option B | Built (stub table without conditions) |
| 1 | **Decision matrix** | Ordered rows "when <condition over revealed facts> then <probabilities>", first match wins, a default row | Built in simple form (stub table with conditions over step results and attributes). To extend: typed revealed variables from C3 S1, an explicit "unknown" test, validation that every row is reachable |
| 2 | **Score and thresholds** | A points score over revealed facts (each fact adds points), cut-offs map the score to options. The form many clinical risk tools take | To build. It is what the optimiser tunes most naturally (a few numbers per decision) |
| 3 | **Learned table** | Level 1 fitted from past decisions (frequency trainer) | Built on `plat/ds` |
| 4 | **JEV over HTTP** | The team's model: context and options in, probabilities out | Client and contract tests built; waits for the JEV owner (fork F3) |

Rules that hold at every level:

- **Only revealed facts.** The context is built from the revealed record by the adapter; a policy
  has no other input (invariant I1).
- **Probabilities, then one draw.** The engine samples with a common random number per
  (patient, decision), or takes the most likely option, by run setting. Identical probabilities
  give identical choices across flowcharts.
- **Unknown is a value.** A fact that has not been revealed is unknown, not false. Matrices and
  scores must say what they do with unknown (a row for it, or zero points).
- **Readable.** Levels 0 to 3 are shown and edited in the web app as tables. A decision a person
  cannot read is not accepted as a pathway rule; the optimiser's output is constrained to these
  forms.

## What changes for the vision

| # | Change | Notes for speccing |
|---|---|---|
| D1 | Context carries typed revealed variables (`chest_ct.size_mm`, `history.haemoptysis`) with the day each became known | Follows C3 S1. A contract change: `context` gains `revealed`; keep `history` for compatibility; bump the contract's minor version and extend the contract tests |
| D2 | Decision matrix, extended: conditions over typed variables, an `is unknown` test, reachability and overlap warnings, row-level source notes | Mostly validation and the safe evaluator's grammar (comparisons with numbers already exist) |
| D3 | Score-and-thresholds policy | New table shape in the flowchart document; evaluated in-process; shown as a points table in the web app |
| D4 | The judgement nodes' first matrices (nurse, GP, specialist; C3 S4) | Content, not code: each row needs a source or `assumption`, like the catalogue. Calibrated so the Finnish scenario's published waits and shares hold |
| D5 | Explanation with every answer: which row or which points produced it | The contract already has an `explanation` field; make it structured so the patient trace can show "row 3: haemoptysis and age over 40" |
| D6 | "What would JEV need": an export of decision contexts in the dataset format for the JEV owner | Exists as decisions export; confirm the shape with the JEV owner |

## Relation to the optimiser

The optimiser (C5) changes the pathway in two ways: the order of steps (built) and the decision
criteria (to build). For criteria it edits levels 1 and 2 only: it adds, removes or reorders
matrix rows and moves thresholds. With JEV attached (level 4) it does not edit the model; it can
(a) report where the model's choices cost time, as evidence, and (b) produce an improved matrix
as a training target or a comparison baseline. Whether an optimiser may override a decision that
a model owns is fork F7 (lean: no, unless switched on).

## Sub-wholes (for the spec agent)

| # | Sub-whole | Contains |
|---|---|---|
| J1 | Typed context and contract version bump | D1 |
| J2 | Decision matrix extension and validation | D2, D5 |
| J3 | Score-and-thresholds policy | D3, D5 |
| J4 | Judgement-node matrices for the Finnish scenario | D4 (with C3 E4; review required) |
| J5 | Editor support in the web app for matrices and scores | with C6 |
| J6 | JEV hand-over pack | D6, the contract tests, a one-page description for the JEV owner |

## Open questions

| # | Question | Lean | Who |
|---|---|---|---|
| Q1 | Who owns JEV and is there an API yet (fork F3) | Unknown; the contract in spec 02 stands until they answer | Tuomas |
| Q2 | Sample or take the most likely option by default (fork F2) | Sample: simulates varied practice, and fixed probabilities only make sense sampled | Tuomas |
| Q3 | Should a decision be able to order several tests at once | Yes, as an option that is a named bundle, so the contract stays "choose one option" | Architect; spec agent to confirm it fits the engine |
