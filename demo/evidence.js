/* demo/evidence.js: the Evidence page ("Does it hold up?", UI lane L4).
 *
 * Every number shown is read at load time from window.START_DATA (demo/data/start_bundle.js, written by
 * demo/export_start.py from docs/review_checks/norway_*.json and docs/validation_results.json) or, for the claim
 * labels, from window.RESEARCH_DATA (demo/data/research_bundle.js, D69). Nothing is typed here; chart geometry
 * (dot sizes, track height, tick step) is read from data-* attributes on #ev-figure.
 *
 * D68: no optimiser result combined with the faster scanner is shown. D62: plausibility framing, always ranges,
 * never claim the optimiser bettered the authors. Wording follows docs/pitch/filled/numbers_sheet.md (rows A1-A7, B1-B7).
 */
(function () {
  "use strict";

  var S = window.START_DATA || {};
  var R = window.RESEARCH_DATA || null;
  var E = S.evidence || null;
  var SVGNS = "http://www.w3.org/2000/svg";
  var HUNDRED = 100;
  var fig = document.getElementById("ev-figure");
  var G = {
    dot: num(fig && fig.dataset.dotR),
    ring: num(fig && fig.dataset.ringR),
    track: num(fig && fig.dataset.trackH),
    tick: num(fig && fig.dataset.tickH),
    step: num(fig && fig.dataset.step),
    compact: num(fig && fig.dataset.compactScale),
    axis: num(fig && fig.dataset.axisH)
  };

  function num(v) { var x = parseFloat(v); return isFinite(x) ? x : null; }
  function isNum(x) { return typeof x === "number" && isFinite(x); }
  function pct(x) { return isNum(x) ? Math.round(x * HUNDRED) + "%" : "pending"; }
  function pctBare(x) { return isNum(x) ? String(Math.round(x * HUNDRED)) : "?"; }
  function range(b) { return b && isNum(b.min) && isNum(b.max) ? pctBare(b.min) + "–" + pct(b.max) : "pending"; }
  function fixed1(x) { return isNum(x) ? (Math.round(x * 10) / 10).toString() : "?"; }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function svg(tag, attrs) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    return e;
  }
  function rowOf(key) { return E && (E.rows || []).filter(function (r) { return r.key === key; })[0]; }

  /* ---------- claim labels (D69): Published / Our simulation / Our assumption, linking research.html#<id> ---------- */
  function claim(id) { return R && (R.claims || []).filter(function (c) { return c.id === id; })[0]; }
  function basisLabel(basis) {
    var L = (R && R.basis_labels) || {};
    return L[basis] || ({ published: "Published", simulation: "Our simulation", assumption: "Our assumption" })[basis];
  }
  function claimLink(id, text, fallbackBasis) {
    var c = claim(id);
    var basis = (c && c.basis) || fallbackBasis;
    var a = el("a", "ev-claim ev-claim--" + basis);
    a.href = "research.html#" + id;
    a.title = (c && c.claim) || "Where this comes from";
    a.appendChild(el("span", "ev-claim__basis", basisLabel(basis)));
    a.appendChild(document.createTextNode(" " + text));
    return a;
  }

  /* ---------- bindings in the static HTML ---------- */
  function bind(name, value) {
    var nodes = document.querySelectorAll('[data-bind="' + name + '"]');
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = value;
  }

  /* ---------- the range chart (main figure and small multiples share it) ----------
   * rows: [{label, sub, subClass, band:{min,max}, mid, ring, values:[Node], miss:bool, strong:bool}]
   * opts: {domain:[lo,hi], step, fmt, axis:bool, compact:bool}
   */
  function niceDomain(rows, step) {
    var lo = Infinity, hi = -Infinity;
    rows.forEach(function (r) {
      [r.band && r.band.min, r.band && r.band.max, r.mid, r.ring].forEach(function (v) {
        if (isNum(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
      });
    });
    if (!isFinite(lo)) return [0, 1];
    return [Math.floor(lo / step) * step, Math.ceil(hi / step) * step];
  }

  function rangeChart(host, rows, opts) {
    host.textContent = "";
    var step = opts.step || G.step;
    var dom = opts.domain || niceDomain(rows, step);
    var wrap = el("div", "ev-rc" + (opts.compact ? " ev-rc--compact" : ""));
    host.appendChild(wrap);
    var tracks = [];
    rows.forEach(function (r) {
      var line = el("div", "ev-rc__row" + (r.strong ? " ev-rc__row--strong" : ""));
      var lab = el("div", "ev-rc__label");
      lab.appendChild(el("span", "ev-rc__name", r.label));
      if (r.sub) lab.appendChild(el("span", "ev-rc__sub" + (r.subClass ? " " + r.subClass : ""), r.sub));
      line.appendChild(lab);
      var tr = el("div", "ev-rc__track");
      line.appendChild(tr);
      tracks.push({ host: tr, row: r });
      if (!opts.compact || (r.values && r.values.length)) {
        var vals = el("div", "ev-rc__values");
        (r.values || []).forEach(function (v) { vals.appendChild(v); });
        line.appendChild(vals);
      }
      wrap.appendChild(line);
    });
    var axisHost = null;
    if (opts.axis !== false) {
      var axl = el("div", "ev-rc__row ev-rc__row--axis");
      axl.appendChild(el("div", "ev-rc__label"));
      axisHost = el("div", "ev-rc__track");
      axl.appendChild(axisHost);
      if (!opts.compact) axl.appendChild(el("div", "ev-rc__values"));
      wrap.appendChild(axl);
    }

    function draw() {
      tracks.forEach(function (t) { drawTrack(t.host, t.row, dom, opts); });
      if (axisHost) drawAxis(axisHost, dom, step, opts.fmt || pct);
    }
    draw();
    return draw;
  }

  function scaleOf(width, dom) {
    var pad = G.ring + 2;
    return function (v) { return pad + (v - dom[0]) / (dom[1] - dom[0]) * (width - 2 * pad); };
  }

  function drawTrack(host, r, dom, opts) {
    host.textContent = "";
    var w = host.clientWidth || host.getBoundingClientRect().width;
    var h = opts.compact ? G.track * G.compact : G.track;
    if (!w) return;
    var x = scaleOf(w, dom), cy = h / 2;
    var s = svg("svg", { width: w, height: h, viewBox: "0 0 " + w + " " + h, "aria-hidden": "true" });
    if (r.band && isNum(r.band.min) && isNum(r.band.max)) {
      var x0 = x(r.band.min), x1 = x(r.band.max);
      s.appendChild(svg("line", { "class": "ev-range", x1: x0, x2: x1, y1: cy, y2: cy }));
      s.appendChild(svg("line", { "class": "ev-range", x1: x0, x2: x0, y1: cy - G.tick, y2: cy + G.tick }));
      s.appendChild(svg("line", { "class": "ev-range", x1: x1, x2: x1, y1: cy - G.tick, y2: cy + G.tick }));
    }
    if (r.miss && isNum(r.ring) && isNum(r.mid)) {
      s.appendChild(svg("line", { "class": "ev-miss", x1: x(r.ring), x2: x(r.mid), y1: cy, y2: cy }));
    }
    if (isNum(r.ring)) s.appendChild(svg("circle", { "class": "ev-ring", cx: x(r.ring), cy: cy, r: opts.compact ? G.ring * G.compact : G.ring }));
    if (isNum(r.mid)) s.appendChild(svg("circle", { "class": r.midClass || "ev-dot", cx: x(r.mid), cy: cy, r: opts.compact ? G.dot * G.compact : G.dot }));
    host.appendChild(s);
  }

  function drawAxis(host, dom, step, fmt) {
    host.textContent = "";
    var w = host.clientWidth || host.getBoundingClientRect().width;
    if (!w) return;
    var h = G.axis;
    var x = scaleOf(w, dom);
    var s = svg("svg", { width: w, height: h, viewBox: "0 0 " + w + " " + h, "aria-hidden": "true" });
    s.appendChild(svg("line", { "class": "ev-axis", x1: x(dom[0]), x2: x(dom[1]), y1: 1, y2: 1 }));
    var n = Math.round((dom[1] - dom[0]) / step);
    for (var i = 0; i <= n; i++) {
      var v = dom[0] + i * step, xv = x(v);
      s.appendChild(svg("line", { "class": "ev-axis", x1: xv, x2: xv, y1: 1, y2: 1 + G.tick }));
      var t = svg("text", { "class": "ev-axis-label", x: xv, y: h - 2, "text-anchor": "middle" });
      t.textContent = fmt(v);
      s.appendChild(t);
    }
    host.appendChild(s);
  }

  /* ---------- top: headline and main chart ---------- */
  var redraws = [];

  function top() {
    var obs = rowOf("observed"), fast = rowOf("faster_pet"), auth = rowOf("authors"), opt = rowOf("optimiser_no_equipment");
    bind("today_best", pct(obs && obs.best_fit));
    bind("opt_best", pct(opt && opt.best_fit));
    bind("opt_range", range(opt && opt.band));
    bind("n_settings", isNum(E.n_settings) ? String(E.n_settings) : "pending");
    bind("target_days", isNum(E.target_days) ? String(E.target_days) : "pending");
    bind("published_patients", isNum(E.published_patients) ? String(E.published_patients) : "pending");
    bind("beats_scanner", E.optimiser && isNum(E.optimiser.beats_scanner_alone) ? String(E.optimiser.beats_scanner_alone) : "pending");

    function values(r, pubId, simId) {
      var out = [];
      if (pubId && r && isNum(r.published)) out.push(claimLink(pubId, pct(r.published), "published"));
      else out.push(el("span", "ev-claim ev-claim--none", "not published"));
      out.push(claimLink(simId, pct(r && r.best_fit) + " (" + range(r && r.band) + ")", "simulation"));
      return out;
    }
    var rows = [
      { label: "Today's pathway", sub: "fitted to the published value", band: obs && obs.band, mid: obs && obs.best_fit,
        ring: obs && obs.published, midClass: "ev-dot ev-dot--today",
        values: values(obs, "pub-stokstad-observed-40", "sim-no-fitted-observed") },
      { label: "Faster scanner alone", sub: "predicted · we over-predict", subClass: "ev-rc__sub--miss", band: fast && fast.band,
        mid: fast && fast.best_fit, ring: fast && fast.published, miss: true,
        values: values(fast, "pub-stokstad-faster-pet-48", "sim-no-faster-pet-overpredicted") },
      { label: "Authors' reordering", sub: "predicted · includes the faster scanner", band: auth && auth.band,
        mid: auth && auth.best_fit, ring: auth && auth.published,
        values: values(auth, "pub-stokstad-reordered-80", "sim-no-authors-band") },
      { label: "Our optimiser, no new equipment", sub: "simulated · found from today's pathway", band: opt && opt.band,
        mid: opt && opt.best_fit, strong: true,
        values: values(opt, null, "sim-no-optimiser-found-redesign") }
    ];
    var host = document.getElementById("ev-chart");
    redraws.push(rangeChart(host, rows, { step: G.step }));

    var rk = E.ranking;
    var rankHost = document.getElementById("ev-rank");
    if (rk && isNum(rk.holds_in) && isNum(rk.settings)) {
      rankHost.appendChild(claimLink("sim-no-ranking-holds",
        "authors' reordering > faster scanner > today in " + rk.holds_in + " of " + rk.settings + " settings", "simulation"));
    }
  }

  /* ---------- below DETAILS: robustness small multiples ---------- */
  function panel(host, heading, build, note, files) {
    var p = el("article", "ev-sm");
    p.appendChild(el("h4", "ev-sm__finding", heading));
    var body = el("div", "ev-sm__body");
    p.appendChild(body);
    host.appendChild(p);
    var redraw = build(body);
    if (redraw) redraws.push(redraw);
    if (note) p.appendChild(el("p", "ev-sm__note", note));
    if (files) {
      var f = el("p", "ev-sm__src label");
      f.appendChild(document.createTextNode("Source "));
      f.appendChild(el("code", null, files));
      p.appendChild(f);
    }
  }

  function stat(big, small) {
    var d = el("div", "ev-stat");
    d.appendChild(el("span", "num ev-stat__num", big));
    d.appendChild(el("span", "ev-stat__label", small));
    return d;
  }

  function multiples() {
    var host = document.getElementById("ev-multiples");
    host.textContent = "";
    var auth = rowOf("authors"), fast = rowOf("faster_pet");
    var n = E.n_settings;

    // 1. Ranking
    var rk = E.ranking;
    if (rk) panel(host, "The ranking holds in every setting that fits",
      function (b) {
        var g = el("div", "ev-stats");
        g.appendChild(stat(rk.holds_in + " of " + rk.settings, "fitting settings rank the authors' reordering above the faster scanner, and the scanner above today"));
        g.appendChild(stat(rk.holds_at_grid_points + " of " + rk.grid_points, "of every predicted grid point, fitting or not, keep the same order"));
        b.appendChild(g);
      },
      "Reordering adds " + (rk.authors_gain_pts || []).join(" to ") + " points over today in the model; the faster scanner adds " +
      (rk.scanner_gain_pts || []).join(" to ") + ". The same order as the paper's own figures, so a consistency check, not new evidence.",
      "docs/review_checks/norway_ranking.json");

    // 2. Grid extension
    var gr = E.grid;
    if (gr && auth) panel(host, "Widening the search turned a narrow match into a wide band",
      function (b) {
        return rangeChart(b, [
          { label: "First grid", sub: gr.first_accepted + " of " + gr.first_points + " settings fit", band: gr.first_authors, mid: gr.first_authors && gr.first_authors.median, ring: auth.published },
          { label: "Extended grid", sub: gr.extended_accepted + " of " + gr.extended_points + " settings fit", band: gr.extended_authors, mid: gr.extended_authors && gr.extended_authors.median, ring: auth.published, strong: true }
        ], { compact: true, step: G.step * 2 });
      },
      "Authors' reordering, median and range. The first grid's narrow band was its top corner. " +
      pct(gr.authors_in_published_ci) + " of the fitting settings fall inside the paper's interval for the reordering, " +
      pct(gr.scanner_in_published_ci) + " for the faster scanner.",
      "docs/review_checks/norway_grid_extension.json");

    // 3. Two targets act as one
    var t1 = E.targets_as_one;
    if (t1 && auth) panel(host, "The two targets act as one, so dropping either changes little",
      function (b) {
        var names = { both_targets: "Both targets", share_only: "Share only", median_only: "Median only" };
        return rangeChart(b, (t1.calibrated_on || []).map(function (c) {
          return { label: names[c.on] || c.on, sub: c.accepted + " settings fit", band: c.authors, mid: c.authors && c.authors.median, ring: auth.published, strong: c.on === "both_targets" };
        }), { compact: true, step: G.step * 2 });
      },
      "Authors' reordering, calibrated on one target or both. A higher share in time goes with a shorter median, so the data pin down a region of the five unknowns, not a point. Robust to dropping a target, but not extra evidence.",
      "docs/review_checks/norway_leave_one_out.json, norway_identifiability.json");

    // 4. Target noise
    var nz = E.noise;
    if (nz && auth && fast) panel(host, "Noise in a small published cohort moves the prediction about as much as its gap to the paper",
      function (b) {
        return rangeChart(b, [
          { label: "Faster scanner alone", sub: "mean of fitting settings", band: { min: nz.scanner.p5, max: nz.scanner.p95 }, mid: nz.scanner.mean, ring: fast.published },
          { label: "Authors' reordering", sub: "mean of fitting settings", band: { min: nz.authors.p5, max: nz.authors.p95 }, mid: nz.authors.mean, ring: auth.published, strong: true }
        ], { compact: true, step: G.step * 2 });
      },
      "The targets were redrawn " + nz.draws + " times within the sampling error of a cohort the size of the paper's, and the fit was redone each time. Bars: the middle nine in ten draws. The tolerance we used is about one standard error; the result does not depend on it.",
      "docs/review_checks/norway_noise.json");

    // 5. The scanner miss
    var sm = E.scanner_miss;
    if (sm && fast) panel(host, "We over-predict the faster scanner, and correlated delays do not fix it",
      function (b) {
        return rangeChart(b, (sm.runs || []).map(function (r) {
          return { label: r.rho ? "Shared slowness " + r.rho : "Independent waits", sub: r.accepted + " of " + r.grid_points + " settings fit",
            band: r.scanner, mid: r.scanner && r.scanner.median, ring: sm.published, miss: true };
        }), { compact: true, step: G.step * 2 });
      },
      "Faster scanner alone, median and range, with each patient's waits made more alike (a shared slowness). In our virtual hospital PET-CT lies on the critical path for most patients; in the real cohort other delays held patients back as well. Re-discussing incomplete cases at the board did not close the gap either.",
      "docs/review_checks/norway_mechanisms.json");

    // 6. Optimiser against today and the scanner
    var op = E.optimiser;
    if (op) panel(host, "With no new equipment the optimiser beats today everywhere, the scanner alone in most settings",
      function (b) {
        var g = el("div", "ev-stats");
        g.appendChild(stat(op.beats_observed + " of " + n, "settings where it beats today's pathway, by " + fixed1(op.gain_over_observed_pts.min) + " to " + fixed1(op.gain_over_observed_pts.max) + " points"));
        var s2 = stat(op.beats_scanner_alone + " of " + n, "settings where it beats the faster scanner alone");
        s2.appendChild(claimLink("sim-no-noequipment-vs-scanner", "· where this comes from", "simulation"));
        g.appendChild(s2);
        b.appendChild(g);
      },
      "It loses to the scanner mostly where PET-CT is ordered at the first visit and the wait after the board is short. Compared with the authors' reordering it is not a like-for-like pair: theirs includes the faster scanner, ours does not.",
      "docs/review_checks/norway_opt_summary.json");

    // 7. Ablation
    if (op && op.ablation) panel(host, "Every one of its four changes helps; ordering PET-CT early matters most",
      function (b) {
        var names = { a: "Board before sampling is done", b: "PET-CT always ordered early", c: "Exercise test always early", d: "Sampling planned at triage" };
        var subs = { a: "the authors' change", b: "the authors' change", c: "the authors' change", d: "not in the paper · needs clinical review" };
        var rows = op.ablation.map(function (a) {
          return { label: names[a.change], sub: subs[a.change], subClass: a.change === "d" ? "ev-rc__sub--miss" : "",
            band: { min: a.loss_min_pts, max: a.loss_max_pts }, mid: a.loss_median_pts, strong: a.change === "b" };
        });
        var hi = Math.max.apply(null, op.ablation.map(function (a) { return a.loss_max_pts || 0; }));
        var stepPts = G.step * HUNDRED / 2;
        return rangeChart(b, rows, { compact: true, domain: [0, Math.ceil(hi / stepPts) * stepPts], step: stepPts,
          fmt: function (v) { return String(Math.round(v)); } });
      },
      "Points lost when one change is removed: median (dot) and range over the fitting settings. Removing any change lowers the result in every setting. Three of the four are the authors' own timing changes.",
      "docs/review_checks/norway_opt_summary.json, norway_opt_bestfit.json");

    // 8. Structure check
    var st = E.structure;
    if (st && auth) panel(host, "A stricter reading of the paper moves our authors' pathway closer to it; a sensitivity result, not the headline",
      function (b) {
        function r(v, label, strong) {
          return { label: label, sub: v.in_published_ci + " of " + st.settings + " in the paper's interval",
            band: v.band, mid: v.band && v.band.median, ring: auth.published, strong: strong };
        }
        return rangeChart(b, [
          r(st.shipped, "As built (shown above)", true),
          r(st.pet_at_first_visit, "PET-CT at the first visit"),
          r(st.no_sample_wait, "Treatment not waiting for the sample"),
          r(st.stricter, "Both: the stricter reading")
        ], { compact: true, step: G.step * 2 });
      },
      "Authors' reordering, median and range, with each of the two differences we found between our reconstruction and the paper's text corrected. Each correction alone moves the result by more than its gap to the paper's figure, so that gap says little. The stricter reading was not refitted on today's pathway, and we read summaries of the paper, not its figures. The shipped scenario is unchanged; whether to adopt it is open for the team lead.",
      "docs/review_checks/norway_opt_structure.json");
  }

  /* ---------- the rest of DETAILS ---------- */
  function rest() {
    var L = S.ledger && (S.ledger.scenarios || []).filter(function (s) { return s.id === "stokstad"; })[0];
    if (L) {
      bind("ledger_blocks", String(L.blocks));
      bind("ledger_sourced", String(L.sourced));
      bind("ledger_assumption", String(L.assumption));
    } else {
      var li = document.getElementById("ev-ledger-line");
      if (li) li.parentNode.removeChild(li);
    }
    var a = el("a", "ev-research", "Research behind the numbers");
    a.href = "research.html";
    document.getElementById("ev-research-link").appendChild(a);
    var li2 = document.getElementById("ev-research-li");
    if (li2) {
      var t = li2.firstChild;
      var a2 = el("a", null, "Research behind the numbers");
      a2.href = "research.html";
      if (t && t.nodeType === Node.TEXT_NODE) t.nodeValue = t.nodeValue.replace("Research behind the numbers", "");
      li2.insertBefore(a2, li2.firstChild);
    }
  }

  /* ---------- start ---------- */
  function footerText() {
    var when = S.generated_at ? " at " + S.generated_at.replace("T", " ").replace("+00:00", " UTC") : "";
    return "Synthetic patients only · not clinically reviewed · numbers read from data/start_bundle.js" + when;
  }

  function init() {
    if (window.Site) {
      if (typeof window.Site.nav === "function") window.Site.nav("evidence");
      if (typeof window.Site.footer === "function") window.Site.footer(footerText());
    } else {
      var f = document.getElementById("ev-footer");
      if (f) f.textContent = footerText();
    }
    if (!E) {
      var msg = "The Norway numbers are pending: demo/data/start_bundle.js has no `evidence` field. Run python demo/export_start.py.";
      document.getElementById("ev-chart").textContent = msg;
      document.getElementById("ev-multiples").textContent = msg;
      return;
    }
    top();
    multiples();
    rest();
    var pending = null;
    window.addEventListener("resize", function () {
      if (pending) cancelAnimationFrame(pending);
      pending = requestAnimationFrame(function () { redraws.forEach(function (f) { f(); }); });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
