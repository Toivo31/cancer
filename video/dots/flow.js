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

  let layer = null, lctx = null;    // offscreen layer for balls with motion trails

  function geom(side) {
    const pw = W * 0.4, cx = side ? W * 0.73 : W * 0.27;
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
      ctx.strokeStyle = fastOn && rowOf(b) >= FAST_FROM_ROW ? "rgba(120,220,255,0.3)" : "rgba(233,239,230,0.12)";
      ctx.lineWidth = 0.6 + 5 * Math.sqrt(E[k] / n);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    if (fastOn) {
      const [fx, fy0] = nodeXY(g, "spec_visit", true), [, fy1] = nodeXY(g, "book_treat", true);
      ctx.strokeStyle = "rgba(120,220,255,0.55)"; ctx.lineWidth = 2; ctx.setLineDash([6, 6]);
      ctx.beginPath(); ctx.moveTo(fx, fy0 + H * 0.03); ctx.lineTo(fx, fy1 - H * 0.02); ctx.stroke(); ctx.setLineDash([]);
      ctx.save(); ctx.translate(fx - H * 0.018, (fy0 + fy1) / 2); ctx.rotate(-Math.PI / 2);
      ctx.font = `${Math.round(H * 0.018)}px "DotGothic16", monospace`; ctx.textAlign = "center";
      ctx.fillStyle = "rgba(120,220,255,0.9)"; ctx.fillText("FAST LANE", 0, 0); ctx.restore();
    }
    ctx.font = `${Math.round(H * 0.0145)}px "Courier Prime", monospace`; ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (const node in LABEL) {
      const [x, y] = nodeXY(g, node, false);
      ctx.fillStyle = "rgba(200,208,198,0.55)"; ctx.fillText(LABEL[node], x, y + H * 0.012);
      ctx.fillStyle = "rgba(233,239,230,0.35)"; ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fill();
    }
    const [tx, ty] = nodeXY(g, "__finish", false);
    ctx.strokeStyle = "rgba(184,255,207,0.4)"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(tx - g.pw * 0.42, ty); ctx.lineTo(tx + g.pw * 0.42, ty); ctx.stroke();
    ctx.textBaseline = "top"; ctx.font = `${Math.round(H * 0.018)}px "DotGothic16", monospace`;
    ctx.fillStyle = "rgba(184,255,207,0.9)"; ctx.fillText("TREATMENT STARTS", tx, ty + H * 0.008);
  }

  function groupRGB(p) { return p.g === VAGUE ? [255, 120, 190] : [245, 240, 225]; }

  function balls(g, v, day, target, fastOn) {
    const n = v.patients.length, swarm = {}, laneQ = {};
    const out = { on: 0, missed: 0, grp: { [VAGUE]: [0, 0], other: [0, 0] }, missedVague: 0, back: [0, 0] };
    const golden = 2.39996, R = H * 0.0042;
    for (let i = 0; i < n; i++) {
      const p = v.patients[i], s = stateOf(p, day, target), fast = fastOn && p.ft;
      const gk = p.g === VAGUE ? VAGUE : "other";
      out.grp[gk][1]++;
      if (p.path.some(e => e[0] === "represent" && e[2] <= day)) out.back[p.g === VAGUE ? 0 : 1]++;
      const [cr, cg, cb] = groupRGB(p);
      let x, y, col, rad = R, halo = 0;
      if (s.kind === "done") {
        if (s.ontime) { out.on++; out.grp[gk][0]++; }
        const [tx, ty] = nodeXY(g, "__finish", false);
        x = tx + (rnd(i, 7) - 0.5) * g.pw * 0.8; y = ty - H * 0.008 - rnd(i, 8) * H * 0.05;
        col = s.ontime ? (p.g === VAGUE ? "rgba(255,170,215,0.95)" : "rgba(184,255,207,0.95)") : "rgba(130,135,130,0.55)";
      } else if (s.kind === "gone") {
        out.missed++; if (p.g === VAGUE) out.missedVague++;
        const since = day - (p.tx || 0);
        if (since > 6) continue;
        const last = p.path.length ? p.path[p.path.length - 1][0] : "nurse_visit";
        const [lx, ly] = nodeXY(g, last, false);
        x = lx + (rnd(i, 3) - 0.5) * 30 - since * 8; y = ly + since * since * 6;
        col = `rgba(255,70,60,${Math.max(0, 1 - since / 6)})`; rad *= 1.4;
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
        col = fb ? "rgba(150,235,255,1)" : `rgba(${cr},${cg},${cb},1)`; rad *= 1.15;
      }
      if (halo > 0.3) { lctx.fillStyle = `rgba(255,140,40,${0.12 * halo})`; lctx.beginPath(); lctx.arc(x, y, rad * 2.6, 0, Math.PI * 2); lctx.fill(); }
      lctx.fillStyle = col; lctx.beginPath(); lctx.arc(x, y, rad, 0, Math.PI * 2); lctx.fill();
    }
    return out;
  }

  function header(g, out, n, title, sub) {
    ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
    ctx.font = `${Math.round(H * 0.03)}px "DotGothic16", monospace`;
    ctx.fillStyle = g.side ? "rgba(120,220,255,0.95)" : "rgba(233,239,230,0.95)";
    ctx.fillText(title, g.cx, H * 0.06);
    ctx.font = `${Math.round(H * 0.016)}px "Courier Prime", monospace`; ctx.fillStyle = "rgba(160,170,160,0.9)";
    ctx.fillText(sub, g.cx, H * 0.086);
    // per-group share treated within 90 days (the inequality, in two bars)
    const rows = [[VAGUE, "vague symptoms", "rgba(255,120,190,0.95)"], ["other", "alarm symptoms", "rgba(245,240,225,0.95)"]];
    const bx = g.cx - g.pw * 0.45, bw = g.pw * 0.5;
    rows.forEach(([k, lab, c], i) => {
      const [on, tot] = out.grp[k], sh = tot ? on / tot : 0, y = H * (0.12 + i * 0.04);
      ctx.fillStyle = "rgba(255,255,255,0.06)"; ctx.fillRect(bx, y, bw, H * 0.022);
      ctx.fillStyle = c; ctx.fillRect(bx, y, bw * sh, H * 0.022);
      ctx.textAlign = "left"; ctx.font = `${Math.round(H * 0.016)}px "Courier Prime", monospace`;
      ctx.fillText(`${Math.round(100 * sh)}%  ${lab}`, bx + bw + 8, y + H * 0.017);
    });
    ctx.textAlign = "left"; ctx.font = `${Math.round(H * 0.013)}px "Courier Prime", monospace`;
    ctx.fillStyle = "rgba(160,170,160,0.85)";
    ctx.fillText("treated within 90 days, by symptom group", bx, H * 0.112);
    // missed, one line under the bars
    ctx.textAlign = "left"; ctx.font = `${Math.round(H * 0.016)}px "Courier Prime", monospace`;
    ctx.fillStyle = "rgba(255,110,100,0.95)";
    ctx.fillText(`${out.missed} sent home, cancer missed` + (out.missed ? ` · ${out.missedVague} had vague symptoms` : ""), bx, H * 0.21);
  }

  function callout(text, x, y, color, a) {
    if (a <= 0) return;
    ctx.font = `${Math.round(H * 0.016)}px "Courier Prime", monospace`; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    ctx.fillStyle = color.replace("A", a.toFixed(2)); ctx.fillText(text, x, y);
  }

  // note card: shows one synthetic note; left = the problem, right = our note reader flagging it
  function noteCard(g, idx, a) {
    const note = NOTES[idx % NOTES.length];
    const x = g.side ? W * 0.512 : W * 0.012, y = g.y(11.5), w = W * 0.165, h = H * 0.135;
    ctx.globalAlpha = a;
    ctx.fillStyle = "rgba(14,16,15,0.92)"; ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = g.side ? "rgba(120,220,255,0.6)" : "rgba(255,179,71,0.5)"; ctx.lineWidth = 1; ctx.strokeRect(x, y, w, h);
    ctx.font = `${Math.round(H * 0.0135)}px "DotGothic16", monospace`; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillStyle = g.side ? "rgba(120,220,255,0.95)" : "rgba(255,179,71,0.95)";
    ctx.fillText(g.side ? "NOTE READER + DECISION MODEL" : "WHAT THE NOTE SAYS", x + 8, y + 7);
    // wrapped note with the flagged span marked
    const fs = Math.round(H * 0.0145); ctx.font = `${fs}px "Courier Prime", monospace`;
    const words = [];
    note.slice(0, 3).forEach((part, pi) => part.split(/(\s+)/).filter(s => s.length).forEach(t => words.push([t, pi === 1])));
    let cx = x + 8, cy = y + 7 + fs * 1.6;
    for (const [t, hl] of words) {
      const tw = ctx.measureText(t).width;
      if (cx + tw > x + w - 8 && t.trim()) { cx = x + 8; cy += fs * 1.25; }
      if (!t.trim() && cx === x + 8) continue;
      if (hl && t.trim()) {
        ctx.fillStyle = g.side ? "rgba(120,220,255,0.28)" : "rgba(255,179,71,0.18)"; ctx.fillRect(cx - 1, cy - 1, tw + 2, fs * 1.15);
      }
      ctx.fillStyle = "rgba(233,239,230,0.92)"; ctx.fillText(t, cx, cy); cx += tw;
    }
    ctx.font = `${Math.round(H * 0.0135)}px "Courier Prime", monospace`;
    ctx.fillStyle = g.side ? "rgba(120,220,255,0.95)" : "rgba(255,150,120,0.95)";
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
    const vOld = sc.variants[0], vNew = sc.variants[1];
    if (!layer || layer.width !== cv.width) {
      layer = document.createElement("canvas"); layer.width = cv.width; layer.height = cv.height;
      lctx = layer.getContext("2d"); lctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    }
    lctx.save(); lctx.setTransform(1, 0, 0, 1, 0, 0);
    lctx.globalCompositeOperation = "destination-out"; lctx.fillStyle = `rgba(0,0,0,${Math.min(1, 0.22 + dt * 4)})`;
    lctx.fillRect(0, 0, layer.width, layer.height); lctx.restore();
    lctx.globalCompositeOperation = "source-over";

    const gL = geom(0), gR = geom(1);
    ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(W / 2, H * 0.03); ctx.lineTo(W / 2, H * 0.9); ctx.stroke();
    drawChart(gL, vOld, false);
    drawChart(gR, vNew, true);
    const oL = balls(gL, vOld, day, target, false);
    const oR = balls(gR, vNew, day, target, true);
    ctx.drawImage(layer, 0, 0, W, H);
    header(gL, oL, vOld.patients.length, "TODAY", "median " + median(vOld) + " days to treatment");
    header(gR, oR, vNew.patients.length, "OUR SOLUTION", "notes read, warning signs flagged, fast lane · median " + median(vNew) + " days");

    // inequality callouts on the left, by the "Back to GP" swarm
    const a = Math.min(1, Math.max(0, (day - 25) / 8));
    callout("sent back to the GP:", W * 0.012, gL.y(2.3), "rgba(233,239,230,A)", a);
    callout(`${oL.back[0]} vague symptoms`, W * 0.012, gL.y(2.3) + H * 0.022, "rgba(255,120,190,A)", a);
    callout(`${oL.back[1]} alarm symptoms`, W * 0.012, gL.y(2.3) + H * 0.044, "rgba(245,240,225,A)", a);

    // note cards: cycle every 4 s of real time, from day 10
    if (day > 10) {
      const idx = Math.floor(performance.now() / 4000), fa = Math.min(1, (day - 10) / 4);
      noteCard(gL, idx, fa); noteCard(gR, idx, fa);
    }

    // clock
    ctx.textAlign = "center"; ctx.textBaseline = "alphabetic"; ctx.font = `${Math.round(H * 0.045)}px "DotGothic16", monospace`;
    ctx.fillStyle = day >= target ? "rgba(255,179,71,0.95)" : "rgba(233,239,230,0.95)";
    ctx.fillText("DAY " + String(Math.floor(day)).padStart(3, "0"), W / 2, H * 0.06);
    ctx.font = `${Math.round(H * 0.013)}px "Courier Prime", monospace`; ctx.fillStyle = "rgba(160,170,160,0.85)";
    ctx.fillText("since first contact", W / 2, H * 0.082);
    if (!SHOW.active) {
      ctx.fillText("521 simulated lung cancer patients, the same on both sides · one synthetic county · note texts are synthetic examples · note reader and decision model are prototypes",
        W / 2, H * 0.975);
    }
  }

  return { draw };
})();
