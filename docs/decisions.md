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
| D14 | Guardrail "no fewer tissue-confirmed diagnoses (2% noise)" added | provisional | Optimiser otherwise accepted "skip sampling" as a speed-up | `optimiser/search.py::guardrails` |
| D15 | Scenario-level clinical `needs` (e.g. tumour board needs PET-CT) constrain the optimiser | provisional | Optimiser otherwise let the board meet without staging | `optimiser:` block in scenario YAML |
| D16 | Stokstad calibration uses two structural overlaps not reported in the paper (on-time PET ordered at referral triage; part of the referral-to-treatment interval falls before the board) | provisional, needs Fig. 4 / authors | Published per-step medians chained in series exceed the 46.5-day median | `calibration.grid` in `scenarios/stokstad.yaml` |
| D17 | Dashboard headline for the Norwegian case = optimiser with the faster scanner (40%→88%); the no-new-equipment result (67%) is shown as a comparison | **needs Tuomas** | Same premise as the authors' 80%; but "no new equipment" may be the stronger pitch line | `demo/export.py::build_stokstad` (variant order) |
| D18 | Optimiser's 4th change "book tissue sampling at referral triage" kept | **needs clinical check** | Beyond the paper; plausible (straight-to-test) but unverified | add to `optimiser.needs` to forbid |
| D19 | Test results drawn independently given condition + attributes | provisional | Simplicity; correlated delays/results may explain the faster-PET over-prediction | `pathway_sim/patients.py` |
| D20 | Finnish scenario target = 90 days from first contact (display/optimiser target) | **needs Tuomas** | At 42 days every flowchart is 0% (Finnish pathway is ~100 d from first contact); no Finnish first-contact-to-treatment target found | `target_days` in `scenarios/finland_lung.yaml` |
| D21 | Server `urgent_lead_days`: fast-track patients book with a shorter lead (replaces negative extra_wait workaround) | provisional | Fast track in Finland is mostly about booking lead, not queue position | `pathway_sim/engine.py::_Server` |
| D22 | Optimiser accepts a change only if it helps in **each** of two training cohorts (noise-aware) | provisional | One cohort let noise through (Finland "GP first" passed train, failed held-out) | `Config.train_seeds` |
| D23 | Equity guardrail: no presentation group may get >1 day slower or >1 pp less often on time (groups with ≥10 cancers per cohort) | provisional | "Equal care" is the challenge; blocks gains bought at one group's expense | `Config.equity_*` |
| D24 | Two-step lookahead among the top-6 proposals when no single change helps | provisional | Some reorderings only help together | `Config.lookahead` |
| D25 | Decision-model reward = usable sampling result − days/30 (30 days "worth" one diagnosis) | **value judgement, needs Tuomas** | Needed to train from revealed outcomes | `--days-per-diagnosis` in `decision_model/in_loop.py` |
| D26 | Choice nodes can restrict which options are on offer (`availability`), and policies see queue state (`option_leads`) | provisional | Needed for the comparison-dependent test of the decision model (open Q12) and to stop per-patient choices overloading shared queues | `pathway_sim/engine.py` |
| D27 | Finnish headline = optimiser with reorder/standardise edits only (no fast track): book specialist visit on referral arrival; reserve treatment slot at board referral. "Urgent booking for every referred patient" shown as a conditional finding (0/50/100% of assumed lead reduction) | **needs Tuomas** | Independent review B1: fast-tracking everyone only swaps in the assumed urgent lead; the gain is the assumption | `demo/export.py::build_capacity_scenario`, `urgent_booking_conditional` |
| D28 | Guard and policy-rule names are validated at load time | settled | A typo silently evaluated to None | `pathway_sim/scenario.py` |
| D29 | Direction: online platform (build flowchart → attach JEV → train → simulate → optimise → rerun); JEV is an external API on decision points; stub with hardcoded probabilities until it exists | settled (Tuomas, 14 Nov) | End goal beyond the hackathon | `docs/platform/README.md` |
| D30 | Forks F1 to F7 of the platform plan (decision points, sampling, JEV contract and owner, web stack, hosting and data, Sunday cut, `standardise` under JEV) | **needs Tuomas** | Each has a lean in the plan; none is decided | `docs/platform/README.md` section 5 |
