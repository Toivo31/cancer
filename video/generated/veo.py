"""Generate the trailer's film-world shots with Google Veo through the Gemini API (standard library only).

    python video/generated/veo.py --list-models          # which Veo models this key can use
    python video/generated/veo.py --shot b3_waiting_room # one shot -> video/generated/out/b3_waiting_room.mp4
    python video/generated/veo.py --all                  # every shot in shots.json

Key: GEMINI_API_KEY in .env (or the environment). Each shot costs Gemini credits; generate one, check
it, then the rest. Model: --model, else VEO_MODEL in .env, else the newest Veo model the key lists.
Shots and prompts are in shots.json; on-screen text and numbers are added in the edit, not generated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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


def key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        sys.exit("Set GEMINI_API_KEY in .env (create it at aistudio.google.com).")
    return k


def call(method: str, url: str, body: dict | None = None, timeout: float = 120) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"x-goog-api-key": key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"API error {e.code}: {e.read()[:600].decode(errors='replace')}")


def veo_models() -> list[str]:
    out, token = [], ""
    while True:
        d = call("GET", f"{API}/models?pageSize=200" + (f"&pageToken={token}" if token else ""))
        out += [m["name"].split("/", 1)[1] for m in d.get("models", []) if "veo" in m["name"].lower()]
        token = d.get("nextPageToken", "")
        if not token:
            return sorted(out)


def generate(shot: dict, cfg: dict, model: str) -> Path:
    prompt = shot["prompt"].format(person=cfg["person"], style=cfg["style"])
    body = {"instances": [{"prompt": prompt}],
            "parameters": {"aspectRatio": "16:9", "negativePrompt": cfg["negative"], "personGeneration": "allow_adult"}}
    print(f"[{shot['id']}] {model}: starting")
    op = call("POST", f"{API}/models/{model}:predictLongRunning", body)
    name = op["name"]
    while not op.get("done"):
        time.sleep(10)
        op = call("GET", f"{API}/{name}")
        print(f"[{shot['id']}] waiting…")
    if "error" in op:
        sys.exit(f"[{shot['id']}] failed: {op['error']}")
    resp = op.get("response", {})
    samples = (resp.get("generateVideoResponse") or resp).get("generatedSamples") or resp.get("generatedVideos") or []
    if not samples:
        sys.exit(f"[{shot['id']}] no video returned (maybe filtered): {json.dumps(resp)[:500]}")
    uri = samples[0]["video"]["uri"]
    out = HERE / "out" / f"{shot['id']}.mp4"
    out.parent.mkdir(exist_ok=True)
    req = urllib.request.Request(uri, headers={"x-goog-api-key": key()})
    with urllib.request.urlopen(req, timeout=300) as r:
        out.write_bytes(r.read())
    (HERE / "out" / f"{shot['id']}.prompt.txt").write_text(prompt + "\n")
    print(f"[{shot['id']}] saved {out.relative_to(ROOT)}")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--list-models", action="store_true")
    a = ap.parse_args(argv)
    load_env()
    if a.list_models:
        print("\n".join(veo_models()) or "no Veo models available for this key")
        return
    cfg = json.loads((HERE / "shots.json").read_text())
    shots = cfg["shots"] if a.all else [s for s in cfg["shots"] if s["id"] in a.shot]
    if not shots:
        sys.exit("Pick --shot <id> or --all. Ids: " + ", ".join(s["id"] for s in cfg["shots"]))
    model = a.model or os.environ.get("VEO_MODEL") or (veo_models() or [""])[-1]
    if not model:
        sys.exit("No Veo model available for this key (try --list-models).")
    for s in shots:
        generate(s, cfg, model)


if __name__ == "__main__":
    main()
