"use strict";
// Document zoom: one patient's (synthetic) note, read by our note reader, and the decision model's estimates
// for the next step, with percentages and their sources. Standalone: index.html?doc (loops every 14 s);
// also used by ?show between the flow scene's build and the drop.
//
// Numbers and where they come from (keep in sync with README):
// - Chest X-ray finds 77-80% of lung cancers in symptomatic patients (best-quality studies; 76.8% in primary care):
//   Bradley et al., Br J Gen Pract 2019;69:e827, doi:10.3399/bjgp19X706853 (checked against the PMC abstract).
// - CT finds 97%: simulator assumption (params note: sensitivity about 0.95, LDCT screening 0.85 in Horeweg 2014).
// - Central tumour, bronchoscopy 94% diagnostic in about 14 days vs needle biopsy 68% in about 22 days: measured in
//   our simulator (exploration runs, 161 and 150 synthetic cases; runs/model_in_loop.json on overnight/sim).
// The note reader and decision model are prototypes; the note is synthetic.

const ZOOM = (() => {
  const NOTE = [
    [["Visit 3", "anch"], " · woman, 64, former smoker"],
    ["Cough for 7 weeks. Tired, ", ["lost 6 kg", "red"], " since summer."],
    [["Chest X-ray 4 weeks ago: no clear finding.", "xray"]],
    [["Likely post-viral cough.", "anch"], " Advised rest."],
  ];
  const FLAGS = {
    red: ["RED FLAG", "unexplained weight loss", "rgba(200,45,35,1)"],
    anch: ["ANCHORING", "same explanation for 3 visits", "rgba(200,125,0,1)"],
    xray: ["CHECK", "an X-ray misses about 1 in 5 lung cancers", "rgba(25,95,165,1)"],
  };
  const NEXT = [
    ["Chest X-ray again", 0.77, "finds 77-80% of lung cancers · Bradley et al. 2019 (review)", false],
    ["Direct CT", 0.97, "finds 97% · simulator assumption", true],
  ];
  const BIOPSY = [
    ["Bronchoscopy", 0.94, "94% get a diagnosis · about 14 days", true],
    ["Needle biopsy", 0.68, "68% get a diagnosis · about 22 days", false],
  ];

  function txt(s, x, y, size, color, font = "Courier Prime", align = "left", base = "alphabetic") {
    ctx.font = `${font === "DotGothic16" ? "600 " : ""}${Math.round(size)}px "Inter", sans-serif`; ctx.fillStyle = color;
    ctx.textAlign = align; ctx.textBaseline = base; ctx.fillText(s, x, y);
  }
  const clamp = x => Math.max(0, Math.min(1, x));

  function bar(label, val, sub, best, x, y, w, k, accent) {
    txt(label, x, y, H * 0.024, "rgba(45,45,42,0.95)");
    const by = y + H * 0.012, bh = H * 0.03;
    ctx.fillStyle = "rgba(0,0,0,0.07)"; ctx.fillRect(x, by, w, bh);
    ctx.fillStyle = best ? accent : "rgba(150,150,145,0.75)"; ctx.fillRect(x, by, w * val * k, bh);
    txt(Math.round(100 * val * k) + "%", x + w + W * 0.01, by + bh * 0.8, H * 0.03, best ? accent : "rgba(85,85,80,0.9)", "DotGothic16");
    txt(sub, x, by + bh + H * 0.025, H * 0.016, "rgba(105,105,100,0.9)");
    if (best && k >= 1) txt("◀ MODEL PICKS", x + w + W * 0.06, by + bh * 0.8, H * 0.018, accent, "DotGothic16");
  }

  // t = seconds since the document scene started (about 12 s of content)
  function draw(t) {
    // in the music sample, shrink the whole scene a little so the subtitles do not cover it
    if (SHOW.active) { ctx.save(); ctx.translate(W / 2, 0); ctx.scale(0.86, 0.86); ctx.translate(-W / 2, -H * 0.02); }
    // document
    const dx = W * 0.04, dy = H * 0.13, dw = W * 0.45, dh = H * 0.5;
    const a = clamp(t / 0.6);
    ctx.globalAlpha = a;
    ctx.fillStyle = "#ffffff"; ctx.fillRect(dx, dy, dw, dh); ctx.fillStyle = "#e8c56a"; ctx.fillRect(dx, dy, dw, H * 0.008);
    // clean white paper with a honey-yellow top rule
    txt("REFERRAL · NOTE FROM THE HEALTH CENTRE", dx + W * 0.025, dy + H * 0.045, H * 0.022, "rgba(30,40,30,0.9)", "DotGothic16");
    txt("synthetic example", dx + dw - W * 0.025, dy + H * 0.045, H * 0.015, "rgba(60,70,60,0.8)", "Courier Prime", "right");
    // note lines, typed in; flagged spans highlighted by the reader from t = 2.2
    const fs = H * 0.0235, lx = dx + W * 0.022;
    let charsLeft = Math.floor((t - 0.4) * 55);
    const spans = [];
    NOTE.forEach((line, li) => {
      let x = lx; const y = dy + H * 0.12 + li * fs * 2.1;
      ctx.font = `${Math.round(fs)}px "Inter", sans-serif`;
      for (const part of line) {
        const [s, flag] = typeof part === "string" ? [part, null] : part;
        const shown = s.slice(0, Math.max(0, Math.min(s.length, charsLeft))); charsLeft -= s.length;
        const w = ctx.measureText(shown).width;
        if (flag) spans.push({ flag, x, y, w: ctx.measureText(s).width });
        txt(shown, x, y, fs, "rgba(25,30,25,0.95)");
        x += w;
      }
    });
    // reader highlights + flag chips (one by one)
    const order = ["red", "anch", "xray"];
    order.forEach((f, k) => {
      const ka = clamp((t - 2.2 - k * 0.8) / 0.4); if (!ka) return;
      const [head, why, col] = FLAGS[f];
      spans.filter(s => s.flag === f).forEach(s => {
        ctx.strokeStyle = col.replace(",1)", `,${ka})`); ctx.lineWidth = 3;
        ctx.strokeRect(s.x - 4, s.y - fs * 0.95, s.w + 8, fs * 1.35);
      });
      const cy = dy + dh + H * 0.05 + k * H * 0.05;
      ctx.globalAlpha = a * ka;
      ctx.fillStyle = col; ctx.fillRect(dx, cy - H * 0.026, W * 0.006, H * 0.034);
      txt(head, dx + W * 0.014, cy, H * 0.024, col, "DotGothic16");
      txt(why, dx + W * 0.11, cy, H * 0.021, "rgba(45,45,42,0.92)");
      ctx.globalAlpha = a;
    });
    txt("NOTE READER", dx, dy - H * 0.02, H * 0.022, "rgba(25,95,165,0.95)", "DotGothic16");

    // decision model, right side
    const rx = W * 0.53, rw = W * 0.3, accent = "rgba(30,135,85,1)";
    const k1 = clamp((t - 5) / 1.2), k2 = clamp((t - 8) / 1.2);
    if (t > 4.6) {
      txt("DECISION MODEL · NEXT STEP", rx, dy - H * 0.02, H * 0.022, "rgba(25,95,165,0.95)", "DotGothic16");
      txt("Which test finds the cancer, if there is one?", rx, dy + H * 0.03, H * 0.02, "rgba(85,85,80,0.9)");
      NEXT.forEach(([l, v, s, b], i) => bar(l, v, s, b, rx, dy + H * 0.1 + i * H * 0.1, rw, k1, accent));
    }
    if (t > 7.6) {
      txt("CT shows a central tumour. Which biopsy?", rx, dy + H * 0.34, H * 0.02, "rgba(85,85,80,0.9)");
      BIOPSY.forEach(([l, v, s, b], i) => bar(l, v, s, b, rx, dy + H * 0.41 + i * H * 0.1, rw, k2, accent));
      txt("measured in our simulator, 311 synthetic cases", rx, dy + H * 0.62, H * 0.015, "rgba(105,105,100,0.9)");
    }
    // route stamp
    const k3 = clamp((t - 10.2) / 0.5);
    if (k3) {
      ctx.save(); ctx.globalAlpha = a * k3;
      ctx.translate(rx + rw * 0.55, dy + H * 0.72); ctx.rotate(-0.06);
      ctx.strokeStyle = "rgba(25,95,165,0.95)"; ctx.lineWidth = 3;
      ctx.strokeRect(-W * 0.16, -H * 0.045, W * 0.32, H * 0.075);
      txt("ROUTE: FAST LANE · URGENT CT", 0, H * 0.008, H * 0.03, "rgba(25,95,165,1)", "DotGothic16", "center", "middle");
      ctx.restore();
      txt("A clinician confirms every step.", rx, dy + H * 0.82, H * 0.019, "rgba(45,45,42,0.9)");
    }
    ctx.globalAlpha = 1;
    if (SHOW.active) ctx.restore();
    txt("Note: synthetic example · note reader and decision model: prototypes · X-ray figure: Bradley et al. 2019 · CT figure: simulator assumption",
        W / 2, H * 0.975 - (SHOW.active ? H * 0.11 : 0), H * 0.014, "rgba(105,105,100,0.85)", "Courier Prime", "center");
  }

  return { draw };
})();
