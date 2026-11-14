/* JEV node page. Data: window.JEV_DATA (data/jev_bundle.js, from demo/export_jev.py). No result is typed here:
   scores come from the bundle (recordings of the deployed model, labelled) or from a live call the viewer starts.
   Nothing is scored offline and nothing is invented: without an endpoint a card says so. */
(function () {
  "use strict";

  // ---- Configuration: the two values to fill in or change -------------------------------------------------------
  var HF_URL = "";   // Hugging Face page of the published model. Empty: the model card shows a placeholder.
  var HOSTED_API = "https://cancer123--birch-decision-1138-demo.us-east.modal.run/api/decision"; // team gateway (decision_api/HOSTED_API.md on main)
  // ------------------------------------------------------------------------------------------------------------------

  var D = window.JEV_DATA, M = D && D.model;
  var results = {};          // preset key -> {variant -> {status, response, error, at, endpoint, started}}
  var current = null;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function html(tag, cls, h) { var e = el(tag, cls); e.innerHTML = h; return e; }
  function sc(x) { return typeof x === "number" && isFinite(x) ? x.toFixed(2) : "?"; }
  function when(iso) { return iso ? String(iso).slice(0, 16).replace("T", " ") + " UTC" : "unknown time"; }
  function short(h) { return h ? String(h).slice(0, 10) : "?"; }
  function param(k) { var m = new RegExp("[?&]" + k + "=([^&#]*)").exec(location.search); return m ? decodeURIComponent(m[1]) : null; }

  if (!D) { document.getElementById("work").appendChild(html("div", "err", "No data: run <code>python demo/export_jev.py</code>, then reload.")); return; }

  // ================================================================================================ model card
  (function card() {
    var hf = document.getElementById("hf");
    if (HF_URL) hf.innerHTML = "<b>Published model</b><a href=\"" + esc(HF_URL) + "\" target=\"_blank\" rel=\"noopener\">Hugging Face model page</a><br>Weights and this card.";
    else hf.innerHTML = "<b>Hugging Face: placeholder</b>Not published yet. When it is, set <code>HF_URL</code> at the top of <code>demo/jev.js</code>.";

    var be = M.backend || {};
    document.getElementById("d-enc").textContent = "adapters (LoRA) in the last " + M.adapt_last_n + " blocks; the rest frozen";
    var steps = [
      "<b>Encoder.</b> A large open vision-language model (" + esc(be.model || "backbone not recorded") + "), frozen, with small trained adapters in its last " + M.adapt_last_n + " blocks. The context, and each answer together with its question, are encoded <b>separately</b>, each into one vector (taken at the last token of the final two blocks).",
      "<b>Scoring head.</b> A small transformer over the answers. Each answer vector is combined with the context vector, then the answers attend to each other. Each answer's score is its direct match with the context plus a correction computed from the whole answer set. A softmax over the offered answers gives one score per answer.",
      "<b>Why it can compare answers.</b> Because the answers see each other, an answer's score can depend on what else is offered. Because no answer position enters the head (ids and order never reach the text), reordering the answers only reorders the scores.",
      "<b>Several questions, one context.</b> A request may carry several questions; the context is encoded once and each question's answers are scored against it.",
      "<b>Optional reasoning step, off by default.</b> The same frozen backbone, with its original language head, may call read-only tools and write a short evidence summary. That text is added to the context, then the trained head scores the unchanged answers."
    ];
    var ol = document.getElementById("arch-text");
    document.getElementById("arch-short").innerHTML = "<b>Context and answers are encoded separately</b> by a frozen open model with small trained adapters. <b>A small head lets the answers look at each other</b>, then scores each one: direct match with the context plus a correction from the whole answer set. <b>Reordering the answers only reorders the scores</b>; adding or removing one can change the others.";
    steps.forEach(function (h) { ol.appendChild(html("li", null, h)); });

    var f = document.getElementById("facts"), S = M.sources || {};
    var more = el("details", "fold more-facts"); more.appendChild(el("summary", null, "Inputs, speed, code and sources")); var f2 = el("dl", "facts"); more.appendChild(f2);
    function fact(k, h, src, extra) { var t = extra ? f2 : f; t.appendChild(el("dt", null, k)); var d = html("dd", null, h); if (src) d.appendChild(el("span", "src", src)); t.appendChild(d); }
    fact("Checkpoint", be.step != null ? "<b>step " + esc(be.step) + "</b>, weights " + esc(short(be.checkpoint_sha256)) + "…, " + esc(be.quantization || "") + ". Served on one GPU." : "<span class=\"q\">not recorded</span>");
    fact("Inputs", "Text context (optionally up to a few images); one or more questions, each with " + "its allowed answers (natively up to " + esc(M.max_choices_native) + "; the public demo gateway takes up to " + esc(M.max_choices_gateway) + " answers and " + esc(M.max_questions_gateway) + " questions per call).", S.contract, true);
    fact("Output", "One score per answer, <b>summing to one over the offered answers</b>, the proposed answer and its margin. Every response is marked <code>requires_review</code>. No written rationale unless the reasoning step is on.");
    fact("Use", "Propose one of the allowed next steps at a pathway node for a person to accept or override; rank or flag records for human review. <b>Not for</b> diagnosis, acting without review, or reading a score as the probability of a disease.");
    var sn = M.sanity;
    fact("Training data", "<span class=\"q\">Not documented in this repository.</span> The owner's checks reuse public questions (" + esc(sn ? sn.datasets.join(", ") : "?") + ") and skin photos from the PAD-UFES-20 training split. Our simulator can export synthetic patient-record decisions for training (<code>docs/platform/jev-training-data.md</code>); whether this checkpoint saw them is an open question.");
    fact("Evaluation", sn ? "Smoke checks only: " + esc(sn.correct) + " of " + esc(sn.total) + " reused public questions (previous checkpoint " + esc(sn.previous_correct) + " of " + esc(sn.total) + "), not a benchmark. No clinical validation of any kind." : "<span class=\"q\">none recorded</span>");
    if (M.first_score_seconds) fact("Speed", "About " + esc(Math.round(M.first_score_seconds)) + " s for a warm call in the owner's check; a cold start takes minutes.", S.checks, true);
    fact("Code", "Encoder, head and routing: <code>decision_api/runtime/decision_model/</code> (on main). Adapter to the simulator: <code>jev/birch.py</code>.", S.prototype ? S.prototype : null, true);
    fact("Sources", "Architecture: " + esc(S.encoder) + "; " + esc(S.head) + "; " + esc(S.routing) + ". Reasoning step: " + esc(S.refinement) + ".", null, true);
    f.parentNode.appendChild(more);
  })();

  // ================================================================================================ endpoint
  var mode = document.getElementById("ep-mode"), url = document.getElementById("ep-url"), status = document.getElementById("ep-status");
  var MODES = [["recorded", "Recordings only (no network)"], ["hosted", "Team's hosted gateway (live, GPU)"], ["same", "This server's /api/decision (python demo/serve_jev.py)"], ["custom", "Another endpoint…"]];
  MODES.forEach(function (m) { var o = el("option", null, m[1]); o.value = m[0]; mode.appendChild(o); });
  (function initMode() {
    var a = param("api");
    if (a === "hosted" || a === "same" || a === "recorded") mode.value = a;
    else if (a) { mode.value = "custom"; url.value = a; }
    else mode.value = "recorded";
  })();
  function base() {
    if (mode.value === "hosted") return HOSTED_API;
    if (mode.value === "same") return location.protocol.indexOf("http") === 0 ? location.origin + "/api/decision" : null;
    if (mode.value === "custom") return url.value.trim().replace(/\/+$/, "") || null;
    return null;
  }
  function showStatus() {
    url.hidden = mode.value !== "custom";
    var b = base();
    if (mode.value === "recorded") status.innerHTML = "Only <b>recorded</b> outputs are shown. Pick an endpoint to score examples live; a live call starts only when you press a button.";
    else if (!b && mode.value === "same") status.innerHTML = "<b>Needs a server:</b> open this page through <code>python demo/serve_jev.py</code> (it serves this folder and the decision proxy on one origin).";
    else if (!b) status.innerHTML = "Enter the base URL of a decision API (ends in <code>/api/decision</code>).";
    else status.innerHTML = "Live calls go to <code>" + esc(b) + "</code>. Each press is one call; a cold model can take minutes. The label on every answer comes from the answer itself.";
  }
  mode.addEventListener("change", function () { showStatus(); if (current) render(current); });
  url.addEventListener("change", function () { showStatus(); if (current) render(current); });
  showStatus();

  // ================================================================================================ live calls
  function live(key, variant, route, body) {
    var b = base(); if (!b) return;
    results[key] = results[key] || {};
    var r = results[key][variant] = { status: "pending", started: Date.now(), endpoint: b + route };
    var p = current; render(p);
    var tick = setInterval(function () { if (current === p && r.status === "pending") { var s = document.getElementById("pend-" + key + "-" + variant); if (s) s.textContent = Math.round((Date.now() - r.started) / 1000) + " s"; } }, 1000);
    function done(ok, payload) {
      clearInterval(tick);
      r.status = ok ? "done" : "error"; r.at = new Date().toISOString();
      if (ok) r.response = payload; else r.error = payload;
      if (current === p) render(p);
    }
    function poll(statusUrl) {
      if (Date.now() - r.started > 660000) return done(false, "No answer after eleven minutes. The job may still finish on the server; it was not resubmitted.");
      setTimeout(function () {
        fetch(b + statusUrl).then(handle).catch(function (e) { done(false, "Polling failed: " + e.message); });
      }, 1000);
    }
    function handle(res) {
      return res.json().catch(function () { return {}; }).then(function (j) {
        if (res.status === 202 && j.status_url) return poll(j.status_url);
        if (!res.ok) return done(false, "HTTP " + res.status + ": " + (j.detail || res.statusText) + ". Nothing was substituted.");
        done(true, j);
      });
    }
    fetch(b + route, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(handle).catch(function (e) { done(false, "Could not reach " + b + route + " (" + e.message + "). Nothing was substituted."); });
  }

  // ================================================================================================ output pieces
  function provenance(dec, kind, extra) {
    var be = (dec && dec.backend) || {}, m = be.mode, cls, txt;
    if (m === "model") { cls = "model"; txt = (kind === "live" ? "Live call · " : "Recorded · ") + "deployed model, step " + be.step; }
    else if (m === "fixture") { cls = "notmodel"; txt = (kind === "live" ? "Live · " : "") + "scripted fixture, not the model"; }
    else if (m === "mock") { cls = "notmodel"; txt = (kind === "live" ? "Live · " : "") + "mock, not the model"; }
    else { cls = "notmodel"; txt = "Unknown backend (" + (m || "no mode") + "): not shown as model output"; }
    var box = el("div");
    box.appendChild(el("span", "prov " + cls, txt));
    var bits = [];
    if (extra) bits.push(extra);
    if (dec && dec.created_at) bits.push(when(dec.created_at));
    if (dec && typeof dec.latency_ms === "number") bits.push("scored in " + (dec.latency_ms / 1000).toFixed(1) + " s");
    if (dec && dec.id) bits.push("decision " + short(dec.id));
    box.appendChild(el("div", "provline", bits.join(" · ")));
    return box;
  }
  function question(dec, qid) { return dec && (dec.questions || []).filter(function (q) { return q.id === qid; })[0]; }
  function bars(choices, topId, cls, topLabel) {
    var wrap = el("div", "bars " + (cls || ""));
    var mx = Math.max.apply(null, choices.map(function (c) { return c.score; }).concat([1e-9]));
    choices.forEach(function (c) {
      var r = el("div", "bar" + (c.id === topId ? " best" : ""));
      var t = el("div", "bt"); var i = el("i"); i.style.width = Math.max(0, c.score / mx * 100) + "%";
      t.appendChild(i); t.appendChild(document.createTextNode(c.text + (c.id === topId ? "  · " + (topLabel || "proposed") : "")));
      r.appendChild(t); r.appendChild(el("div", "bv", sc(c.score))); wrap.appendChild(r);
    });
    return wrap;
  }
  function scoreBlock(dec, q, kind, extra) {
    var box = el("div"), qq = question(dec, q.id);
    box.appendChild(provenance(dec, kind, extra));
    if (!qq) box.appendChild(el("div", "err", "The answer has no scores for this question."));
    else box.appendChild(bars(qq.choices, qq.proposed_action_id));
    return box;
  }
  function empty(msg) { return html("div", "empty", msg); }
  function runButton(p, variant, label, route, body) {
    var b = base(), btn = el("button", "btn main", label || ("Score live" + (b ? "" : " (pick an endpoint above)")));
    if (!b) { btn.disabled = true; btn.title = "Choose an endpoint in the bar above"; }
    var r = results[p.key] && results[p.key][variant];
    if (r && r.status === "pending") { btn.disabled = true; btn.textContent = "Waiting for the model…"; }
    btn.addEventListener("click", function () { live(p.key, variant, route || p.route, body || p.request); });
    return btn;
  }
  function liveState(p, variant) {
    var r = results[p.key] && results[p.key][variant];
    if (!r) return null;
    if (r.status === "pending") return html("div", "empty", "<b>Waiting</b> for " + esc(r.endpoint) + " · <span id=\"pend-" + esc(p.key) + "-" + esc(variant) + "\">0 s</span>. A cold model can take several minutes.");
    if (r.status === "error") return html("div", "err", esc(r.error));
    return null;
  }
  function liveDecision(p, variant) {
    var r = results[p.key] && results[p.key][variant];
    if (!r || r.status !== "done") return null;
    return r.response.decision || r.response;
  }

  // ================================================================================================ cards
  var P = D.presets.slice();
  P.push({ key: "own", tag: "Your own", title: "Write a context and answers", own: true });
  var nav = document.getElementById("presets");
  P.forEach(function (p) {
    var b = el("button", "preset"); b.type = "button"; b.setAttribute("role", "tab"); b.id = "tab-" + p.key;
    b.appendChild(el("span", "tag", p.tag)); b.appendChild(el("span", "tt", p.title));
    var has = p.recorded || p.recorded_preset, st = el("span", "st" + (has ? " has" : ""), p.own ? "needs a live endpoint" : has ? "recorded model output" : p.gp ? "simulator node · live only" : "live only");
    b.appendChild(st);
    b.addEventListener("click", function () { select(p.key, true); });
    nav.appendChild(b);
  });
  function select(key, push) {
    var p = P.filter(function (x) { return x.key === key; })[0] || P[0];
    P.forEach(function (x) { document.getElementById("tab-" + x.key).setAttribute("aria-selected", x === p ? "true" : "false"); });
    current = p; render(p);
    if (push && history.replaceState) history.replaceState(null, "", "#" + p.key);
  }

  function colOf(title, cls) { var c = el("div", "col " + (cls || "")); c.appendChild(el("h3", null, title)); return c; }
  function questionsCol(p) {
    var c = colOf("Question and allowed answers");
    p.questions.forEach(function (q, i) {
      if (p.questions.length > 1) c.appendChild(el("div", "lab", "Question " + (i + 1)));
      c.appendChild(el("div", "qtext", q.text));
      var ul = el("ol", "choices"); q.choices.forEach(function (ch) { ul.appendChild(el("li", null, ch.text)); }); c.appendChild(ul);
    });
    if (p.gp) {
      var d = el("details", "fold"); d.appendChild(el("summary", null, "All " + p.gp.offered_all.length + " actions the simulator offers here"));
      var ul = el("ul"); p.gp.offered_all.forEach(function (a) { ul.appendChild(el("li", null, a.text)); }); d.appendChild(ul); c.appendChild(d);
      c.appendChild(html("div", "note", "The public gateway takes at most " + esc(M.max_choices_gateway) + " answers per question (the model itself " + esc(M.max_choices_native) + "), so this card offers " + p.gp.offered.length + ": every action the placeholder table weighs at this visit, plus common next steps."));
    }
    c.appendChild(html("div", "src-line", "Text: " + esc(p.source_of_text)));
    return c;
  }
  function contextCol(p) {
    var c = colOf("Context the model reads");
    if (p.gp) {
      var g = p.gp;
      c.appendChild(el("div", "ctx", g.case_context));
      c.appendChild(el("div", "lab", "Record so far (" + g.evidence.length + " entries, oldest first)"));
      var ul = el("ul", "ev");
      g.evidence.forEach(function (e) { var li = el("li"); li.innerHTML = "<b>" + esc(e.source_id.split(":").slice(2).join(":") || "entry") + "</b> " + esc(e.text); ul.appendChild(li); });
      c.appendChild(ul);
      var row = el("div", "btnrow"); var a = el("a", "btn", "Open this patient in the encounter loop"); a.href = g.link; row.appendChild(a); c.appendChild(row);
      c.appendChild(html("div", "src-line", "Patient " + esc(g.patient_id) + " of the encounter-loop run (" + esc(g.scenario) + ", run of " + esc(when(g.encounter_generated_at)) + "), GP visit on day " + esc(g.t_days) + ". Built by <code>jev.birch.BirchPolicy.request_for</code> and <code>map_request</code>, the code the simulator calls at this node."));
      var d = el("details", "fold"); d.appendChild(el("summary", null, "The exact text the model receives"));
      d.appendChild(el("div", "ctx", g.model_text)); c.appendChild(d);
      var h = el("details", "hidden-side"); h.appendChild(el("summary", null, "Hidden side (teaching view; the model never sees it)"));
      h.appendChild(el("div", null, "In the simulation this patient has " + String(g.teach.primary).replace(/_/g, " ") + ". What happened: " + g.teach.example + ". The record above is all a clinician, and the model, would have."));
      c.appendChild(h);
      return c;
    }
    if (p.own) return c;
    c.appendChild(el("div", "ctx", p.context_display));
    if (p.key === "reasoning" && p.recorded) {
      var d2 = el("details", "fold"); d2.appendChild(el("summary", null, "The context after the reasoning step (recorded)"));
      d2.appendChild(el("div", "ctx", p.recorded.with_refinement.refinement.context)); c.appendChild(d2);
    }
    return c;
  }
  function limits(p) {
    var box = el("div", "limits"); box.appendChild(html("b", null, "Limits of this example"));
    var ul = el("ul"); (p.limits || []).forEach(function (t) { ul.appendChild(el("li", null, t)); }); box.appendChild(ul);
    return box;
  }

  function outputCol(p) {
    var c = colOf("Model output", "out");
    var q = p.questions[0];
    var ld = liveDecision(p, "main"), st = liveState(p, "main");
    if (ld) c.appendChild(scoreBlock(ld, q, "live", results[p.key].main.endpoint));
    else if (p.recorded_preset) c.appendChild(scoreBlock(p.recorded_preset.response.decision || p.recorded_preset.response, q, "recorded", "recorded with export_jev.py --record on " + when(p.recorded_preset.recorded_at)));
    else c.appendChild(empty("<b>No recorded model output for this example yet.</b> Score it live with an endpoint (bar above). Nothing on this page is scored offline, and no score is made up."));
    if (st) c.appendChild(st);
    c.appendChild(runButton(p, "main"));
    var dec = ld || (p.recorded_preset && (p.recorded_preset.response.decision || p.recorded_preset.response));
    var qq = dec && dec.backend && dec.backend.mode === "model" && question(dec, q.id);
    if (qq && p.key === "screening") {
      var f = qq.choices.filter(function (x) { return x.id === "flag"; })[0];
      if (f) c.appendChild(html("div", "headline", "<span class=\"num\">" + sc(f.score) + "</span><span class=\"what\">score on <b>Flag</b>, relative to the three answers. A register would be sorted by it and the top records read by a person; it is not the probability of cancer.</span>"));
    }
    if (qq && p.key === "triage") {
      var top = qq.choices.filter(function (x) { return x.id === qq.proposed_action_id; })[0];
      if (top) c.appendChild(html("div", "headline", "<span class=\"num\">" + esc(top.id.replace("_", " ")) + "</span><span class=\"what\">proposed class. For a queue, sort by the score on <b>urgent</b>; send <b>human review</b> to a person.</span>"));
    }
    if (p.gp) {
      var t = p.gp.table, ids = Object.keys(t.probs).sort(function (a, b) { return t.probs[b] - t.probs[a]; });
      var lab = {}; p.gp.offered_all.forEach(function (a) { lab[a.id] = a.text; });
      c.appendChild(el("div", "lab", "What the simulator uses here today"));
      c.appendChild(el("span", "prov table", "Placeholder decision table, not the model"));
      c.appendChild(bars(ids.map(function (k) { return { id: k, text: lab[k] || k, score: t.probs[k] }; }), t.drawn, "tablebars", "drawn in the run"));
      c.appendChild(html("div", "note", "The table is a hand-written rule (<code>" + esc(t.note) + "</code>); the run drew <b>" + esc(lab[t.drawn] || t.drawn) + "</b>. The model is meant to replace this table at every GP decision, with the same request as on this card."));
    }
    return c;
  }

  function reasoningOut(p) {
    var c = colOf("Model output: reasoning trace, then scores", "out"), q = p.questions[0];
    var ld = liveDecision(p, "main"), lr = ld && results[p.key].main.response.refinement;
    var rec = p.recorded.with_refinement, ref = lr || rec.refinement, dec = ld || rec.decision;
    if (ld) c.appendChild(provenance(ld, "live", results[p.key].main.endpoint));
    else c.appendChild(provenance(rec.decision, "recorded", "the owner's recording (" + (p.recorded.source ? "decision_api/web, copied from " + p.recorded.source.commit : "decision_api/web") + ")"));
    var st = liveState(p, "main"); if (st) c.appendChild(st);
    var ul = el("ol", "trace");
    (ref.trace || []).forEach(function (t) {
      var li = el("li" , t.tool ? null : "gen");
      if (t.tool) {
        var args = Object.keys(t.arguments || {}).map(function (k) { return k + "=" + t.arguments[k]; }).join(", ");
        var ents = (t.response && t.response.entries) || [];
        li.innerHTML = "<span class=\"k\">Round " + esc(t.round) + " · tool call</span><code>" + esc(t.tool) + "(" + esc(args) + ")</code> returned " + ents.length + " record entries, read only and visible at this step:" +
          ents.map(function (e) { return "<br>· <b>" + esc(e.source_id) + "</b> " + esc(e.text); }).join("");
      } else if (t.summary) {
        li.innerHTML = "<span class=\"k\">Round " + esc(t.round) + " · evidence summary</span><span class=\"gen-label\">generated text, may contain errors; not a source record</span><br>" + esc(t.summary);
      } else li.innerHTML = "<span class=\"k\">Round " + esc(t.round) + "</span>" + esc(t.status || "");
      ul.appendChild(li);
    });
    c.appendChild(ul);
    c.appendChild(html("div", "note", "Budget used: " + esc(ref.tokens_used) + " generated tokens, " + esc(ref.tool_calls_used) + " tool call, " + esc(ref.rounds_used) + " rounds; stop: " + esc(ref.stop_reason || "summary written") + "."));
    var qa = question(dec, q.id), qb = question(p.recorded.without_refinement, q.id);
    c.appendChild(el("div", "lab", "Scores after the reasoning step"));
    if (qa) c.appendChild(bars(qa.choices, qa.proposed_action_id));
    if (qb) {
      c.appendChild(el("div", "lab", "Same question without it (recorded separately, same checkpoint)"));
      c.appendChild(bars(qb.choices, qb.proposed_action_id));
      if (qa) {
        var a = qa.choices.filter(function (x) { return x.id === qa.proposed_action_id; })[0], b = qb.choices.filter(function (x) { return x.id === qa.proposed_action_id; })[0];
        if (a && b) c.appendChild(html("div", "note", "The added text moved the proposed answer's score by <b>" + (a.score - b.score >= 0 ? "+" : "") + (a.score - b.score).toFixed(3) + "</b>. The summary is evidence for the scorer, not its decision: read the summary and the scores together."));
      }
    }
    c.appendChild(runButton(p, "main", base() ? "Rerun live with reasoning" : null));
    return c;
  }

  // the comparison card: two questions, plus shuffled and reduced answer sets
  function variantsOf(p) {
    var req = p.request;
    function mm(t) { var m = /([\d.]+)\s*mm/.exec(t); return m ? parseFloat(m[1]) : -Infinity; }
    var rev = JSON.parse(JSON.stringify(req)); rev.questions.forEach(function (q) { q.choices.reverse(); }); rev.case_id += "-reversed";
    var drop = JSON.parse(JSON.stringify(req));
    var big = req.questions[0].choices.slice().sort(function (a, b) { return mm(b.text) - mm(a.text); })[0];
    drop.questions.forEach(function (q) { q.choices = q.choices.filter(function (c) { return c.id !== big.id; }); }); drop.case_id += "-without-largest";
    return { main: { label: "As listed", req: req }, reversed: { label: "Same answers, reversed order", req: rev }, dropped: { label: "Largest answer removed (" + big.text + ")", req: drop } };
  }
  function compareOut(p) {
    var c = colOf("Model output: both questions", "out"), V = variantsOf(p);
    c.appendChild(html("div", "mini", "<div class=\"dp\"><b>Scoring answers one at a time</b>Each answer only meets the context. It can learn 'larger is better', but it cannot know that 11 mm is the second largest without seeing 14 mm.</div>" +
      "<div class=\"jv\"><b>JEV's head</b>Answers attend to each other before scoring, so 'second largest' is a question it can represent. Whether this checkpoint gets it right is shown only by a call.</div>"));
    var any = false;
    Object.keys(V).forEach(function (vk) {
      var v = V[vk], ld = liveDecision(p, vk), st = liveState(p, vk);
      var rec = vk === "main" && p.recorded_preset && (p.recorded_preset.response.decision || p.recorded_preset.response);
      var dec = ld || rec;
      if (!dec && !st) return;
      any = true;
      c.appendChild(el("div", "lab", v.label));
      if (st) { c.appendChild(st); return; }
      c.appendChild(provenance(dec, ld ? "live" : "recorded", ld ? results[p.key][vk].endpoint : "recorded with export_jev.py --record"));
      var pair = el("div", "qpair");
      v.req.questions.forEach(function (q) {
        var qq = question(dec, q.id), cell = el("div");
        cell.appendChild(el("div", "qtext", q.text));
        if (qq) cell.appendChild(bars(qq.choices, qq.proposed_action_id)); else cell.appendChild(el("div", "err", "no scores for this question"));
        pair.appendChild(cell);
      });
      c.appendChild(pair);
    });
    if (!any) c.appendChild(empty("<b>No recorded model output for this example yet.</b> Score it live (bar above). Then reverse the order, or remove the largest answer, and see what moves."));
    // symmetry check once both orders have answers
    var a = liveDecision(p, "main"), b = liveDecision(p, "reversed");
    if (a && b && a.backend && b.backend && a.backend.mode === "model" && b.backend.mode === "model") {
      var diff = 0;
      p.request.questions.forEach(function (q) {
        var qa = question(a, q.id), qb = question(b, q.id); if (!qa || !qb) return;
        qa.choices.forEach(function (x) { var y = qb.choices.filter(function (z) { return z.id === x.id; })[0]; if (y) diff = Math.max(diff, Math.abs(x.score - y.score)); });
      });
      c.appendChild(html("div", "note", "<b>Order check:</b> with the answers reversed, each answer kept its score to within " + diff.toFixed(4) + " (largest change over both questions). The scores follow the answers, not their positions."));
    }
    var row = el("div", "btnrow");
    row.appendChild(runButton(p, "main", base() ? "Score live" : null, "/score", V.main.req));
    row.appendChild(runButton(p, "reversed", base() ? "Reverse the order" : "Reverse the order (needs an endpoint)", "/score", V.reversed.req));
    row.appendChild(runButton(p, "dropped", base() ? "Remove the largest" : "Remove the largest (needs an endpoint)", "/score", V.dropped.req));
    c.appendChild(row);
    c.appendChild(html("div", "note", "A small numpy prototype of this head beat parameter-matched one-at-a-time scorers on a synthetic task whose right answer depends on the other options (<code>decision_model/README.md</code>). That is the prototype, not this checkpoint."));
    return c;
  }

  // free text
  function ownCols(p) {
    var cols = el("div", "cols");
    var maxA = M.max_choices_gateway;
    var c1 = colOf("Context the model reads"), c2 = colOf("Question and allowed answers"), c3 = colOf("Model output", "out");
    var form = el("div", "own");
    var ta = el("textarea"); ta.id = "own-ctx"; ta.placeholder = "Visible information only: symptoms, the record so far, results. Synthetic text, no real patient data."; ta.value = p.ctx || "";
    form.appendChild(ta); c1.appendChild(form);
    var f2 = el("div", "own ans");
    var qi = el("input"); qi.type = "text"; qi.id = "own-q"; qi.placeholder = "Question, e.g. What should the GP do next?"; qi.value = p.q || "";
    var ai = el("textarea"); ai.id = "own-a"; ai.placeholder = "One answer per line (two to " + maxA + ")"; ai.value = p.a || ""; ai.style.minHeight = "110px";
    var lbl = el("label", "note"); var cb = el("input"); cb.type = "checkbox"; cb.id = "own-ref"; cb.checked = !!p.ref;
    lbl.appendChild(cb); lbl.appendChild(document.createTextNode(" Reasoning step first (text only; tools are bound to the owner's sample record, so none for your own text)"));
    f2.appendChild(qi); f2.appendChild(ai); f2.appendChild(lbl); c2.appendChild(f2);
    [ta, qi, ai, cb].forEach(function (x) { x.addEventListener("input", function () { p.ctx = ta.value; p.q = qi.value; p.a = ai.value; p.ref = cb.checked; }); });
    var ld = liveDecision(p, "main"), st = liveState(p, "main");
    if (ld) {
      var qd = (ld.questions || [])[0];
      c3.appendChild(provenance(ld, "live", results[p.key].main.endpoint));
      if (qd) c3.appendChild(bars(qd.choices, qd.proposed_action_id));
      var rf = results[p.key].main.response.refinement;
      if (rf && rf.context) { var d = el("details", "fold"); d.appendChild(el("summary", null, "Context after the reasoning step")); d.appendChild(el("div", "ctx", rf.context)); c3.appendChild(d); }
    } else if (!st) c3.appendChild(empty(base() ? "Write a context, a question and the answers, then score." : "<b>Free text needs a live endpoint.</b> Pick one in the bar above. Nothing is scored offline, and nothing is made up."));
    if (st) c3.appendChild(st);
    var btn = el("button", "btn main", "Score live"); if (!base()) btn.disabled = true;
    var msg = el("div", "note");
    btn.addEventListener("click", function () {
      p.ctx = ta.value; p.q = qi.value; p.a = ai.value; p.ref = cb.checked;
      var answers = ai.value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
      if (!ta.value.trim() || !qi.value.trim()) { msg.textContent = "Write a context and a question."; return; }
      if (answers.length < 2 || answers.length > maxA) { msg.textContent = "Give between two and " + maxA + " answers, one per line."; return; }
      var req = { context: ta.value.trim(), case_id: "demo-jev-own", questions: [{ id: "q", text: qi.value.trim(), choices: answers.map(function (t, i) { return { id: "a" + (i + 1), text: t }; }) }] };
      if (cb.checked) live(p.key, "main", "/reason", { request: req, reasoning: { enabled: true, max_tokens: 128, max_rounds: 3, max_tool_calls: 0 } });
      else live(p.key, "main", "/score", req);
    });
    c3.appendChild(btn); c3.appendChild(msg);
    cols.appendChild(c1); cols.appendChild(c2); cols.appendChild(c3);
    return cols;
  }

  function render(p) {
    var w = document.getElementById("work"); w.textContent = "";
    w.appendChild(el("span", "eyebrow", p.tag));
    w.appendChild(el("h2", null, p.title));
    if (p.own) {
      w.appendChild(el("p", "pitch", "Your context and answers, scored by a live endpoint. Use synthetic text only. Scores are relative to the answers you give: add or remove one and the others can change."));
      w.appendChild(ownCols(p));
      return;
    }
    w.appendChild(el("p", "pitch", p.pitch));
    var cols = el("div", "cols");
    cols.appendChild(contextCol(p));
    cols.appendChild(questionsCol(p));
    cols.appendChild(p.key === "reasoning" && p.recorded ? reasoningOut(p) : p.key === "compare" ? compareOut(p) : outputCol(p));
    w.appendChild(cols);
    w.appendChild(limits(p));
  }

  // ================================================================================================ footer, start
  var src = D.recorded_source && D.recorded_source.copied_from;
  document.getElementById("honest").innerHTML = "<b>Read these with the scores.</b> <span class=\"v\">Scores are relative</span>: they sum to one over the answers offered and change when the answer list changes; they are not probabilities of disease. <span class=\"v\">Synthetic data</span>: every patient and record is made up; the examples written for this page have not been read by a clinician. <span class=\"v\">A person decides</span>: every answer is a proposal for review. " +
    "Recorded outputs: the model owner's recordings" + (src ? " (copied from " + esc(src.ref) + " at " + esc(src.commit) + ")" : "") + "; page data built " + esc(when(D.generated_at)) + " by <code>demo/export_jev.py</code>.";
  var start = (location.hash || "").slice(1);
  var def = P.filter(function (x) { return x.default; })[0] || P[0];
  select(P.some(function (x) { return x.key === start; }) ? start : def.key, false);
})();
