# Website validation — 15 November 2026

- Three static integrity tests pass: HTML dependencies, JavaScript module dependencies, and the 300-route simplified export.
- All 20 Firefox desktop/mobile checks pass on the final release. They cover exactly three slides; no controls in the simulation; graph branching and actual patient-dot motion; editable Text, Photo and Custom requests; native retrieval contract; separate review; saved-input restoration; pending-job polling without replaying POST; stale-result suppression; and mobile overflow. API contract checks intercept responses in the browser and do not claim live model execution.
- A separate real request to the public Modal gateway completed on checkpoint 2350. The two-choice appointment-policy example proposed Patient B (the urgent referral). Submission returned HTTP 202 with CORS allowed; the accepted job was polled without repeating its POST. See [recorded validation response](validation/live-score.json). This is one integration check, not a general accuracy claim.
- Modal bundles normalise file modification times. The website disables conditional responses and caching for application assets and versions script/style entry points, avoiding old scripts after a redeploy.

The simulation compresses saved synthetic routes and timing. There is no live optimiser or clinical action in the graph. Saved examples do not start paid inference; live computation is explicit.
