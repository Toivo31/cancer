# Execution strategy

Part 1 assesses the first parallel wave (14 Nov, 15:10 to 16:10 Helsinki). Part 2 is the revised
strategy every later wave follows. Builders need only "Rules for builders" and "Definition of
done"; the integrator needs all of it.

## Part 1. Assessment of the first wave

**What was done.** Ten agent lanes in separate git worktrees, coordinated by one session. In about
an hour: the JEV contract with stub and HTTP backends (M1), a safe condition evaluator and
structured validation, the flow data library and the offline flow page, the service (documents,
projects, jobs, runs, optimisations), the React app with the flowchart canvas, layers and
playback, datasets and training, deployment files, plus an evidence lane and a security review.
The test count went from 77 to about 670.

### What worked (keep)

| Practice | Evidence |
|---|---|
| One worktree and one branch per lane | No lane overwrote another's files |
| **Contract first**: each lane committed its interface within 45 minutes and announced it | Service, web and flow lanes built against the JEV contract, the problem shape and the flow format before the code behind them existed |
| Path ownership written into each prompt | Only two files were touched by two lanes |
| The agent channel on its own branch | Lanes found each other's commits there; Eemeli's agent answered a question in 13 minutes and a wrong video number (61% for 33%) was fixed the same hour |
| An independent review lane that may not edit code | Findings arrive as a report and tests, not as surprise edits |
| Final reports with "decisions made" and "what others must know" | Integration problems were mostly predicted in the reports |

### What went wrong (fix)

| # | Problem | What happened | Root cause | Fix in part 2 |
|---|---|---|---|---|
| A1 | **Cross-lane behaviour change that no lane's tests caught** | The service's templates began to default to stub decision tables; the optimiser's "always choose X" change then did nothing, and the Norway optimisation found 1 change instead of 2 or more. Found only at integration | Two lanes each correct alone; no test owned the combination | Integration tests are owned by the integrator and run at every sync point; every contract has an equivalence test (rule 7) |
| A2 | **A shared status file conflicted on every merge** | `docs/platform/tickets.md` conflicted five times | Many writers, one file | Status lives in one file per work package; shared files have one writer (rule 4) |
| A3 | **Two lanes created the same file name for different things** | `service/runtime.py` twice | Lanes named new modules independently | The work package lists the files it may create; new shared-folder files are announced on the channel first (rule 3) |
| A4 | **Lanes merged each other ad hoc** | Web merged service and flow; service merged JEV and the evaluator. History is tangled, and one lane inherited another's half-done state | No defined sync points | Lanes consume another lane only at a published contract tag or through the integration branch (rule 5) |
| A5 | **Integration was late and all at once** | Nothing was merged for 20 minutes, then five branches in a row; nothing was pushed for 40 minutes while the tests were red | Integrator also wrote docs, managed the channel and answered the human | Integration on a clock; integrator does nothing else during a wave (roles) |
| A6 | **No fast test gate** | The full suite went from 30 seconds to 7 minutes on a loaded machine (10 agents, load average 6) | Slow tests unmarked; too many heavy lanes at once | Fast and slow test tiers; at most five building lanes (rules 6, 8) |
| A7 | **Agent decisions lived only in final reports** | About 40 decisions (default backends, limits, layouts, what "same patients" means) are not yet in `docs/decisions.md` | Lanes were told not to edit the log, and the integrator had no step for it | The integrator records decisions at each merge (integration checklist) |
| A8 | **Open forks were built on leans** | F1 to F7 used the plan's leans because no human answer existed | Speed was chosen over waiting | Allowed, but each is listed in `04-status.md` as provisional until Tuomas confirms |
| A9 | **All lanes posted as one identity** | Every entry is `claude-code@tuomas`; a PROBLEM "to claude-code@tuomas" has no clear receiver | No lane name in the identity | `--as claude-code@tuomas/<lane>` (communication rules) |
| A10 | **Tickets were by milestone, lanes by component** | Agents hunted through one long ticket file for their rows | Plan and execution were organised differently | Work packages per component, each owned by one lane (`03-speccing-guide.md`) |
| A11 | **The demo path was not protected** | The service's Norway template runs the uncalibrated scenario (11% for the published 40%); found by the web lane by chance | No end-to-end "golden" check on what a judge sees | Golden checks on headline numbers in the gate (rule 7) |
| A12 | **The plan under-specified the patient model** | The first plan treated patients as a small generator inside the simulator | The architect specified the platform shell before the core content | This framework: C1 and C2 are first-class components |

