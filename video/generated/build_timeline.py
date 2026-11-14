"""Build the punchy cut's timing (trailer2.js) from the narration recordings.

Measures where each phrase starts in every line's recording (the longest pauses split the phrases), then schedules
every scene, every on-screen line and every sound effect from those onsets. Writes video/dots/trailer_assets/cues.json
and timeline.json. Re-run it whenever the recordings change.

    python video/generated/build_timeline.py                       # the files already in trailer_assets/ (s1.wav ... s7.wav)
    python video/generated/build_timeline.py --from-dir ~/rec --rate 1.0     # your own recordings, played at natural speed

Recordings: one file per line, s1 ... s7, any format ffmpeg reads (.wav, .m4a, .mp3). Silence at the start and end
is trimmed. Needs numpy, scipy and imageio-ffmpeg.
"""
import argparse, difflib, json, re, subprocess, shutil
from pathlib import Path

import numpy as np
from scipy.io import wavfile
import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "dots" / "trailer_assets"
FF = imageio_ffmpeg.get_ffmpeg_exe()


def to_wav(src, dst):
    """Any audio file -> mono 24 kHz wav with leading and trailing silence trimmed."""
    flt = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(src), "-af", flt, "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(dst)], check=True)


def phrase_onsets(path, k):
    """Start times (s) of k phrases: the k-1 longest pauses inside the speech split it."""
    sr, a = wavfile.read(path); a = a.astype(float); a = a.mean(1) if a.ndim > 1 else a
    w = int(sr * 0.01); n = len(a) // w
    rms = np.array([np.sqrt((a[i * w:(i + 1) * w] ** 2).mean()) for i in range(n)])
    on = rms > rms.max() * 0.06
    segs, st = [], None
    for i, v in enumerate(on):
        if v and st is None: st = i
        if not v and st is not None: segs.append([st, i]); st = None
    if st is not None: segs.append([st, n])
    segs = [g for g in segs if g[1] - g[0] >= 12]     # breaths and clicks are not phrases
    merged = []
    for s, e in segs:                       # pauses shorter than 60 ms are inside words
        if merged and s - merged[-1][1] < 6: merged[-1][1] = e
        else: merged.append([s, e])
    gaps = sorted(range(1, len(merged)), key=lambda i: merged[i][0] - merged[i - 1][1], reverse=True)[: k - 1]
    starts = [merged[0][0]] + [merged[i][0] for i in sorted(gaps)]
    while len(starts) < k: starts.append(starts[-1])
    return [round(s * 0.01, 2) for s in starts], len(a) / sr


