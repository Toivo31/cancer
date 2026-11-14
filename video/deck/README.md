# Presentation deck (source)

Source of the slide deck built from the trailer's scenes (claude.ai Slides artifact). Same look as the video:
warm white paper, dark ink, Inter, blue only for the fast track.

- `deck.json`: title, slide order and sections.
- `deck.css`: the shared style.
- `slides/<id>.html`: one slide each; the speaker notes (`<aside>`) hold the narration line for that slide.
- `images/`: the two stills from the video. In the slides they are referenced by their uploaded ids:
  `/_blob/2e5cf60c1565899e9fa566952c6ae824` = `images/visual_crop.jpg` (the pathway graph with the fast track, cropped; `images/visual.jpg` is the uncropped still),
  `/_blob/a6878672577134b5bd01528af1d6a916` = `images/notes.jpg` (the note reader).

The live deck (present, export to PowerPoint or PDF) is the claude.ai artifact; this folder is a copy for the repo.
