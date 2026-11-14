/* Overview page (demo/start.html): binds every number from the bundles the other screens use. No number is typed here.
   Sources: window.FLOW_DATA (data/flow_bundle.js), window.ENC_DATA (data/encounter_bundle.js),
   window.START_DATA (data/start_bundle.js, from demo/export_start.py), window.CARDS_DATA (data/cards_bundle.js),
   window.RESEARCH_DATA (data/research_bundle.js: published / our simulation / our assumption labels, D69).
   Missing data shows "pending". Design constants live in start.css, not here (tests/test_demo_start.py numeral rule). */
(function () {
  "use strict";
  var FLOW = window.FLOW_DATA, ENC = window.ENC_DATA, ST = window.START_DATA, CARDS = window.CARDS_DATA, RES = window.RESEARCH_DATA;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function ok(x) { return typeof x === "number" && isFinite(x); }
  function pct(x) { return ok(x) ? Math.round(x * 100) + "%" : null; }
  function pos(x) { return ok(x) ? Math.max(0, Math.min(100, x * 100)) + "%" : null; }
  function dd(x) { return ok(x) ? String(Math.round(x)) : null; }
  function $(id) { return document.getElementById(id); }
  function set(id, text) { var e = $(id); if (e && text != null) e.textContent = text; }
  function pending(box, why) { box.appendChild(el("span", "ov-pending", "pending")); box.appendChild(el("span", "ov-cap", " " + why)); }
  function big(box, parts, sep) {       // detail headline numbers, joined with arrows (or sep)
    var row = el("div", "ov-big");
    parts.forEach(function (t, i) {
      if (i) row.appendChild(el("span", "ov-arrow", sep || "→"));
      row.appendChild(el("span", "num", t));
    });
    box.appendChild(row);
  }
  function cap(box, html) { var c = el("p", "ov-cap"); c.innerHTML = html; box.appendChild(c); return c; }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }
  function variant(sc, key) { return sc && sc.variants.filter(function (v) { return v.key === key; })[0]; }
  function scen(id) { return FLOW && FLOW.scenarios.filter(function (s) { return s.id === id; })[0]; }
  function when(iso) { return iso ? String(iso).slice(0, 16).replace("T", " ") + " UTC" : "unknown time"; }
  function rg(b) { return b ? pct(b.min) + " to " + pct(b.max) + ", median " + pct(b.median) : null; }
  function share(v) { return v && v.flow && v.flow.metrics && v.flow.metrics.share_within_target; }
  function norwayOpt() { return ST && ST.norway && ST.norway.optimiser; }
  function consistencyText() {
    var c = ST && ST.encounter_consistency; if (!c || !c.tuning) return "";
    return "The loop agrees with the calibrated chain on " + c.tuning.passed + " of " + c.tuning.total + " checks on the tuning seeds" + (c.fresh ? ", " + c.fresh.passed + " of " + c.fresh.total + " on fresh seeds" : "") + (c.pooled ? ", " + c.pooled.passed + " of " + c.pooled.total + " pooled" : "") + ", only just.";
  }
  function guard(id, fn) {
    var box = $(id); if (!box) return;
    try { fn(box); } catch (e) { box.textContent = ""; pending(box, "could not read the data (" + e.message + ")"); }
  }

  // Claim labels (D69): "Our simulation" etc. from the research bundle, linking research.html#<claim id>.
  var CLAIMS = {};
  ((RES && RES.claims) || []).forEach(function (c) { CLAIMS[c.id] = c; });
  function basisLink(id) {
    var c = CLAIMS[id], labels = (RES && RES.basis_labels) || {};
    if (!c) return null;
    var a = el("a", "ov-basis__link ov-basis--" + c.basis + " basis basis--" + c.basis, labels[c.basis] || c.basis);
    a.href = "research.html#" + encodeURIComponent(id);
    a.title = c.claim;
    return a;
  }
  function claimList(box, ids) {        // below DETAILS: each claim with its label, linking research.html#<claim id>
    var ul = el("ul", "ov-claims");
    ids.forEach(function (id) {
      var a = basisLink(id); if (!a) return;
      var li = el("li"); li.appendChild(a); li.appendChild(el("span", null, " " + CLAIMS[id].claim)); ul.appendChild(li);
    });
    if (ul.childNodes.length) box.appendChild(ul);
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-claim]"), function (p) {
    p.textContent = "";
    String(p.getAttribute("data-claim")).split(" ").forEach(function (id) {
      var a = basisLink(id); if (!a) return;
      if (p.childNodes.length) p.appendChild(document.createTextNode(" "));
      p.appendChild(a);
    });
  });

  // ---------- Top: three cards ----------
  var fin = scen("finland"), nor = scen("norway");
  var fb = variant(fin, "baseline"), fs = variant(fin, "suggested");
  var nb = variant(nor, "observed"), ns = variant(nor, "suggested");
  var pub = nor && nor.published, O = norwayOpt();

  // I Simulate: median days to treatment today, synthetic Finnish county
  guard("c-simulate", function () {
    set("n-sim-days", dd(fb && fb.flow.metrics.median_days_to_treatment));
  });

  // II Optimise: Finland, today vs two reorders, held-out patients
  guard("c-optimise", function () {
    var a = share(fb), b = share(fs);
    set("n-opt-today", pct(a)); set("n-opt-after", pct(b));
    if (pos(a)) $("b-today").style.height = pos(a);
    if (pos(b)) $("b-after").style.height = pos(b);
    $("b-today").setAttribute("data-v", pct(a) || ""); $("b-after").setAttribute("data-v", pct(b) || "");
    if (fin && ok(fin.target_days)) set("t-opt", "treated within " + dd(fin.target_days) + " days after two reorders, no new equipment, on held-out patients.");
  });

  // III Check: Norway, published today vs fitted model, and the optimiser with no new equipment (best fit, range)
  guard("c-check", function () {
    var t = share(nb), s = share(ns), band = O && O.bands && O.bands.optimiser_no_equipment;
    set("n-chk-today", pct(t)); set("n-chk-after", pct(s));
    if (pub && pos(pub.observed_share)) $("r-pub").style.left = pos(pub.observed_share);
    if (pos(t)) $("r-fit").style.left = pos(t);
    if (pos(s)) $("r-opt").style.left = pos(s);
    if (band && pos(band.min) && pos(band.max)) {
      $("r-bar").style.left = pos(band.min);
      $("r-bar").style.width = (Math.min(band.max, 1) - Math.max(band.min, 0)) * 100 + "%";
    }
    $("r-pub").title = pub ? "published " + pct(pub.observed_share) : "";
    $("r-fit").title = "our model, fitted: " + (pct(t) || "pending");
    $("r-opt").title = "our model, reordered, best fit: " + (pct(s) || "pending");
    if (band) set("t-chk-range", "No new equipment, best fit. " + pct(band.min) + " to " + pct(band.max) + " across the " + O.n_settings + " settings that fit; within " + dd(nor.target_days) + " days.");
  });

  // Footer (the nav is filled by site.js from data-page)
  if (window.Site && typeof window.Site.footer === "function")
    window.Site.footer("Synthetic patients only · not clinically reviewed · numbers read from start_bundle.js, flow_bundle.js, encounter_bundle.js and research_bundle.js when the page opens");

  // ---------- DETAILS ----------

  // The problem: synthetic Finnish county, today's pathway, share within the provisional target
  guard("p-problem", function (box) {
    var m = fb && fb.flow.metrics, s = m && pct(m.share_within_target);
    if (!s) return pending(box, "run demo/export_flow.py");
    cap(box, "<b>" + esc(s) + "</b> of lung cancers treated within <b>" + esc(dd(fin.target_days)) + " days</b> of first contact today, held-out patients of the <b>synthetic</b> Finnish county. The " + esc(dd(fin.target_days)) +
      "-day target is provisional (no Finnish first-contact target found); median " + esc(dd(m.median_days_to_treatment)) + " days. Not a measured Finnish figure.");
  });

  // Reordering: today vs suggested on held-out patients (Finland), Norway beside it
  guard("p-order", function (box) {
    var a = fb && pct(share(fb)), b = fs && pct(share(fs));
    if (!a || !b) return pending(box, "run demo/export_flow.py");
    big(box, [a, b]);
    cap(box, "treated within " + esc(dd(fin.target_days)) + " days, synthetic Finnish county, two reorders, no new capacity. Median " + esc(dd(fb.flow.metrics.median_days_to_treatment)) + " → " + esc(dd(fs.flow.metrics.median_days_to_treatment)) + " days. Missed cancers per cohort " +
      esc(dd(fb.flow.metrics.missed_cancers)) + " → " + esc(dd(fs.flow.metrics.missed_cancers)) + " (guardrail). Scenario: <code>" + esc(fb.flow.scenario) + "</code>, the hospital-chain model.");
    if (nb && ns) {
      var line = "<b>Norway, no new equipment:</b> " + esc(pct(share(nb))) + " → <b>" + esc(pct(share(ns))) + "</b> treated within " + esc(dd(nor.target_days)) + " days, simulated, best-fitting setting.";
      if (O && O.bands.optimiser_no_equipment) line += " Over the " + esc(O.n_settings) + " settings that fit the observed data: " + esc(rg(O.bands.optimiser_no_equipment)) + " (today: " + esc(rg(O.bands.observed)) + "); better than today in " + esc(O.counts.noeq_beats_observed) + " of " + esc(O.n_settings) + ".";
      cap(box, line);
    }
    claimList(box, ["sim-fi-reorder-headline", "sim-fi-median-days", "sim-fi-guardrails", "sim-no-optimiser-found-redesign"]);
    var gb = $("go-order");
    if (gb && nor) {
      gb.appendChild(document.createTextNode(" · "));
      var a1 = el("a", null, "Norway: today and reordered, no new equipment"); a1.href = "flow.html?s=norway&compare&left=observed&right=suggested"; gb.appendChild(a1);
    }
  });

  // Trust: Norway check, published next to simulated, with the whole honest picture
  guard("p-trust", function (box) {
    var obs = nb, fp = variant(nor, "faster_pet"), au = variant(nor, "authors");
    if (!pub || !au) return pending(box, "run demo/export_flow.py");
    big(box, [pct(pub.authors_estimate_share) + " published", pct(share(au)) + " simulated"], "·");
    var stamp = el("span", "stamp ov-detail__stamp", "Predicted, not fitted"); box.appendChild(stamp);
    cap(box, "The authors' reordered pathway, <b>predicted, not fitted</b>: the model was fitted only on today's order (" + esc(pct(share(obs))) + " vs published " + esc(pct(pub.observed_share)) + "). This is the best-fitting setting.");
    var N = ST && ST.norway, p = N && N.all_settings && N.all_settings.pred, S = O && O.structure;
    if (p && p.optimal) cap(box, "<b>The range is wider.</b> Over all " + esc(N.all_settings.accepted) + " settings that fit the observed data, the authors' pathway as we built it comes out at " + esc(pct(p.optimal.min)) + " to " + esc(pct(p.optimal.max)) +
      ", typically about " + esc(pct(p.optimal.median)) + ". The " + esc(pct(pub.authors_estimate_share)) + " is the best match, not a sharp hit.");
    else cap(box, "Range over all settings that fit: <span class=\"ov-pending\">pending</span>.");
    cap(box, "<b>It over-predicts the faster scanner alone:</b> " + esc(pct(share(fp))) + " in the model against " + esc(pct(pub.faster_pet_share)) + " published" +
      (p && p.faster_pet ? " (range " + esc(pct(p.faster_pet.min)) + " to " + esc(pct(p.faster_pet.max)) + ")" : "") + ". Trust the ranking of reorderings, not the exact size.");
    if (S) cap(box, "<b>Structure check:</b> read literally (treatment does not wait for the tissue sample; PET-CT ordered at the first visit, not at triage), the authors' pathway gives a median of " + esc(pct(S.literal_median)) + " over the " + esc(S.settings) + " settings, with " + esc(S.literal_in_published_ci) + " of " + esc(S.settings) +
      " inside the published " + esc(pct(S.published_ci[0])) + " to " + esc(pct(S.published_ci[1])) + " interval (the shipped version: " + esc(S.shipped_in_published_ci) + "). Caveats: only the paper's text was read, not its figures; the observed pathway was not recalibrated under that reading; the shipped scenario is unchanged.");
    if (ns && O) {
      var VP = ST && ST.validation && ST.validation.published, ci = VP && VP.optimal && VP.optimal.ci95;
      var d = document.createElement("details"); d.className = "ov-more"; d.open = true;
      d.appendChild(el("summary", null, "What our optimiser did on this test"));
      var h = "<p><b>A plausibility check, not a forecast.</b> Started from the observed pathway, with no new equipment and without being told the answer, the optimiser reached " + esc(rg(O.bands.optimiser_no_equipment)) + " across the " + esc(O.n_settings) + " settings that fit (best fit " + esc(pct(share(ns))) + "; today " + esc(rg(O.bands.observed)) + "). Its pathway contains the authors' three timing changes (PET-CT and exercise test ordered early, tumour board without waiting for the tissue sample) plus a fourth: planning tissue sampling when the referral is triaged, which <b>needs a clinical check</b>. It did not improve on the authors' redesign.</p>" +
        "<p>Not a like-for-like pair: the authors' " + esc(pct(pub.authors_estimate_share)) + (ci ? " (" + esc(pct(ci[0])) + " to " + esc(pct(ci[1])) + ")" : "") + " includes the shorter PET-CT wait; ours does not. Without new equipment it beats the faster scanner alone (" + esc(rg(O.bands.faster_pet)) + ") in only " + esc(O.counts.noeq_beats_scanner_alone) + " of " + esc(O.n_settings) + " settings.</p>" +
        "<p>The numbers come from a model fitted to one hospital. Treat them as a ranking, not a forecast.</p>";
      var c = el("div", "ov-cap"); c.innerHTML = h; d.appendChild(c); box.appendChild(d);
    }
    var v = ST && ST.validation;
    if (v) cap(box, esc(v.accepted) + " of " + esc(v.grid_points) + " settings on the original grid reproduce the observed pathway. The " + esc(pct(pub.authors_estimate_share)) + " also depends on the fitted practice of ordering PET-CT at triage.");
    claimList(box, ["pub-stokstad-observed-40", "pub-stokstad-reordered-80", "sim-no-fitted-observed", "sim-no-authors-band", "sim-no-faster-pet-overpredicted", "sim-no-noequipment-vs-scanner"]);
  });

  // Primary care: the encounter loop's own results
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
      : " Multi-seed report: <span class=\"ov-pending\">pending</span>."));
    var ex = $("ex-links");
    (ENC.examples || []).slice(0, 2).forEach(function (e) {
      ex.appendChild(document.createTextNode(" · "));
      var a = el("a", null, "Example: " + e.label); a.href = "encounter.html?p=" + encodeURIComponent(e.id); ex.appendChild(a);
    });
    claimList(box, ["as-primary-care-behaviour"]);
  });

  // Synthetic patients: the card itself moved to the Patients page (lane L3); the counts stay here as one line
  guard("p-cards", function (box) {
    var T = CARDS && CARDS.totals;
    box.textContent = "";
    if (T) box.appendChild(document.createTextNode(T.model_written_cards + " model-written and " + T.template_cards + " template-written synthetic patients in " + T.libraries + " libraries (counted " + when(CARDS.generated_at) + "). Two ways of writing the same patient, and the hidden side, are on the "));
    else box.appendChild(document.createTextNode("Two ways of writing the same patient, and the hidden side, are on the "));
    var a = el("a", null, "Patients page"); a.href = "patients.html"; box.appendChild(a);
    box.appendChild(document.createTextNode("."));
  });

  // Data and honesty: ledger and catalogue counts
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
    claimList(box, ["as-ledger-counts", "as-target-90d", "as-synthetic-patients", "as-catalogue-draft"]);
  });
})();
