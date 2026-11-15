"""Render the trailer (video/dots/index.html?trailer, trailer2.js) to an mp4. Timing and effects come from
trailer_assets/timeline.json (build_timeline.py).

The page is played on a fake clock, one frame at a time, in the installed Chrome (picture, including the ink filter),
and the sound is mixed here from the same files and cues the page uses (music excerpt, narration at 1.2x, the two
synthesized effects). Needs: playwright, imageio-ffmpeg, numpy, scipy (a scratch venv is enough).

    python video/render_trailer.py [--seconds 59.5] [--fps 30] [--size 1280x960] [--out video/generated/out/trailer.mp4]

The dots server must be up: .venv/bin/python -m note_reader.server (port 8770).
"""
import argparse, json, subprocess, sys, tempfile, wave
from pathlib import Path

import numpy as np
from scipy.io import wavfile
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
DOTS = ROOT / "dots"
SR = 48000
RATE = 1.05
FF = imageio_ffmpeg.get_ffmpeg_exe()


def load_stereo(path, tmp, atempo=None):
    """Any wav -> float32 stereo at SR (optionally pitch-preserving tempo change through ffmpeg)."""
    out = Path(tmp) / (Path(path).stem + "_conv.wav")
    cmd = [FF, "-y", "-loglevel", "error", "-i", str(path)]
    if atempo: cmd += ["-filter:a", f"atempo={atempo}"]
    cmd += ["-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(out)]
    subprocess.run(cmd, check=True)
    sr, a = wavfile.read(out)
    return a.astype(np.float32) / 32768.0


def tone(buf, f, t, dur, vol, f2=None):
    """The page's WebAudio tone: sine, exponential attack to vol in 10 ms, exponential decay to 0.0001 at dur."""
    n = int(dur * SR); x = np.arange(n) / SR
    if f2:
        half = dur * 0.5
        fr = np.where(x < half, f * (f2 / f) ** (x / half), f2)
    else:
        fr = np.full(n, f)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    with np.errstate(all="ignore"):
        g = np.where(x < 0.01, 0.0001 * (vol / 0.0001) ** (x / 0.01), vol * (0.0001 / vol) ** ((x - 0.01) / (dur - 0.01)))
    sig = (np.sin(ph) * g).astype(np.float32)
    i = int(t * SR); j = min(len(buf), i + n)
    if i < len(buf): buf[i:j, 0] += sig[: j - i]; buf[i:j, 1] += sig[: j - i]


def normalize(path, tmp, target=-14.0, tp=-1.5, lra=11.0):
    """Two-pass EBU R128 loudness normalisation (YouTube plays at about -14 LUFS)."""
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(path), "-af", f"loudnorm=I={target}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    blob = r.stderr[r.stderr.rindex("{"): r.stderr.rindex("}") + 1]
    m = json.loads(blob)
    out = Path(tmp) / "mix_norm.wav"
    flt = (f"loudnorm=I={target}:TP={tp}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(path), "-af", flt, "-ar", str(SR), "-c:a", "pcm_s16le", str(out)], check=True)
    print(f"loudness: {m['input_i']} LUFS (peak {m['input_tp']} dBTP) -> {target} LUFS")
    return out


def mix_audio(seconds, tmp):
    TL = json.load(open(DOTS / "trailer_assets" / "timeline.json"))
    n = int(seconds * SR); buf = np.zeros((n, 2), dtype=np.float32)
    cues = json.load(open(DOTS / "trailer_assets" / "cues.json"))        # [at, id, text, dur]
    spans = [(c[0], c[0] + c[3] / (c[4] if len(c) > 4 else RATE)) for c in cues]
    # music: excerpt from 18.8 s, only until 10.5 s (it stops when the visualisation starts), ducked under the voice
    MUSIC_OFFSET, MUSIC_OUT, MUSIC_FADE, MUSIC_VOL = 18.8, TL["music_out"], 3.0, 0.22
    m = load_stereo(DOTS / "audio" / "excerpt.wav", tmp)
    seg = m[int(MUSIC_OFFSET * SR): int((MUSIC_OFFSET + MUSIC_OUT + MUSIC_FADE) * SR)].copy()
    t = np.arange(len(seg)) / SR
    duck = np.ones_like(t)
    for a, b in spans: duck[(t >= a) & (t < b)] = 0.35
    k = np.ones(int(0.03 * SR)) / int(0.03 * SR)
    duck = np.convolve(duck, k, mode="same")
    gain = MUSIC_VOL * (1 - (1 - np.minimum(1, t / 3.5)) ** 2) * duck
    gain *= np.clip((MUSIC_OUT + MUSIC_FADE - t) / MUSIC_FADE, 0, 1)
    seg *= gain[:, None]
    buf[: len(seg)] += seg[: n]
    # narration at 1.2x, pitch kept
    for cue in cues:
        at, cid = cue[0], cue[1]
        v = load_stereo(DOTS / "trailer_assets" / f"{cid}.wav", tmp, atempo=(cue[4] if len(cue) > 4 else RATE))
        i = int(at * SR); j = min(n, i + len(v))
        if i < n: buf[i:j] += v[: j - i]
    # effects (same recipes as sfx() in trailer2.js), at the times in timeline.json
    for at_, kind in TL["sfx"]:
        if kind == "tick": tone(buf, 2400, at_, 0.04, 0.05); tone(buf, 1200, at_, 0.03, 0.03)
        elif kind == "tock": tone(buf, 1800, at_, 0.04, 0.04); tone(buf, 900, at_, 0.03, 0.03)
        elif kind == "bling": tone(buf, 1318.5, at_, 1.1, 0.08); tone(buf, 1975.5, at_ + 0.1, 1.3, 0.07); tone(buf, 2637, at_ + 0.1, 0.5, 0.025); tone(buf, 3951, at_ + 0.2, 0.4, 0.015)
        elif kind == "bling2": tone(buf, 1975.5, at_, 1.0, 0.1); tone(buf, 2637, at_ + 0.05, 0.5, 0.04)
        else:
            tone(buf, 110, at_, 1.6, 0.5, 42); tone(buf, 55, at_, 1.8, 0.35)
            for f, v in ((523.3, 0.05), (784, 0.04), (1046.5, 0.03)): tone(buf, f, at_ + 0.15, 2.2, v)
    peak = float(np.abs(buf).max())
    if peak > 0.98: buf *= 0.98 / peak
    out = Path(tmp) / "mix.wav"
    wavfile.write(out, SR, (buf * 32767).astype(np.int16))
    print(f"audio mixed: {seconds:.1f} s, peak {peak:.2f}")
    return normalize(out, tmp)


def render_frames(seconds, fps, size, silent_mp4, base_url):
    from playwright.sync_api import sync_playwright
    w, h = (int(x) for x in size.split("x"))
    n = int(round(seconds * fps))
    enc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(silent_mp4)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.add_init_script("""window.__fake = null; const real = performance.now.bind(performance);
                              performance.now = () => window.__fake === null ? real() : window.__fake;""")
        pg.goto(f"{base_url}/dots/index.html?trailer&mute&r=render", wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(2500)      # images, fonts and cues load
        pg.evaluate("window.__fake = 1000")
        pg.mouse.click(w // 2, h // 2)     # start(): t = 0 at fake 1000 ms
        for f in range(n):
            pg.evaluate("t => { window.__fake = t; }", 1000 + f / fps * 1000)
            pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=93))
            if f % 150 == 0: print(f"frame {f}/{n}", flush=True)
        br.close()
    enc.stdin.close(); enc.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=json.load(open(DOTS / "trailer_assets" / "timeline.json"))["len"] - 0.2)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--url", default="http://127.0.0.1:8770")
    ap.add_argument("--out", default=str(ROOT / "generated" / "out" / "trailer.mp4"))
    ap.add_argument("--audio-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        mix = mix_audio(a.seconds, tmp)
        if a.audio_only:
            subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(mix), str(out.with_suffix(".m4a"))], check=True); return
        silent = Path(tmp) / "silent.mp4"
        render_frames(a.seconds, a.fps, a.size, silent, a.url)
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mix), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
