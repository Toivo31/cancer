"""Narrator voice-over with Gemini TTS (standard library only).

    python video/generated/tts.py                    # all lines -> video/generated/out/vo/<id>.wav
    python video/generated/tts.py --line vo3_wait    # one line
    python video/generated/tts.py --voice Charon --model gemini-2.5-pro-preview-tts

Lines and the narrator style are in vo_lines.json. Key: GEMINI_API_KEY in .env.
Output: 24 kHz 16-bit mono WAV per line, plus durations printed for the edit.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import wave
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


def speak(text: str, style: str, voice: str, model: str, out: Path) -> float:
    body = {"contents": [{"parts": [{"text": f"{style}\n\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = urllib.request.Request(f"{API}/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"API error {e.code}: {e.read()[:400]!r}")
    part = d["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = base64.b64decode(part["data"])
    rate = 24000
    mime = part.get("mimeType", "")
    if "rate=" in mime:
        rate = int(mime.split("rate=")[1].split(";")[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return len(pcm) / 2 / rate


def tighten(path: Path, max_pause: float = 0.3, thresh: int = 500) -> float:
    """Cut leading/trailing silence and shorten pauses longer than max_pause (seconds). Returns new length."""
    import array
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate(); a = array.array("h", w.readframes(w.getnframes()))
    win = int(rate * 0.02)
    loud = [max(abs(x) for x in a[i:i + win]) > thresh for i in range(0, len(a), win)]
    if not any(loud):
        return len(a) / rate
    first = loud.index(True); last = len(loud) - 1 - loud[::-1].index(True)
    out, quiet, keep = array.array("h"), 0, int(max_pause / 0.02)
    for k in range(max(0, first - 2), min(len(loud), last + 3)):
        chunk = a[k * win:(k + 1) * win]
        if loud[k]:
            quiet = 0; out.extend(chunk)
        else:
            quiet += 1
            if quiet <= keep:
                out.extend(chunk)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(out.tobytes())
    return len(out) / rate


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", action="append", default=[])
    ap.add_argument("--voice", default=os.environ.get("TTS_VOICE", "Charon"))
    ap.add_argument("--model", default=os.environ.get("TTS_MODEL", "gemini-2.5-pro-preview-tts"))
    ap.add_argument("--suffix", default="", help="added to file names, e.g. _kore to compare voices")
    ap.add_argument("--lines", default="vo_lines.json", help="lines file in video/generated/ (vo_lines_60s.json for the 1-minute cut)")
    a = ap.parse_args(argv)
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY in .env.")
    cfg = json.loads((HERE / a.lines).read_text())
    lines = [l for l in cfg["lines"] if not a.line or l["id"] in a.line]
    total = 0.0
    for l in lines:
        out = HERE / "out" / "vo" / f"{l['id']}{a.suffix}.wav"
        sec = speak(l["text"], cfg["voice_style"], a.voice, a.model, out)
        sec = tighten(out)
        total += sec
        slot = l.get("slot")
        fit = "" if slot is None else (f"fits {slot:.1f} s" if sec <= slot else f"OVER by {sec - slot:.1f} s")
        print(f"{l['id']:<12} {sec:5.1f} s  from {l['at']}  {fit:<16} {out.relative_to(ROOT)}")
    print(f"total speech {total:.1f} s, voice {a.voice}, model {a.model}")


if __name__ == "__main__":
    main()
