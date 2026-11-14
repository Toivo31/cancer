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
  function rg(b) { return b ? pct(b.min) + " to " + pct(b.max) + ", median " + pct(b.median) : null; }
  function consistencyText() {
    var c = ST && ST.encounter_consistency; if (!c || !c.tuning) return "";
    return "The loop agrees with the calibrated chain on " + c.tuning.passed + " of " + c.tuning.total + " checks on the tuning seeds" + (c.fresh ? ", " + c.fresh.passed + " of " + c.fresh.total + " on fresh seeds" : "") + (c.pooled ? ", " + c.pooled.passed + " of " + c.pooled.total + " pooled" : "") + ", only just.";
  }
  function norwayOpt() { return ST && ST.norway && ST.norway.optimiser; }
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
    var R = ST && ST.encounter_results, cs = R && R.consistency;
    cap(box, "<b>One illustration run</b> of " + esc(when(ENC.generated_at)) + " (one seed, no warm-up); queues fill up as a run gets longer." + (cs && cs.within90 ?
      " The multi-seed report (<code>docs/encounter_results.md</code>, " + esc(R.seeds.length) + " seeds of " + esc(R.n) + ", " + esc(dd(R.warmup_days)) + "-day warm-up) gives <b>" + esc(pct(cs.within90.loop.mean)) + "</b> within " + esc(dd(ENC.target_days)) + " days (range " + esc(pct(cs.within90.loop.lo)) + " to " + esc(pct(cs.within90.loop.hi)) + "), median " + esc(dd(cs.ref_med.loop.mean)) + " days to referral. Quote the report. " + consistencyText() + " Decisions are placeholder tables."
      : " Multi-seed report: <span class=\"pending\">pending</span>."));
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
    var nb = nor && variant(nor, "observed"), ns = nor && variant(nor, "suggested"), O = norwayOpt();
    if (nb && ns) {
      var line = "<b>Norway, no new equipment:</b> " + esc(pct(nb.flow.metrics.share_within_target)) + " → <b>" + esc(pct(ns.flow.metrics.share_within_target)) + "</b> treated within " + esc(dd(nor.target_days)) + " days, simulated, best-fitting setting.";
      if (O && O.bands.optimiser_no_equipment) line += " Over the " + esc(O.n_settings) + " settings that fit the observed data: " + esc(rg(O.bands.optimiser_no_equipment)) + " (today: " + esc(rg(O.bands.observed)) + "); better than today in " + esc(O.counts.noeq_beats_observed) + " of " + esc(O.n_settings) + ".";
      cap(box, line);
    }
    var gb = document.getElementById("go-order");
    if (gb && nor) {
      var a1 = el("a", "btn sm", "Norway: no new equipment"); a1.href = "flow.html?s=norway&compare&left=observed&right=suggested"; gb.appendChild(a1);
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
    var N = ST && ST.norway, p = N && N.all_settings && N.all_settings.pred, O = N && N.optimiser, S = O && O.structure;
    if (p && p.optimal) cap(box, "<b>The range is wider.</b> Over all " + esc(N.all_settings.accepted) + " settings that fit the observed data, the authors' pathway as we built it comes out at " + esc(pct(p.optimal.min)) + " to " + esc(pct(p.optimal.max)) +
      ", typically about " + esc(pct(p.optimal.median)) + ". The " + esc(pct(pub.authors_estimate_share)) + " is the best match, not a sharp hit.");
    else cap(box, "Range over all settings that fit: <span class=\"pending\">pending</span>.");
    cap(box, "<b>It over-predicts the faster scanner alone:</b> " + esc(pct(sh(fp))) + " in the model against " + esc(pct(pub.faster_pet_share)) + " published" +
      (p && p.faster_pet ? " (range " + esc(pct(p.faster_pet.min)) + " to " + esc(pct(p.faster_pet.max)) + ")" : "") + ". Trust the ranking of reorderings, not the exact size.");
    if (S) cap(box, "<b>Structure check:</b> read literally (treatment does not wait for the tissue sample; PET-CT ordered at the first visit, not at triage), the authors' pathway gives a median of " + esc(pct(S.literal_median)) + " over the " + esc(S.settings) + " settings, with " + esc(S.literal_in_published_ci) + " of " + esc(S.settings) +
      " inside the published " + esc(pct(S.published_ci[0])) + " to " + esc(pct(S.published_ci[1])) + " interval (the shipped version: " + esc(S.shipped_in_published_ci) + "). Caveats: only the paper's text was read, not its figures; the observed pathway was not recalibrated under that reading; the shipped scenario is unchanged.");
    if (nf && O) {
      var d = document.createElement("details"); d.className = "more"; d.open = true;
      d.appendChild(el("summary", null, "What our optimiser did on this test"));
      var h = "<p><b>It found the authors' redesign without being told it.</b> Started from the observed pathway only, it arrived at the authors' three changes (PET-CT and exercise test ordered early, tumour board without waiting for the tissue sample) plus a fourth, overlapping change: planning tissue sampling when the referral is triaged, which <b>needs a clinical check</b>. It performs the same as the authors' redesign, not better: the gap in our simulator (" + esc(pct(sh(nf))) + " against " + esc(pct(sh(au))) + " at the best fit) comes from how we built the authors' pathway, where treatment waits for a tissue sample that only starts after the tumour board. Without that wait the two are within a few points in every setting.</p>" +
        "<p><b>With the faster scanner:</b> " + esc(rg(O.bands.optimiser_scanner)) + " across the " + esc(O.n_settings) + " settings (best fit " + esc(pct(sh(nf))) + "). It beats the scanner alone in " + esc(O.counts.scanner_beats_scanner_alone) + " of " + esc(O.n_settings) + ".</p>" +
        "<p><b>No new equipment:</b> " + esc(rg(O.bands.optimiser_no_equipment)) + " (best fit " + esc(pct(sh(ns))) + "), better than today in " + esc(O.counts.noeq_beats_observed) + " of " + esc(O.n_settings) + ". It beats the faster scanner alone (" + esc(rg(O.bands.faster_pet)) + ") in only " + esc(O.counts.noeq_beats_scanner_alone) + " of " + esc(O.n_settings) + ". The authors' " + esc(pct(pub.authors_estimate_share)) + " needs the scanner, so it is not comparable with this number.</p>" +
        "<p>The numbers come from a model fitted to one hospital. Treat them as a ranking, not a forecast.</p>";
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
      [["Complaint, in the patient's words", d.complaint], ["History taken", d.history]]));
    cols.appendChild(col("tmpl", "Template wording of the same patient",
      [["Complaint", t.complaint], ["History taken", t.history]]));
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
      "), " + esc(T.libraries) + " libraries, counted from the library manifests on " + esc(when(C.generated_at)) + ". The patient shown is the first lung-cancer card of the largest model-written library (libraries made with the newer results prompt are preferred when present). Test reports are left out here on purpose.";
    box.appendChild(pc);
  });
})();
