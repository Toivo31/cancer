"use strict";
// Trailer, punchy cut (index.html?trailer). Light paper and dark ink; the fast-track line is the only colour.
// Every scene, every on-screen line and every sound effect is cued from trailer_assets/timeline.json, which
// video/generated/build_timeline.py writes from the word timings of the narration (s1 ... s7). Statements cut in hard
// on the spoken word. Clock: wall time from the click; ?mute runs silent, &from= starts later. Space pauses.

const TRAILER = (() => {
  if (FINAL.active) return FINAL;          // ?final: Tuomas's final script (trailer_final.js)
  const active = qs.has("trailer");
  if (!active) return { active: false };
  help.classList.add("hidden"); st.ui = false; st.playing = false;
  FLOW.half = true; FLOW.every = 6; FLOW.simple = true; HALF_DOTS = true;   // draw one in six patients
  const PAPER = "#fbf9ef", INK = "#1f1f1d", GREY = "#6b6b66", FAINT = "#8a8a85";
  const MUSIC_OFFSET = 18.8, MUSIC_FADE = 3, MUSIC_VOL = 0.22, PIC = 0.9;

  // the animation is grey and one blue: every colour drawn to the canvas becomes its grey, except the fast-track line
  let monoOn = false;
  function toGrey(c) {
    let r, g, b, a = 1, m;
    if ((m = c.match(/^rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+))?\s*\)/))) { r = +m[1]; g = +m[2]; b = +m[3]; if (m[4] !== undefined) a = +m[4]; }
    else if ((m = c.match(/^#([0-9a-f]{6})$/i))) { r = parseInt(m[1].slice(0, 2), 16); g = parseInt(m[1].slice(2, 4), 16); b = parseInt(m[1].slice(4), 16); }
    else return c;
    if (b >= r + 50 && b >= g + 10 && FLOW.laneInk) return c;
    const y = Math.round(0.3 * r + 0.59 * g + 0.11 * b);
    return a < 1 ? `rgba(${y},${y},${y},${a})` : `rgb(${y},${y},${y})`;
  }
  for (const k of ["fillStyle", "strokeStyle"]) {
    const d = Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype, k);
    Object.defineProperty(CanvasRenderingContext2D.prototype, k, { get: d.get, configurable: true, set(v) { d.set.call(this, monoOn && typeof v === "string" ? toGrey(v) : v); } });
  }

  // timeline, narration, captions
  let TL = null, LINES = [], SPANS = [], CAPS = [], SFX = [];
  const music = new Audio("audio/excerpt.wav"); music.preload = "auto";
  Promise.all([fetch("trailer_assets/timeline.json").then(r => r.json()), fetch("trailer_assets/cues.json").then(r => r.json())]).then(([tl, c]) => {
    TL = tl;
    LINES = c.map(([at, id, text, dur, rate]) => { const au = new Audio(`trailer_assets/${id}.wav`); au.preload = "auto"; au.playbackRate = rate; au.preservesPitch = true; return { at, id, au, text, len: dur / rate, played: false }; });
    SPANS = LINES.map(l => [l.at, l.at + l.len, l.text]);
    CAPS = SPANS.filter((x, i) => TL.captions.includes(LINES[i].id));
    SFX = TL.sfx.map(([at, kind]) => ({ at, kind, done: false }));
  }).catch(() => {});

  const SCAN = [], NSCAN = 49;             // the scanner clip, 2 s at 24 fps, played at 1.5x
  for (let i = 1; i <= NSCAN; i++) { const im = new Image(); im.src = `trailer_assets/scanclip/f${String(i).padStart(3, "0")}.jpg`; SCAN.push(im); }
  let filterOn = null;

  // clock
  const mute = qs.has("mute"); let t0 = 0, pausedAt = null, started = false, ac = null;
  function start() {
    if (started) {
      if (pausedAt === null) { pausedAt = T(); music.pause(); LINES.forEach(l => l.au.pause()); }
      else { t0 = performance.now() / 1000 - pausedAt; pausedAt = null; LINES.forEach(l => { if (l.played && !l.au.ended && l.au.currentTime > 0) l.au.play(); }); }
      return;
    }
    started = true; const from = +(qs.get("from") || 0);
    if (!mute) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { ac = null; } }
    SFX.forEach(f => { f.done = from > f.at + 0.2; }); LINES.forEach(l => { l.played = from > l.at + 0.2; });
    t0 = performance.now() / 1000 - from;
  }
  window.addEventListener("click", start);
  window.addEventListener("keydown", e => { if (e.key === " ") { start(); e.stopImmediatePropagation(); e.preventDefault(); } }, true);
  const T = () => (!started ? +(qs.get("from") || 0) : pausedAt !== null ? pausedAt : performance.now() / 1000 - t0);

  // sound effects, synthesized (the renderer mixes the same recipes)
  function tone(f, t, dur, vol, type = "sine", f2 = null) {
    const o = ac.createOscillator(), g = ac.createGain(); o.type = type; o.frequency.setValueAtTime(f, t);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur * 0.5);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.005); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  function sfx(kind) {
    if (!ac) return; const t = ac.currentTime + 0.02;
    if (kind === "tick") { tone(2400, t, 0.04, 0.05); tone(1200, t, 0.03, 0.03); }
    else if (kind === "tock") { tone(1800, t, 0.04, 0.04); tone(900, t, 0.03, 0.03); }
    else if (kind === "bling") { tone(1318.5, t, 1.1, 0.08); tone(1975.5, t + 0.1, 1.3, 0.07); tone(2637, t + 0.1, 0.5, 0.025); tone(3951, t + 0.2, 0.4, 0.015); }
    else if (kind === "bling2") { tone(1975.5, t, 1.0, 0.1); tone(2637, t + 0.05, 0.5, 0.04); }
    else { tone(110, t, 1.6, 0.5, "sine", 42); tone(55, t, 1.8, 0.35); tone(523.3, t + 0.15, 2.2, 0.05); tone(784, t + 0.15, 2.2, 0.04); tone(1046.5, t + 0.15, 2.2, 0.03); }
  }
  function syncSound() {
    if (mute || !started || pausedAt !== null || !TL) return;
    const t = T();
    for (const f of SFX) if (!f.done && t >= f.at) { f.done = true; if (t < f.at + 0.3) sfx(f.kind); }
    for (const l of LINES) if (!l.played && t >= l.at) { l.played = true; l.au.currentTime = 0; l.au.play().catch(() => {}); }
    const out = TL.music_out;
    if (t < out + MUSIC_FADE) {
      const want = t + MUSIC_OFFSET;
      if (music.paused || Math.abs(music.currentTime - want) > 0.3) { music.currentTime = want; music.play().catch(() => {}); }
      const duck = SPANS.some(([a, b]) => t >= a && t < b) ? 0.35 : 1;
      music.volume = Math.max(0, Math.min(1, MUSIC_VOL * (1 - Math.pow(1 - Math.min(1, t / 3.5), 2)) * duck * Math.min(1, (out + MUSIC_FADE - t) / MUSIC_FADE)));
    } else if (!music.paused) music.pause();
  }

  // scenes
  let scene = "wait";
  const clamp = x => Math.max(0, Math.min(1, x));
  function update() {
    const rt = T(); syncSound();
    TRAILER.t = rt; TRAILER.blue = false; monoOn = false; FLOW.mini = 0; FLOW.build = 1; FLOW.scale = 0;
    if (!TL) { scene = "wait"; return "tdraw"; }
    const A = TL.anim;
    if (rt < TL.scan.a) scene = "hook";
    else if (rt < TL.modes.a) scene = "scan";
    else if (rt < TL.fw.a) scene = "modes";
    else if (rt < A.a) scene = "fw";
    else if (rt < A.end) {
      scene = "anim"; TRAILER.blue = true; monoOn = true;
      FLOW.newKey = "baseline";
      FLOW.build = clamp((rt - A.a) / (A.dots - A.a - 0.2));
      FLOW.scale = clamp((rt - A.dots - 0.4) / 0.5);
      FLOW.mini = clamp((rt - A.fast) / 0.5);
      st.day = Math.max(0, rt - A.dots) * 4;
      return "flow";
    }
    else if (rt < TL.man.end) scene = "man";
    else if (rt < TL.doc.end) { scene = "doc"; TRAILER.docT = (rt - TL.doc.a) * 1.6; return "doc"; }
    else if (rt < TL.fin.a) scene = "credit";
    else scene = "fin";
    return "tdraw";
  }

  // drawing helpers (picture coordinates are W x H; begin() maps the animation into the top band)
  let full = false;
  function begin(mode) {
    const colour = started && TRAILER.blue;
    if (filterOn !== !colour) { cv.style.filter = colour ? "none" : "url(#ink) grayscale(1)"; filterOn = !colour; }
    ctx.save();
    full = mode === "tdraw";
    if (full) return;
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
    const s = PIC; ctx.translate(W * (1 - s) / 2, H * 0.012); ctx.scale(s, s);
    ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  }
  function text(s, x, y, size, color, weight = 400, align = "center") {
    ctx.font = `${weight} ${Math.round(size)}px "Inter", sans-serif`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "middle"; ctx.fillText(s, x, y);
  }

  function draw() {
    const t = TRAILER.t;
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
    if (!started || scene === "wait") { text("CLICK OR PRESS SPACE TO PLAY", W / 2, H / 2, H * 0.03, GREY, 600); return; }
    if (scene === "hook") {                    // the sourced gap; each number lands on its spoken word
      const h = TL.hook, cnt = (n, a) => Math.round(n * clamp((t - a) / 0.35)), big = Math.min(H * 0.13, W * 0.075);
      text("Same lymphoma. Days from first symptom to treatment:", W / 2, H * 0.24, H * 0.032, INK, 500);
      if (t >= h.n123) { text(cnt(123, h.n123) + " days", W * 0.3, H * 0.47, big, INK, 800); text("occupational or private care", W * 0.3, H * 0.6, H * 0.03, GREY, 500); }
      if (t >= h.n207) { text(cnt(207, h.n207) + " days", W * 0.7, H * 0.47, big, INK, 800); text("public health centre", W * 0.7, H * 0.6, H * 0.03, GREY, 500);
                         text("Kuitunen et al., Cancer Medicine 2026 (DLBCL)", W / 2, H * 0.75, H * 0.019, FAINT, 500); }
      return;
    }
    if (scene === "scan") {                    // the one real picture, greyscale
      const k = clamp((t - TL.scan.a) / ((TL.scan.clip || TL.scan.end) - TL.scan.a)) * 0.999;   // then the last frame holds
      let im = SCAN[Math.floor(k * NSCAN)];
      if (!im || !im.complete || !im.naturalWidth) im = SCAN.find(x => x.complete && x.naturalWidth);
      if (!im) return;
      const r = Math.max(W / im.naturalWidth, H / im.naturalHeight), w = im.naturalWidth * r, hh = im.naturalHeight * r;
      ctx.drawImage(im, (W - w) / 2, (H - hh) / 2, w, hh);
      return;
    }
    if (scene === "modes") {                   // LOCKED, as approved: the two statements fade in, exactly as in trailer.js
      const m = TL.modes;
      [[m.l1, "Trust AI too little,", "and doctors check everything."], [m.l2, "Trust it too much,", "and nobody checks."]].forEach(([at, a, b], i) => {
        const k = clamp((t - at) / 0.4); if (!k) return;
        ctx.globalAlpha = k;
        text(a, W * 0.12, H * (0.36 + i * 0.26), H * 0.07, INK, 800, "left");
        text(b, W * 0.12, H * (0.45 + i * 0.26), H * 0.045, GREY, 500, "left");
        ctx.globalAlpha = 1;
      });
      return;
    }
    if (scene === "fw") {                      // the framework in three lines
      const f = TL.fw;
      if (t >= f.h) text("OUR FRAMEWORK", W * 0.12, H * 0.2, H * 0.028, GREY, 700, "left");
      [[f.l1, "Clinicians define each pipeline."], [f.l2, "The system runs it."], [f.l3, "Unsure? A doctor reviews the case."]].forEach(([at, line], i) => {
        if (t < at) return;
        text(String(i + 1), W * 0.08, H * (0.36 + i * 0.17), H * 0.055, FAINT, 700, "left");
        text(line, W * 0.12, H * (0.36 + i * 0.17), H * 0.062, INK, 800, "left");
      });
      return;
    }
    if (scene === "man") {                     // the manifesto: its points land on the words
      const m = TL.man, x = W * 0.12;
      if (t >= m.lab) text("WHAT WE BELIEVE", x, H * 0.16, H * 0.026, GREY, 700, "left");
      if (t >= m.m1) { text("Free doctors from repeating tasks,", x, H * 0.27, H * 0.06, INK, 800, "left");
                       text("so they can concentrate on difficult cases.", x, H * 0.35, H * 0.038, GREY, 500, "left"); }
      [[m.i1, "Scheduling visits."], [m.i2, "Routing patients to the right specialists."], [m.i3, "Identifying symptoms."]].forEach(([at, l], i) => {
        if (at !== undefined && t >= at) text(l, x, H * (0.5 + i * 0.09), H * 0.045, INK, 600, "left"); });
      return;
    }
    if (scene === "credit") {                  // the challenge, then each name on its word (with its chime)
      const c = TL.credit;
      text("THE CHALLENGE", W / 2, H * 0.3, H * 0.022, GREY, 600);
      text("AstraZeneca: Equal Care Across Finland", W / 2, H * 0.37, H * 0.045, INK, 700);
      if (t >= c.b1) {                         // three parts, true to what runs where: the model, where it is served, the note reader
        [[0.2, "DECISION MODEL", "NVIDIA Nemotron"], [0.5, "SERVED ON", "Modal"], [0.8, "NOTE READER", "Verda"]].forEach(([x, lab, name]) => {
          text(lab, W * x, H * 0.55, H * 0.022, GREY, 600); text(name, W * x, H * 0.62, H * 0.05, INK, 800); });
        ctx.fillStyle = "rgba(0,0,0,0.25)"; ctx.fillRect(W * 0.35 - 1, H * 0.52, 2, H * 0.15); ctx.fillRect(W * 0.65 - 1, H * 0.52, 2, H * 0.15);
      }
      return;
    }
    // the suggestion, a beat, then the punchline alone
    const e = TL.fin;
    if (t < e.punch) {
      if (t >= e.lab) text("OUR SUGGESTION", W * 0.12, H * 0.24, H * 0.028, GREY, 700, "left");
      if (t >= e.l1) { text("Pilot one clinician-validated pipeline", W * 0.12, H * 0.35, H * 0.06, INK, 800, "left");
                       text("in North Savo.", W * 0.12, H * 0.43, H * 0.06, INK, 800, "left"); }
      if (t >= e.l2) text("Track treatment within target times.", W * 0.12, H * 0.56, H * 0.042, GREY, 500, "left");
      if (t >= e.l3) text("More time for hard cases and the human encounter.", W * 0.12, H * 0.66, H * 0.042, INK, 600, "left");
      return;
    }
    text("Waiting is a decision nobody made.", W / 2, H * 0.48, H * 0.075, INK, 800);
    if (t >= e.repo) text("github.com/Toivo31/cancer", W / 2, H * 0.62, H * 0.024, GREY, 500);
  }

  // over the animation: it runs inside our framework
  function overlay(mode) {
    if (mode !== "flow" || !TL) return;
    const a = clamp((T() - TL.anim.a) / 0.3);
    ctx.save(); ctx.globalAlpha = a;
    ctx.fillStyle = "rgba(251,249,239,0.96)"; ctx.fillRect(W * 0.76, H * 0.045, W * 0.23, H * 0.12);
    ctx.strokeStyle = "rgba(30,30,28,1)"; ctx.lineWidth = 2.5; ctx.strokeRect(W * 0.76, H * 0.045, W * 0.23, H * 0.12);
    text("IN OUR FRAMEWORK", W * 0.875, H * 0.088, H * 0.027, "rgba(30,30,28,1)", 800);
    text("clinician-defined rules", W * 0.875, H * 0.133, H * 0.017, "#333", 500);
    ctx.restore();
  }

  // captions only where the voice says something the screen does not. TV style: white text on a grey box that
  // hugs each line, so a caption never reads as part of the slide
  function finish() {
    ctx.restore();
    const y0 = full ? H * 0.86 : H * (0.012 + PIC) + H * 0.008;
    if (!full) { ctx.fillStyle = PAPER; ctx.fillRect(0, y0, W, H - y0); }
    const t = T(), c = CAPS.find(([a, b]) => t >= a && t < b); if (!c || !started || qs.has("nocap")) return;
    const size = H * 0.027; ctx.font = `500 ${Math.round(size)}px "Inter", sans-serif`;
    const maxW = W * 0.72;
    const wrap = s => { const out = []; let cur = ""; for (const w of s.split(" ")) { const tr = cur ? cur + " " + w : w; if (ctx.measureText(tr).width > maxW && cur) { out.push(cur); cur = w; } else cur = tr; } out.push(cur); return out; };
    // like TV subtitles: at most two lines at a time, broken at sentence ends; each part shows for its share of the line
    const groups = []; let pend = "";
    for (const sen of c[2].split(/(?<=[.!?])\s+/)) {
      const both = pend ? pend + " " + sen : sen;
      if (wrap(both).length <= 2) { pend = both; continue; }
      if (pend) groups.push(wrap(pend));
      const ls = wrap(sen); for (let i = 0; i < ls.length; i += 2) groups.push(ls.slice(i, i + 2));
      pend = "";
    }
    if (pend) groups.push(wrap(pend));
    const lines = groups.flat(), total = lines.join(" ").length, frac = (t - c[0]) / (c[1] - c[0]);
    let shown = groups[groups.length - 1], acc = 0;
    for (const g of groups) { acc += g.join(" ").length / total; if (frac < acc) { shown = g; break; } }
    const lh = size * 1.45, mid = (y0 + H) / 2, padX = size * 0.5, boxH = size * 1.4;
    shown.forEach((l, i, lines) => {
      const y = mid + (i - (lines.length - 1) / 2) * lh, w = ctx.measureText(l).width;
      ctx.fillStyle = "rgba(48,48,46,0.88)"; ctx.fillRect(W / 2 - w / 2 - padX, y - boxH / 2, w + 2 * padX, boxH);
      text(l, W / 2, y, size, "#ffffff", 500);
      ctx.font = `500 ${Math.round(size)}px "Inter", sans-serif`;
    });
  }

  return { active: true, update, begin, draw, overlay, finish, t: 0, docT: 0, get LEN() { return TL ? TL.len : 60; } };
})();
