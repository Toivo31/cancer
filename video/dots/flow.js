"use strict";
// Flow scene: two vertical flowcharts side by side. Left = today's pathway, right = the optimiser's change
// (fast lane: suspected cancer gets priority once the hospital has handled the referral). Every ball is one
// simulated lung cancer patient (same 521 patients on both sides), coloured by symptom group: pink = vague
// (non-specific) symptoms, white = alarm symptoms. Balls start at the bottom (first contact) and climb towards
// treatment; waiting balls swarm around a step; a ball sent home with the cancer missed turns red and drops out.
// Note cards: left shows how notes can hide warning signs; right shows our note reader + decision model
// (prototype) flagging them. Note texts are synthetic examples from technique_classifier/taxonomies.
// Standalone: index.html?flow ; also used by ?show.

const FLOW = (() => {
  const SHOW_DOCS = false; // strategy picture and article cards (sources stay in README)
  // node -> [row (0 = bottom), x offset in panel widths]
  const POS = {
    nurse_visit: [0, -0.2], gp_visit: [0, 0.2], gp_after_nurse: [1, -0.2], cxr: [2, 0],
    persist: [3, -0.3], second_look: [3, 0.25], represent: [4, -0.3], gp_referral: [4, 0.05],
    triage: [5, 0], spec_visit: [6, 0], ct: [7, 0], bronch: [8, -0.2], ttnb: [8, 0.2],
    pet: [9, 0], mdt: [10, 0], book_treat: [11, 0], __finish: [12, 0],
  };
  const LABEL = {
    nurse_visit: "Nurse", gp_visit: "GP", gp_after_nurse: "GP after nurse", cxr: "Chest X-ray",
    persist: "Symptoms persist?", second_look: "GP re-reads X-ray", represent: "Back to GP",
    gp_referral: "GP referral", triage: "Hospital handles referral", spec_visit: "Specialist", ct: "CT",
    bronch: "Bronchoscopy", ttnb: "Needle biopsy", pet: "PET-CT", mdt: "Tumour board",
    book_treat: "Treatment slot",
  };
  const FAST_FROM_ROW = 6;          // fast lane from the specialist visit upwards (after referral handling)
  const ROWS = 12;
  const VAGUE = "non_specific";
  const FAST_GAIN = 21;   // drawn on the fast lane: priority moved the patient ahead by 3+ weeks (271 of 466); the rest on the regular route

  // synthetic example notes: [before, flagged span, after, left tag (problem), right tag (our flag)]
  const NOTES = [
    ["Tired, lost 6 kg. ", "Likely stress.", " Return if needed.",
     "no test · back to GP", "FLAG: unexplained weight loss → CT"],
    ["Visit 3: cough 7 wks, smoker. ", "Still bronchitis as before.", " Antibiotics renewed.",
     "same diagnosis 3 visits", "FLAG: anchoring, 3 visits → refer"],
    ["", "Frequent attender,", " insists something is wrong. Reassured.",
     "label instead of a test", "FLAG: stigmatising language → review"],
    ["Hb 98, ferritin low. ", "Iron tablets started.", " No follow-up.",
     "red flag, no referral", "FLAG: red flag without action → fast lane"],
  ];

  // sourced inequality facts shown on the left (not simulated): [head, text, source]
  const EVIDENCE = [
    ["INCOME / WORK", "Same lymphoma: 123 days to treatment via occupational or private care, 207 via a public health centre.", "Kuitunen et al., Cancer Medicine 2026"],
    ["LOW INCOME", "Upfront fees for several cancer services can be a barrier for people on low incomes.", "OECD/EU Cancer Profile Finland 2025"],
    ["EDUCATION", "Lung cancer is over twice as common among the least educated, and they get surgery less often.", "OECD/EU 2025 · Zai et al. 2025"],
    ["EASTERN FINLAND", "Kainuu, Etelä-Savo, Pohjois-Karjala: most life years lost to early death (men); low income more common.", "THL 2022 · all causes, 2017-2019"],
  ];

  function wrap(text, x, y, maxW, lh) {
    let line = "", yy = y;
    for (const w of text.split(" ")) {
      const t = line ? line + " " + w : w;
      if (ctx.measureText(t).width > maxW && line) { ctx.fillText(line, x, yy); line = w; yy += lh; } else line = t;
    }
    if (line) ctx.fillText(line, x, yy);
    return yy + lh;
  }

  function evidenceBox(g, idx, a) {
    const [head, text, src] = EVIDENCE[idx % EVIDENCE.length];
    const x = W * 0.008, y = g.y(1.75), w = W * 0.12;
    ctx.globalAlpha = a;
    ctx.fillStyle = "rgba(205,40,125,0.9)"; ctx.fillRect(x, y, W * 0.003, H * 0.17);
    ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.font = `600 ${Math.round(H * 0.0135)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(205,40,125,0.8)";
    ctx.fillText("WHO FALLS BEHIND", x + W * 0.007, y);
    ctx.font = `600 ${Math.round(H * 0.0165)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(205,40,125,1)";
    ctx.fillText(head, x + W * 0.007, y + H * 0.019);
    ctx.font = `${Math.round(H * 0.0135)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(45,45,42,0.92)";
    const yy = wrap(text, x + W * 0.007, y + H * 0.045, w, H * 0.0175);
    ctx.font = `${Math.round(H * 0.012)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(105,105,100,0.9)";
    wrap(src + " · sourced, not simulated", x + W * 0.008, yy + H * 0.004, w, H * 0.016);
    ctx.globalAlpha = 1;
  }

  // evidence panel (left half): the strategy cover plus cards for peer-reviewed or working-paper sources.
  // Every number on a card was checked against the source text (see README, "Sources checked").
  const PICS = [
    { src: "img/strategy.png", at: 3, rot: -0.03, x: 0.03, y: 0.12, w: 0.2,
      head: "NATIONAL CANCER STRATEGY 2026-2035 · GOAL 3",
      cap: "Indicator 3.1: \"Potilaat pääsevät hoitoon tavoiteaikojen puitteissa\" (patients reach treatment within target times). STM, p. 33." },
  ];
  if (SHOW_DOCS) PICS.forEach(p => { p.img = new Image(); p.img.onload = () => { p.ok = true; }; p.img.src = p.src; });

  const ARTICLES = [
    { at: 18, rot: 0.025, x: 0.255, y: 0.11, w: 0.2,
      journal: "BR J GEN PRACT 2019;69(689):e827-35",
      title: "Sensitivity of chest X-ray for detecting lung cancer in people presenting with symptoms: a systematic review",
      authors: "Bradley SH, Abraham S, Callister MEJ, et al.",
      big: "77-80%", label: "of lung cancers seen on chest X-ray (best studies)",
      use: "Why our model suggests direct CT", doi: "doi:10.3399/bjgp19X706853" },
    { at: 30, rot: -0.02, x: 0.03, y: 0.44, w: 0.2,
      journal: "BMC HEALTH SERV RES 2019;19:679",
      title: "Reasons for prolonged time for diagnostic workup for stage I-II lung cancer and estimated effect of applying an optimized pathway",
      authors: "Stokstad T, et al.",
      big: "40% → 80%", label: "treated within 42 days: observed → reordered pathway (model estimate)",
      use: "The published case our simulator reproduces", doi: "doi:10.1186/s12913-019-4517-z" },
    { at: 42, rot: 0.02, x: 0.255, y: 0.44, w: 0.2,
      journal: "MPIDR WORKING PAPER WP 2025-016",
      title: "Disparities in cancer stage at diagnosis, treatment, and mortality across socioeconomic groups in Finland",
      authors: "Zai X, Li P, Dei Bardi L, et al.",
      big: "OR 1.48", label: "lung cancer surgery, women with high vs low education; similar by income",
      use: "Who falls behind in Finland", doi: "doi:10.4054/MPIDR-WP-2025-016" },
  ];

  function articleCard(a, alpha) {
    const w = W * a.w, pad = W * 0.01, x = W * a.x, y = H * a.y;
    // measure height first
    ctx.font = `600 ${Math.round(H * 0.0155)}px "Inter", sans-serif`;
    const titleLines = Math.ceil(ctx.measureText(a.title).width / (w - 2 * pad)) + 0.4;
    const h = H * (0.02 + 0.024 + 0.022 * titleLines + 0.03 + 0.05 + 0.03 + 0.028);
    ctx.save(); ctx.globalAlpha = alpha;
    ctx.translate(x + w / 2, y + h / 2); ctx.rotate(a.rot * (2 - alpha)); ctx.translate(-w / 2, -h / 2);
    ctx.shadowColor = "rgba(0,0,0,0.14)"; ctx.shadowBlur = 16; ctx.shadowOffsetY = 4;
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, w, h);
    ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
    ctx.fillStyle = "#e8c56a"; ctx.fillRect(0, 0, w, H * 0.005);
    ctx.textAlign = "left"; ctx.textBaseline = "top";
    let yy = H * 0.018;
    ctx.font = `600 ${Math.round(H * 0.0115)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(105,105,100,0.95)";
    ctx.fillText(a.journal, pad, yy); yy += H * 0.022;
    ctx.font = `600 ${Math.round(H * 0.0155)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(30,30,28,0.95)";
    yy = wrap(a.title, pad, yy, w - 2 * pad, H * 0.021);
    ctx.font = `${Math.round(H * 0.012)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(105,105,100,0.95)";
    ctx.fillText(a.authors, pad, yy + H * 0.002); yy += H * 0.03;
    ctx.fillStyle = "rgba(0,0,0,0.08)"; ctx.fillRect(pad, yy - H * 0.006, w - 2 * pad, 1);
    ctx.font = `700 ${Math.round(H * 0.034)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(25,95,165,1)";
    ctx.fillText(a.big, pad, yy); yy += H * 0.043;
    ctx.font = `${Math.round(H * 0.0125)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(45,45,42,0.95)";
    yy = wrap(a.label, pad, yy, w - 2 * pad, H * 0.016);
    ctx.font = `600 ${Math.round(H * 0.0115)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(200,125,0,1)";
    ctx.fillText("→ " + a.use, pad, yy + H * 0.004);
    ctx.font = `${Math.round(H * 0.0105)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(130,130,125,0.95)";
    ctx.fillText(a.doi, pad, h - H * 0.02);
    ctx.restore();
  }

  function evidencePanel(day) {
    if (SHOW_DOCS) for (const p of PICS) {
      const a = Math.min(1, Math.max(0, (day - p.at) / 4));
      if (!a || !p.ok) continue;
      const w = W * p.w, h = w * p.img.height / p.img.width, x = W * p.x, y = H * p.y;
      ctx.save(); ctx.globalAlpha = a;
      ctx.translate(x + w / 2, y + h / 2); ctx.rotate(p.rot * (2 - a)); ctx.translate(-w / 2, -h / 2);
      ctx.shadowColor = "rgba(0,0,0,0.18)"; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4;
      ctx.fillStyle = "#ffffff"; ctx.fillRect(-10, -10, w + 20, h + H * 0.07 + 10);
      ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
      ctx.drawImage(p.img, 0, 0, w, h);
      ctx.fillStyle = "rgba(25,30,25,0.95)"; ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.font = `600 ${Math.round(H * 0.0135)}px "Inter", sans-serif`; ctx.fillText(p.head, 0, h + 8);
      ctx.font = `${Math.round(H * 0.0125)}px "Inter", sans-serif`;
      wrap(p.cap, 0, h + 8 + H * 0.02, w, H * 0.016);
      ctx.restore();
    }
    if (SHOW_DOCS) for (const a of ARTICLES) {
      const al = Math.min(1, Math.max(0, (day - a.at) / 4));
      if (al) articleCard(a, al);
    }
    // who falls behind: sourced facts, cycling, bottom left
    if (day > 8) {
      const idx = Math.floor(performance.now() / 4000), [head, text, src] = EVIDENCE[idx % EVIDENCE.length];
      const x = W * 0.03, y = H * 0.7, w = W * 0.22;
      ctx.globalAlpha = Math.min(1, (day - 8) / 4);
      ctx.fillStyle = "rgba(205,40,125,0.9)"; ctx.fillRect(x, y, W * 0.003, H * 0.1);
      ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.font = `600 ${Math.round(H * 0.016)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(205,40,125,1)";
      ctx.fillText("WHO FALLS BEHIND · " + head, x + W * 0.008, y);
      ctx.font = `${Math.round(H * 0.016)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(45,45,42,0.92)";
      const yy = wrap(text, x + W * 0.008, y + H * 0.028, w, H * 0.021);
      ctx.font = `${Math.round(H * 0.013)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(105,105,100,0.9)";
      wrap(src + " · sourced, not simulated", x + W * 0.008, yy + H * 0.002, w, H * 0.017);
      ctx.globalAlpha = 1;
    }
  }

  let layer = null, lctx = null;    // offscreen layer for balls with motion trails

  // titles per shown variant: [title, subtitle prefix]
  const TITLES = {
    baseline: ["TODAY'S PATHWAY", ""],
    solution: ["SUGGESTED CHANGE", "specialist booked when the referral arrives, treatment slot reserved at the board · "],
    fastlane: ["WITH A FAST LANE (CONDITIONAL)", "assumes urgent booking times hold · "],
    bundled: ["CT AND PET-CT ORDERED TOGETHER", ""],
  };
  const SINGLE = true;     // only our solution's flowchart
  function geom(side) {
    const pw = SINGLE && side ? W * 0.5 : W * 0.4, cx = side ? (SINGLE ? W * 0.56 : W * 0.73) : W * 0.27;
    const yb = H * 0.86, yt = H * 0.3;
    return { pw, cx, side, y: r => yb - (yb - yt) * r / ROWS };
  }
  const rowOf = node => (POS[node] || [0])[0];
  function nodeXY(g, node, fast) {
    const p = POS[node] || [0, 0];
    let x = g.cx + p[1] * g.pw;
    if (fast && p[0] >= FAST_FROM_ROW && p[0] < ROWS) x = g.cx + 0.3 * g.pw;
    return [x, g.y(p[0])];
  }

  function edges(v) {
    if (v._edges) return v._edges;
    const cnt = {};
    for (const p of v.patients) {
      const seq = p.path.map(e => e[0]).filter(n => n in POS);
      if (p.tt !== null) seq.push("__finish");
      for (let i = 0; i + 1 < seq.length; i++) { const k = seq[i] + ">" + seq[i + 1]; cnt[k] = (cnt[k] || 0) + 1; }
    }
    return (v._edges = cnt);
  }

  function drawChart(g, v, fastOn) {
    const E = edges(v), n = v.patients.length;
    for (const k in E) {
      const [a, b] = k.split(">");
      const fa = fastOn && rowOf(a) >= FAST_FROM_ROW, fb = fastOn && rowOf(b) >= FAST_FROM_ROW && b !== "__finish";
      const [x1, y1] = nodeXY(g, a, fa), [x2, y2] = nodeXY(g, b, fb);
      ctx.strokeStyle = fastOn && rowOf(b) >= FAST_FROM_ROW ? "rgba(25,95,165,0.3)" : "rgba(45,45,42,0.12)";
      ctx.lineWidth = 0.6 + 5 * Math.sqrt(E[k] / n);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    if (fastOn) {
      const [fx, fy0] = nodeXY(g, "spec_visit", true), [, fy1] = nodeXY(g, "book_treat", true);
      ctx.strokeStyle = "rgba(25,95,165,0.55)"; ctx.lineWidth = 2; ctx.setLineDash([6, 6]);
      ctx.beginPath(); ctx.moveTo(fx, fy0 + H * 0.03); ctx.lineTo(fx, fy1 - H * 0.02); ctx.stroke(); ctx.setLineDash([]);
      ctx.save(); ctx.translate(fx - H * 0.018, (fy0 + fy1) / 2); ctx.rotate(-Math.PI / 2);
      ctx.font = `600 ${Math.round(H * 0.018)}px "Inter", sans-serif`; ctx.textAlign = "center";
      ctx.fillStyle = "rgba(25,95,165,0.9)"; ctx.fillText("FAST LANE", 0, 0); ctx.restore();
    }
    ctx.font = `${Math.round(H * 0.0145)}px "Inter", sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (const node in LABEL) {
      const [x, y] = nodeXY(g, node, false);
      ctx.fillStyle = "rgba(85,85,80,0.55)"; ctx.fillText(LABEL[node], x, y + H * 0.012);
      ctx.fillStyle = "rgba(45,45,42,0.35)"; ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fill();
    }
    const [tx, ty] = nodeXY(g, "__finish", false);
    ctx.strokeStyle = "rgba(30,135,85,0.4)"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(tx - g.pw * 0.42, ty); ctx.lineTo(tx + g.pw * 0.42, ty); ctx.stroke();
    ctx.textBaseline = "top"; ctx.font = `600 ${Math.round(H * 0.018)}px "Inter", sans-serif`;
    ctx.fillStyle = "rgba(30,135,85,0.9)"; ctx.fillText("TREATMENT STARTS", tx, ty + H * 0.008);
  }

  function groupRGB(p) { return p.g === VAGUE ? [20, 20, 20] : [150, 150, 145]; }   // vague = black, alarm = mid grey

  function balls(g, v, day, target, fastOn, draw = true) {
    const n = v.patients.length, swarm = {}, laneQ = {};
    const out = { on: 0, missed: 0, grp: { [VAGUE]: [0, 0], other: [0, 0] }, missedVague: 0, back: [0, 0] };
    const golden = 2.39996, R = H * 0.0042;
    for (let i = 0; i < n; i++) {
      const p = v.patients[i], s = stateOf(p, day, target), fast = fastOn && p.fl;
      const gk = p.g === VAGUE ? VAGUE : "other";
      out.grp[gk][1]++;
      if (p.path.some(e => e[0] === "represent" && e[2] <= day)) out.back[p.g === VAGUE ? 0 : 1]++;
      const [cr, cg, cb] = groupRGB(p);
      let x, y, col, rad = R, halo = 0;
      if (s.kind === "done") {
        if (s.ontime) { out.on++; out.grp[gk][0]++; }
        const [tx, ty] = nodeXY(g, "__finish", false);
        x = tx + (rnd(i, 7) - 0.5) * g.pw * 0.8; y = ty - H * 0.008 - rnd(i, 8) * H * 0.05;
        col = s.ontime ? (p.g === VAGUE ? "rgba(20,20,20,0.95)" : "rgba(150,150,145,0.95)") : "rgba(215,212,205,0.8)";
      } else if (s.kind === "gone") {
        out.missed++; if (p.g === VAGUE) out.missedVague++;
        const since = day - (p.tx || 0);
        if (since > 6) continue;
        const last = p.path.length ? p.path[p.path.length - 1][0] : "nurse_visit";
        const [lx, ly] = nodeXY(g, last, false);
        x = lx + (rnd(i, 3) - 0.5) * 30 - since * 8; y = ly + since * since * 6;
        col = `rgba(200,45,35,${Math.max(0, 1 - since / 6)})`; rad *= 1.4;
      } else if (s.kind === "wait" || s.kind === "start") {
        const node = s.node || "nurse_visit";
        const onLane = fast && rowOf(node) >= FAST_FROM_ROW;
        const [nx, ny] = nodeXY(g, node, onLane);
        const h = Math.min(1, (s.waitFor || 0) / 30);
        if (onLane) {
          // fast lane: a tidy short queue beside the lane instead of a swarm
          const k = (laneQ[node] = (laneQ[node] || 0) + 1) - 1, per = 14, sp = R * 1.9;
          x = nx + sp * (1.2 + (k % per)); y = ny - sp * 0.5 + Math.floor(k / per) * sp * 0.85;
          rad = R * 0.72;
        } else {
          const k = (swarm[node] = (swarm[node] || 0) + 1);
          const rr = H * 0.0058 * Math.sqrt(k), ang = k * golden + day * 0.09 * (k % 2 ? 1 : -1);
          x = nx + Math.cos(ang) * rr * 1.25; y = ny + Math.sin(ang) * rr * 0.55;
          halo = h;
        }
        col = `rgba(${cr},${cg},${cb},0.95)`;
      } else {
        const fa = fast && rowOf(s.from) >= FAST_FROM_ROW, fb = fast && rowOf(s.to) >= FAST_FROM_ROW && s.to !== "__finish";
        const [x1, y1] = nodeXY(g, s.from, fa), [x2, y2] = nodeXY(g, s.to, fb), f = ease(s.frac);
        x = x1 + (x2 - x1) * f + (rnd(i, 4) - 0.5) * 10; y = y1 + (y2 - y1) * f;
        col = fb ? "rgba(25,95,165,1)" : `rgba(${cr},${cg},${cb},1)`; rad *= 1.15;
      }
      if (!draw) continue;
      if (halo > 0.3) { lctx.fillStyle = `rgba(225,150,20,${0.12 * halo})`; lctx.beginPath(); lctx.arc(x, y, rad * 2.6, 0, Math.PI * 2); lctx.fill(); }
      lctx.fillStyle = col; lctx.beginPath(); lctx.arc(x, y, rad, 0, Math.PI * 2); lctx.fill();
      if (fastOn && i === FLOW.focus) FLOW.focusXY = [x, y];
      if (fastOn) FLOW.pos.push([x, y, i]);
    }
    return out;
  }

  function header(g, out, n, title, sub, ref = null) {
    ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
    ctx.font = `600 ${Math.round(H * 0.03)}px "Inter", sans-serif`;
    ctx.fillStyle = g.side ? "rgba(25,95,165,0.95)" : "rgba(45,45,42,0.95)";
    ctx.fillText(title, g.cx, H * 0.06);
    ctx.font = `${Math.round(H * 0.016)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(105,105,100,0.9)";
    ctx.fillText(sub, g.cx, H * 0.086);
    // per-group share treated within 90 days (the inequality, in two bars)
    const rows = [[VAGUE, "vague symptoms", "rgba(20,20,20,0.95)"], ["other", "alarm symptoms", "rgba(150,150,145,0.95)"]];
    const bx = g.cx - g.pw * 0.45, bw = g.pw * 0.5;
    rows.forEach(([k, lab, c], i) => {
      const [on, tot] = out.grp[k], sh = tot ? on / tot : 0, y = H * (0.12 + i * 0.04);
      ctx.fillStyle = "rgba(0,0,0,0.06)"; ctx.fillRect(bx, y, bw, H * 0.022);
      ctx.fillStyle = c; ctx.fillRect(bx, y, bw * sh, H * 0.022);
      let todayTxt = "";
      if (ref) {   // today's share at the same day, as a grey marker
        const [o2, t2] = ref.grp[k], s2 = t2 ? o2 / t2 : 0;
        ctx.fillStyle = "rgba(85,85,80,0.9)"; ctx.fillRect(bx + bw * s2 - 1, y - 3, 3, H * 0.022 + 6);
        todayTxt = `  (today ${Math.round(100 * s2)}%)`;
      }
      ctx.fillStyle = c; ctx.textAlign = "left"; ctx.font = `${Math.round(H * 0.016)}px "Inter", sans-serif`;
      ctx.fillText(`${Math.round(100 * sh)}%  ${lab}` + todayTxt, bx + bw + 8, y + H * 0.017);
    });
    ctx.textAlign = "left"; ctx.font = `${Math.round(H * 0.013)}px "Inter", sans-serif`;
    ctx.fillStyle = "rgba(105,105,100,0.85)";
    ctx.fillText("treated within 90 days, by symptom group" + (ref ? " · grey mark = today's pathway" : ""), bx, H * 0.112);
    // missed, one line under the bars
    ctx.textAlign = "left"; ctx.font = `${Math.round(H * 0.016)}px "Inter", sans-serif`;
    ctx.fillStyle = "rgba(200,45,35,0.95)";
    ctx.fillText(`${out.missed} sent home, cancer missed` + (out.missed ? ` · ${out.missedVague} had vague symptoms` : ""), bx, H * 0.21);
  }

  function callout(text, x, y, color, a) {
    if (a <= 0) return;
    ctx.font = `${Math.round(H * 0.016)}px "Inter", sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    ctx.fillStyle = color.replace("A", a.toFixed(2)); ctx.fillText(text, x, y);
  }

  // note card: shows one synthetic note; left = the problem, right = our note reader flagging it
  function noteCard(g, idx, a) {
    const note = NOTES[idx % NOTES.length];
    const x = g.side ? W * 0.512 : W * 0.012, y = g.y(11.5), w = W * 0.165, h = H * 0.135;
    ctx.globalAlpha = a;
    ctx.fillStyle = "rgba(255,255,255,0.92)"; ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = g.side ? "rgba(25,95,165,0.6)" : "rgba(200,125,0,0.5)"; ctx.lineWidth = 1; ctx.strokeRect(x, y, w, h);
    ctx.font = `600 ${Math.round(H * 0.0135)}px "Inter", sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillStyle = g.side ? "rgba(25,95,165,0.95)" : "rgba(200,125,0,0.95)";
    ctx.fillText(g.side ? "NOTE READER + DECISION MODEL" : "WHAT THE NOTE SAYS", x + 8, y + 7);
    // wrapped note with the flagged span marked
    const fs = Math.round(H * 0.0145); ctx.font = `${fs}px "Inter", sans-serif`;
    const words = [];
    note.slice(0, 3).forEach((part, pi) => part.split(/(\s+)/).filter(s => s.length).forEach(t => words.push([t, pi === 1])));
    let cx = x + 8, cy = y + 7 + fs * 1.6;
    for (const [t, hl] of words) {
      const tw = ctx.measureText(t).width;
      if (cx + tw > x + w - 8 && t.trim()) { cx = x + 8; cy += fs * 1.25; }
      if (!t.trim() && cx === x + 8) continue;
      if (hl && t.trim()) {
        ctx.fillStyle = g.side ? "rgba(25,95,165,0.28)" : "rgba(200,125,0,0.18)"; ctx.fillRect(cx - 1, cy - 1, tw + 2, fs * 1.15);
      }
      ctx.fillStyle = "rgba(45,45,42,0.92)"; ctx.fillText(t, cx, cy); cx += tw;
    }
    ctx.font = `${Math.round(H * 0.0135)}px "Inter", sans-serif`;
    ctx.fillStyle = g.side ? "rgba(25,95,165,0.95)" : "rgba(200,70,40,0.95)";
    ctx.fillText((g.side ? "" : "→ ") + (g.side ? note[4] : note[3]), x + 8, y + h - fs * 1.5);
    ctx.globalAlpha = 1;
  }

  function median(v) {
    if (v._med) return v._med;
    const t = v.patients.map(p => p.tt).filter(x => x !== null).sort((a, b) => a - b);
    return (v._med = Math.round(t[Math.floor(t.length / 2)]));
  }

  function draw(day, dt) {
    const sc = D.scenarios[0], target = sc.target_days;
    const vOld = sc.variants[0], vNew = current();
    if (!vNew._fl) {
      vNew.patients.forEach((p, i) => { const b = vOld.patients[i]; p.fl = !!(p.ft && p.tt !== null && b.tt !== null && b.tt - p.tt >= FAST_GAIN); });
      vNew._fl = true;
    }
    if (!layer || layer.width !== cv.width) {
      layer = document.createElement("canvas"); layer.width = cv.width; layer.height = cv.height;
      lctx = layer.getContext("2d"); lctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    }
    lctx.save(); lctx.setTransform(1, 0, 0, 1, 0, 0);
    lctx.globalCompositeOperation = "destination-out"; lctx.fillStyle = `rgba(0,0,0,${Math.min(1, 0.22 + dt * 4)})`;
    lctx.fillRect(0, 0, layer.width, layer.height); lctx.restore();
    lctx.globalCompositeOperation = "source-over";

    const gL = geom(0), gR = geom(1);
    if (!SINGLE) {
      ctx.strokeStyle = "rgba(0,0,0,0.08)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(W / 2, H * 0.03); ctx.lineTo(W / 2, H * 0.9); ctx.stroke();
      drawChart(gL, vOld, false);
    }
    drawChart(gR, vNew, vNew.patients.some(p => p.fl));
    const oL = balls(gL, vOld, day, target, false, !SINGLE);
    FLOW.focusXY = null; FLOW.pos = [];
    const oR = balls(gR, vNew, day, target, true);
    ctx.drawImage(layer, 0, 0, W, H);
    if (FLOW.focusXY && FLOW.ring) {
      const [fx, fy] = FLOW.focusXY;
      ctx.strokeStyle = "rgba(25,95,165,0.95)"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(fx, fy, H * 0.016 + 3 * Math.sin(performance.now() / 150), 0, Math.PI * 2); ctx.stroke();
    }
    if (SINGLE) {
      const T = TITLES[vNew.key] || [vNew.label.toUpperCase(), ""];
      header(gR, oR, vNew.patients.length, T[0], `${T[1]}median ${median(vNew)} days (today ${median(vOld)})`, vNew === vOld ? null : oL);
      evidencePanel(day);
    } else {
    header(gL, oL, vOld.patients.length, "TODAY", "median " + median(vOld) + " days to treatment");
    header(gR, oR, vNew.patients.length, "OUR SOLUTION", "notes read, warning signs flagged, fast lane · median " + median(vNew) + " days");

    // inequality callouts on the left, by the "Back to GP" swarm
    const a = Math.min(1, Math.max(0, (day - 25) / 8));
    callout("sent back to the GP:", W * 0.012, gL.y(6.6), "rgba(45,45,42,A)", a);
    callout(`${oL.back[0]} vague symptoms`, W * 0.012, gL.y(6.6) + H * 0.022, "rgba(205,40,125,A)", a);
    callout(`${oL.back[1]} alarm symptoms`, W * 0.012, gL.y(6.6) + H * 0.044, "rgba(70,70,66,A)", a);

    // note cards: cycle every 4 s of real time, from day 10
    if (day > 10) {
      const idx = Math.floor(performance.now() / 4000), fa = Math.min(1, (day - 10) / 4);
      noteCard(gL, idx, fa); noteCard(gR, idx, fa);
      evidenceBox(gL, idx, fa);
    }
    }

    // clock
    ctx.textAlign = "center"; ctx.textBaseline = "alphabetic"; ctx.font = `600 ${Math.round(H * 0.045)}px "Inter", sans-serif`;
    ctx.fillStyle = day >= target ? "rgba(200,125,0,0.95)" : "rgba(45,45,42,0.95)";
    const cxk = SINGLE ? W * 0.13 : W / 2;
    ctx.fillText("DAY " + String(Math.floor(day)).padStart(3, "0"), cxk, H * 0.06);
    ctx.font = `${Math.round(H * 0.013)}px "Inter", sans-serif`; ctx.fillStyle = "rgba(105,105,100,0.85)";
    ctx.fillText("since first contact · 521 simulated lung cancer patients", cxk, H * 0.082);
    if (!SHOW.active) {
      ctx.fillText("521 simulated lung cancer patients · one synthetic county · note texts are synthetic examples · note reader and decision model are prototypes",
        W / 2, H * 0.975);
    }
  }

  // a vague-symptom patient on the fast lane whose referral is being handled around this day
  function pickFocus(day) {
    const v = current(), anyFl = v.patients.some(p => p.fl);
    let best = null, bd = 1e9;
    v.patients.forEach((p, i) => {
      if (p.g !== VAGUE || (anyFl && !p.fl) || p.tt === null) return;
      const tr = p.path.find(e => e[0] === "triage"); if (!tr) return;
      const d = Math.abs(tr[2] - day);
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  }

  function current() {
    const vs = D.scenarios[0].variants;
    return vs.find(v => v.key === FLOW.newKey) || vs[1];
  }

  return { draw, pickFocus, current, focus: null, focusXY: null, ring: false, pos: [], newKey: "fastlane" };
})();