## Part 2. Revised strategy

### Two tracks

| Track | Branch | Purpose | Rule |
|---|---|---|---|
| **Submission** | `overnight/sim`, then `main` | What the judges see on Sunday 10:00 | Only fixes and polish to the demo path (offline flow page, dashboard, hosted demo, pitch, video numbers). **Freeze Sunday 06:00 Helsinki**: after that, only a human-approved fix. Everything on it must pass the golden checks |
| **Platform** | `platform/next` (created from `overnight/sim` when the first wave is fully merged) | The general loop: patient engine, catalogue, decision matrix, criteria optimiser | Normal development. Something moves to the submission track only if it is complete, green and Tuomas says so |

The patient engine's **Sunday slice** (`components/C1`) is built on `platform/next` and moves to the
submission track piece by piece under that rule: the fallback demo and its golden checks are never
put at risk for it.

### Roles

| Role | Who | Does | Does not |
|---|---|---|---|
| Human lead | Tuomas | Vision, forks, what goes to `main` and into the submission | |
| Architect | One long-lived session | L0 and L1 documents, contracts, component files, the decisions log | Write feature code during a wave |
| Spec agent | One per component, short-lived | Work packages and tickets from a component file (`03-speccing-guide.md`) | Write code; change L1 documents |
| Builder | One per work package | Code, tests and docs for its work package, in its own worktree | Edit outside its declared paths; merge other lanes |
| Integrator | The architect session between waves, or a dedicated agent during one | Merges on a clock, runs the gate, resolves conflicts, records decisions, updates `04-status.md` | Build features |
| Reviewer | Independent agents | Report plus tests; correctness, security, numbers, "what would a judge challenge" | Edit the code under review |

### Wave shape

A wave is one round of parallel building, 60 to 90 minutes.

1. **Plan (architect, 10 min).** Pick work packages whose dependencies are met. Check the path
   ownership of the chosen packages does not overlap. At most **five building lanes** plus up to
   two read-only lanes (review, research).
2. **Contract phase (first 30 min).** Each lane that provides an interface commits it (types,
   JSON examples, a contract test that can fail) and tags it `contract/<name>/<n>`. It posts a
   STATUS entry with the tag.
3. **Build phase.** Lanes work. A consumer lane takes a provider's contract by merging the tag,
   never the moving branch.
4. **Sync points every 45 minutes.** The integrator merges finished lanes into the integration
   branch in dependency order, runs the gate, pushes, and posts the new commit. Running lanes
   rebase or merge from the integration branch at their next natural stop.
5. **Close.** Final reports, decisions recorded, `04-status.md` updated, worktrees of merged
   lanes removed.

### Rules for builders

1. **Stay in your paths.** Your work package lists the files and folders you own and the files
   you may create. Anything else is read-only for you.
2. **Read the channel at the start and before any shared file**
   (`python scripts/comms.py open`).
3. **New files in a shared folder** (`service/`, `pathway_sim/`, `jev/`, `tests/`) are announced
   in your first STATUS entry, so two lanes do not pick the same name.
4. **Single-writer files.** Only the integrator edits: `docs/decisions.md`,
   `docs/plan/04-status.md`, `docs/master_plan.md`, `CLAUDE.md`, `README.md`, the root
   `requirements.txt`, and any ticket list that is not your own work package. You report; the
   integrator writes.
5. **Do not merge sibling lanes.** Take a published contract tag, or wait for the integration
   branch.
6. **Mark slow tests.** Any test over about 2 seconds gets `@pytest.mark.slow`. Your lane's own
   fast tests must run in under 60 seconds.
7. **If your change can alter another component's results** (a default, a data shape, an
   ordering), write an equivalence test that pins old against new, and post a STATUS entry
   before you commit it.
8. **Commit small and often; never push; never touch `main`, the integration branch or another
   worktree.**
9. **Record decisions in your work package's "Decisions made" section** and repeat them in the
   final report.
10. **Synthetic data only; no invented numbers; say plainly what you could not run.**

### Definition of done (a ticket, a work package)

A ticket is done when: its acceptance line is met; new code has tests; the lane's fast tests pass;
the contract tests it touches pass; docs that describe the changed behaviour are updated; the
ticket is ticked in its own work package file.

