"use strict";
// Patient race: a few simulated patients as large dots moving through the named steps of the Finnish
// pathway. Top lane = today's pathway, bottom lane = the same patients with the optimiser's fast track
// (priority once the hospital has handled the referral). Standalone: index.html?race ; also used by ?show.
// Patients are chosen evenly by time to treatment today (8 quantiles among those treated in both runs),
// not hand-picked.

const RACE = (() => {
  const STEPS = [
    ["primary", "Health centre"], ["cxr", "Chest X-ray"], ["referral", "Referral"], ["spec", "Specialist"],
    ["ct", "CT"], ["biopsy", "Biopsy"], ["pet", "PET-CT"], ["board", "Tumour board"], ["slot", "Treatment slot"],
    ["treat", "Treatment"],
  ];
  const NODE_STEP = {
    nurse_visit: 0, gp_visit: 0, gp_after_nurse: 0, persist: 0, represent: 0, second_look: 1, cxr: 1,
    gp_referral: 2, triage: 2, spec_visit: 3, ct: 4, bronch: 5, ttnb: 5, pet: 6, pet_early: 6, pet_after_ct: 6,
    mdt: 7, book_treat: 8, __finish: 9,
  };
  const STAGE_STEP = { detection: 0, referral: 2, diagnosis: 4, treatment_start: 7 };

  function pick(v0, v1, k = 8) {
    const both = [];
    v0.patients.forEach((p, i) => { if (p.tt !== null && v1.patients[i].tt !== null) both.push([i, p.tt]); });
    both.sort((a, b) => a[1] - b[1]);
    return Array.from({ length: k }, (_, j) => both[Math.floor(both.length * (j + 0.5) / k)][0]);
  }

  function stepOf(node, path) {
    if (node in NODE_STEP) return NODE_STEP[node];
    const e = path.find(x => x[0] === node);
    return e ? (STAGE_STEP[e[1]] ?? 0) : 0;
  }

  // x position of a patient at day t, plus its state for colouring
  function where(p, t, target) {
    const s = stateOf(p, t, target);
    if (s.kind === "done") return { step: 9, kind: "done", ontime: s.ontime };
    if (s.kind === "gone") return { step: null, kind: "gone" };
    if (s.kind === "start") return { step: 0, kind: "wait", w: 0 };
    if (s.kind === "wait") return { step: stepOf(s.node, p.path), kind: "wait", w: s.waitFor };
    const a = stepOf(s.from, p.path), b = stepOf(s.to, p.path);
    return { step: a + (b - a) * ease(s.frac), kind: "move" };
  }

  const trails = {};   // lane -> per-patient furthest x reached (progress trail)

  function draw(day, opts = {}) {
    const sc = D.scenarios[0], target = sc.target_days;
    const v0 = sc.variants[0], v1 = sc.variants[1];
    const ids = RACE.ids || (RACE.ids = pick(v0, v1));
    const x0 = W * 0.13, x1 = W * 0.88, xs = i => x0 + (x1 - x0) * i / (STEPS.length - 1);
    const lanes = [
      { v: v0, label: "TODAY", top: H * 0.2, color: "rgba(233,239,230,0.95)" },
      { v: v1, label: "WITH FAST TRACK AFTER THE HOSPITAL HANDLES THE REFERRAL", top: H * 0.56, color: "rgba(184,255,207,0.95)" },
    ].slice(0, opts.lanes || 2);
    const rowH = H * 0.036, r = H * 0.011;

    // step columns and labels
    ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
    STEPS.forEach(([, lab], i) => {
      ctx.strokeStyle = i === 9 ? "rgba(184,255,207,0.35)" : "rgba(255,255,255,0.07)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(xs(i), H * 0.16); ctx.lineTo(xs(i), H * 0.9); ctx.stroke();
      ctx.font = `${Math.round(H * 0.017)}px "Courier Prime", monospace`;
      ctx.fillStyle = "rgba(200,208,198,0.85)";
      ctx.fillText(lab.toUpperCase(), xs(i), H * 0.15);
    });

    // clock
    ctx.textAlign = "right";
    ctx.font = `${Math.round(H * 0.05)}px "DotGothic16", monospace`;
    ctx.fillStyle = day >= target ? "rgba(255,179,71,0.95)" : "rgba(233,239,230,0.95)";
    ctx.fillText("DAY " + String(Math.floor(day)).padStart(3, "0"), W * 0.97, H * 0.075);
    ctx.font = `${Math.round(H * 0.016)}px "Courier Prime", monospace`;
    ctx.fillStyle = "rgba(160,170,160,0.9)";
    ctx.fillText(ids.length + " of " + v0.patients.length + " simulated patients, chosen evenly by waiting time · target " + target + " days", W * 0.97, H * 0.105);

    lanes.forEach((L, li) => {
      ctx.textAlign = "left";
      ctx.font = `${Math.round(H * 0.022)}px "DotGothic16", monospace`;
      ctx.fillStyle = L.color;
      ctx.fillText(L.label, W * 0.03, L.top - H * 0.012);
      const tr = trails[li] || (trails[li] = {});
      ids.forEach((pi, row) => {
        const p = L.v.patients[pi], y = L.top + rowH * (row + 0.5);
        const w = where(p, day, target);
        if (w.step === null) return;
        const x = xs(w.step);
        tr[pi] = Math.max(tr[pi] || x0, x);
        if (day < 0.01) tr[pi] = x0;
        // progress trail
        ctx.strokeStyle = li ? "rgba(184,255,207,0.22)" : "rgba(233,239,230,0.16)"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(tr[pi], y); ctx.stroke();
        // dot: white moving, orange glow while waiting, green when treated on time, grey when late
        let fill = "rgba(240,244,238,0.95)";
        if (w.kind === "wait") {
          const h = Math.min(1, w.w / 30);
          fill = `rgba(255,${(235 - 90 * h) | 0},${(220 - 180 * h) | 0},1)`;
          ctx.fillStyle = `rgba(255,150,40,${0.18 * h})`;
          ctx.beginPath(); ctx.arc(x, y, r * (2 + 1.2 * h + 0.3 * Math.sin(day * 2 + row)), 0, Math.PI * 2); ctx.fill();
        }
        if (w.kind === "done") fill = w.ontime ? "rgba(184,255,207,1)" : "rgba(160,170,160,0.9)";
        ctx.fillStyle = fill;
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
        if (w.kind === "done") {
          ctx.font = `${Math.round(H * 0.016)}px "Courier Prime", monospace`;
          ctx.fillStyle = fill; ctx.textAlign = "left";
          ctx.fillText("day " + Math.round(p.tt), x + r * 2, y + H * 0.006);
        }
      });
    });
  }

  return { draw, ids: null };
})();
