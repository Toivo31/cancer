"use strict";
// Final trailer preview (index.html?final): Tuomas's "Trailer: the full idea script (final version)" cut to ONE
// MINUTE. Same five acts, cards and announcer, shorter shots, no narrator. Music: the Cymatics excerpt from 0:12.5
// at excerpt 29.3 s (film time = excerpt time - 16.8 s), so its drop (excerpt 49.8) lands at 0:33 on Norway;
// hard stop at 0:47.
// Pieces still missing are shown as PLACEHOLDER (the real diagnosis clip, the friend's shots F1 and F2,
// the team's corridor shot); our Gemini stills stand in. Sound effects are synthesised here.
// Clock: wall time (no voice-over track). ?mute: no sound. ?from=<s>: start there.

const FINAL = (() => {
  if (!qs.has("final")) return { active: false };
  help.classList.add("hidden"); st.ui = false; st.playing = false;

  const LEN = 60, DROP = 33, MUSIC_IN = 12.5, MUSIC_OUT = 47, OFFSET = 16.8, PIC = 0.86;
  const mute = qs.has("mute");
  const music = new Audio("audio/excerpt.wav"); music.preload = "auto";
  const img = {};
  for (const id of ["a2_consultation", "a4_stain", "b2_slip", "b3_waiting_room", "b4_unfold", "b9_door"]) {
    const im = new Image(); im.src = `trailer_assets/${id}_still.png`; img[id] = im;
  }

  // ---- sound: announcer (filtered to sound like a PA), chime, typewriter clicks, stamps
  let ac = null, buffers = {}, started = false, t0 = 0, fired = new Set();
  async function loadBuf(name) {
    const r = await fetch(`trailer_assets/${name}.wav`); buffers[name] = await ac.decodeAudioData(await r.arrayBuffer());
  }
  function announcer(name) {
    if (!ac || !buffers[name]) return;
    const s = ac.createBufferSource(); s.buffer = buffers[name];
    const bp = ac.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 1700; bp.Q.value = 0.8;
    const g = ac.createGain(); g.gain.value = 1.6;
    s.connect(bp).connect(g).connect(ac.destination); s.start();
  }
  function tone(freq, dur, vol = 0.2, type = "sine") {
    if (!ac) return;
    const o = ac.createOscillator(), g = ac.createGain(); o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(vol, ac.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + dur);
    o.connect(g).connect(ac.destination); o.start(); o.stop(ac.currentTime + dur);
  }
  function noise(dur, vol, freq) {
    if (!ac) return;
    const n = ac.createBuffer(1, ac.sampleRate * dur, ac.sampleRate), d = n.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 3);
    const s = ac.createBufferSource(), f = ac.createBiquadFilter(), g = ac.createGain();
    s.buffer = n; f.type = "bandpass"; f.frequency.value = freq; g.gain.value = vol;
    s.connect(f).connect(g).connect(ac.destination); s.start();
  }
  const click = () => noise(0.04, 0.6, 3000);
  const stamp = () => { noise(0.12, 1.2, 180); tone(70, 0.2, 0.3); };
  const chime = () => { tone(660, 1.4, 0.15); setTimeout(() => tone(880, 1.6, 0.12), 350); };

  // one-shot sound cues (film time, action)
  const CUES = [
    [4.2, () => announcer("an1_take_number")],
    [9, click], [9.6, click], [10.2, click],
    [13, click], [14.3, click], [15.9, click],
    [25.3, stamp], [26.1, stamp], [26.9, stamp],
    [50, chime], [50.4, () => announcer("an2_number_one")],
    [52, click], [52.6, click],
  ];

  async function start() {
    if (started) return;
    started = true; t0 = performance.now() / 1000 - (+(qs.get("from") || 0));
    if (!mute) { ac = new AudioContext(); await Promise.all(["an1_take_number", "an2_number_one"].map(loadBuf)).catch(() => {}); }
  }
  window.addEventListener("click", start);
  window.addEventListener("keydown", e => { if (e.key === " ") { start(); e.stopImmediatePropagation(); e.preventDefault(); } }, true);
  const T = () => (started ? performance.now() / 1000 - t0 : +(qs.get("from") || 0));

  function sound(t) {
    if (mute || !started) return;
    for (const [at, fn] of CUES) if (t >= at && t < at + 0.5 && !fired.has(at)) { fired.add(at); fn(); }
    if (t >= MUSIC_IN && t < MUSIC_OUT) {
      const want = t + OFFSET;
      if (music.paused || Math.abs(music.currentTime - want) > 0.35) { music.currentTime = want; music.play().catch(() => {}); }
      music.volume = Math.min(1, (t - MUSIC_IN) / 1.5);
    } else if (!music.paused) music.pause();          // dead stop on the bar at 1:41
  }

  function setScene(scenIdx, split, pair) {
    if (st.scen !== scenIdx) { st.scen = scenIdx; for (const k in shown) delete shown[k]; snap = true; }
    st.v = 0; st.split = split; if (pair) st.splitPair = pair;
  }

  // ---- timeline
  let part = "film";
  function update() {
    const t = T(); FINAL.t = t; sound(t);
    if (t < 17.5) { part = "film"; return "tdraw"; }
    if (t < 31.5) { FLOW.newKey = "baseline"; st.day = Math.min(140, (t - 17.5) * 8); return "flow"; }
    if (t < DROP) { FLOW.newKey = "baseline"; st.day = 105; return "flow"; }                    // ghost search
    if (t < 42) { setScene(1, true, [0, 1]); st.day = 28 + (t - DROP) * 6; return "lanes"; }
    if (t < 47) { FINAL.docT = 6 + (t - 42) * 1.3; return "doc"; }
    part = "end"; return "tdraw";
  }

  // ---- helpers (picture coordinates W x H inside the top band)
  function begin() {
    ctx.save(); ctx.fillStyle = "#fdfcf8"; ctx.fillRect(0, 0, W, H);
    ctx.translate(W * (1 - PIC) / 2, H * 0.012); ctx.scale(PIC, PIC);
    ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  }
  function still(id, a, dur, zoom = 0.08) {
    const im = img[id]; if (!im.complete || !im.naturalWidth) return;
    const k = Math.max(0, Math.min(1, (FINAL.t - a) / dur)), s = 1 + zoom * k;
    const r = Math.max(W / im.naturalWidth, H / im.naturalHeight) * s, w = im.naturalWidth * r, h = im.naturalHeight * r;
    ctx.drawImage(im, (W - w) / 2, (H - h) / 2, w, h);
  }
  const black = (a = 1) => { ctx.fillStyle = `rgba(0,0,0,${Math.max(0, Math.min(1, a))})`; ctx.fillRect(0, 0, W, H); };
  function text(s, x, y, size, color, weight = 400, align = "center") {
    ctx.font = `${weight} ${Math.round(size)}px "Inter", sans-serif`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "middle"; ctx.fillText(s, x, y);
  }
  function mono(s, x, y, size, color, align = "center") {
    ctx.font = `${Math.round(size)}px ui-monospace, "Courier New", monospace`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "middle"; ctx.fillText(s, x, y);
  }
  function typed(s, at, x, y, size, color, cps = 28) {        // typewriter reveal
    const n = Math.max(0, Math.min(s.length, Math.floor((FINAL.t - at) * cps)));
    mono(s.slice(0, n), x, y, size, color);
  }
  function placeholder(label) {
    ctx.fillStyle = "rgba(0,0,0,0.65)"; ctx.fillRect(W * 0.02, H * 0.03, W * 0.36, H * 0.05);
    text("PLACEHOLDER · " + label, W * 0.03, H * 0.055, H * 0.02, "#fff", 600, "left");
  }
  function card(s, size = 0.052, y = 0.5, bg = true) {
    if (bg) { ctx.fillStyle = "rgba(253,252,248,0.82)"; ctx.fillRect(0, H * (y - 0.07), W, H * 0.14); }
    mono(s, W / 2, H * y, H * size, "#111");
  }
  function paper(lines, starts, pushFrom, pushDur) {          // the slip: typed lines, then push into the ink
    const k = pushFrom === null ? 0 : Math.max(0, (FINAL.t - pushFrom) / pushDur), s = 1 + 9 * k * k;
    black();
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(s, s);
    ctx.fillStyle = "#f3eee0"; ctx.fillRect(-W * 0.38, -H * 0.22, W * 0.76, H * 0.44);
    ctx.translate(-W / 2, -H / 2);
    lines.forEach((l, i) => typed(l, starts[i], W / 2, H * (0.44 + i * 0.11), H * 0.033, "#151515"));
    ctx.restore();
    black((k - 0.7) * 3.5);
  }

  // ---- film world (acts 1, 2 and 5)
  function draw() {
    const t = FINAL.t;
    black();
    if (!started) { text("CLICK OR PRESS SPACE TO PLAY · FINAL SCRIPT, 1 MINUTE", W / 2, H / 2, H * 0.03, "#ddd", 600); return; }
    if (part === "film") {
      if (t < 4) {                                              // the diagnosis (real clip goes here)
        if (t < 2) still("a2_consultation", 0, 2, 0.05); else still("a4_stain", 2, 2, 0.12);
        placeholder("real diagnosis clip, trim to 4 s");
      } else if (t < 7) {                                       // the corridor and the red sign
        still("b3_waiting_room", 4, 3, 0.06);
        ctx.fillStyle = "#0b0505"; ctx.fillRect(W * 0.32, H * 0.29, W * 0.36, H * 0.13);
        mono("YOUR EXPECTED WAIT TIME", W / 2, H * 0.32, H * 0.022, "#ff3b2f");
        mono("FOR CANCER DIAGNOSIS: 87 DAYS", W / 2, H * 0.365, H * 0.026, "#ff3b2f");
        text("Dramatisation", W * 0.97, H * 0.06, H * 0.02, "rgba(255,255,255,0.85)", 600, "right");
        placeholder("team's corridor shot");
      } else if (t < 9) still("b4_unfold", 7, 2, 0.06);
      else if (t < 13) paper(["A COMPUTER CAN NEVER BE HELD ACCOUNTABLE", "THEREFORE A COMPUTER MUST NEVER", "MAKE A MANAGEMENT DECISION"], [9, 9.6, 10.2], 11.2, 1.8);
      else {                                                    // act 2: the flip, one card per bar
        if (t < 14.3) typed("NEITHER CAN A QUEUE.", 13, W / 2, H * 0.5, H * 0.05, "#f2f2f2", 40);
        else if (t < 15.9) typed("YET A QUEUE DECIDES HOW LONG YOU WAIT.", 14.3, W / 2, H * 0.5, H * 0.045, "#f2f2f2", 45);
        else typed("NOBODY CHOSE 87 DAYS.", 15.9, W / 2, H * 0.5, H * 0.055, "#f2f2f2", 40);
      }
      return;
    }
    // act 5: the call
    if (t < 50.4) {
      still("b9_door", 47, 3.4, 0.03);
      const left = Math.max(0, Math.round(87 * (1 - Math.min(1, (t - 47.3) / 2.6))));
      ctx.fillStyle = "#0b0505"; ctx.fillRect(W * 0.53, H * 0.27, W * 0.17, H * 0.1);
      mono(`${left} DAYS`, W * 0.615, H * 0.32, H * 0.04, "#ff3b2f");
      if (Math.floor(t * 8) % 7 === 0) black(0.08);          // faint flicker
      return;
    }
    if (t < 52) { still("b9_door", 47, 5, 0.07); return; }
    if (t < 55) { paper(["A QUEUE CAN NEVER BE HELD ACCOUNTABLE", "THEREFORE A QUEUE MUST NEVER", "MAKE A MEDICAL DECISION"], [52, 52.6, 52.6], null, 1); return; }
    if (t < 55.6) return;
    if (t < 58) { typed("WAITING IS A DECISION NOBODY MADE.", 55.6, W / 2, H * 0.5, H * 0.05, "#f2f2f2", 30); return; }
    text("EQUAL CARE PATHWAYS", W / 2, H * 0.44, H * 0.06, "#f2f2f2", 800);
    text("github.com/Toivo31/cancer", W / 2, H * 0.53, H * 0.024, "#ccc");
    text("A doctor decides every case. All patients are simulated.", W / 2, H * 0.6, H * 0.019, "#999");
  }

  // ---- overlays on the dot scenes (acts 3 and 4)
  function overlay(mode) {
    const t = FINAL.t;
    if (mode === "flow") {
      if (t >= 31.5) {                                          // ghost search: offset copies flicker faster
        const n = Math.floor((t - 31.5) * (6 + (t - 31.5) * 10));
        ctx.save(); ctx.globalAlpha = 0.25;
        for (let i = 1; i <= 3; i++) { ctx.translate(((n * 37 * i) % 60) - 30, ((n * 23 * i) % 40) - 20); FLOW.draw(105 + i * 7, 0); }
        ctx.restore();
      }
      if (t < 22) { card("THE PATHWAY IS A MAP.", 0.05, 0.92); text("Simulated patients", W * 0.97, H * 0.04, H * 0.02, "#555", 600, "right"); }
      else if (t < 25) { card("THE MACHINES ARE FAST. THE PAPER BETWEEN THEM IS NOT.", 0.038, 0.5); placeholder("F1 paper chain, 3 s"); }
      else if (t < 29) {
        [["REFER", 25.3, 0.3], ["CT", 26.1, 0.5], ["PET-CT", 26.9, 0.7]].forEach(([w, at, x]) => {
          if (t < at) return;
          const k = Math.min(1, (t - at) / 0.15), s = 1.6 - 0.6 * k;
          ctx.save(); ctx.translate(W * x, H * 0.3); ctx.rotate(-0.08); ctx.scale(s, s);
          ctx.strokeStyle = "#111"; ctx.lineWidth = 6; ctx.strokeRect(-W * 0.08, -H * 0.05, W * 0.16, H * 0.1);
          mono(w, 0, 0, H * 0.05, "#111"); ctx.restore();
        });
        card("EVERY DECISION WAS RIGHT.", 0.05, 0.92);
        placeholder("F2 stamps, 4 s");
      }
      else if (t < 31.5) card("TOGETHER, THEY BUILT THE QUEUE.", 0.05, 0.92);
    }
    if (mode === "lanes") {
      ctx.fillStyle = "rgba(253,252,248,0.94)"; ctx.fillRect(W * 0.28, H * 0.0, W * 0.44, H * 0.17);
      text("40%  →  80%", W / 2, H * 0.075, H * 0.1, "#111", 800);
      text("Treated on time. Same tests, new order. Model estimate, Stokstad et al. 2019.", W / 2, H * 0.145, H * 0.02, "#444");
      if (t >= 38.5) card("MORE CAPACITY: 48%.  NEW ROUTE: 80%.", 0.05, 0.55);
    }
    if (mode === "doc") {
      if (t < 44.3) card("EVERY STEP SEES THE WHOLE.", 0.045, 0.06);
      else card("A DOCTOR STILL DECIDES.", 0.045, 0.06);
    }
  }

  // bottom band: what is heard (announcer lines) as subtitles
  const SUBS = [[4.2, 8.5, "ANNOUNCER: Please take a number. Your wait is normal."], [50.4, 52.2, "ANNOUNCER: Number one."]];
  function finish() {
    ctx.restore();
    const y0 = H * (0.012 + PIC) + H * 0.008;
    ctx.fillStyle = "#fdfcf8"; ctx.fillRect(0, y0, W, H - y0);
    const t = FINAL.t, s = SUBS.find(([a, b]) => t >= a && t < b);
    if (s && started) text(s[2], W / 2, (y0 + H) / 2, H * 0.027, "#1f1f1d", 500);
    if (started) text(`${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`, W * 0.985, (y0 + H) / 2, H * 0.016, "#999", 400, "right");
  }

  return { active: true, update, begin, draw, overlay, finish, t: 0, docT: 0, LEN };
})();
