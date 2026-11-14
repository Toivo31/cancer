"""Generate still frames for the trailer's film-world shots (Gemini image model, standard library only).

    python video/generated/stills.py --shot b2_slip          # one still -> video/generated/out/b2_slip_still.png
    python video/generated/stills.py --all                   # every shot in shots.json that has no still yet
    python video/generated/stills.py --shot b2_slip --force  # regenerate

Veo is not available on our project, so these stills are animated in the edit (slow push-in or pan).
Key: GEMINI_API_KEY in .env. Model: --model, else STILLS_MODEL in .env, else gemini-3-pro-image.
No readable text or numbers are generated; those are overlaid in the edit.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
API = "https://generativelanguage.googleapis.com/v1beta"


def load_env() -> None:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def still(shot: dict, cfg: dict, model: str, force: bool) -> Path | None:
    out = HERE / "out" / f"{shot['id']}_still.png"
    if out.exists() and not force:
        print(f"[{shot['id']}] exists, skipped (use --force)")
        return out
    prompt = ("Still frame from a film. " + shot["prompt"].format(person=cfg["person"], style=cfg["style"])
              + " Avoid: " + cfg["negative"] + ". No subtitles, captions or any text in the image. 16:9.")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    req = urllib.request.Request(f"{API}/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"[{shot['id']}] API error {e.code}: {e.read()[:300]!r}")
        return None
    parts = (d.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    img = [p for p in parts if "inlineData" in p]
    if not img:
        print(f"[{shot['id']}] no image returned: {[p.get('text', '')[:150] for p in parts]}")
        return None
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(base64.b64decode(img[0]["inlineData"]["data"]))
    (HERE / "out" / f"{shot['id']}_still.prompt.txt").write_text(prompt + "\n")
    print(f"[{shot['id']}] saved {out.relative_to(ROOT)}")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model")
    a = ap.parse_args(argv)
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY in .env.")
    cfg = json.loads((HERE / "shots.json").read_text())
    shots = cfg["shots"] if a.all else [s for s in cfg["shots"] if s["id"] in a.shot]
    if not shots:
        sys.exit("Pick --shot <id> or --all. Ids: " + ", ".join(s["id"] for s in cfg["shots"]))
    model = a.model or os.environ.get("STILLS_MODEL") or "gemini-3-pro-image"
    for s in shots:
        still(s, cfg, model, a.force)


if __name__ == "__main__":
    main()
