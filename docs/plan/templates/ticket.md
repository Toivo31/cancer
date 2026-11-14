# Ticket template

Tickets live as rows in their work package's table. Use this long form only when a row is not
enough (a ticket with several traps or a tricky acceptance).

```
### <WP>-T<n>: <verb-first title that says the result>

Size: S | M            Needs: <ticket ids or "–">            Blocked: <question id or "no">

Files (likely): <paths>

Do: two to five sentences. What changes, in behaviour terms.

Done when:
- <observable, testable statement>
- <the test that proves it, by name or description>

Notes: traps, links to code (`path:line`), the reason behind any constraint.
```

Good acceptance lines:

- "Two calls of `sample_cohort(catalogue, n=500, seed=7)` return equal cards (test)."
- "A card's revealed view has no key from the hidden section; the type has no such field (test
  that fails if one is added)."
- "`GET /api/projects/{p}/cohorts/{c}/cards/17` returns the public and revealed parts only unless
  `?reveal=all` is given and the project is in teaching mode (two tests)."

Bad acceptance lines: "works", "is fast", "handles errors", "matches the spec".
