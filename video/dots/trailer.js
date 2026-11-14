"use strict";
// Trailer preview, one-minute cut (index.html?trailer). An animatic of script v3 (docs/project-docs/
// trailer-script-v3.md on overnight/sim) built from: Gemini stills (slow push-ins), the 60 s voice-over
// (one natural-speed file per line in trailer_assets/, played at 1.2x with pitch kept; cues.json), the dot
// scenes and the note popup, the product pitch, the proof card and the ending. Clock: wall time.
// The picture is drawn in the top 85% of the frame; subtitles have their own band at the bottom.
// Music: audio/excerpt.wav (git-ignored) starts at once from excerpt 8.8 s, so its drop (excerpt 49.8 s)
// lands at 0:41 when the Norwegian piles dissolve; hard stop at 0:58.

const TRAILER = (() => {
  if (FINAL.active) return FINAL;          // ?final: Tuomas's final script (trailer_final.js)
  const active = qs.has("trailer");
  if (!active) return { active: false };
  help.classList.add("hidden"); st.ui = false; st.playing = false;
  FLOW.half = true; FLOW.every = 6; FLOW.simple = true; HALF_DOTS = true;      // draw every other patient; counts still use all of them

  const LEN = 69.2, PL = 19, P0 = 5.8, IBM = 999, DROP = 31, MUSIC_OFFSET = 18.8, MUSIC_OUT = 2.3, MUSIC_FADE = 3, MUSIC_VOL = 0.22;  // music (with its crackle) stops when the visualisation starts   // drop at excerpt 49.8 lands at 0:31 (OPTIMISE card)
  // the simulation scene is blue and grey only: every other colour drawn to the canvas is turned into its grey (blue stays)
  let monoOn = false;
  function toGrey(c) {
    let r, g, b, a = 1, m;
    if ((m = c.match(/^rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+))?\s*\)/))) { r = +m[1]; g = +m[2]; b = +m[3]; if (m[4] !== undefined) a = +m[4]; }
    else if ((m = c.match(/^#([0-9a-f]{6})$/i))) { r = parseInt(m[1].slice(0, 2), 16); g = parseInt(m[1].slice(2, 4), 16); b = parseInt(m[1].slice(4), 16); }
    else return c;
    if (b >= r + 50 && b >= g + 10 && FLOW.laneInk) return c;   // blue only for the fast-track line itself
    const y = Math.round(0.3 * r + 0.59 * g + 0.11 * b);
    return a < 1 ? `rgba(${y},${y},${y},${a})` : `rgb(${y},${y},${y})`;
  }
  for (const k of ["fillStyle", "strokeStyle"]) {
    const d = Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype, k);
    Object.defineProperty(CanvasRenderingContext2D.prototype, k, { get: d.get, configurable: true, set(v) { d.set.call(this, monoOn && typeof v === "string" ? toGrey(v) : v); } });
  }
  const PIC = 0.9;                        // simulation scenes are zoomed out to this share; stills stay full frame
  // narration: one file per line (natural speed), each played at 1.2x with pitch preserved at its cue time
  const RATE = 1.05, music = new Audio("audio/excerpt.wav"); music.preload = "auto";
  let started = false, CAPS = [], SPANS = [], LINES = [];
  const NOCAP = new Set(["v2_rule", "v4a_modes", "v5_pitch", "v6c_build", "v7_end", "v8_punch"]);
  fetch("trailer_assets/cues.json").then(r => r.json()).then(c => {
    LINES = c.map(([at, id, text, dur, rate = RATE]) => { const au = new Audio(`trailer_assets/${id}.wav`); au.preload = "auto"; au.playbackRate = rate; au.preservesPitch = true; return { at, id, au, text, dur: dur / rate * RATE, played: false }; });
    SPANS = LINES.map(l => [l.at, l.at + l.dur / RATE, l.text]);
    CAPS = SPANS.filter((x, i) => !NOCAP.has(LINES[i].id));
  }).catch(() => {});

  const img = {};
  for (const id of ["a2_consultation", "a4_stain", "b2_slip", "b3_waiting_room", "b4_unfold", "b9_door"]) {
    const im = new Image(); im.src = `trailer_assets/${id}_still.png`; img[id] = im;
  }
  for (const id of ["scan_wide", "scan_close"]) { const im = new Image(); im.src = `trailer_assets/${id}.webp`; img[id] = im; }
  const SCAN = [], NSCAN = 49;               // the 2 s scanner clip, 24 fps frames
  for (let i = 1; i <= NSCAN; i++) { const im = new Image(); im.src = `trailer_assets/scanclip/f${String(i).padStart(3, "0")}.jpg`; SCAN.push(im); }
  const CLIP_END = 3.8 + 2 / 1.5, COLOUR = [3.8, CLIP_END + 0.5];   // the 2 s clip at 1.5x speed, then its last frame held for 0.5 s                 // one scanner shot, in colour                 // the scanner shots keep their colours (canvas filter off)
  let filterOn = null;

  // clock: wall time from the click (?mute: no sound). Space pauses and resumes.
  const mute = qs.has("mute"); let t0 = 0, pausedAt = null;
  function start() {
    if (started) {
      if (pausedAt === null) { pausedAt = T(); music.pause(); LINES.forEach(l => l.au.pause()); }
      else { t0 = performance.now() / 1000 - pausedAt; pausedAt = null; LINES.forEach(l => { if (l.played && !l.au.ended && l.au.currentTime > 0) l.au.play(); }); }
      return;
    }
    started = true; const from = +(qs.get("from") || 0);
    if (!mute) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { ac = null; } }
    SFX.forEach(f => { f.done = from > f.at + 0.2; }); t0 = performance.now() / 1000 - from;
    LINES.forEach(l => { l.played = from > l.at + 0.2; });
  }
  window.addEventListener("click", start);
  window.addEventListener("keydown", e => { if (e.key === " ") { start(); e.stopImmediatePropagation(); e.preventDefault(); } }, true);
  const T = () => (!started ? +(qs.get("from") || 0) : pausedAt !== null ? pausedAt : performance.now() / 1000 - t0);

  // sound effects, synthesized (no files): a bling on the build credit, a low hit under the punchline
  let ac = null; const SFX = [{ at: 45.7, kind: "bling", done: false }, { at: 47.5, kind: "bling2", done: false }, { at: 63.4, kind: "hit", done: false }];
  function tone(f, t, dur, vol, type = "sine", f2 = null) {
    const o = ac.createOscillator(), g = ac.createGain(); o.type = type; o.frequency.setValueAtTime(f, t);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur * 0.5);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  function sfx(kind) {
    if (!ac) return; const t = ac.currentTime + 0.02;
    if (kind === "bling") { tone(1318.5, t, 1.1, 0.16); tone(1975.5, t + 0.1, 1.3, 0.14); tone(2637, t + 0.1, 0.5, 0.05); tone(3951, t + 0.2, 0.4, 0.03); }
    else if (kind === "bling2") { tone(1975.5, t, 1.0, 0.1); tone(2637, t + 0.05, 0.5, 0.04); }
    else { tone(110, t, 1.6, 0.5, "sine", 42); tone(55, t, 1.8, 0.35); tone(523.3, t + 0.15, 2.2, 0.05); tone(784, t + 0.15, 2.2, 0.04); tone(1046.5, t + 0.15, 2.2, 0.03); }
  }
  function syncMusic() {
    if (mute || !started || pausedAt !== null) return;
    const t = T();
    for (const f of SFX) if (!f.done && t >= f.at) { f.done = true; if (t < f.at + 1) sfx(f.kind); }
    for (const l of LINES) if (!l.played && t >= l.at) { l.played = true; l.au.currentTime = 0; l.au.play().catch(() => {}); }
    if (t < MUSIC_OUT + MUSIC_FADE) {
      const want = t + MUSIC_OFFSET;
      if (music.paused || Math.abs(music.currentTime - want) > 0.3) { music.currentTime = want; music.play().catch(() => {}); }
      const duck = SPANS.some(([a, b]) => t >= a && t < b) ? 0.35 : 1;
      music.volume = Math.max(0, Math.min(1, MUSIC_VOL * (1 - Math.pow(1 - Math.min(1, t / 3.5), 2)) * duck * Math.min(1, (MUSIC_OUT + MUSIC_FADE - t) / MUSIC_FADE)));
    } else if (!music.paused) music.pause();
  }

  function setScene(scenIdx, v) {
    if (st.scen !== scenIdx) { st.scen = scenIdx; for (const k in shown) delete shown[k]; snap = true; }
    st.v = v; st.split = false;
  }

  let scene = "film";
  function update() {
    const rt = T(); syncMusic();
    // real time: 0-10.5 film, pitch (PL s), flow today 8 s (with a little fast track, in blue), note reading 8 s, build credit 4 s, ending
    const F0 = P0 + PL, D0 = F0 + 11, K0 = D0 + 8, E0 = K0 + 7.2;
    TRAILER.t = rt; TRAILER.blue = rt >= F0 && rt < D0; monoOn = TRAILER.blue; FLOW.mini = 0; FLOW.build = 1; FLOW.scale = 0;
    if (rt < P0) { scene = "film"; return "tdraw"; }
    if (rt < F0) { TRAILER.t = 19 + (rt - P0); scene = "pitch"; return "tdraw"; }
    // the fast-track line appears as "a few take the fast track" is spoken
    if (rt < D0) { FLOW.newKey = "baseline"; FLOW.build = Math.min(1, (rt - F0) / 2.8); FLOW.scale = Math.max(0, Math.min(1, (rt - F0 - 3.4) / 0.6)); FLOW.mini = Math.max(0, Math.min(1, (rt - F0 - 6.5) / 0.8)); st.day = Math.max(0, rt - F0 - 3) * 4; return "flow"; }
    if (rt < K0) { TRAILER.docT = (rt - D0) * 1.6; return "doc"; }
    if (rt < E0) { scene = "build"; return "tdraw"; }
    scene = "end"; return "tdraw";
  }

  // ---- drawing helpers (picture coordinates are W x H; begin() maps them into the top band)
  let full = false;
  function begin(mode) {
    const t = T(), colour = started && TRAILER.blue;
    if (filterOn !== !colour) { cv.style.filter = colour ? "none" : "url(#ink) grayscale(1)"; filterOn = !colour; }
    ctx.save();
    full = mode === "tdraw";                  // film stills and cards: full frame, subtitles over the picture
    if (full) return;
    ctx.fillStyle = "#fbf9ef"; ctx.fillRect(0, 0, W, H);
    const s = PIC; ctx.translate(W * (1 - s) / 2, H * 0.012); ctx.scale(s, s);
    ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  }
  function still(id, t0, dur, zoom = 0.08) {
    const im = img[id]; if (!im.complete || !im.naturalWidth) return;
    const k = Math.max(0, Math.min(1, (TRAILER.t - t0) / dur)), s = 1 + zoom * k;
    const r = Math.max(W / im.naturalWidth, H / im.naturalHeight) * s, w = im.naturalWidth * r, h = im.naturalHeight * r;
    ctx.drawImage(im, (W - w) / 2, (H - h) / 2, w, h);
  }
  function fade(a) { if (a > 0) { ctx.fillStyle = `rgba(0,0,0,${Math.min(1, a)})`; ctx.fillRect(0, 0, W, H); } }
  function text(s, x, y, size, color, weight = 400, align = "center") {
    ctx.font = `${weight} ${Math.round(size)}px "Inter", sans-serif`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "middle"; ctx.fillText(s, x, y);
  }
  function mono(s, x, y, size, color) {
    ctx.font = `${Math.round(size)}px ui-monospace, "Courier New", monospace`; ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(s, x, y);
  }
  function note(lines, t0, dur) {
    const k = Math.max(0, (TRAILER.t - t0) / dur), s = 1 + 6 * k * k;
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(s, s);
    ctx.fillStyle = "#f3eee0"; ctx.fillRect(-W * 0.36, -H * 0.2, W * 0.72, H * 0.4);
    lines.forEach((l, i) => mono(l, 0, -H * 0.06 + i * H * 0.12, H * 0.034, "#161616"));
    ctx.restore();
    fade((k - 0.75) * 4);
  }

  function draw() {
    const t = TRAILER.t;
    ctx.fillStyle = "#fbf9ef"; ctx.fillRect(0, 0, W, H);
    if (!started) { text("CLICK OR PRESS SPACE TO PLAY", W / 2, H / 2, H * 0.03, "#6b6b66", 600); return; }
    if (scene === "film") {
      if (t < COLOUR[0]) {                           // the hook: a sourced gap, counted up
        const cnt = (n, t0) => Math.round(n * Math.max(0, Math.min(1, (t - t0) / 0.7)));
        text("Same lymphoma. Days from first symptom to treatment:", W / 2, H * 0.24, H * 0.03, "#1f1f1d", 500);
        if (t > 0.3) { text(cnt(123, 0.3) + " days", W * 0.3, H * 0.47, H * 0.13, "#1f1f1d", 800);
                       text("occupational or private care", W * 0.3, H * 0.6, H * 0.03, "#6b6b66", 500); }
        if (t > 1.3) { text(cnt(207, 1.3) + " days", W * 0.7, H * 0.47, H * 0.13, "#1f1f1d", 800);
                       text("public health centre", W * 0.7, H * 0.6, H * 0.03, "#6b6b66", 500); }
        text("Kuitunen et al., Cancer Medicine 2026 (DLBCL)", W / 2, H * 0.76, H * 0.019, "#8a8a85", 500);
      }
      else if (t < COLOUR[1]) scanner(t);
      else if (t >= IBM) {                                                  // the IBM line, typed
        const l = "A COMPUTER CAN NEVER BE HELD ACCOUNTABLE", n = Math.max(0, Math.min(l.length, Math.floor((t - 5.85) * 17)));
        mono(l.slice(0, n), W / 2, H * 0.5, H * 0.04, "#1f1f1d");
      }
      return;
    }
    if (scene === "pitch") { pitch(t); return; }
    if (scene === "build") {                  // credit, synced to the voice: each name appears (and chimes) as it is spoken
      const V = P0 + PL + 20.1, tt = T();      // voice start; "Nemotron" is spoken at +0.81 s, "Verda" at +2.57 s (1.05x)
      const col = (x, labelAt, nameAt, label, name) => {
        const al = Math.max(0, Math.min(1, (tt - labelAt) / 0.3)), an = Math.max(0, Math.min(1, (tt - nameAt) / 0.25));
        if (al) { ctx.globalAlpha = al; text(label, x, H * 0.55, H * 0.022, "#6b6b66", 600); }
        if (an) { ctx.globalAlpha = an; text(name, x, H * 0.62 + (1 - an) * H * 0.015, H * 0.055, "#1f1f1d", 800); }
        ctx.globalAlpha = 1;
      };
      { const K = P0 + PL + 19, aa = Math.max(0, Math.min(1, (tt - K - 0.2) / 0.6));
        ctx.globalAlpha = aa; text("THE CHALLENGE", W / 2, H * 0.3, H * 0.022, "#6b6b66", 600); text("AstraZeneca: Equal Care Across Finland", W / 2, H * 0.37, H * 0.045, "#1f1f1d", 700); ctx.globalAlpha = 1; }
      col(W * 0.3, V + 0.05, V + 0.81, "BUILT WITH", "NVIDIA Nemotron");
      if (tt > V + 1.85) { ctx.globalAlpha = Math.min(1, (tt - V - 1.85) / 0.3); ctx.fillStyle = "rgba(0,0,0,0.25)"; ctx.fillRect(W * 0.5 - 1, H * 0.52, 2, H * 0.15); ctx.globalAlpha = 1; }
      col(W * 0.7, V + 1.85, V + 2.57, "POWERED BY", "Verda");
      return;
    }
    const pk = Math.max(0, Math.min(1, (T() - 63.4) / 0.5));       // the punchline arrives last; the rest steps back
    ctx.globalAlpha = 1 - 0.65 * pk;
    text("SCIENCE-BASED PILOT", W / 2, H * 0.24, H * 0.024, "#6b6b66", 700);
    text("One clinician-validated pipeline, piloted in Finland.", W / 2, H * 0.32, H * 0.038, "#1f1f1d", 700);
    text("More time for hard cases, and for the human encounter.", W / 2, H * 0.42, H * 0.03, "#3a3a37", 500);
    ctx.globalAlpha = 1;
    text("github.com/Toivo31/cancer", W / 2, H * 0.9, H * 0.018, "#8a8a85", 500);
    ctx.globalAlpha = pk;
    text("Waiting is a decision nobody made.", W / 2, H * 0.62, H * 0.07, "#1f1f1d", 800);
    ctx.globalAlpha = 1;
  }

  // the scanner: original orientation, no zoom. First the shot with less of the face, then the one with more;
  // the picture slides steadily downwards so the table (kelkka) seems to move out of the scanner.
  function scanner(t) {
    const k = Math.max(0, Math.min(0.999, (t - COLOUR[0]) / (CLIP_END - COLOUR[0])));   // after the clip, the last frame holds
    let im = SCAN[Math.floor(k * NSCAN)];
    if (!im || !im.complete || !im.naturalWidth) im = SCAN.find(x => x.complete && x.naturalWidth);
    if (!im) return;
    const r = Math.max(W / im.naturalWidth, H / im.naturalHeight), w = im.naturalWidth * r, h = im.naturalHeight * r;
    ctx.drawImage(im, (W - w) / 2, (H - h) / 2, w, h);
  }

  // the product pitch: four panels on the beat; the music drop lands on OPTIMISE
  function pitch(t) {
    ctx.fillStyle = "#fbf9ef"; ctx.fillRect(0, 0, W, H);
    const pt = t - 19, fade = at => Math.max(0, Math.min(1, (pt - at) / 0.4));
    if (pt < 8) {                              // the two failure modes, as two plain statements
      [[0.5, "Trust AI too little,", "and doctors check everything."], [2.0, "Trust it too much,", "and nobody checks."]].forEach(([at, a, b], i) => {
        const k = fade(at); if (!k) return;
        ctx.globalAlpha = k;
        text(a, W * 0.12, H * (0.36 + i * 0.26), H * 0.07, "#1f1f1d", 800, "left");
        text(b, W * 0.12, H * (0.45 + i * 0.26), H * 0.045, "#6b6b66", 500, "left");
        ctx.globalAlpha = 1;
      });
      return;
    }
    text("EQUAL CARE PATHWAYS", W * 0.12, H * 0.16, H * 0.026, "#6b6b66", 700, "left");
    [[8.0, "Clinicians define the pipeline."], [10.0, "The system runs it."], [12.4, "When the model is unsure, a doctor reviews the case."]].forEach(([at, line], i) => {
      const k = fade(at); if (!k) return;
      ctx.globalAlpha = k;
      text(String(i + 1), W * 0.08, H * (0.34 + i * 0.17), H * 0.05, "#8a8a85", 700, "left");
      text(line, W * 0.12, H * (0.34 + i * 0.17), H * 0.055, "#1f1f1d", 800, "left");
      ctx.globalAlpha = 1;
    });
  }

  // overlays on the dot scenes (picture coordinates)
  function overlay(mode) {
    const t = TRAILER.t;
    if (mode === "flow" && TRAILER.blue) {      // the simulation runs inside our framework
      const a = Math.min(1, (T() - (P0 + PL)) / 0.4);
      ctx.save(); ctx.globalAlpha = a;
      ctx.fillStyle = "rgba(251,249,239,0.96)"; ctx.fillRect(W * 0.76, H * 0.045, W * 0.23, H * 0.12);
      ctx.strokeStyle = "rgba(30,30,28,1)"; ctx.lineWidth = 2.5; ctx.strokeRect(W * 0.76, H * 0.045, W * 0.23, H * 0.12);
      text("IN OUR FRAMEWORK", W * 0.875, H * 0.088, H * 0.027, "rgba(30,30,28,1)", 800);
      text("clinician-defined rules", W * 0.875, H * 0.133, H * 0.017, "#333", 500);
      ctx.restore();
    }
    if (mode === "lanes") {
      ctx.fillStyle = "rgba(251,249,239,0.95)"; ctx.fillRect(0, 0, W, H * 0.12);
      text("A REAL NORWEGIAN HOSPITAL · STOKSTAD ET AL. 2019", W * 0.04, H * 0.06, H * 0.026, "#1f1f1d", 700, "left");
      text(t < DROP ? "Published 40%  ·  Ours 40%" : "Reordered, same patients: 80%  (88% with the faster scanner · 67% no new equipment)",
           W * 0.96, H * 0.06, H * 0.022, "#1f1f1d", 700, "right");
    }
    if (mode === "flowcard") {                 // the challenge and the tech challenges, as text beside the running flow
      const a = Math.max(0, Math.min(1, t / 0.5)), bx = W * 0.66, by = H * 0.3, bw = W * 0.32, bh = H * 0.5;
      ctx.globalAlpha = a; ctx.fillStyle = "rgba(251,249,239,0.96)"; ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = "rgba(25,95,165,0.9)"; ctx.lineWidth = 2; ctx.strokeRect(bx, by, bw, bh);
      const X = bx + W * 0.015;
      text("THE CHALLENGE", X, by + H * 0.05, H * 0.019, "rgba(25,95,165,1)", 700, "left");
      text("AstraZeneca:", X, by + H * 0.09, H * 0.024, "#111", 800, "left");
      text("Equal Care Across Finland", X, by + H * 0.125, H * 0.024, "#111", 800, "left");
      ["Find the gaps in access and outcomes.", "Locate them in the pathway.", "Recommend concrete actions."].forEach((l, i) =>
        text("· " + l, X, by + H * (0.17 + i * 0.037), H * 0.019, "#333", 500, "left"));
      if (t > 2.5) {
        text("TECH CHALLENGES WE ENTERED", X, by + H * 0.33, H * 0.019, "rgba(25,95,165,1)", 700, "left");
        ["Modal", "Nemotron", "Gemma", "Gemini API", "Codex", "Verda Compute"].forEach((l, i) => {
          if (t < 2.5 + i * 0.25) return;
          text("· " + l, X + (i % 2) * W * 0.15, by + H * (0.375 + Math.floor(i / 2) * 0.04), H * 0.021, "#222", 600, "left"); });
      }
      ctx.globalAlpha = 1;
    }
  }

  // end of frame: leave the picture band, draw the subtitle band
  function finish() {
    ctx.restore();
    const y0 = full ? H * 0.86 : H * (0.012 + PIC) + H * 0.008;
    if (!full) { ctx.fillStyle = "#fbf9ef"; ctx.fillRect(0, y0, W, H - y0); }
    const t = T(), c = CAPS.find(([a, b]) => t >= a && t < b); if (!c || !started) return;
    const size = H * 0.027; ctx.font = `${Math.round(size)}px "Inter", sans-serif`;
    const lines = [], maxW = W * 0.78; let cur = "";
    for (const w of c[2].split(" ")) { const tr = cur ? cur + " " + w : w; if (ctx.measureText(tr).width > maxW && cur) { lines.push(cur); cur = w; } else cur = tr; }
    lines.push(cur);
    const lh = size * 1.3, mid = (y0 + H) / 2;
    const onPic = scene === "film" && t >= COLOUR[0] && t < COLOUR[1];
    if (onPic) {                               // over the picture: dark box behind the text
      const bh = lines.length * lh + size * 0.6;
      ctx.fillStyle = "rgba(0,0,0,0.6)"; ctx.fillRect(W * 0.1, mid - bh / 2, W * 0.8, bh);
    }
    lines.forEach((l, i) => text(l, W / 2, mid + (i - (lines.length - 1) / 2) * lh, size, onPic ? "#fff" : "#1f1f1d", 500));
  }

  return { active: true, update, begin, draw, overlay, finish, t: 0, docT: 0, LEN };
})();
