# Speccing guide: from a component to work packages and tickets

For **spec agents**. You have been given one component file (`components/C*.md`). Your output is a
set of work packages with tickets that builder agents can execute without asking you anything.
You write no product code.

## What you receive and what you produce

| You read | You write |
|---|---|
| `00-vision.md`, `01-architecture.md`, your component file, the code and docs it names, `02-execution-strategy.md` | `docs/plan/packages/<component>/README.md` (the package map) and one `WP-<component>-<n>-<slug>.md` per work package, from `templates/work-package.md` |

The component file already names the **sub-wholes** (P1, P2, …) of the component. Start from
those: usually one sub-whole is one work package. Split a sub-whole only if it cannot be finished
by one agent in one wave (about 60 to 90 minutes) or if two parts of it could run in parallel with
separate files. Merge two only if they share nearly all their files.

## Method (work in these phases)

1. **Understand.** Read the component file twice. Read the existing code it touches; run it. Write
   down, for yourself, what exists, what the component file asks for, and the gap.
2. **Question.** List what the component file leaves open. For each: can you decide it at your
   level (a detail inside one work package)? Then decide and record it under "Decisions for the
   builder" as a lean, not an order. Does it change a contract, an invariant or the scope? Then
   do not decide: post a QUESTION to the architect on the channel and mark the affected ticket
   `blocked: <question id>`.
3. **Cut.** Draw the dependency graph of the sub-wholes. Find the contracts between them. A work
   package that provides a contract gets a first ticket "publish the contract" (types, JSON
   examples, a failing-capable contract test), sized S, so consumers can start.
4. **Write** each work package from the template. Then write its tickets.
5. **Check** your packages against the lists below. Then read them once more as the builder: is
   there any sentence where you would have to guess?
6. **Hand over.** Post a STATUS entry with the folder path. Tick nothing.

## What a good work package has

- **One outcome** a person can try ("`python -m patient_engine sample --n 1000` writes a cohort
  and prints a marginals table").
- **Owned paths** (folders or files it may edit) and **files it may create**, exact. No overlap
  with any other open work package. If overlap is unavoidable, name the single shared file and
  say which package edits it first.
- **Interfaces**: what it provides (with the contract's name and version) and what it consumes
  (with the tag or commit it can rely on).
- **Acceptance**: checks a machine can run. At least one end-to-end check, the invariants from
  `01-architecture.md` that apply (name them: I1, I3, …), and one check on behaviour at an edge.
- **Out of scope**, explicitly, so the builder does not wander.
- **Guidance, phrased as things to look at and weigh**, not as a recipe. The builder decides how.
  Give the reason behind each constraint so the builder can make a good call when reality
  differs from your plan.
- **Review required?** Yes if it touches invariant I1, a headline number, medical content or the
  network.
- **Size**: S (under an hour), M (one wave), L (more than one wave: split it).

## What a good ticket has

Use `templates/ticket.md`. A ticket is one change with one acceptance line.

- A verb-first title that says the result ("Sample background and condition from the catalogue").
- **Needs**: ticket ids that must be done first. Tickets with no shared need can run in parallel.
- **Files**: the ones it will most likely touch (a hint, not a fence; the fence is the package's
  owned paths).
- **Done when**: observable and testable. Bad: "sampler works". Good: "with seed 1 and n 50 000
  the share of each condition is within 0.5 percentage points of the catalogue's prevalence
  (test), and two calls with the same seed return identical cards (test)".
- **Notes**: traps you found while reading the code, links to the lines that matter.
- 3 to 8 tickets per work package. More means the package is too big.

## Rules

1. **Do not restate the architecture.** Link to it. A work package that copies the component file
   goes stale.
2. **Do not invent numbers.** Medical values come from the catalogue with sources (C2). If a
   ticket needs a value that does not exist, the ticket says "use the catalogue's entry; if
   missing, add it as `assumption` with a note and list it in the report".
3. **Every package states which invariants it could break** and how the builder proves it did not.
4. **Keep the old thing working.** If a package replaces something that runs today (for example
   the patient generator), it includes a ticket for the adapter or the switch, and an equivalence
   or comparison test.
5. **Tests are part of each ticket**, not a ticket at the end.
6. **Prefer additive changes** behind a version or flag until the switch-over ticket.
7. **Write for an agent with no memory of this conversation.** Paths, commands, names. No "as
   discussed".

## Package map (`packages/<component>/README.md`)

One table and one graph:

```
| WP | Outcome | Size | Needs | Provides contract | Owned paths | Review |
|----|---------|------|-------|-------------------|-------------|--------|
```

plus a dependency graph in text (`WP-C1-1 → WP-C1-2, WP-C1-3`), the suggested wave plan (which
packages can run together), and the open questions you posted.

## Checklist before you hand over

- [ ] Every sub-whole of the component file is covered by a package or listed as deferred with a reason.
- [ ] No two open packages own the same path.
- [ ] Every provided contract has a "publish the contract" ticket first.
- [ ] Every package has machine-checkable acceptance and names its invariants.
- [ ] No ticket depends on a decision that only a human can make without being marked blocked.
- [ ] A builder could start any unblocked package from its file alone.
