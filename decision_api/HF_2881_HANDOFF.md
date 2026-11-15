# HF and Modal release2881

Published model: https://huggingface.co/Toivo31/Nemotron-Birch

- Weights commit: `d9055bf542c278056f85658694e16482d70bb38c`.
- Helper/card/runtime commit: `9c187cef961c35bc700bed593c665c8b690d4a65`.
- Source: `Toivo31/project-birch-03/birch08-task-instructions-v1/checkpoint-00002881`.
- Trainable SHA256: `ec2bc28fd13d1933b6d18bee23e23928f326b24940467db7db4729426e7de16f`.
- Only inference weights/state/manifest are published; optimizer omitted.

The original card text is preserved as an exact prefix, including its historical
2350 benchmark table. The appended short section explains2881 and probability
prediction. No internal medical-retention evaluation was added to the card.

`decision_api/probability.py` is published standalone as `birch.py`. It exposes
`predict_proba(context, question, choices, reasoning_budget=0)` with ordered
probabilities, optional additional instructions/details and matching inline or
newline candidate serialization. Hosted mode needs no credentials or GPU.
`load_model()` downloads the published snapshot and pinned base for local NF4
inference. The HF runtime is a namespaced copy of the reviewed inference modules
(`birch_runtime`); its quantizer imports the relative shared-generation helper.
It does not overwrite a simulator's `decision_model` package. Requirements and
local high-memory CUDA setup are in the HF repository's `INFERENCE.md`.

Model card and actual downloaded helper were checked against live2881 with
reasoning off/on. Native GPU preflight passed real tool retrieval, bounded
refinement, shared-prefix identities, branch restoration and exact before/after
classifier parity. This checks integration, not prediction correctness. The
computer-crash illustration selected an implausible choice on2881; existing
2350 benchmark claims were not relabelled as2881 results.

Modal source: `decision_api/modal_inference.py`. Stable legacy URL retains1138;
actual backend metadata is2881. Both default saved examples and the saved native
refinement are refreshed from2881, with2350 archives retained. The simulator
bridge also pins2881 and separates its cache by step/hash. No training files,
cloud training jobs or provider timers were changed. No night schedule added.

Evidence: `validation/checkpoint2881.json`. Local checks:31 Python tests,
11 JavaScript tests and18 browser checks. Model packaging and public helper
inference were additionally exercised. Deployment source now excludes nested
bytecode/test directories to prevent build races with local test compilation.