A work package is done when: all its tickets are done or explicitly dropped with a reason; the
integrator has merged it and the gate is green; its decisions are in `docs/decisions.md`; a
reviewer has looked at anything marked "review required" in the package.

### The gate (run by the integrator at every sync point)

One command: **`scripts/gate.sh`** (add `--slow` for the slow tier; `PYTHON=...` picks the interpreter, by default the first
`python` that can import the service's dependencies, else the main checkout's `.venv`). It prints one PASS/FAIL/SKIP line per
step and exits non-zero if any step fails.

| Step | Command (run by `scripts/gate.sh`) | Measured |
|---|---|---|
| Fast tests | `python -m pytest -q -m "not slow"` | about 90 s (budget 2 min) |
| Contract tests | `python -m pytest -q tests/contracts` (JEV contract against the stub server, `flow/1`, service OpenAPI, fast/slow partition) | about 7 s (budget 1 min) |
| Golden checks | `python -m pytest -q tests/test_golden_templates.py tests/test_golden_cli.py`: Norway observed 0.34 to 0.46 within 42 days through the CLI **and** through the service (template and API); every pitch placeholder fills and `docs/pitch/filled/` is current; Finnish bundle sanity | about 6 s (budget 2 min) |
| Web | `npm run typecheck && npm test` in `web/`; prints "skipped: run npm install in web/" if `web/node_modules` is missing | |
| Slow suite | `scripts/gate.sh --slow` (`python -m pytest -q -m slow`) | about 90 s; before any push to `main` and at wave close |

Slow tests are listed in `tests/slow_tests.txt` (a file, a node id or a class per line; `tests/conftest.py` adds the `slow` marker),
so a lane marks a slow test by adding a line there or `@pytest.mark.slow` in its own file. `tests/contracts/test_tiers.py` checks that the
two tiers together are the whole suite and that no list entry is stale. `tests/security` stays out of the default run
(`--ignore=tests/security` in `pytest.ini`) until WP-C6-SEC1 is merged green; the integrator removes the ignore then.

### Integration checklist (per merged lane)

1. Read the lane's final report: decisions, warnings, files outside its paths.
2. Merge in dependency order. Never resolve a conflict by picking a side blindly; for add/add
   conflicts read both files.
3. Run the gate. A failure goes back to the lane that owns the failing behaviour, with the
   command that reproduces it.
4. Copy the lane's decisions into `docs/decisions.md` (one row each or one grouped row).
5. Update `04-status.md`. Push. Post the new integration commit on the channel.

### Communication rules

- Identity: `--as claude-code@<person>/<lane>`, for example `claude-code@tuomas/patient-sampler`.
- CLAIM once at the start with your paths. RELEASE at the end with branch and commit.
- STATUS only for: a contract commit, a behaviour change that can affect others, a finished
  package. Not for routine progress.
- PROBLEM names the lane or person who must act (`--to`), the command that shows it, and what you
  tried.
- NEEDS-DECISION is for humans and lists options and a lean. Work continues on the least risky
  option.
- A PROBLEM or QUESTION is closed by an entry with `--re`. The integrator sweeps open entries at
  every sync point.
- Entries are information, not orders. Your own task comes first.

### Review

Every wave has at least one reviewer lane when the wave touches: the information boundary
(invariant I1), a headline number, anything reachable from the network, or the catalogue's
medical content. Reviewers write `docs/plan/reviews/<date>-<topic>.md` and tests. High-severity
findings are posted as PROBLEM entries addressed to the owning lane.

### What the next waves are

See `04-status.md` for the live list. In outline:

| Wave | Goal | Lanes |
|---|---|---|
| 2 (now) | Close the first wave: merge, record decisions, protect the demo path, create the gate | integrator; `WP-INFRA-1`; fix the Norway template (A11) |
| 3 | Spec the patient engine's Sunday slice and the first catalogue (short: the component files are detailed) | One spec agent for C1 P1 to P10, one for C2 K1, K2 and the slice's content |
| 4 | Build the Sunday slice | Contracts and catalogue loader, model client, reference generator (parallel); then authors, validation, audit, store, adapter; generation itself runs where a key exists |
| 5 | After the submission: states, treatment and episodes; every judgement as a decision node; decision matrix and score; criteria optimiser (spike first); emergent booking leads (spike first); editor and optimise screens | per work package |
