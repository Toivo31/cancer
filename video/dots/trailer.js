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
  FLOW.half = true; HALF_DOTS = true;      // draw every other patient; counts still use all of them

  const LEN = 60, PL = 13, DROP = 31, MUSIC_OFFSET = 18.8, MUSIC_OUT = 10.5;  // music (with its crackle) stops when the visualisation starts   // drop at excerpt 49.8 lands at 0:31 (OPTIMISE card)
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
  const PIC = 0.8;                        // simulation scenes are zoomed out to this share; stills stay full frame
  // narration: one file per line (natural speed), each played at 1.2x with pitch preserved at its cue time
  const RATE = 1.2, music = new Audio("audio/excerpt.wav"); music.preload = "auto";
  let started = false, CAPS = [], LINES = [];
  fetch("trailer_assets/cues.json").then(r => r.json()).then(c => {
    LINES = c.map(([at, id, text, dur]) => { const au = new Audio(`trailer_assets/${id}.wav`); au.preload = "auto"; au.playbackRate = RATE; au.preservesPitch = true; return { at, au, text, dur, played: false }; });
    CAPS = LINES.map(l => [l.at, l.at + l.dur / RATE, l.text]);
  }).catch(() => {});

  const img = {};
  for (const id of ["a2_consultation", "a4_stain", "b2_slip", "b3_waiting_room", "b4_unfold", "b9_door"]) {
    const im = new Image(); im.src = `trailer_assets/${id}_still.png`; img[id] = im;
  }
  for (const id of ["scan_wide", "scan_close"]) { const im = new Image(); im.src = `trailer_assets/${id}.webp`; img[id] = im; }
  const COLOUR = [3.8, 4.6];                 // one scanner shot, in colour                 // the scanner shots keep their colours (canvas filter off)
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
  let ac = null; const SFX = [{ at: 40.5, kind: "bling", done: false }, { at: 56.0, kind: "hit", done: false }];
  function tone(f, t, dur, vol, type = "sine", f2 = null) {
    const o = ac.createOscillator(), g = ac.createGain(); o.type = type; o.frequency.setValueAtTime(f, t);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur * 0.5);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  function sfx(kind) {
    if (!ac) return; const t = ac.currentTime + 0.02;
    if (kind === "bling") { tone(1318.5, t, 1.1, 0.16); tone(1975.5, t + 0.1, 1.3, 0.14); tone(2637, t + 0.1, 0.5, 0.05); tone(3951, t + 0.2, 0.4, 0.03); }
    else { tone(110, t, 1.6, 0.5, "sine", 42); tone(55, t, 1.8, 0.35); tone(523.3, t + 0.15, 2.2, 0.05); tone(784, t + 0.15, 2.2, 0.04); tone(1046.5, t + 0.15, 2.2, 0.03); }
  }
  function syncMusic() {
    if (mute || !started || pausedAt !== null) return;
    const t = T();
    for (const f of SFX) if (!f.done && t >= f.at) { f.done = true; if (t < f.at + 1) sfx(f.kind); }
    for (const l of LINES) if (!l.played && t >= l.at) { l.played = true; l.au.currentTime = 0; l.au.play().catch(() => {}); }
    if (t < MUSIC_OUT) {
      const want = t + MUSIC_OFFSET;
      if (music.paused || Math.abs(music.currentTime - want) > 0.3) { music.currentTime = want; music.play().catch(() => {}); }
      const duck = CAPS.some(([a, b]) => t >= a && t < b) ? 0.35 : 1;
      music.volume = Math.max(0, Math.min(1, Math.min(1, t / 0.3) * duck));
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
    const F0 = 10.5 + PL, D0 = F0 + 8, K0 = D0 + 8, E0 = K0 + 6;
    TRAILER.t = rt; TRAILER.blue = rt >= F0 && rt < D0; monoOn = TRAILER.blue; FLOW.mini = 0;
    if (rt < 10.5) { scene = "film"; return "tdraw"; }
    if (rt < F0) { TRAILER.t = 21.8 + (rt - 10.5); scene = "pitch"; return "tdraw"; }
    if (rt < D0) { FLOW.newKey = "baseline"; FLOW.mini = Math.max(0, Math.min(1, (rt - F0 - 4) / 1)); st.day = (rt - F0) * 9; return "flow"; }
    if (rt < K0) { TRAILER.docT = (rt - D0) * 1.6; return "doc"; }
    if (rt < E0) { scene = "build"; return "tdraw"; }
    scene = "end"; return "tdraw";
  }

  // ---- drawing helpers (picture coordinates are W x H; begin() maps them into the top band)
  let full = false;
  function begin(mode) {
    const t = T(), colour = started && ((t >= COLOUR[0] && t < COLOUR[1]) || TRAILER.blue);
    if (filterOn !== !colour) { cv.style.filter = colour ? "none" : "url(#ink) grayscale(1)"; filterOn = !colour; }
    ctx.save();
    full = mode === "tdraw";                  // film stills and cards: full frame, subtitles over the picture
    if (full) return;
    ctx.fillStyle = "#fdfcf8"; ctx.fillRect(0, 0, W, H);
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
    if (!started) { ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H); text("CLICK OR PRESS SPACE TO PLAY · 50 SECONDS", W / 2, H / 2, H * 0.03, "#ddd", 600); return; }
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
    if (scene === "film") {
      if (t < 2) {                                   // the hook: 87 DAYS slams onto black
        const k = Math.max(0, 1 - t / 0.22), sc = 1 + 0.5 * k;
        ctx.save(); ctx.translate(W / 2, H * 0.47); ctx.scale(sc, sc);
        mono("87 DAYS", 0, 0, H * 0.2, "#f4f4f4"); ctx.restore();
        if (t > 0.7) text("to wait for a cancer diagnosis", W / 2, H * 0.64, H * 0.035, "#cfcfcf", 500);
        text("Dramatisation", W * 0.96, H * 0.05, H * 0.02, "rgba(255,255,255,0.7)", 600, "right");
      }
      else if (t < 3) still("a2_consultation", 2, 1, 0.04);               // quick montage, hard cuts
      else if (t < 3.8) still("a4_stain", 3, 0.8, 0.1);
      else if (t < 4.6) scanner(t);                                         // in colour
      else if (t < 8.4) {
        still("b3_waiting_room", 4.6, 3.8, 0.05);
        { const z = 1 + 0.05 * Math.max(0, Math.min(1, (TRAILER.t - 4.6) / 3.8));      // stuck to the wall: zooms with the picture
          ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2, -H / 2);
          mono("87 DAYS", W * 0.536, H * 0.348, H * 0.042, "rgba(255,190,90,0.95)"); ctx.restore(); }
        text("Dramatisation", W * 0.96, H * 0.05, H * 0.02, "rgba(255,255,255,0.85)", 600, "right");
      }
      else {                                                                // the IBM line, typed on black
        const L = ["A COMPUTER CAN NEVER BE HELD ACCOUNTABLE", "THEREFORE A COMPUTER MUST NEVER", "MAKE A MANAGEMENT DECISION"];
        L.forEach((l, i) => { const n = Math.max(0, Math.min(l.length, Math.floor((t - 8.4 - i * 0.45) * 60))); mono(l.slice(0, n), W / 2, H * (0.42 + i * 0.08), H * 0.036, "#eee"); });
      }
      return;
    }
    if (scene === "pitch") { pitch(t); return; }
    if (scene === "build") {
      const a = Math.max(0, Math.min(1, (T() - (10.5 + PL + 17)) / 0.5));   // 6 s scene: 1 s of black first, then the credit
      ctx.globalAlpha = a; text("Built with Nemotron, powered by Verda.", W / 2, H * 0.5, H * 0.045, "#f2f2f2", 700); ctx.globalAlpha = 1; return;
    }
    const pk = Math.max(0, Math.min(1, (T() - 56) / 0.5));       // the punchline arrives last; the rest steps back
    ctx.globalAlpha = 1 - 0.65 * pk;
    text("We propose a research-based framework for future automation.", W / 2, H * 0.2, H * 0.036, "#f2f2f2", 700);
    text("OUR SUGGESTION", W / 2, H * 0.34, H * 0.024, "#9fc3ea", 700);
    text("Pilot one clinician-validated pipeline in one wellbeing services county.", W / 2, H * 0.42, H * 0.034, "#f2f2f2", 600);
    text("Measure: patients reaching treatment within target times (Goal 3, indicator 3.1).", W / 2, H * 0.5, H * 0.024, "#ddd", 500);
    text("More time for hard cases, and for the human encounter.", W / 2, H * 0.6, H * 0.03, "#f2f2f2", 600);
    text("Clinicians define, automate and validate each pipeline, transparently. The dots are an illustration. github.com/Toivo31/cancer", W / 2, H * 0.92, H * 0.016, "#bbb");
    ctx.globalAlpha = pk;
    text("Waiting is a decision nobody made.", W / 2, H * 0.76, H * 0.06, "#ffffff", 800);
    ctx.globalAlpha = 1;
  }

  // the scanner: original orientation, no zoom. First the shot with less of the face, then the one with more;
  // the picture slides steadily downwards so the table (kelkka) seems to move out of the scanner.
  function scanner(t) {
    const a = COLOUR[0], b = COLOUR[1], mid = a + (b - a) * 0.5;
    const im = img.scan_close;
    if (!im.complete || !im.naturalWidth) return;
    const k = (t - a) / (b - a);                                  // one continuous slide across both shots
    const r = Math.max(W / im.naturalWidth, H / im.naturalHeight), w = im.naturalWidth * r, h = im.naturalHeight * r;
    const y = (H - h) / 2;                                       // still: no movement
    ctx.drawImage(im, (W - w) / 2, y, w, h);
  }

  // the product pitch: four panels on the beat; the music drop lands on OPTIMISE
  function pitch(t) {
    ctx.fillStyle = "#fdfcf8"; ctx.fillRect(0, 0, W, H);
    const pt = t - 21.8;                       // seconds into the pitch scene; the first 5.2 s are the two failure modes
    if (pt < 5.2) {
      text("TWO WAYS AI FAILS IN MEDICINE", W / 2, H * 0.14, H * 0.05, "#111", 800);
      const C = [[0.5, "TRUST TOO LITTLE", "Doctors check everything.", "No time is saved."],
                 [2.0, "TRUST TOO MUCH", "Doctors stop checking.", "Errors slip through."]];
      C.forEach(([at, h, l1, l2], i) => {
        const a = Math.max(0, Math.min(1, (pt - at) / 0.35)); if (!a) return;
        const x = W * (0.08 + i * 0.44), y = H * 0.27 + (1 - a) * H * 0.03, w = W * 0.4, hh = H * 0.42;
        ctx.globalAlpha = a; ctx.fillStyle = "#fff"; ctx.fillRect(x, y, w, hh);
        ctx.strokeStyle = "#1f1f1d"; ctx.lineWidth = 2; ctx.strokeRect(x, y, w, hh);
        text(h, x + w / 2, y + hh * 0.26, H * 0.04, "#111", 800);
        text(l1, x + w / 2, y + hh * 0.56, H * 0.03, "#333", 500);
        text(l2, x + w / 2, y + hh * 0.74, H * 0.03, "#333", 500);
        ctx.globalAlpha = 1;
      });
      return;
    }
    text("EQUAL CARE PATHWAYS", W * 0.05, H * 0.1, H * 0.05, "#111", 800, "left");
    text("A simple, transparent framework to automate cancer care.", W * 0.05, H * 0.16, H * 0.024, "#444", 500, "left");
    const P = [
      [27.0, "DEFINE", "Clinicians define each pipeline as a simple flowchart of rules."],
      [28.6, "AUTOMATE", "The system reads the note and runs the pipeline: red flag, no follow-up, fast track."],
      [30.4, "VALIDATE", "Clinicians validate each pipeline before it runs. If the model is unsure, it flags the case for clinical review."],
    ];
    const pw = W * 0.28, gap = W * 0.03, x0 = W * 0.05, y0 = H * 0.21, ph = H * 0.56;
    P.forEach(([at, head, cap], i) => {
      const a = Math.max(0, Math.min(1, (t - at) / 0.35)); if (!a) return;
      const x = x0 + i * (pw + gap), y = y0 + (1 - a) * H * 0.04;
      ctx.globalAlpha = a;
      ctx.fillStyle = "#ffffff"; ctx.fillRect(x, y, pw, ph);
      ctx.strokeStyle = "#1f1f1d"; ctx.lineWidth = 2; ctx.strokeRect(x, y, pw, ph);
      text(`${i + 1}  ${head}`, x + W * 0.012, y + H * 0.05, H * 0.032, "#111", 800, "left");
      const cx = x + pw / 2, vy = y + H * 0.1, vh = H * 0.28;
      ctx.strokeStyle = "#1f1f1d"; ctx.fillStyle = "#1f1f1d"; ctx.lineWidth = 1.5;
      if (head === "DEFINE") {                      // a small flowchart drawing itself
        const n = Math.min(6, Math.floor((t - at) * 6) + 1);
        for (let k = 0; k < n; k++) {
          const ny = vy + vh * 0.85 - k * vh * 0.85 / 5, nx = cx + (k % 2 ? 1 : -1) * (k === 3 ? pw * 0.18 : 0);
          ctx.beginPath(); ctx.arc(nx, ny, 7, 0, Math.PI * 2); ctx.fill();
          if (k) { const py = vy + vh * 0.85 - (k - 1) * vh * 0.85 / 5, px = cx + ((k - 1) % 2 ? 1 : -1) * (k - 1 === 3 ? pw * 0.18 : 0); ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(nx, ny); ctx.stroke(); }
        }
      } else if (head === "AUTOMATE") {          // a note, a flag, then the rule fires
        ctx.fillStyle = "#f3f1ea"; ctx.fillRect(x + pw * 0.08, vy + vh * 0.05, pw * 0.84, vh * 0.36);
        text("Tired, lost 6 kg.", x + pw * 0.12, vy + vh * 0.16, H * 0.017, "#222", 400, "left");
        ctx.strokeRect(x + pw * 0.12 + H * 0.098, vy + vh * 0.16 - H * 0.014, H * 0.07, H * 0.028);
        text("Likely stress.", x + pw * 0.12, vy + vh * 0.31, H * 0.017, "#222", 400, "left");
        if (t > at + 0.6) text("red flag, no follow-up", cx, vy + vh * 0.56, H * 0.0155, "#222", 600);
        if (t > at + 1.2) { text("↓", cx, vy + vh * 0.7, H * 0.03, "#111", 800); text("FAST TRACK", cx, vy + vh * 0.88, H * 0.022, "#111", 800); }
      } else if (head === "VALIDATE") {          // two rules, then the stamp
        ctx.fillStyle = "#f3f1ea"; ctx.fillRect(x + pw * 0.08, vy + vh * 0.03, pw * 0.84, vh * 0.64);
        text("RULE FT-07", x + pw * 0.12, vy + vh * 0.13, H * 0.017, "#222", 800, "left");
        text("IF red flag AND no follow-up", x + pw * 0.12, vy + vh * 0.26, H * 0.0145, "#222", 400, "left");
        text("→ fast track", x + pw * 0.12, vy + vh * 0.34, H * 0.0145, "#222", 400, "left");
        if (t > at + 0.5) { text("IF the model is unsure", x + pw * 0.12, vy + vh * 0.47, H * 0.0145, "#222", 400, "left");
                            text("→ clinical review", x + pw * 0.12, vy + vh * 0.55, H * 0.0145, "#222", 400, "left"); }
        if (t > at + 1.2) {
          ctx.save(); ctx.translate(cx, vy + vh * 0.84); ctx.rotate(-0.06);
          ctx.lineWidth = 3; ctx.strokeRect(-pw * 0.4, -H * 0.03, pw * 0.8, H * 0.06);
          text("CLINICIAN-VALIDATED", 0, 0, H * 0.015, "#111", 800); ctx.restore();
        }
      }
      ctx.font = `${Math.round(H * 0.019)}px "Inter", sans-serif`; ctx.fillStyle = "#333"; ctx.textAlign = "left"; ctx.textBaseline = "top";
      let line = "", yy = y + ph - H * 0.17;
      for (const w of cap.split(" ")) { const tr = line ? line + " " + w : w; if (ctx.measureText(tr).width > pw - W * 0.024 && line) { ctx.fillText(line, x + W * 0.012, yy); line = w; yy += H * 0.026; } else line = tr; }
      ctx.fillText(line, x + W * 0.012, yy);
      ctx.globalAlpha = 1;
    });
    text("Clinicians define, automate and validate each pipeline, transparently · the dots are an illustration", W / 2, H * 0.81, H * 0.02, "#555", 600);
  }

  // overlays on the dot scenes (picture coordinates)
  function overlay(mode) {
    const t = TRAILER.t;
    if (mode === "flow" && TRAILER.blue) {      // the simulation runs inside our framework
      const a = Math.min(1, (T() - (10.5 + PL)) / 0.4);
      ctx.save(); ctx.globalAlpha = a;
      ctx.fillStyle = "rgba(253,252,248,0.96)"; ctx.fillRect(W * 0.76, H * 0.045, W * 0.23, H * 0.12);
      ctx.strokeStyle = "rgba(30,30,28,1)"; ctx.lineWidth = 2.5; ctx.strokeRect(W * 0.76, H * 0.045, W * 0.23, H * 0.12);
      text("IN OUR FRAMEWORK", W * 0.875, H * 0.088, H * 0.027, "rgba(30,30,28,1)", 800);
      text("clinician-defined rules", W * 0.875, H * 0.133, H * 0.017, "#333", 500);
      ctx.restore();
    }
    if (mode === "lanes") {
      ctx.fillStyle = "rgba(253,252,248,0.95)"; ctx.fillRect(0, 0, W, H * 0.12);
      text("A REAL NORWEGIAN HOSPITAL · STOKSTAD ET AL. 2019", W * 0.04, H * 0.06, H * 0.026, "#1f1f1d", 700, "left");
      text(t < DROP ? "Published 40%  ·  Ours 40%" : "Reordered, same patients: 80%  (88% with the faster scanner · 67% no new equipment)",
           W * 0.96, H * 0.06, H * 0.022, "#1f1f1d", 700, "right");
    }
    if (mode === "flowcard") {                 // the challenge and the tech challenges, as text beside the running flow
      const a = Math.max(0, Math.min(1, t / 0.5)), bx = W * 0.66, by = H * 0.3, bw = W * 0.32, bh = H * 0.5;
      ctx.globalAlpha = a; ctx.fillStyle = "rgba(253,252,248,0.96)"; ctx.fillRect(bx, by, bw, bh);
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
    if (!full) { ctx.fillStyle = "#fdfcf8"; ctx.fillRect(0, y0, W, H - y0); }
    const t = T(), c = CAPS.find(([a, b]) => t >= a && t < b); if (!c || !started) return;
    const size = H * 0.027; ctx.font = `${Math.round(size)}px "Inter", sans-serif`;
    const lines = [], maxW = W * 0.78; let cur = "";
    for (const w of c[2].split(" ")) { const tr = cur ? cur + " " + w : w; if (ctx.measureText(tr).width > maxW && cur) { lines.push(cur); cur = w; } else cur = tr; }
    lines.push(cur);
    const lh = size * 1.3, mid = (y0 + H) / 2;
    if (full) {                                // over the picture: dark box behind the text
      const bh = lines.length * lh + size * 0.6;
      ctx.fillStyle = "rgba(0,0,0,0.6)"; ctx.fillRect(W * 0.1, mid - bh / 2, W * 0.8, bh);
    }
    lines.forEach((l, i) => text(l, W / 2, mid + (i - (lines.length - 1) / 2) * lh, size, full ? "#fff" : "#1f1f1d", 500));
  }

  return { active: true, update, begin, draw, overlay, finish, t: 0, docT: 0, LEN };
})();
