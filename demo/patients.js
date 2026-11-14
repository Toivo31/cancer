/* Patients page (demo/patients.html): one example patient as a sealed truth and a visible record, the optimiser loop,
   and the synthetic-patient details. Every number is read from the bundles at load time; none is typed here.
   Sources: window.ENC_DATA (data/encounter_bundle.js: patients with record lines, truth split, examples),
   window.CARDS_DATA (data/cards_bundle.js: library counts, one example card), window.FLOW_DATA (data/flow_bundle.js:
   Norway observed and suggested variants on held-out cohorts), window.START_DATA (data/start_bundle.js: range over the
   fitting settings, catalogue counts), window.RESEARCH_DATA (data/research_bundle.js: claim ids and basis labels, D69). The sealed truth (ENC_DATA.truth) is read only after the reader lifts the seal.
   URL: ?p=<patient id> picks a patient from the bundle, ?truth opens with the seal lifted, ?theme=night via site.js. */
(function () {
  "use strict";
  var ENC = window.ENC_DATA, CARDS = window.CARDS_DATA, FLOW = window.FLOW_DATA, ST = window.START_DATA;
  var Q = new URLSearchParams(location.search);
  var S = { open: Q.has("truth"), i: 0, list: [] };

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function ok(x) { return typeof x === "number" && isFinite(x); }
  function pct(x) { return ok(x) ? Math.round(x * 100) + "%" : "pending"; }
  function when(iso) { return iso ? String(iso).slice(0, 16).replace("T", " ") + " UTC" : "unknown time"; }
  function guard(id, fn) {
    var box = $(id); if (!box) return;
    try { fn(box); } catch (e) { box.textContent = "pending (could not read the data: " + e.message + ")"; }
  }

  /* ------------------------------------------------------------------ site chrome (site.js, L0) */
  function chrome() {
    // site.js fills the nav itself (data-page="patients"); the footer gets the page's own sentence, without digits.
    var foot = "Synthetic patients only · not clinically reviewed · numbers read from encounter_bundle.js, cards_bundle.js, flow_bundle.js and start_bundle.js";
    if (window.Site && typeof window.Site.footer === "function") window.Site.footer(foot); else $("pt-footer").textContent = foot;
  }

  // D69 basis labels: <span class="pt-basis" data-claim="id"> becomes a link to research.html#id when the research
  // register (research_bundle.js) lists that claim; otherwise it stays a plain label.
  function claimLinks() {
    var R = window.RESEARCH_DATA, known = {};
    ((R && R.claims) || []).forEach(function (c) { known[c.id] = c; });
    Array.prototype.forEach.call(document.querySelectorAll(".pt-basis[data-claim]"), function (sp) {
      var c = known[sp.getAttribute("data-claim")];
      if (!c) return;
      var a = el("a", sp.className, (R.basis_labels && R.basis_labels[c.basis]) || sp.textContent);
      a.href = "research.html#" + encodeURIComponent(c.id);
      a.title = c.claim;
      a.setAttribute("data-claim", c.id);
      sp.parentNode.replaceChild(a, sp);
    });
  }

  /* ------------------------------------------------------------------ the example patient */
  function patientsById() {
    var m = {}; (ENC && ENC.patients || []).forEach(function (p) { m[String(p.id)] = p; }); return m;
  }
  function pickList() {
    var byId = patientsById(), ex = (ENC && ENC.examples) || [];
    var list = ex.filter(function (e) { return byId[String(e.id)]; }).map(function (e) { return { id: String(e.id), label: e.label, key: e.key }; });
    var want = Q.get("p");
    if (want && byId[want] && !list.some(function (e) { return e.id === want; })) list.unshift({ id: want, label: null, key: "url" });
    var start = 0;
    if (want) list.forEach(function (e, i) { if (e.id === want) start = i; });
    else list.forEach(function (e, i) { if (e.key === "cancer_as_infection") start = i; });
    S.list = list; S.i = start;
    return byId;
  }

  // Compact a mechanical record line ("Day 14.1 · GP · <findings> · ordered X · note: ...") to what a reader needs.
  function compact(text) {
    var seg = String(text).split(" · ");
    var day = seg[0], who = seg[1] || "", rest = seg.slice(2);
    var note = ""; rest = rest.filter(function (s) { if (s.indexOf("note: ") === 0) { note = s.slice(6); return false; } return true; });
    var what;
    if (/^(GP|Nurse)$/.test(who)) {
      // the note reads "GP: fatigue, finger clubbing. Plan: X." -> findings and plan
      var m = note.match(/^[A-Z]+:\s*(.*?)\.\s*Plan:\s*(.*?)\.?$/);
      what = m ? (m[1] ? m[1] + ". " : "") + "Plan: " + m[2] : rest[rest.length - 1] || note;
      who = who + " visit";
    } else if (who === "result") {
      what = rest.join(" · "); who = "Result";
    } else if (who === "hospital") {
      what = (rest[0] || note).replace(/: result$/, ""); who = "Hospital";
    } else if (/^(discharge|return)$/.test(who)) {
      what = note || rest.join(" · "); who = who.charAt(0).toUpperCase() + who.slice(1);
    } else {
      what = rest[0] || note; who = who.charAt(0).toUpperCase() + who.slice(1);
    }
    return { day: day.replace(/^Day\s+/, ""), who: who, what: what, full: text };
  }

  var BYID = null;
  function current() { var e = S.list[S.i]; return e ? BYID[e.id] : null; }

  function renderRecord() {
    var p = current(), box = $("pt-lines"), who = $("pt-who");
    box.textContent = "";
    if (!p) { who.textContent = "pending: no example patient in data/encounter_bundle.js"; return; }
    var tr = S.open && ENC.truth ? ENC.truth[String(p.id)] : null;
    who.textContent = "Patient " + p.id + " · " + p.g;
    p.lines.forEach(function (l, i) {
      if (l[1]) return;                       // assessments (the decider's words) are left to the encounter page
      var c = compact(l[2]);
      var li = el("li", "pt-line"); li.title = c.full;
      li.appendChild(el("span", "pt-day", "Day " + Math.round(parseFloat(c.day))));
      var body = el("span", "pt-what");
      body.appendChild(el("b", null, c.who)); body.appendChild(document.createTextNode(" " + c.what));
      li.appendChild(body);
      if (tr && tr.marks && tr.marks[i] != null) {
        li.classList.add(tr.marks[i] ? "pt-line--ok" : "pt-line--bad");
        li.appendChild(el("span", "pt-mark", tr.marks[i] ? "matches a true condition" : "treats a condition the patient does not have"));
      }
      box.appendChild(li);
    });
    var bad = box.querySelector(".pt-line--bad, .pt-line--ok");
    if (bad) box.scrollTop = Math.max(0, bad.offsetTop - box.offsetTop - box.clientHeight / 3);
    $("pt-open").href = "encounter.html?p=" + encodeURIComponent(p.id) + (S.open ? "&truth" : "");
  }

  function renderTruth() {
    var box = $("pt-truth"), btn = $("pt-reveal"), seal = $("pt-seal"), stamp = $("pt-seal-stamp");
    box.textContent = "";
    btn.setAttribute("aria-pressed", S.open ? "true" : "false");
    btn.textContent = S.open ? "Seal it again" : "Lift the seal";
    btn.className = "btn pt-reveal " + (S.open ? "btn--secondary" : "btn--primary");
    seal.setAttribute("data-state", S.open ? "open" : "sealed");
    stamp.textContent = S.open ? "Lifted" : "Sealed";
    stamp.classList.toggle("stamp--brick", S.open);
    if (!S.open) { box.hidden = true; return; }       // nothing of the truth is in the page until here
    var p = current(), tr = p && ENC.truth && ENC.truth[String(p.id)];
    box.hidden = false;
    if (!tr) { box.appendChild(el("p", null, "pending: no sealed truth for this patient in the bundle")); return; }
    box.appendChild(el("div", "label", "Actually had"));
    var c = el("p", "pt-cond", tr.conditions.join(", "));
    if (tr.cancer) { c.appendChild(document.createTextNode(" ")); c.appendChild(el("span", "pt-cancer", "cancer")); }
    box.appendChild(c);
    if (tr.caption) box.appendChild(el("p", "pt-cap", tr.caption + "."));
    box.appendChild(el("p", "pt-note", "No clinician in the simulation ever sees this. Only the scoring code reads it, after the run."));
  }

  function render() { renderTruth(); renderRecord(); }

  function setOpen(on) {
    S.open = on;
    if (window.history && history.replaceState) {
      var q = new URLSearchParams(location.search);
      if (on) q.set("truth", ""); else q.delete("truth");
      var s = q.toString().replace(/truth=(&|$)/, "truth$1");
      history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
    }
    render();
  }

  /* ------------------------------------------------------------------ step five: the reported number */
  function norway() {
    var sc = FLOW && FLOW.scenarios.filter(function (s) { return s.id === "norway"; })[0];
    if (!sc) return null;
    function v(k) { return sc.variants.filter(function (x) { return x.key === k; })[0]; }
    var o = v("observed"), s = v("suggested");
    var opt = ST && ST.norway && ST.norway.optimiser, band = opt && opt.bands && opt.bands.optimiser_no_equipment;
    return { days: sc.target_days, today: o && o.flow.metrics.share_within_target, after: s && s.flow.metrics.share_within_target,
      band: band, n: opt && opt.n_settings, note: s && s.note };
  }
  function renderResult() {
    guard("pt-result", function (box) {
      var r = norway();
      if (!r || !ok(r.today) || !ok(r.after)) { box.textContent = "pending: Norway variants missing from data/flow_bundle.js"; return; }
      box.textContent = "";
      var big = el("span", "pt-big");
      big.appendChild(el("span", "num pt-today", pct(r.today)));
      big.appendChild(el("span", "pt-to", "→"));
      big.appendChild(el("span", "num", pct(r.after)));
      box.appendChild(big);
      box.appendChild(el("span", "pt-small", "Norwegian hospital, treated within " + Math.round(r.days) + " days, reordering only, no new equipment. Best fit" +
        (r.band ? "; " + pct(r.band.min) + " to " + pct(r.band.max) + " across the " + r.n + " settings that fit" : "") + "."));
    });
    guard("pt-result-detail", function (box) {
      var r = norway();
      if (!r) { box.textContent = "pending"; return; }
      box.textContent = "a simulation of the Norwegian hospital in Stokstad et al. (2019). Today's pathway gives " + pct(r.today) +
        " treated within " + Math.round(r.days) + " days; the change the optimiser found from that pathway alone, with no new equipment, gives " + pct(r.after) +
        " on cohorts the search never saw, at the best-fitting setting" + (r.band ? ", and " + pct(r.band.min) + " to " + pct(r.band.max) +
        " (median " + pct(r.band.median) + ") across the " + r.n + " settings that fit the published observed pathway" : "") +
        ". The size is an estimate resting on our inputs; the ranking is the part to trust.";
    });
  }

  /* ------------------------------------------------------------------ details: the card (copied from start.js at the base commit) */
  function renderCards() {
    guard("pt-cards", function (box) {
      var C = CARDS, ex = C && C.example;
      if (!C || !ex) { box.textContent = "pending: run demo/export_cards.py"; return; }
      var bg = ex.background, bgt = Object.keys(bg).map(function (k) { return k.replace("_", " ") + " " + bg[k]; }).join(", ");
      function col(cls, title, rows) {
        var c = el("div", "pt-col " + cls); c.appendChild(el("div", "label", title));
        rows.forEach(function (r) { c.appendChild(el("div", "pt-lab", r[0])); c.appendChild(el("div", "pt-txt", r[1])); });
        return c;
      }
      var cols = el("div", "pt-cols");
      var d = ex.decider_sees, t = ex.template;
      cols.appendChild(col("pt-col--model", "Written by a language model: what the decider sees",
        [["Complaint, in the patient's words", d.complaint], ["History taken", d.history]]));
      cols.appendChild(col("pt-col--tmpl", "Template wording of the same patient",
        [["Complaint", t.complaint], ["History taken", t.history]]));
      box.appendChild(el("div", "pt-bg label", "Patient " + ex.card + " (library " + ex.library + "): " + bgt));
      box.appendChild(cols);
      var hd = document.createElement("details"); hd.className = "pt-hidden";
      hd.appendChild(el("summary", null, "Hidden side (never shown to the decision model)"));
      var tr = ex.hidden.conditions.map(function (c) {
        var a = Object.keys(c.attributes).map(function (k) { return k.replace("_", " ") + " " + c.attributes[k]; }).join(", ");
        return c.label + " (" + c.role + (a ? "; " + a : "") + ")";
      }).join(" and ");
      hd.appendChild(el("div", "pt-txt", "True condition: " + tr + ". The test results were drawn from these facts. Only the scoring code reads them, after a run ends."));
      box.appendChild(hd);
      var T = C.totals, lib = C.libraries;
      function names(w) { return lib.filter(function (l) { return l.wording === w; }).map(function (l) { return l.name + ": " + l.cards; }).join("; "); }
      var pc = el("p", "pt-src");
      pc.appendChild(el("b", null, String(T.model_written_cards)));
      pc.appendChild(document.createTextNode(" model-written patients (" + names("model") + ") and "));
      pc.appendChild(el("b", null, String(T.template_cards)));
      pc.appendChild(document.createTextNode(" template-written (" + names("template") + "), " + T.libraries + " libraries, counted from the library manifests on " +
        when(C.generated_at) + ". The patient shown is the first lung-cancer card of the largest model-written library. Test reports are left out here on purpose."));
      box.appendChild(pc);
    });
  }

  function renderCatalogue() {
    guard("pt-catalogue", function (box) {
      var C = ST && ST.catalogue, conds = {};
      ((CARDS && CARDS.libraries) || []).forEach(function (l) { Object.keys(l.by_condition || {}).forEach(function (k) { conds[k] = 1; }); });
      var nc = Object.keys(conds).length;
      var s = (nc ? "The cards cover " + nc + " conditions. " : "");
      s += C ? "Catalogue " + (C.path || "") + ", status " + (C.status || "unknown") + ": " + C.sourced + " of its " + C.total + " entries cite a source, " + C.assumption + " are marked assumption." :
        "Catalogue counts pending (data/start_bundle.js).";
      box.textContent = s;
    });
    guard("pt-prompts", function (box) {
      var lib = (CARDS && CARDS.libraries) || [];
      if (!lib.length) { box.textContent = "Library list pending (data/cards_bundle.js)."; return; }
      box.textContent = "Libraries in this build and the results prompt that wrote them: " + lib.map(function (l) {
        return l.name + " (" + (l.wording === "model" ? "model-written" : "template") + ", " + (l.results_prompt || "unknown") + ")";
      }).join("; ") + ". Prompt g2@1 is the leaking one; g2@3 writes reports from values only.";
    });
  }

  /* ------------------------------------------------------------------ start */
  chrome();
  claimLinks();
  guard("pt-lines", function () {
    BYID = pickList();
    $("pt-reveal").addEventListener("click", function () { setOpen(!S.open); });
    var nx = $("pt-next");
    if (S.list.length < 2) nx.hidden = true;
    nx.addEventListener("click", function () { S.i = (S.i + 1) % S.list.length; render(); });
    render();
  });
  renderResult();
  renderCards();
  renderCatalogue();
})();
