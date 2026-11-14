# Planning framework (start here)

This folder is the entry point for every person and agent working on this repo. It says what we are
building, how the parts fit, who does what, and how a part gets from an idea to merged code.
Written 14 Nov 2026 by the architect session (Tuomas's Claude Code). Direction comes from Tuomas.

If you are an agent: read this file, then the file for your level (table below). Do not start
building from this folder alone unless a work package or ticket has been written for you.

## The levels

Work is planned top-down in four levels. Each level has one kind of document and one kind of owner.
A lower level may not change a higher level's document; it raises a question instead
(`python scripts/comms.py post --type QUESTION ...`).

| Level | Document | Answers | Owner | Lives in |
|---|---|---|---|---|
| L0 Vision | `00-vision.md` | Why, for whom, what the loop is, what is out of scope | Tuomas (architect writes it down) | this folder |
| L1 Architecture | `01-architecture.md`, `components/C*.md` | Which components exist, their boundaries and contracts, the design of each at a high level | Architect | this folder |
| L2 Work packages | `packages/<component>/WP-*.md` | One buildable whole inside a component: scope, interface, acceptance, tickets | Spec agent, one per component | this folder |
| L3 Tickets | the ticket list inside each work package | One change an agent can finish in one sitting, with files and tests | Spec agent writes, builder agent executes | inside the work package |

How to write L2 and L3 is in `03-speccing-guide.md`, with templates in `templates/`.

## Reading order by role

| You are | Read |
|---|---|
| A human on the team | `00-vision.md`, `04-status.md` |
| A **spec agent** asked to break a component into work packages and tickets | `00-vision.md`, `01-architecture.md`, your `components/C*.md`, `03-speccing-guide.md`, `templates/` |
| A **builder agent** with a ticket or work package | your work package, the component file it belongs to, `02-execution-strategy.md` sections "Rules for builders" and "Definition of done" |
| A **reviewer agent** | `01-architecture.md` (the invariants), the component file, `02-execution-strategy.md` section "Review" |
| The **integrator** | `02-execution-strategy.md`, `04-status.md` |

## Files

| File | What it is |
|---|---|
| `00-vision.md` | The product, the loop, principles, non-goals, assumptions waiting for Tuomas |
| `01-architecture.md` | Component map, data flow, contracts, invariants, repo layout |
| `02-execution-strategy.md` | Assessment of the first parallel wave, and the rules for the next ones: roles, lanes, integration, communication, quality gates |
| `03-speccing-guide.md` | How to turn a component into work packages and tickets |
| `04-status.md` | What is built, where, what is running, what is open. The only file here that changes often |
| `components/C1-patient-engine.md` | Synthetic patients: the patient card, hidden variables, generation, storage, LLM narrative |
| `components/C2-clinical-catalogue.md` | The medical content: conditions, findings, tests with accuracy, all sourced |
| `components/C3-simulation.md` | The flowchart simulator: what exists, what changes for the new patient model |
| `components/C4-decision-layer.md` | What sits at a decision node: probabilities, decision matrix, score, JEV |
| `components/C5-optimiser.md` | How the pathway and the decision criteria are optimised |
| `components/C6-platform.md` | Service, web app, datasets and training, deployment (mostly built; points to `docs/platform/`) |
| `components/C7-evidence.md` | Sources, calibration, validation, honesty rules |
| `templates/work-package.md`, `templates/ticket.md` | Fill-in templates for L2 and L3 |

## How this relates to the older documents

Nothing is thrown away. This folder is the index over them.

| Older document | Status |
|---|---|
| `docs/master_plan.md` | The Junction entry's master plan (goal, evidence, judging). Still canonical for the hackathon story. Section 12 points here |
| `docs/platform/README.md`, `docs/platform/specs/01` to `07` | Detailed specs of the platform parts that are now built. Canonical for those parts; `components/C6-platform.md` summarises and links |
| `docs/platform/tickets.md` | Ticket list of the first wave (M1 to M8). Kept as the record. New work is ticketed inside work packages, not there |
| `docs/architecture.md` | The engine's contract as built. Canonical for `pathway_sim/` internals |
| `docs/decisions.md` | The decisions log. Still the one place for decisions; only the integrator writes to it |
| The agent channel (branch `agent-comms`) | Live coordination. See `02-execution-strategy.md` |

Rule from `CLAUDE.md`: when a decision in the plan changes, update `docs/master_plan.md` in the
same change. For anything in this folder the equivalent is: update the component file and add a
row to `docs/decisions.md`.
