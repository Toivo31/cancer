# Modal deployment checks, 14 November 2026

Live checkpoint: **2350**, immutable weight SHA256
`22570c201a9e3d25dcdf7aa904770a568328e034ccb5ac89623784707a7323e8`.
The stable endpoint name still contains1138. Use response provenance for identity.

The real one-GPU preflight in `step2350.json` verified:

- Original pretrained Nemotron generation, actual scoped history retrieval,
  two rounds, one tool call and84/128 generated tokens,21.82s generation.
- Prefix parameter identities unchanged; original decision tail/head restored.
- Uncached classifier scores identical before/after generation (maximum error0).
- 78.28GiB allocated;78.54GiB peak on this short request. This does not measure
  every maximum-length prompt or image combination.
- A public credential-free request with a four-token budget stopped at exactly
  four tokens and executed no tools; truncated generation was not appended.
- The actual teammate simulator adapter from `overnight/sim` called a secretless
  local proxy, then the hosted gateway, then native checkpoint2350 successfully.
  Its bridge rejects old checkpoint caches and checks live step/hash.

The earlier1138 migration smoke also verified off-mode score parity, bounded
output handling and rejection of another patient. The same runtime is used for2350.
Local checks:29 Python tests,11 JavaScript tests,18 actual Firefox browser checks;
packaged native runtime authentication/off-mode scoring also passed.

Four saved examples were regenerated using2350: the synthetic pathway and the
same three unchanged PAD-UFES-20 pictures. The three photo proposals agree with
their training labels. They are training examples, and this is not evidence of
useful image understanding or clinical performance. Original1138 recordings
remain separately labelled in the web directory.

Six previously selected text questions were reused as a small smoke check:
5/6 label agreement at2350 versus4/6 at1138. The computer-crash question now
proposes losing data. The MedQA9971 hormone/enzyme question regressed. These six
reused questions are not a new benchmark or a general improvement claim.

Generated summaries can overreach: the native sample recommends an action despite
the evidence-only instruction. They stay labelled as generated, fallible text,
separate from actual records; neither summaries nor relative candidate scores
should be represented as clinical evidence. Human review remains required.

Selection:2350 is a completed compatible curriculum checkpoint. The later2366
experimental reasoning pilot was considered, but its paired40-case raw-context
screen fell from29/40 to25/40. This was a deployment selection, with no changes
to training, its jobs, data, provider controls or timers.


An experimental text batching path was rejected after GPU relative-score differences reached0.01270 (about1.27percentage points) in the synthetic eight-choice case. Production retains the original independent encoding shapes. Accepted optimizations are deterministic generation-output caching with explicit hit accounting, fixed-image registration reuse, existing pooled-feature reuse, and a fast gateway response path. See the performance artifact for measured timings once recorded.
