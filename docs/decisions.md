# Decisions log (provisional unless marked settled)

Each entry: what, why, how to change it. Flag to Tuomas before it hardens.

| # | Decision | Status | Why | How to change |
|---|---|---|---|---|
| D1 | Flowchart is a DAG with `after` / `after_any` prerequisites and guards, not a linear list | provisional | The Stokstad optimal pathway is mostly *parallel* ordering (PET-CT + exercise test at once, sampling while treatment is booked); a sequence cannot express it | `pathway_sim/scenario.py` + contract |
| D2 | Three resource types: `server` (capacity queue), `delay` (wait drawn from a published distribution), `batch` (weekly tumour board) | provisional | Stokstad re-timed patients with observed waits (delay mode); Finland needs emergent queues (server mode); tumour board is batching, not queueing | per-resource `type` in scenario YAML |
| D3 | Stokstad check uses delay mode; Finnish scenario uses capacity mode | provisional (lean A) | Faithful to the paper's method; capacity only where we have to invent it anyway | scenario YAML |
| D4 | First run = hand-written starting flowchart + `RulePolicy` | provisional (open Q1) | No simulated doctors; the decision model has nothing to learn from before a first run | swap `--policy` |
| D5 | Guardrails: missed cancers ≤ baseline on the same patients; capacity enforced by queues; target 42 days | provisional (open Q9) | Prevents "faster by skipping tests" | `optimiser/config` |
| D6 | Optimiser accepts on training cohort rerun (common random numbers), reports on a held-out cohort | provisional (open Q8) | Best-of-many on the same patients selects on noise | `optimiser/search.py` |
| D7 | Scope: lung cancer only | provisional (open Q14) | One validation target exists for lung | scenario files |
| D8 | Finnish scenario clock starts at first contact | provisional (fork D) | Finland loses time before referral; Goal 3 framing | `clock_start` |
| D9 | Equity shown as a split by presentation group (site-specific vs non-specific symptoms) | provisional (open Q2) | Cheap to simulate; cited evidence that non-specific presenters wait longer | `groups` in scenario |
| D10 | Optimiser search space: reorder + parallelise first, fast-track second | provisional (fork C) | Matches the evidence on reordering; fast tracks have crowd-out risk | operator list |
| D11 | Decision model: rule policy drives runs; Jev-type model trained to imitate and benchmarked vs dot-product at one choice node | provisional (fork B, Tuomas: "idk") | Model needs a training signal; imitation is the honest available one | `--policy model` |
| D12 | Demo = static HTML dashboard reading a JSON bundle | settled (Tuomas: yes) | Easy to show, no server | — |
| D13 | Work pushed to one branch `overnight/sim` | settled (Tuomas) | Visible to team in the morning | — |
