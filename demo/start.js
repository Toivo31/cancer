/* Start page: binds numbers from the bundles the other screens use. No number is typed here.
   Sources: window.CARDS_DATA (data/cards_bundle.js, from demo/export_cards.py), window.FLOW_DATA (data/flow_bundle.js), window.ENC_DATA (data/encounter_bundle.js),
   window.START_DATA (data/start_bundle.js, from demo/export_start.py). Missing data shows "pending". */
(function () {
  "use strict";
  var FLOW = window.FLOW_DATA, ENC = window.ENC_DATA, ST = window.START_DATA, CARDS = window.CARDS_DATA;

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
    var nb = nor && variant(nor, "observed"), ns = nor && variant(nor, "suggested"), nf = nor && variant(nor, "suggested_faster_pet"), na = nor && variant(nor, "authors");
    if (nb && ns) {
      var line = "<b>Norway, no new equipment:</b> " + esc(pct(nb.flow.metrics.share_within_target)) + " → <b>" + esc(pct(ns.flow.metrics.share_within_target)) + "</b> treated within " + esc(dd(nor.target_days)) + " days, simulated.";
      if (nf && na) line += " The authors' " + esc(pct(nor.published.authors_estimate_share)) + " needs a new, faster PET-CT scanner; with that same scanner our pathway gives <b>" + esc(pct(nf.flow.metrics.share_within_target)) + "</b> and theirs " + esc(pct(na.flow.metrics.share_within_target)) + " in the simulator. Detail in step 4.";
      cap(box, line);
    }
    var gb = document.getElementById("go-order");
    if (gb && nor) {
      var a1 = el("a", "btn sm", "Norway: no new equipment"); a1.href = "flow.html?s=norway&compare&left=observed&right=suggested"; gb.appendChild(a1);
      var a2 = el("a", "btn sm", "Norway: same scanner as the authors"); a2.href = "flow.html?s=norway&compare&left=authors&right=suggested_faster_pet"; gb.appendChild(a2);
    }
  });

  // 4. Trust: Norway check, published next to simulated, with the whole honest picture
  guard("p-trust", function (box) {
    var nor = scen("norway"), pub = nor && nor.published;
    var obs = nor && variant(nor, "observed"), fp = nor && variant(nor, "faster_pet"), au = nor && variant(nor, "authors");
    var nf = nor && variant(nor, "suggested_faster_pet"), ns = nor && variant(nor, "suggested");
    if (!pub || !au) return pending(box, "run demo/export_flow.py");
    var sh = function (v) { return v.flow.metrics.share_within_target; };
    big(box, [pct(pub.authors_estimate_share) + " published", pct(sh(au)) + " simulated"]);
    cap(box, "The authors' reordered pathway, <b>predicted, not fitted</b>: the model was fitted only on today's order (" + esc(pct(sh(obs))) + " vs published " + esc(pct(pub.observed_share)) + "). This is the best-fitting setting.");
    var N = ST && ST.norway, p = N && N.all_settings && N.all_settings.pred, r = N && N.ranges, w = N && N.without_fourth;
    if (p && p.optimal) cap(box, "<b>The range is wider.</b> Over all " + esc(N.all_settings.accepted) + " settings that fit the observed data, the authors' pathway comes out at " + esc(pct(p.optimal.min)) + " to " + esc(pct(p.optimal.max)) +
      ", typically about " + esc(pct(p.optimal.median)) + ". The " + esc(pct(pub.authors_estimate_share)) + " is the best match, not a sharp hit.");
    else cap(box, "Range over all settings that fit: <span class=\"pending\">pending</span>.");
    cap(box, "<b>It over-predicts the faster scanner alone:</b> " + esc(pct(sh(fp))) + " in the model against " + esc(pct(pub.faster_pet_share)) + " published" +
      (p && p.faster_pet ? " (range " + esc(pct(p.faster_pet.min)) + " to " + esc(pct(p.faster_pet.max)) + ")" : "") + ". Trust the ranking of reorderings, not the exact size.");
    if (nf) {
      var d = document.createElement("details"); d.className = "more"; d.open = true;
      d.appendChild(el("summary", null, "Our optimiser against the authors' pathway"));
      var h = "<p><b>Same scanner, fair comparison:</b> the authors' " + esc(pct(pub.authors_estimate_share)) + " assumes a new, faster PET-CT scanner. With that same scanner our optimiser's pathway gives <b>" + esc(pct(sh(nf))) + "</b> in the simulator, against " + esc(pct(sh(au))) + " for the authors' pathway" +
        (r && r.optimiser_faster_scanner && r.authors ? " (across " + esc(r.n_sets) + " fitting settings: " + esc(pct(r.optimiser_faster_scanner.min)) + " to " + esc(pct(r.optimiser_faster_scanner.max)) + " against " + esc(pct(r.authors.min)) + " to " + esc(pct(r.authors.max)) + "; ahead in " + esc(r.optimiser_above_authors_in) + " of " + esc(r.n_sets) + ")" : "") + ".</p>" +
        "<p><b>No new equipment:</b> our pathway gives <b>" + esc(pct(sh(ns))) + "</b>. That is not comparable with the authors' " + esc(pct(pub.authors_estimate_share)) + ", which needs the scanner.</p>" +
        "<p><b>What the optimiser found:</b> the authors' three changes plus a fourth, planning tissue sampling when the referral is triaged. That fourth change is beyond the paper and <b>needs a clinical check</b>." +
        (w ? " Without it the pathway gives " + esc(pct(w.three_changes)) + ", so the fourth change adds about " + esc(dd((w.all_four - w.three_changes) * 100)) + " points; most of the lead over the authors comes from how the optimiser orders the same steps." : "") + "</p>" +
        "<p>The optimiser's numbers come from a model fitted to one hospital. Treat them as a ranking, not a forecast.</p>";
      var c = el("div", "cap"); c.innerHTML = h; d.appendChild(c); box.appendChild(d);
    }
    var v = ST && ST.validation;
    if (v) cap(box, esc(v.accepted) + " of " + esc(v.grid_points) + " settings on the original grid reproduce the observed pathway. The " + esc(pct(pub.authors_estimate_share)) + " also depends on the fitted practice of ordering PET-CT at triage.");
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

  // Synthetic patients card: one model-written patient as the decider sees it, the template wording, the hidden side
  guard("p-cards", function (box) {
    var C = CARDS, ex = C && C.example;
    if (!C || !ex) return pending(box, "run demo/export_cards.py");
    var bg = ex.background, bgt = Object.keys(bg).map(function (k) { return k.replace("_", " ") + " " + bg[k]; }).join(", ");
    function col(cls, title, rows) {
      var c = el("div", "pcol " + cls); c.appendChild(el("h3", null, title));
      rows.forEach(function (r) { c.appendChild(el("div", "lab", r[0])); c.appendChild(el("div", "txt", r[1])); });
      return c;
    }
    var cols = el("div", "pcols");
    var d = ex.decider_sees, t = ex.template;
    cols.appendChild(col("model", "Written by a language model: what the decider sees",
      [["Complaint, in the patient's words", d.complaint], ["History taken", d.history], ["Test report: " + d.report.test, d.report.text]]));
    cols.appendChild(col("tmpl", "Template wording of the same patient",
      [["Complaint", t.complaint], ["History taken", t.history], ["Test report: " + d.report.test, t.report]]));
    box.appendChild(el("div", "pbg", "Patient " + ex.card + " (library " + ex.library + "): " + bgt));
    box.appendChild(cols);
    var hd = document.createElement("details"); hd.className = "hidden-side";
    hd.appendChild(el("summary", null, "Hidden side (never shown to the decision model)"));
    var tr = ex.hidden.conditions.map(function (c) {
      var a = Object.keys(c.attributes).map(function (k) { return k.replace("_", " ") + " " + c.attributes[k]; }).join(", ");
      return c.label + " (" + c.role + (a ? "; " + a : "") + ")";
    }).join(" and ");
    hd.appendChild(el("div", "txt", "True condition: " + tr + ". The test results above were drawn from these facts. Only the scoring code reads them, after a run ends."));
    box.appendChild(hd);
    var T = C.totals, lib = C.libraries;
    function names(w) { return lib.filter(function (l) { return l.wording === w; }).map(function (l) { return l.name + ": " + l.cards; }).join("; "); }
    var pc = el("div", "pcounts");
    pc.innerHTML = "<b>" + esc(T.model_written_cards) + "</b> model-written patients (" + esc(names("model")) + ") and <b>" + esc(T.template_cards) + "</b> template-written (" + esc(names("template")) +
      "), " + esc(T.libraries) + " libraries, counted from the library manifests on " + esc(when(C.generated_at)) + ". The patient shown is the first lung-cancer card of the largest model-written library.";
    box.appendChild(pc);
  });
})();
