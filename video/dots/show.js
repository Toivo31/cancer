"use strict";
// Music-synced sample of the video: index.html?show
// Drives the dot animation from the audio clock and draws title, gap and implementation cards plus
// subtitles. Audio: ?audio=<url>, default audio/excerpt.wav (kept out of git by audio/.gitignore).
// Times are seconds in the 2:00 excerpt (song 0:30-2:30); see docs/video_plan_draft.md, "Music map".

const SHOW = (() => {
  const active = qs.has("show");
  if (!active) return { active: false };
  const audio = new Audio(qs.get("audio") || "audio/excerpt.wav");
  audio.preload = "auto";
  let started = false;
  help.classList.add("hidden");
  st.playing = false; st.ui = true;

  const DROP = 49.8;
  const T = { title: 0, gap: 1.5, where: 9, drop: DROP, norway: 58, cards: 72, end: 92, stop: 98 };
  const S0 = 25, S1 = 36, K = 3.38, SLOW = 0.15;   // slow-motion popup; K = simulation days per second (not sped up)

  const SUBS = [
    [1.5, 9, "Two Finns with the same lymphoma. Through occupational or private care: treatment in 123 days. Through a public health centre: 207 days."],
    [9, 20, "Lung cancer in Finland has the longest early waits in the Nordics. Each dot is one simulated patient, from first contact to treatment."],
    [20, 25, "Pink: vague symptoms. Today they are sent back to the GP again and again."],
    [25, 36, "Her referral arrives at the hospital. Our note reader flags the warning signs; the decision model estimates which test finds the cancer fastest. A clinician decides."],
    [36, DROP, "She goes on the fast lane."],
    [DROP, 58, "Reordering two steps alone: 18 to 33 percent within 90 days. With a fast lane, up to 61 percent if urgent booking times hold. Same cancers missed. A clinician decides."],
    [58, 72, "Tested blind on a real Norwegian hospital study: it reproduces their 40 percent, and the reordering that reached 80."],
    [72, 92, "What a wellbeing services county does."],
    [92, 98, "A doctor decides every case. All patients are simulated."],
  ];
  const CARDS = [
    [73.5, "1  ORDER TESTS TOGETHER", "Lung unit books PET-CT, exercise test and tumour board at the first specialist visit.", "Measure: share treated within target"],
    [77.5, "2  DIRECT CT FROM PRIMARY CARE", "Health centres order chest CT directly, with a shared rule for when.", "Measure: days from first contact to CT"],
    [81.5, "3  PUBLISH WAITS PER STEP", "Time to treatment per step and per county, every year (THL, Cancer Registry).", "Goal 3 indicator: treatment within target times"],
    [85.5, "PILOT IN ONE COUNTY FIRST", "Measure before and after.", ""],
  ];

  // ?mute: run on a silent clock (testing, or recording picture only). Otherwise the audio is the clock.
  const mute = qs.has("mute");
  let t0 = 0, pausedAt = null;
  function start() {
    const from = +(qs.get("from") || 0);
    if (started) {
      if (mute) { if (pausedAt === null) pausedAt = clock(); else { t0 = performance.now() / 1000 - pausedAt; pausedAt = null; } }
      else audio.paused ? audio.play() : audio.pause();
      return;
    }
    started = true;
    if (mute) { t0 = performance.now() / 1000 - from; return; }
    const go = () => { audio.currentTime = from; audio.play(); };
    audio.readyState >= 1 ? go() : audio.addEventListener("loadedmetadata", go, { once: true });
  }
  function clock() {
    if (mute) return pausedAt !== null ? pausedAt : performance.now() / 1000 - t0;
    return audio.currentTime;
  }
  window.addEventListener("click", start);
  window.addEventListener("keydown", (e) => { if (e.key === " ") { start(); e.stopImmediatePropagation(); e.preventDefault(); } }, true);

  function setScene(scenIdx, v, split, pair) {
    if (st.scen !== scenIdx) { st.scen = scenIdx; for (const k in shown) delete shown[k]; snap = true; }
    st.v = v; st.split = split; if (pair) st.splitPair = pair;
  }

  // returns "card" (draw only the card) or "lanes" (draw the animation)
  function update() {
    const t = started ? clock() : +(qs.get("from") || 0);
    SHOW.t = t;
    // music fades out over the last 2 s and stops
    if (!mute && started) { audio.volume = Math.max(0, Math.min(1, (T.stop - t) / 2)); if (t >= T.stop && !audio.paused) audio.pause(); }
    if (t < T.where) return "card";
    // flow scene at a constant K days per second; slow motion S0-S1 with a full-page popup of one
    // patient's note being read; no fast-forward afterwards (the drop lands around day 102)
    if (t < T.norway) {
      const d0 = (S0 - T.where) * K, d1 = d0 + (S1 - S0) * SLOW;
      if (t < S0) st.day = (t - T.where) * K;
      else if (t < S1) st.day = d0 + (t - S0) * SLOW;
      else st.day = d1 + (t - S1) * K;
      if (FLOW.focus === null) FLOW.focus = FLOW.pickFocus(d0 + 1);
      FLOW.ring = t > S0 - 2 && t < S1 + 3;
      if (t >= S0 && t < S1) { SHOW.popT = t - S0; SHOW.popDur = S1 - S0; return "pop"; }
      return "flow";
    }
    if (t < T.cards) { setScene(1, 0, true, [0, 1]); st.day = (t - T.norway) * 3.3; return "lanes"; }
    return "card";
  }

  function text(s, x, y, size, color, font = "Courier Prime", align = "center") {
    ctx.font = `${font === "DotGothic16" ? "600 " : ""}${Math.round(size)}px "Inter", sans-serif`; ctx.fillStyle = color;
    ctx.textAlign = align; ctx.textBaseline = "alphabetic"; ctx.fillText(s, x, y);
  }
  function glow(on) { ctx.shadowColor = "rgba(30,135,85,0.55)"; ctx.shadowBlur = on ? 16 : 0; }
  const fade = (t, a, d = 0.6) => Math.max(0, Math.min(1, (t - a) / d));

  function drawCard() {
    const t = SHOW.t;
    if (!started) {
      text("PRESS SPACE OR CLICK TO START", W / 2, H / 2, H * 0.035, "rgba(45,45,42,0.9)", "DotGothic16");
      return;
    }
    if (t < T.gap) {
      glow(true); text("EQUAL CARE PATHWAYS", W / 2, H * 0.5, H * 0.08, `rgba(30,135,85,${fade(t, 0, 0.8)})`, "DotGothic16"); glow(false);
      return;
    }
    if (t < T.where) {
      text("SAME CANCER, DIFFERENT DOOR", W * 0.08, H * 0.2, H * 0.04, "rgba(45,45,42,0.95)", "DotGothic16", "left");
      const rows = [["Occupational or private care", 123, "rgba(30,135,85,0.9)"], ["Public health centre", 207, "rgba(200,125,0,0.95)"]];
      const x0 = W * 0.08, maxW = W * 0.75, k = Math.min(1, (t - T.gap) / 6);
      rows.forEach(([lab, d, c], i) => {
        const y = H * (0.4 + i * 0.2), w = maxW * (d / 220) * k;
        text(lab, x0, y - H * 0.025, H * 0.026, "rgba(45,45,42,0.85)", "Courier Prime", "left");
        ctx.fillStyle = c; ctx.fillRect(x0, y, w, H * 0.06);
        text(Math.round(d * k) + " days", x0 + w + W * 0.012, y + H * 0.045, H * 0.04, c, "DotGothic16", "left");
      });
      text("Days from symptom onset to treatment start, DLBCL (lymphoma). Kuitunen et al., Cancer Medicine 2026;15:e71920",
           x0, H * 0.84, H * 0.018, "rgba(105,105,100,0.9)", "Courier Prime", "left");
      return;
    }
    if (t < T.end) {
      text("WHAT A WELLBEING SERVICES COUNTY DOES", W * 0.06, H * 0.13, H * 0.036, "rgba(45,45,42,0.95)", "DotGothic16", "left");
      CARDS.forEach(([at, head, body, meas], i) => {
        const a = fade(t, at, 0.4); if (!a) return;
        const y = H * (0.2 + i * 0.165);
        ctx.strokeStyle = `rgba(30,135,85,${0.4 * a})`; ctx.lineWidth = 1.5;
        ctx.strokeRect(W * 0.06, y, W * 0.88, H * 0.14);
        glow(true); text(head, W * 0.08, y + H * 0.05, H * 0.032, `rgba(30,135,85,${a})`, "DotGothic16", "left"); glow(false);
        text(body, W * 0.08, y + H * 0.09, H * 0.024, `rgba(45,45,42,${0.9 * a})`, "Courier Prime", "left");
        if (meas) text(meas, W * 0.08, y + H * 0.123, H * 0.019, `rgba(200,125,0,${0.9 * a})`, "Courier Prime", "left");
      });
      return;
    }
    const a = fade(t, T.end, 0.8);
    glow(true); text("EQUAL CARE PATHWAYS", W / 2, H * 0.45, H * 0.07, `rgba(30,135,85,${a})`, "DotGothic16"); glow(false);
    text("[TEAM NAME]  ·  github.com/Toivo31/cancer  ·  [DEMO LINK]", W / 2, H * 0.55, H * 0.024, `rgba(45,45,42,${0.85 * a})`);
  }

  function drawSubs() {
    const t = SHOW.t; if (!started) return;
    const s = SUBS.find(([a, b]) => t >= a && t < b); if (!s) return;
    const size = H * 0.026, maxW = W * 0.8;
    ctx.font = `${Math.round(size)}px "Inter", sans-serif`;
    const lines = [], words = s[2].split(" "); let cur = "";
    for (const w of words) { const tryL = cur ? cur + " " + w : w; if (ctx.measureText(tryL).width > maxW && cur) { lines.push(cur); cur = w; } else cur = tryL; }
    if (cur) lines.push(cur);
    const lh = size * 1.35, boxH = lines.length * lh + size * 0.7, yTop = H * 0.975 - boxH;
    ctx.fillStyle = "rgba(255,255,255,0.92)"; ctx.fillRect(W * 0.08, yTop, W * 0.84, boxH); ctx.fillStyle = "#e8c56a"; ctx.fillRect(W * 0.08, yTop, W * 0.004, boxH);
    lines.forEach((l, i) => text(l, W / 2, yTop + size * 0.35 + lh * (i + 0.8), size, "rgba(45,45,42,0.95)"));
  }

  return { active: true, update, drawCard, drawSubs, t: 0 };
})();
