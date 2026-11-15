# Equal Care Pathways: three-slide website

Live: https://cancer123--equal-care-pathways-web.us-east.modal.run/?release=20261115-5

1. **Simulation:** an automatically moving vertical branching graph, with no visible controls. Routes are simplified from the saved synthetic Finland baseline on `content/pages`. Intermediate steps and timing are compressed for illustration; no new search or live clinical simulation runs here.
2. **Decision Studio:** saved Text and Photo examples plus live Custom questions. A separate example shows synthetic patient retrieval → context refinement → classification. All examples are listed together on one scrollable page. Saved photo and retrieval outputs are clearly labelled and run without GPU use.
3. **Discussion & manifesto:** placeholder.

## Run and deploy

From `website/`:

```bash
python3 -m http.server 8780 --directory public
python3 -m pip install modal
modal deploy modal_app.py
```

Modal serves the website on CPU with scale-to-zero. Live computation uses the existing public decision gateway and checkpoint 2350; no new GPU app, credentials or weights are bundled. Organization access: [Modal invitation](https://modal.com/signup?token=dd6w00V0NL0JDEY0zPvPJ5uZ08k73wqyJLys8mplk8o&shareable-token=true&organization=true). Website visitors need no Modal account.

The browser SDK polls accepted jobs without repeating POST requests. Changing custom inputs invalidates pending display updates. Patient-record tools are disabled for custom questions; optional refinement defaults off. Reviews of live decisions are recorded separately. Saved-result comparisons stay local. Selecting a photo displays its original inputs and saved output.

## Provenance and limits

Simulation inspiration and route source: `content/pages` at `e9a278a` (`demo/flow.*` and `demo/data/flow_bundle.js`); exact source identity is in `public/simulation/SOURCE.md`. The display simplifies 300 saved synthetic patient routes and runs an illustrative, compressed animation. No clinical accuracy or time-saving claim is made by this display.

The medical text example is an exact recorded MedMCQA question and model response from archived checkpoint 1138; its displayed provenance is preserved. It is not a general accuracy or clinical-validation claim. Photo assets are unchanged PAD-UFES-20 training images, not evaluation; attribution and hashes are in `public/samples/`. Scores are relative to the supplied options, not calibrated disease risk. The prior photo ablation does not establish useful image understanding. Human review is required; no clinical action is executed.

## Checks

`tests/browser_check.py` exercises the deployed UI in Firefox through local geckodriver, including real SDK paths with intercepted API responses. It verifies text, photo, custom, refinement and review contracts without paying for GPU calls. Actual live API checks are separate; never replay a scoring POST whose accepted job is pending.

Actual live completion and checks: [VALIDATION.md](VALIDATION.md).

Decision Studio lists all examples on one scrollable page. Predefined medical text, patient retrieval, and photo examples use recorded results only. Medical text preserves archived checkpoint 1138 provenance; photos and retrieval retain checkpoint 2350. Only custom questions compute live. The first slide animates a vertical branching graph without controls.

The first graph is accompanied by six framework explanations: pathway configuration, available patient context, joint scoring of allowed actions with clinician review, optional record retrieval and context refinement, whole-pathway simulation, and optimiser proposals checked by rerunning the same cohort.
