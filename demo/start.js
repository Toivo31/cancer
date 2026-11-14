/* Start page: binds numbers from the bundles the other screens use. No number is typed here.
   Sources: window.FLOW_DATA (data/flow_bundle.js), window.ENC_DATA (data/encounter_bundle.js),
   window.START_DATA (data/start_bundle.js, from demo/export_start.py). Missing data shows "pending". */
(function () {
  "use strict";
  var FLOW = window.FLOW_DATA, ENC = window.ENC_DATA, ST = window.START_DATA;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function ok(x) { return typeof x === "number" && isFinite(x); }
  function pct(x) { return ok(x) ? Math.round(x * 100) + "%" : null; }
  function dd(x) { return ok(x) ? String(Math.round(x)) : null; }
  function pending(box, why) { var p = el("span", "pending", "pending"); box.appendChild(p); box.appendChild(el("span", "cap", why)); }
  function big(box, parts) {            // parts: strings, joined with arrows; null part => pending
    var row = el("div", "big");
    parts.forEach(function (t, i) {
      if (i) row.appendChild(el("span", "arrow", "→"));
      row.appendChild(el("span", "num", t));
    });
    box.appendChild(row);
  }
  function cap(box, html) { var c = el("div", "cap"); c.innerHTML = html; box.appendChild(c); return c; }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }
  function variant(sc, key) { return sc && sc.variants.filter(function (v) { return v.key === key; })[0]; }
  function scen(id) { return FLOW && FLOW.scenarios.filter(function (s) { return s.id === id; })[0]; }
  function when(iso) { return iso ? String(iso).slice(0, 16).replace("T", " ") + " UTC" : "unknown time"; }
  function guard(id, fn) {
    var box = document.getElementById(id);
    try { fn(box); } catch (e) { box.textContent = ""; pending(box, "could not read the data (" + e.message + ")"); }
  }

  // 1. The problem: synthetic Finnish county, today's pathway, share within the provisional target
  guard("p-problem", function (box) {
    var fin = scen("finland"), b = fin && variant(fin, "baseline"), m = b && b.flow.metrics;
    var s = m && pct(m.share_within_target);
    if (!s) return pending(box, "run demo/export_flow.py");
    big(box, [s]);
    cap(box, "of lung cancers treated within <b>" + esc(dd(fin.target_days)) + " days</b> of first contact today, held-out patients of the <b>synthetic</b> Finnish county. The " + esc(dd(fin.target_days)) +
      "-day target is provisional (no Finnish first-contact target found); median " + esc(dd(m.median_days_to_treatment)) + " days. Not a measured Finnish figure.");
  });

  // 2. Primary care: the encounter loop's own results
  guard("p-primary", function (box) {
    var o = ENC && ENC.results && ENC.results.overall;
    var w = o && pct(o.cancer_within_target_share);
    if (!w) return pending(box, "run demo/export_encounter.py");
    big(box, [w]);
    cap(box, "of <b>" + esc(o.cancers) + " cancers</b> treated within " + esc(dd(ENC.target_days)) + " days in the loop (" + esc(o.n) + " simulated patients). Median " + esc(dd(o.cancer_median_days_to_referral)) +
      " days to referral, " + esc(dd(o.cancer_median_days_to_treatment)) + " to treatment; <b>" + esc(o.cancer_left_with_symptoms) + "</b> cancers left primary care with symptoms still present.");
    var tuned = ST && ST.encounter_results;
    cap(box, "Run of " + esc(when(ENC.generated_at)) + (tuned ? "; tuned report found in docs/review_checks/encounter_results.json." : ". Rates are being tuned: tuned report <span class=\"pending\">pending</span>."));
    var ex = document.getElementById("ex-links");
    (ENC.examples || []).slice(0, 2).forEach(function (e) {
      var a = el("a", "btn sm", e.label); a.href = "encounter.html?p=" + encodeURIComponent(e.id); ex.appendChild(a);
    });
  });

  // 3. Reordering: today vs suggested on held-out patients (Finland), Norway beside it
  guard("p-order", function (box) {
    var fin = scen("finland"), nor = scen("norway");
    var fb = fin && variant(fin, "baseline"), fs = fin && variant(fin, "suggested");
    var a = fb && pct(fb.flow.metrics.share_within_target), b = fs && pct(fs.flow.metrics.share_within_target);
    if (!a || !b) return pending(box, "run demo/export_flow.py");
    big(box, [a, b]);
    cap(box, "treated within " + esc(dd(fin.target_days)) + " days, synthetic Finnish county, two reorders, no new capacity. Missed cancers per cohort " +
      esc(dd(fb.flow.metrics.missed_cancers)) + " → " + esc(dd(fs.flow.metrics.missed_cancers)) + " (guardrail). Scenario: <code>" + esc(fb.flow.scenario) + "</code>, the hospital-chain model.");
    var nb = nor && variant(nor, "observed"), ns = nor && variant(nor, "suggested");
    if (nb && ns) cap(box, "Norway, same method, no new equipment: <b>" + esc(pct(nb.flow.metrics.share_within_target)) + " → " + esc(pct(ns.flow.metrics.share_within_target)) + "</b> within " + esc(dd(nor.target_days)) + " days.");
  });

  // 4. Trust: Norway check, published next to simulated
  guard("p-trust", function (box) {
    var nor = scen("norway"), pub = nor && nor.published;
    var obs = nor && variant(nor, "observed"), fp = nor && variant(nor, "faster_pet"), au = nor && variant(nor, "authors");
    if (!pub || !au) return pending(box, "run demo/export_flow.py");
    big(box, [pct(pub.authors_estimate_share) + " published", pct(au.flow.metrics.share_within_target) + " simulated"]);
    cap(box, "authors' reordered pathway, predicted not fitted (fitted only on today's order: " + esc(pct(obs.flow.metrics.share_within_target)) + " vs published " + esc(pct(pub.observed_share)) +
      "). <b>Over-predicts</b> the faster-scanner-only case: " + esc(pct(fp.flow.metrics.share_within_target)) + " vs published " + esc(pct(pub.faster_pet_share)) + ".");
    var v = ST && ST.validation;
    if (v) cap(box, esc(v.accepted) + " of " + esc(v.grid_points) + " calibration settings reproduce the observed pathway; the reordered result is not independent of the fitted practice (see method and limits).");
    var r = ST && ST.norway_robustness, p = r && r.pred;
    if (p && p.optimal && p.faster_pet) cap(box, "Robustness over " + esc(r.accepted) + " settings of a wider grid (p10 to p90): reordered " + esc(pct(p.optimal.p10)) + " to " + esc(pct(p.optimal.p90)) +
      ", faster scanner only " + esc(pct(p.faster_pet.p10)) + " to " + esc(pct(p.faster_pet.p90)) + ". Trust the ranking, not the exact size.");
    else cap(box, "Wider-grid robustness range: <span class=\"pending\">pending</span>.");
  });

  // 6. Data and honesty: ledger and catalogue counts
  guard("p-honest", function (box) {
    var L = ST && ST.ledger, C = ST && ST.catalogue;
    if (!L && !C) return pending(box, "run demo/export_start.py");
    if (L) {
      var f = L.scenarios.filter(function (s) { return s.id === "finland_lung"; })[0];
      var n = L.scenarios.filter(function (s) { return s.id === "stokstad"; })[0];
      if (f) { big(box, [f.sourced + " of " + f.blocks]); cap(box, "inputs of the Finnish scenario carry a source; the other <b>" + esc(f.assumption) + "</b> are marked assumption."); }
      if (n) cap(box, "Norway check: " + esc(n.sourced) + " of " + esc(n.blocks) + " sourced.");
    }
    if (C) cap(box, "Care catalogue (status <b>" + esc(C.status || "unknown") + "</b>, not yet clinician-read): " + esc(C.sourced) + " sourced, <b>" + esc(C.assumption) + "</b> assumption, of " + esc(C.total) + " entries.");
  });
})();
