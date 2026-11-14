# WP-<component>-<n>: <outcome in a few words>

| | |
|---|---|
| Component | C<k> `<component file>` , sub-whole P<j> |
| Status | not started / in progress (`<branch>`) / merged (`<commit>`) / dropped (why) |
| Size | S / M |
| Needs | WP ids, or contract tags it relies on |
| Provides | contract name and version, or "nothing outside the component" |
| Owned paths | folders and files this package may edit |
| May create | new files, exact names |
| Review required | yes (why) / no |
| Track | platform / submission |

## Outcome

One paragraph: what exists when this is done and how a person tries it (a command, a URL, a test).

## Why

Two or three sentences linking to the vision or the component file. What it unblocks.

## Interfaces

**Provides** (shape, version, where the JSON examples and the contract test live).

**Consumes** (what, from where, the tag or commit that is safe to build on).

## Acceptance (all machine-checkable)

- [ ] End to end: `<command>` gives `<observable result>`.
- [ ] Invariants: I<n> holds, shown by `<test>`.
- [ ] Edge: `<what happens with bad or extreme input>`.
- [ ] Fast tests of this package run in under 60 seconds; slower ones are marked `slow`.

## Out of scope

- …

## Things to look at and weigh (guidance, not a recipe)

- What to read first, with paths and line ranges.
- Trade-offs the builder will meet, and what matters on each side.
- Known traps.

## Decisions for the builder (leans; change them if you find a reason and say so)

- …

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | <WP>-T1 | Publish the contract: … | S | – | … |
| [ ] | <WP>-T2 | … | | | |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

Done, not done, commit range, how to run it, what others must know, what could not be tested.
