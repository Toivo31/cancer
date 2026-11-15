# Equal Care Pathways: three-slide website

Live: https://cancer123--equal-care-pathways-web.us-east.modal.run/?release=20261115-3

1. **Simulation:** an automatically moving branching graph, with no visible controls. Routes are simplified from the saved synthetic Finland baseline on `content/pages`. Intermediate steps and timing are compressed for illustration; no new search or live clinical simulation runs here.
2. **Decision Studio:** editable Text, Photo, and Custom question examples with explicit live computation. Text also contains the optional synthetic patient retrieval → context refinement → classification demonstration. Saved photo and retrieval outputs are clearly labelled and run without GPU use.
3. **Discussion & manifesto:** placeholder.

## Run and deploy

From `website/`:

```bash
python3 -m http.server 8780 --directory public
python3 -m pip install modal
modal deploy modal_app.py
```

Modal serves the website on CPU with scale-to-zero. Live computation uses the existing public decision gateway and checkpoint 2350; no new GPU app, credentials or weights are bundled. Organization access: [Modal invitation](https://modal.com/signup?token=dd6w00V0NL0JDEY0zPvPJ5uZ08k73wqyJLys8mplk8o&shareable-token=true&organization=true). Website visitors need no Modal account.

The browser SDK polls accepted jobs without repeating POST requests. Changing inputs invalidates pending display updates. Patient-record tools are disabled for custom questions; optional refinement defaults off. Reviews of live decisions are recorded separately. Saved-result comparisons stay local. Loading a saved photo result restores that result's original inputs.

## Provenance and limits

Simulation inspiration and route source: `content/pages` at `e9a278a` (`demo/flow.*` and `demo/data/flow_bundle.js`); exact source identity is in `public/simulation/SOURCE.md`. The display simplifies 300 saved synthetic patient routes and runs an illustrative, compressed animation. No clinical accuracy or time-saving claim is made by this display.

The medical text question is an authored teaching example, not a benchmark result. Photo assets are unchanged PAD-UFES-20 training images, not evaluation; attribution and hashes are in `public/samples/`. Scores are relative to the supplied options, not calibrated disease risk. The prior photo ablation does not establish useful image understanding. Human review is required; no clinical action is executed.

## Checks

`tests/browser_check.py` exercises the deployed UI in Firefox through local geckodriver, including real SDK paths with intercepted API responses. It verifies text, photo, custom, refinement and review contracts without paying for GPU calls. Actual live API checks are separate; never replay a scoring POST whose accepted job is pending.

Actual live completion and checks: [VALIDATION.md](VALIDATION.md).