_WHISPER = None
def word_times(path, text):
    """Start time (s) of every word of the script line, from Whisper word timestamps aligned to the script
    (so a misheard word still gets its time). Returns None if faster-whisper is not installed."""
    global _WHISPER
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    if _WHISPER is None: _WHISPER = WhisperModel("small.en", device="cpu", compute_type="int8")
    raw = subprocess.run([FF, "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    segs, _ = _WHISPER.transcribe(audio, word_timestamps=True, language="en")
    heard = [(re.sub(r"[^\w']", "", w.word.lower()), float(w.start)) for sg in segs for w in sg.words]
    want = re.findall(r"[\w']+", text.lower())
    t = [None] * len(want)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, want, [h for h, _ in heard]).get_opcodes():
        if op in ("equal", "replace"):
            for k in range(i2 - i1):
                j = j1 + min(j2 - j1 - 1, round(k * (j2 - j1) / max(1, i2 - i1)))
                if 0 <= j < len(heard): t[i1 + k] = heard[j][1]
    for k in range(len(t)):                 # words Whisper missed: the next known time
        if t[k] is None: t[k] = next((x for x in t[k:] if x is not None), heard[-1][1] if heard else 0.0)
    return want, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", help="folder with your recordings s1 ... s7 (any audio format)")
    ap.add_argument("--script", default="script_v3.json", help="script file in video/generated/")
    ap.add_argument("--rate", type=float, help="playback speed (default: the script's, 1.1 for the placeholder voice)")
    a = ap.parse_args()
    script = json.load(open(HERE / a.script))
    rate = a.rate or script.get("rate", 1.0)
    L = {}
    R = {line["id"]: line.get("rate", rate) for line in script["lines"]}      # per-line speed (a locked line keeps its own)
    for line in script["lines"]:
        lid = line["id"]
        if a.from_dir:
            src = next(Path(a.from_dir).expanduser().glob(f"{lid}.*"))
            to_wav(src, ASSETS / f"{lid}.wav")
        ons, dur = phrase_onsets(ASSETS / f"{lid}.wav", len(line["phrases"]))
        wt = word_times(ASSETS / f"{lid}.wav", line["text"])
        if wt:                              # Whisper: each phrase starts at its first word
            words, times = wt; ons, k = [], 0
            for ph in line["phrases"]:
                ons.append(round(times[min(k, len(times) - 1)], 2)); k += len(re.findall(r"[\w']+", ph))
        L[lid] = {"text": line["text"], "ons": ons, "dur": dur, "words": dict(zip(*wt)) if wt else {}}

    # ---- schedule: t is the clock; at(id, start) places a line, on(id, i) is the absolute start of its phrase i
    cues, at = [], {}
    def place(lid, t): at[lid] = t; cues.append([round(t, 2), lid, L[lid]["text"], round(L[lid]["dur"], 2), R[lid]])
    def on(lid, i): return round(at[lid] + L[lid]["ons"][i] / R[lid], 2)
    def end(lid): return round(at[lid] + L[lid]["dur"] / R[lid], 2)
    TL = {}
    word = lambda lid, w, fb: round(at[lid] + L[lid]["words"][w] / rate, 2) if w in L[lid]["words"] else fb
    place("n1", 0.3)                                                    # hook: the gap, then the one real picture
    TL["hook"] = {"a": 0.3, "n123": round(on("n1", 0) + 0.3, 2), "n207": on("n1", 1), "end": round(end("n1") + 0.5, 2)}
    clip = round(TL["hook"]["end"] + 2 / 1.5, 2)                       # the 2 s clip at 1.5x, then its last frame held 1 s
    TL["scan"] = {"a": TL["hook"]["end"], "clip": clip, "end": round(clip + 1.0, 2)}
    t = TL["scan"]["end"]; place("n2", t)                               # the two failure modes: LOCKED, as approved (trailer.js)
    TL["modes"] = {"a": t, "l1": round(t + 0.5, 2), "l2": round(t + 2.0, 2), "end": round(t + 8.0, 2)}
    t = TL["modes"]["end"]; place("n3", t + 0.2)                        # the framework, three lines
    TL["fw"] = {"a": t, "h": on("n3", 0), "l1": on("n3", 1), "l2": on("n3", 2), "l3": on("n3", 3), "end": round(end("n3") + 1.5, 2)}
    t = TL["fw"]["end"]; place("n4a", t + 0.3)                          # the visualisation: chart, then the flow, then the fast track
    TL["anim"] = {"a": t, "dots": on("n4a", 1), "fast": word("n4a", "automated", on("n4a", 2)), "end": round(end("n4a") + 1.0, 2)}
    t = TL["anim"]["end"]; place("n4b", t + 0.2)                        # the manifesto, its points on the words
    TL["man"] = {"a": t, "lab": on("n4b", 0), "m1": on("n4b", 1), "i1": on("n4b", 2), "i2": on("n4b", 3), "end": round(end("n4b") + 2.5, 2)}
    t = TL["man"]["end"]; place("n5", t + 0.3)                          # a model reads the note
    TL["doc"] = {"a": t, "end": round(max(t + 8.0, end("n5") + 1.5), 2)}
    t = TL["doc"]["end"]; place("n6", t + 0.8)                          # credit, the names on the words
    wd = L["n6"]["words"]
    nem = round(at["n6"] + wd["nemotron"] / rate, 2) if "nemotron" in wd else round(on("n6", 0) + 0.7 / rate, 2)
    ver = round(at["n6"] + wd["verda"] / rate, 2) if "verda" in wd else round(on("n6", 1) + 0.75 / rate, 2)
    TL["credit"] = {"a": t, "b1": on("n6", 0), "nem": nem, "b2": on("n6", 1), "ver": ver, "end": round(end("n6") + 1.0, 2)}
    t = TL["credit"]["end"]; place("n7", t + 0.2)                       # the suggestion, a beat, the punchline alone
    punch = round(end("n7") + 1.5, 2); place("n8", punch)
    TL["fin"] = {"a": t, "lab": on("n7", 0), "l1": on("n7", 1), "l2": on("n7", 2), "l3": on("n7", 3), "punch": punch, "repo": round(end("n8") + 1.5, 2)}
    TL["len"] = round(TL["fin"]["repo"] + 1.5, 2)
    TL["music_out"] = round(TL["scan"]["a"] - 3.0, 2)
    ticks = []; k = 0; tt = TL["anim"]["a"]                             # a clock under the waiting, stopping dead on the fast track
    while tt < TL["anim"]["fast"] - 0.05:
        ticks.append([round(tt, 2), "tick" if k % 2 == 0 else "tock"]); tt += 0.5; k += 1
    TL["sfx"] = ticks + [[nem, "bling"], [ver, "bling2"], [punch, "hit"]]
    TL["captions"] = ["n1", "n4a", "n4b", "n5"]                         # the rest is on screen in the same words
    json.dump(cues, open(ASSETS / "cues.json", "w"))
    json.dump(TL, open(ASSETS / "timeline.json", "w"), indent=1)
    for c in cues: print(f"{c[0]:6.2f}  {c[1]}  ends {c[0] + c[3] / rate:6.2f}  phrases {[on(c[1], i) for i in range(len(L[c[1]]['ons']))]}")
    print("length", TL["len"], "s")


if __name__ == "__main__":
    main()
