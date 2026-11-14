/* Simulator page (demo/flow.html, lane L1 of the UI revamp). No build step; data comes from data/flow_bundle.js
   (window.FLOW_DATA) and data/start_bundle.js (window.START_DATA). Format of one flow document:
   docs/platform/flow-format.md (flow/1). Everything shown is simulated. Every number is read from the bundles.
   Spec: docs/plan/ui-revamp/04-sim-view.md (default view, Optimise flip, queue colours, speed, Details menu; D67). */
(function () {
'use strict';
const D = window.FLOW_DATA;
const $ = (s, r) => (r || document).querySelector(s);
/* colours: theme tokens via Site.tokens() (demo/site.js), read at start and on theme change. No colour literals. */
let C = {};
function readTokens() {
  let t = window.Site && Site.tokens ? Site.tokens(true) : null;
  if (!t) {
    const cs = getComputedStyle(document.documentElement);
    t = {};
    ['paper', 'card', 'inset', 'ink', 'ink-2', 'ink-3', 'faint', 'line', 'mustard', 'mustard-ink', 'mustard-tint', 'brick',
      'brick-tint', 'brown', 'carbon'].forEach(k => { t[k] = cs.getPropertyValue('--' + k).trim(); });
  }
  C = {paper: t.paper, card: t.card, inset: t.inset, ink: t.ink, ink2: t['ink-2'], ink3: t['ink-3'], faint: t.faint,
    line: t.line, mustard: t.mustard, mustardInk: t['mustard-ink'], mustardTint: t['mustard-tint'], brick: t.brick,
    brickTint: t['brick-tint'], brown: t.brown};
}
let NODE_W = 118, NODE_H = 30, SLOT = 126, LAYER_H = 70;
const MARGIN_X = 14, MARGIN_T = 40;
const fmt = n => n == null ? '–' : Math.round(n).toLocaleString('en-US');
const f1 = x => x == null ? '–' : (Math.round(x * 10) / 10).toFixed(1);
const pct = (x, d) => x == null ? '–' : (100 * x).toFixed(d == null ? 0 : d) + '%';
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const hexRgb = h => { const m = /^#?([0-9a-f]{6})$/i.exec(String(h).trim()); const v = m ? parseInt(m[1], 16) : 0; return [v >> 16 & 255, v >> 8 & 255, v & 255]; };
const mixHex = (a, b, t) => 'rgb(' + hexRgb(a).map((v, i) => Math.round(v + (hexRgb(b)[i] - v) * t)).join(',') + ')';

/* Playback speeds in days per second (D61: default 2). ?speed= may add another value. */
const SPEEDS = [0.5, 1, 2, 4, 8];
/* Queue colouring (04-sim-view.md, D61): sampled dots that have waited more than WAIT_MIN days at a step, as a share
   of the sample, smoothed over SMOOTH_DAYS playback days, with hysteresis (leave a state at HYST of its threshold).
   Thresholds are fixed per scenario and shared by Today and After. Values chosen by eye: see handoff/L1-simulator.md. */
const QUEUE = {WAIT_MIN: 2, SMOOTH_DAYS: 3, HYST: 0.8, share: {finland: [0.04, 0.10], norway: [0.04, 0.10]}};
/* Groups drawn as dashed boxes (D67) and the return path, by node id. Ids missing from a variant are skipped. */
const GROUPS = {
  finland: [
    {label: 'Hospital', pad: 26, ids: ['triage', 'spec_visit', 'ct', 'sample_choice', 'bronch', 'ttnb', 'diagnosis', 'pet', 'mdt', 'book_treat']},
    {label: 'Tests', pad: 12, ids: ['ct', 'sample_choice', 'bronch', 'ttnb', 'diagnosis', 'pet']}],
  norway: [
    {label: 'Tests', pad: 14, ids: ['sample_plan', 'no_sampling', 'bronch1', 'after_bronch', 'ttnb', 'bronch2', 'no_more', 'ct_redo', 'pet_timing',
      'pet_on_time', 'pet_triage', 'pet_early_route', 'pet_early', 'pet_late', 'workup', 'ex_timing', 'ex_early', 'ex_late']}]};
const isReturnNode = n => n && /^re-?present/i.test(n.short || '');
/* claim ids on the research page (D69) */
const CLAIM = {finland: {share: 'sim-fi-reorder-headline', median: 'sim-fi-median-days', missed: 'sim-fi-guardrails'},
  norway: {share: 'sim-no-noequipment-vs-scanner', today: 'sim-no-fitted-observed', median: 'sim-no-optimiser-found-redesign'}};
const DASH_KEY = {norway: 'stokstad', finland: 'finland_lung'};   // index.html#<key>/<screen>

const LAYERS = [['flow', 'patients (default)', 'Dots are patients; piles are patients waiting.'],
  ['time', 'waiting time per step', 'Mustard fill: median days a patient waits at the step (whole run).'],
  ['queues', 'queue over the year', 'The line in each step is the number waiting there over the simulated calendar year, not the replay clock.'],
  ['decisions', 'decisions', 'Rounded steps are choices; they show the share of patients who got each option.']];
const S = {sid: null, keys: [null, null], layer: 'flow', t: 0, playing: true, speed: 2, opt: false, side: 0, split: false,
  deltas: false, dense: false, tall: false, sel: null, hl: null, pin: null, panes: [], H: 100, big: false, drawer: null, touched: false};
/* ------------------------------------------------------------------ layout (union of both flowcharts) */
function layoutUnion(flows) {
  const nodes = new Map(), edges = new Map();
  flows.forEach(F => {
    F.graph.nodes.forEach(n => { if (!nodes.has(n.id)) nodes.set(n.id, {id: n.id, kind: n.kind}); });
    F.graph.edges.forEach(e => { if (!edges.has(e.id)) edges.set(e.id, {id: e.id, source: e.source, target: e.target}); });
  });
  const preds = {}, succs = {};
  nodes.forEach((_, id) => { preds[id] = []; succs[id] = []; });
  edges.forEach(e => { preds[e.target].push(e.source); succs[e.source].push(e.target); });
  const layer = {};
  const depth = id => layer[id] != null ? layer[id] : (layer[id] = (layer[id] = 0, 1 + Math.max(-1, ...preds[id].map(depth))));
  nodes.forEach((_, id) => depth(id));
  const L = [];
  nodes.forEach((_, id) => { (L[layer[id]] = L[layer[id]] || []).push(id); });
  const frac = {};
  const setFrac = () => L.forEach(arr => arr.forEach((id, i) => { frac[id] = (i + .5) / arr.length; }));
  setFrac();
  for (let it = 0; it < 10; it++) {
    const down = it % 2 === 0;
    const order = down ? L.map((_, i) => i) : L.map((_, i) => L.length - 1 - i);
    order.forEach(li => {
      const nb = down ? preds : succs;
      const key = id => { const a = nb[id]; return a.length ? a.reduce((s, x) => s + frac[x], 0) / a.length : frac[id]; };
      L[li].sort((a, b) => key(a) - key(b) || frac[a] - frac[b]);
      L[li].forEach((id, i) => { frac[id] = (i + .5) / L[li].length; });
    });
  }
  const dense = L.length > 12;
  NODE_H = S.tall ? (dense ? 38 : 42) : 30; LAYER_H = S.tall ? (dense ? 56 : 76) : (dense ? 50 : 70);
  const maxk = Math.max(...L.map(a => a.length));
  const W0 = Math.max(maxk, 4) * SLOT;
  const x = {};
  L.forEach(arr => arr.forEach((id, i) => { x[id] = (i + .5) * W0 / arr.length; }));
  for (let it = 0; it < 40; it++) {
    L.forEach(arr => {
      arr.forEach(id => {
        const nb = preds[id].concat(succs[id]);
        if (nb.length) x[id] = .45 * x[id] + .55 * nb.reduce((s, q) => s + x[q], 0) / nb.length;
      });
      for (let i = 1; i < arr.length; i++) x[arr[i]] = Math.max(x[arr[i]], x[arr[i - 1]] + SLOT);
    });
  }
  let lo = Infinity, hi = -Infinity;
  nodes.forEach((_, id) => { lo = Math.min(lo, x[id]); hi = Math.max(hi, x[id]); });
  const pos = {};
  nodes.forEach((_, id) => { pos[id] = {x: x[id] - lo + SLOT / 2 + MARGIN_X, y: MARGIN_T + layer[id] * LAYER_H + NODE_H / 2}; });
  return {pos, W: hi - lo + SLOT + 2 * MARGIN_X, H: MARGIN_T * 2 + (L.length - 1) * LAYER_H + NODE_H + 8, layer};
}

/* ------------------------------------------------------------------ preparing a pane */
function prepFlow(F) {
  const P = {F, node: {}, adj: {}, edge: {}};
  F.graph.nodes.forEach(n => { P.node[n.id] = n; P.adj[n.id] = []; });
  F.graph.edges.forEach(e => { P.edge[e.id] = e; P.adj[e.source].push(e.target); });
  return P;
}

function pathBetween(P, a, b, cache) {
  const k = a + '>' + b;
  if (cache[k]) return cache[k];
  let res = [a, b];
  const prev = {[a]: null}, q = [a];
  while (q.length) {
    const u = q.shift();
    if (u === b) { res = []; for (let x = b; x != null; x = prev[x]) res.unshift(x); break; }
    for (const v of (P.adj[u] || [])) if (!(v in prev)) { prev[v] = u; q.push(v); }
  }
  return cache[k] = res;
}

function prepPatients(P, pos) {
  const F = P.F, cache = {}, out = [];
  F.cohort.patients.forEach((p, idx) => {
    const ev = p.v.filter(r => r[6]);
    const chain = (ev.length ? ev : p.v).slice().sort((a, b) => a[1] - b[1] || a[2] - b[2]);
    const segs = [];
    chain.forEach(r => {
      if (!(r[0] in pos)) return;
      segs.push({t0: r[1], t1: r[2], n: r[0], s: 0});
      segs.push({t0: r[2], t1: Math.max(r[4], r[2]), n: r[0], s: 1});
    });
    if (p.exit && p.exit in pos && p.t_exit != null) {
      const last = segs[segs.length - 1];
      if (!last || last.n !== p.exit || last.t1 < p.t_exit - 1e-6) segs.push({t0: p.t_exit, t1: Infinity, n: p.exit, s: 2});
      else { last.t1 = Math.max(last.t1, p.t_exit); segs.push({t0: Math.max(last.t1, p.t_exit), t1: Infinity, n: p.exit, s: 2}); }
    }
    if (!segs.length) return;
    segs.sort((a, b) => a.t0 - b.t0);
    // merge into node visits (arrival time at the node)
    let prevNode = null, prevSeg = null;
    segs.forEach(g => {
      g.arr = prevSeg && prevSeg.n === g.n ? prevSeg.arr : g.t0;
      g.from = prevNode && prevNode !== g.n ? prevNode : null;
      if (g.from) g.path = pathBetween(P, g.from, g.n, cache);
      prevNode = g.n; prevSeg = g;
    });
    const treated = p.out === 'treatment';
    out.push({idx, p, segs, treated, late: treated && p.t_treat != null && p.t_treat > F.target_days, missed: !!p.cancer && p.out === 'discharged'});
  });
  return out;
}

/* ------------------------------------------------------------------ dot positions at time t */
function at(pa, d, t, Tt) {
  const segs = d.segs;
  if (t < segs[0].t0) return null;
  let g = segs[0];
  for (let i = segs.length - 1; i >= 0; i--) if (t >= segs[i].t0) { g = segs[i]; break; }
  let state = g.s;
  let tr = null;
  if (g.from && t < g.t0 + Tt) {
    const u = (t - g.t0) / Tt, path = g.path, pos = pa.pos;
    const f = clamp(u, 0, 1) * (path.length - 1), i = Math.min(path.length - 2, Math.floor(f)), w = f - i;
    const a = pos[path[i]], b = pos[path[i + 1]];
    if (a && b) tr = {x: a.x + (b.x - a.x) * w, y: a.y + (b.y - a.y) * w};
  }
  return {g, state, tr};
}

/* ------------------------------------------------------------------ svg drawing */
function curve(a, b) {
  const x1 = a.x, y1 = a.y + NODE_H / 2 - 2, x2 = b.x, y2 = b.y - NODE_H / 2 + 2;
  const dy = Math.max(16, (y2 - y1) * .42);
  const pts = [];
  for (let i = 0; i <= 16; i++) {
    const u = i / 16, v = 1 - u;
    pts.push([v * v * v * x1 + 3 * v * v * u * x1 + 3 * v * u * u * x2 + u * u * u * x2,
      v * v * v * y1 + 3 * v * v * u * (y1 + dy) + 3 * v * u * u * (y2 - dy) + u * u * u * y2]);
  }
  return {d: `M${x1},${y1} C${x1},${y1 + dy} ${x2},${y2 - dy} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2, pts};
}
function wrap(s, w) {
  const words = s.split(' '), lines = [''];
  words.forEach(wd => {
    const cur = lines[lines.length - 1];
    if ((cur + ' ' + wd).trim().length <= w) lines[lines.length - 1] = (cur + ' ' + wd).trim();
    else lines.push(wd);
  });
  return lines.slice(0, 2).map((l, i, a) => i === 1 && a.length === 2 && lines.length > 2 ? l.slice(0, w - 1) + '…' : l);
}
function mix(a, b, t) { return a.map((v, i) => Math.round(v + (b[i] - v) * t)); }
function dn(F, n) {
  if (!F._dup) { const c = {}; F.graph.nodes.forEach(x => { c[x.short] = (c[x.short] || 0) + 1; }); F._dup = c; }
  return F._dup[n.short] > 1 ? n.label : n.short;
}
function shortOpt(F, id, n) {
  const nd = F.graph.nodes.find(x => x.id === id);
  const s = nd ? dn(F, nd) : id;
  return s.length > n + 2 ? s.slice(0, n) + '…' : s;
}

function globalMax(key) {
  let m = 1e-9;
  S.panes.forEach(pa => { const f = key(pa.P.F); if (f > m) m = f; });
  return m;
}
function sc() { return D.scenarios.find(s => s.id === S.sid); }
function variantOf(s, key) { return s.variants.find(v => v.key === key); }
function sideName(side) {
  const k = S.keys[side], V = variantOf(sc(), k);
  if (side === 0 && (k === 'observed' || k === 'baseline')) return 'Today';
  if (side === 1 && V && V.changes && V.changes.length) return 'After the change';
  return V ? V.label : k;
}
/* steps a change touches: steps where a connection now arrives or no longer arrives, and choices whose shares moved
   (exits and milestones left out) */
function touchedNodes() {
  if (S.panes.length < 2) return new Set();
  const [A, B] = S.panes.map(p => p.P.F), ea = new Set(A.graph.edges.map(e => e.id)), eb = new Set(B.graph.edges.map(e => e.id));
  const out = new Set(), kind = {};
  A.graph.nodes.concat(B.graph.nodes).forEach(n => { kind[n.id] = n.kind; });
  B.graph.edges.forEach(e => { if (!ea.has(e.id)) out.add(e.target); });
  A.graph.edges.forEach(e => { if (!eb.has(e.id)) out.add(e.target); });
  Object.keys(B.decisions).forEach(k => {
    const a = A.decisions[k], b = B.decisions[k];
    if (a && b && a.n && b.n && Object.keys(b.share).some(o => Math.abs((b.share[o] || 0) - (a.share[o] || 0)) > .02)) out.add(k);
  });
  [...out].forEach(id => { if (kind[id] === 'exit' || kind[id] === 'milestone' && !A.steps[id]) out.delete(id); });
  return out;
}

/* ------------------------------------------------------------------ svg drawing */
function renderPane(pa) {
  const F = pa.P.F, pos = pa.pos, layer = S.layer, side = pa.side;
  const other = S.panes[1 - side] ? S.panes[1 - side].P.F : null;
  const showNums = S.dense || layer !== 'flow';
  const maxE = globalMax(f => Math.max(1, ...f.graph.edges.map(e => e.n)));
  const maxWait = globalMax(f => Math.max(.1, ...Object.values(f.steps).map(s => s.wait_median || 0)));
  const maxQ = globalMax(f => Math.max(.1, ...Object.values(f.queues).map(q => q.peak)));
  let svg = `<svg viewBox="0 0 ${pa.W} ${pa.H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="The pathway: steps and connections">`;
  const otherEdges = other ? new Set(other.graph.edges.map(e => e.id)) : new Set();
  const selNodes = S.sel && S.sel.pane === side ? pa.selNodes : null;
  const changed = (S.touched || (S.opt && side === 1)) ? pa.touched : null;
  // groups: dashed boxes with a small label (D67)
  (GROUPS[S.sid] || []).forEach(g => {
    const ps = g.ids.filter(id => pos[id] && pa.P.node[id]).map(id => pos[id]);
    if (ps.length < 2) return;
    const x0 = Math.min(...ps.map(p => p.x)) - NODE_W / 2 - g.pad, x1 = Math.max(...ps.map(p => p.x)) + NODE_W / 2 + g.pad;
    const ybot = Math.max(...ps.map(p => p.y)) + NODE_H / 2 + g.pad + 12;
    const y0 = Math.min(...ps.map(p => p.y)) - NODE_H / 2 - g.pad, y1 = ybot;
    svg += `<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="none" stroke="${C.ink3}" stroke-width="1" stroke-dasharray="5 4" opacity=".75"/>`;
    svg += `<text x="${x0 + 6}" y="${y1 - 6}" class="mono" font-size="11" font-weight="700" letter-spacing=".08em" fill="${C.ink3}">${esc(g.label.toUpperCase())}</text>`;
  });
  // edges: strength by thickness only; numbers on hover (or in the dense view)
  let labels = '';
  pa.edgeGeo = [];
  F.graph.edges.forEach(e => {
    const a = pos[e.source], b = pos[e.target];
    if (!a || !b) return;
    const c = curve(a, b);
    const w = e.n ? .9 + 5.6 * Math.sqrt(e.n / maxE) : 1;
    const isNew = side === 1 && S.deltas && other && !otherEdges.has(e.id);
    const ret = isReturnNode(pa.P.node[e.target]) || (isReturnNode(pa.P.node[e.source]) && pa.P.node[e.target].kind !== 'exit');
    let col = ret ? C.brown : isNew ? C.mustard : C.faint, op = e.n ? .45 + .4 * Math.sqrt(e.n / maxE) : .5;
    if (ret || isNew) op = .95;
    const onSel = selNodes && selNodes.edges.has(e.id);
    if (onSel) { col = C.ink; op = 1; }
    const dash = !e.n ? 'stroke-dasharray="2 4"' : isNew ? 'stroke-dasharray="7 3"' : '';
    svg += `<path d="${c.d}" fill="none" stroke="${col}" stroke-opacity="${op}" stroke-width="${onSel ? Math.max(w, 2.5) : w}" ${dash}/>`;
    pa.edgeGeo.push({e, pts: c.pts});
    if (ret && isReturnNode(pa.P.node[e.target]))
      labels += `<text x="${c.mx + 8}" y="${c.my + 4}" class="mono" font-size="12" font-weight="700" fill="${C.brown}" stroke="${C.paper}" stroke-width="3" paint-order="stroke">return</text>`;
    else if (showNums && e.n > .2 * maxE && (layer === 'flow' || layer === 'decisions') && Math.abs(b.y - a.y) < LAYER_H * 1.6)
      labels += `<text x="${c.mx + 5}" y="${c.my + 3}" class="mono" font-size="10" fill="${C.ink3}" stroke="${C.paper}" stroke-width="3" paint-order="stroke">${fmt(e.n)}</text>`;
  });
  if (side === 1 && S.deltas && other) {
    const mine = new Set(F.graph.edges.map(e => e.id));
    other.graph.edges.forEach(e => {
      if (mine.has(e.id)) return;
      const a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      svg += `<path d="${curve(a, b).d}" fill="none" stroke="${C.faint}" stroke-opacity=".8" stroke-width="1.5" stroke-dasharray="2 5"/>`;
    });
  }
  svg += labels;
  // nodes: name only by default
  pa.nodeEl = {};
  F.graph.nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const st = F.steps[n.id], dc = F.decisions[n.id], ex = F.exits[n.id];
    const x = p.x - NODE_W / 2, y = p.y - NODE_H / 2;
    let fill = C.card, stroke = C.ink3, sw = 1, txt = C.ink;
    if (n.kind === 'exit') { stroke = n.outcome === 'treatment' ? C.ink : C.faint; sw = n.outcome === 'treatment' ? 2 : 1; fill = n.outcome === 'treatment' ? C.card : C.paper; if (n.outcome !== 'treatment') txt = C.ink2; }
    if (n.kind === 'milestone') stroke = C.faint;
    let line2 = '', spark = '';
    const otherSt = other && other.steps[n.id];
    if (layer === 'flow') {
      if (showNums) {
        if (st) line2 = fmt(st.n) + ' patients';
        if (dc && dc.n) line2 = fmt(dc.n) + ' decisions';
        if (n.kind === 'exit' && ex) line2 = fmt(ex.n) + ' patients' + (ex.n_cancer && ex.outcome !== 'treatment' ? ` (${fmt(ex.n_cancer)} cancer)` : '');
      }
    } else if (layer === 'time') {
      if (st && st.wait_median != null) {
        const a = clamp(Math.sqrt((st.wait_median || 0) / maxWait), 0, 1);
        fill = mixHex(C.card, C.mustardTint, a);
        stroke = a > .5 ? C.mustard : C.ink3;
        line2 = `wait ${f1(st.wait_median)} d${st.critical_share ? ' · ' + pct(st.critical_share) : ''}`;
      } else if (st) line2 = fmt(st.n) + ' patients';
    } else if (layer === 'queues') {
      const q = F.queues[n.id];
      if (q) {
        const w = NODE_W - 12, h = 7, xs = q.y.length;
        let d = '';
        q.y.forEach((v, i) => { d += (i ? 'L' : 'M') + (x + 6 + w * i / (xs - 1)).toFixed(1) + ',' + (y + NODE_H - 3 - h * Math.min(1, v / maxQ)).toFixed(1); });
        spark = `<path d="${d}" fill="none" stroke="${C.ink2}" stroke-width="1.2"/>`;
        line2 = `peak ${fmt(q.peak)} waiting`;
      } else if (st) line2 = fmt(st.n) + ' patients';
    } else if (layer === 'decisions') {
      if (n.kind === 'decision' && dc && dc.n) {
        const top = Object.entries(dc.share).sort((a, b) => b[1] - a[1]);
        line2 = `${pct(top[0][1])} ${shortOpt(F, top[0][0], 11)}`;
        stroke = C.ink; sw = 2;
      } else { line2 = st ? fmt(st.n) : ''; }
    }
    let delta = '';
    if (S.deltas && otherSt && side === 1 && st && st.critical_wait != null && otherSt.critical_wait != null) {
      const dlt = (st.critical_wait + st.critical_service) - (otherSt.critical_wait + otherSt.critical_service);
      if (Math.abs(dlt) >= .5) delta = `${dlt > 0 ? '+' : '−'}${f1(Math.abs(dlt))} d on path`;
    }
    if (selNodes && selNodes.nodes.has(n.id)) { stroke = C.ink; sw = 2.2; }
    if (S.hl === n.short) { stroke = C.ink; sw = 3; }
    const tall = S.tall;
    const lines = wrap(dn(F, n), 18);
    const ty = tall ? (lines.length === 1 ? y + 15 : y + 12) : (lines.length === 1 ? p.y + 4 : p.y - 2);
    const rx = n.kind === 'decision' ? NODE_H / 2 : 2;
    let g = `<g data-id="${n.id}">`;
    if (changed && changed.has(n.id))
      g += `<rect x="${x - 4}" y="${y - 4}" width="${NODE_W + 8}" height="${NODE_H + 8}" rx="${rx + 3}" fill="none" stroke="${C.mustard}" stroke-width="2" stroke-dasharray="4 3"/>`;
    g += `<rect data-r="1" x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${n.kind === 'exit' && n.outcome !== 'treatment' ? 'stroke-dasharray="3 2"' : ''}/>`;
    lines.forEach((l, i) => { g += `<text x="${p.x}" y="${ty + i * 12}" text-anchor="middle" font-size="12" font-weight="${n.kind === 'exit' && n.outcome === 'treatment' ? 700 : 600}" fill="${txt}">${esc(l)}</text>`; });
    if (line2 && tall) g += `<text x="${p.x}" y="${y + NODE_H - (spark ? 12 : 6)}" text-anchor="middle" class="mono" font-size="9.5" fill="${C.ink3}">${line2}</text>`;
    if (delta) g += `<text x="${p.x}" y="${y + NODE_H + 24}" text-anchor="middle" class="mono" font-size="10.5" font-weight="700" fill="${C.ink}" stroke="${C.paper}" stroke-width="3" paint-order="stroke">${delta}</text>`;
    // queue label ("18 waiting"): filled in by updateQueues
    g += `<text data-q="1" x="${p.x}" y="${y + NODE_H + 12}" text-anchor="middle" class="mono" font-size="11" font-weight="700" stroke="${C.paper}" stroke-width="3" paint-order="stroke"></text>`;
    g += spark + '</g>';
    svg += g;
  });
  svg += '</svg>';
  pa.svgBox.innerHTML = svg;
  pa.svgBox.querySelectorAll('g[data-id]').forEach(el => {
    pa.nodeEl[el.dataset.id] = {r: el.querySelector('rect[data-r]'), q: el.querySelector('text[data-q]'),
      fill: el.querySelector('rect[data-r]').getAttribute('fill'), stroke: el.querySelector('rect[data-r]').getAttribute('stroke'),
      sw: el.querySelector('rect[data-r]').getAttribute('stroke-width')};
  });
  pa.qShown = {};
  updateQueues(pa, true);
}

/* ------------------------------------------------------------------ queue colouring */
function queueTick(pa, raw, t) {
  const thr = (QUEUE.share[S.sid] || [.04, .10]).map(s => s * pa.dots.length);
  const jump = pa.qT == null || t < pa.qT - 1e-6 || t - pa.qT > 4;
  const a = jump ? 1 : 1 - Math.exp(-(t - pa.qT) / QUEUE.SMOOTH_DAYS);
  pa.qT = t;
  pa.q = pa.q || {};
  Object.keys(pa.P.node).forEach(id => {
    const r = raw[id] || 0, o = pa.q[id] = pa.q[id] || {ema: 0, st: 0, n: 0};
    o.ema += (r - o.ema) * a;
    o.n = r;
    const v = o.ema;
    let st = o.st;
    if (jump) st = v >= thr[1] ? 2 : v >= thr[0] ? 1 : 0;
    else {
      if (st < 2 && v >= thr[1]) st = 2;
      else if (st === 2 && v < thr[1] * QUEUE.HYST) st = v >= thr[0] ? 1 : 0;
      if (st === 0 && v >= thr[0]) st = 1;
      else if (st === 1 && v < thr[0] * QUEUE.HYST) st = 0;
    }
    o.st = st;
  });
}
function updateQueues(pa, force) {
  if (!pa.q || !pa.nodeEl) return;
  const on = S.layer === 'flow';
  Object.keys(pa.nodeEl).forEach(id => {
    const el = pa.nodeEl[id], o = pa.q[id] || {st: 0, n: 0};
    const st = on && pa.P.node[id].kind !== 'exit' ? o.st : 0;
    const key = st + ':' + (st ? Math.round(o.ema) : 0);
    if (!force && pa.qShown[id] === key) return;
    pa.qShown[id] = key;
    if (st === 0) { el.r.setAttribute('fill', el.fill); el.r.setAttribute('stroke', el.stroke); el.r.setAttribute('stroke-width', el.sw); el.q.textContent = ''; }
    else {
      el.r.setAttribute('fill', st === 2 ? C.brickTint : C.mustardTint);
      el.r.setAttribute('stroke', st === 2 ? C.brick : C.mustard);
      el.r.setAttribute('stroke-width', st === 2 ? 2.5 : 2);
      el.q.setAttribute('fill', st === 2 ? C.brick : C.mustardInk);
      el.q.textContent = Math.round(o.ema) + ' waiting';
    }
  });
}

/* ------------------------------------------------------------------ canvas dots */
function drawPane(pa, t) {
  const cv = pa.cv, ctx = pa.ctx;
  const cw = pa.gw.clientWidth, ch = pa.gw.clientHeight, dpr = window.devicePixelRatio || 1;
  if (!cw) return;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(ch * dpr)) { cv.width = Math.round(cw * dpr); cv.height = Math.round(ch * dpr); }
  const k = cw / pa.W * dpr;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.setTransform(k, 0, 0, k, 0, 0);
  const Tt = Math.max(.8, S.H / 200), groups = {}, qraw = {};
  const counts = {w: 0, s: 0, ok: 0, late: 0, home: 0, missed: 0, moving: 0, n: pa.dots.length};
  const draws = [];
  pa.dots.forEach(d => {
    const r = at(pa, d, t, Tt);
    if (!r) return;
    const g = r.g;
    if (g.s === 2 && !r.tr) {
      const kind = d.treated ? (d.late ? 'late' : 'ok') : (d.missed ? 'missed' : 'home');
      counts[kind]++;
      (groups[g.n] = groups[g.n] || []).push({d, g, kind, arr: g.arr});
    } else if (r.tr) {
      counts.moving++;
      draws.push({x: r.tr.x, y: r.tr.y, col: C.ink, r: 2.3, d});
    } else {
      const kind = g.s === 0 ? 'w' : 's';
      counts[kind]++;
      if (kind === 'w' && t - g.t0 > QUEUE.WAIT_MIN) qraw[g.n] = (qraw[g.n] || 0) + 1;
      (groups[g.n] = groups[g.n] || []).push({d, g, kind, arr: g.arr});
    }
  });
  queueTick(pa, qraw, t);
  updateQueues(pa);
  pa.hitDots = [];
  Object.keys(groups).forEach(nid => {
    const arr = groups[nid].sort((a, b) => a.arr - b.arr || a.d.idx - b.d.idx);
    const p = pa.pos[nid];
    const n = arr.length, big = n > 50, isExit = pa.P.node[nid].kind === 'exit';
    const sx = big ? 4.1 : 5.9, rs = big ? 3.7 : 5.2, perRow = Math.floor((NODE_W - 6) / sx);
    let dirR = 1;
    if (isExit) {
      let left = Infinity, right = Infinity;
      Object.keys(pa.pos).forEach(k => { const q = pa.pos[k]; if (k === nid || Math.abs(q.y - p.y) > NODE_H) return; if (q.x < p.x) left = Math.min(left, p.x - q.x); else right = Math.min(right, q.x - p.x); });
      left = Math.min(left, p.x); right = Math.min(right, pa.W - p.x);
      dirR = right >= left ? 1 : -1;
    }
    const rowsSide = 7;
    arr.forEach((o, i) => {
      let x, y;
      if (isExit) {
        const c = Math.floor(i / rowsSide), rr = i % rowsSide;
        x = p.x + dirR * (NODE_W / 2 + 6 + c * 3.9); y = p.y - (rowsSide - 1) * 3.9 / 2 + rr * 3.9 + (c % 2 ? 1.9 : 0);
      } else {
        const c = i % perRow, rr = Math.floor(i / perRow);
        x = p.x - NODE_W / 2 + 5 + c * sx + (rr % 2 ? sx / 2 : 0); y = p.y - NODE_H / 2 - 4 - rr * rs;
      }
      let col = C.ink, ring = false, rad = (big || isExit) ? 1.8 : 2.5;
      if (o.kind === 'w') col = mixHex(C.faint, C.ink3, clamp((t - o.g.t0) / 30, 0, 1));
      else if (o.kind === 'late') ring = true;
      else if (o.kind === 'missed') { col = C.brick; ring = true; }
      else if (o.kind === 'home') { col = C.faint; rad = 1.5; }
      draws.push({x, y, col, r: ring ? 2.1 : rad, ring, d: o.d, kind: o.kind});
    });
  });
  draws.forEach(o => {
    ctx.beginPath(); ctx.arc(o.x, o.y, o.r, 0, 6.2832);
    if (o.ring) { ctx.strokeStyle = o.col; ctx.lineWidth = 1.2; ctx.stroke(); }
    else { ctx.fillStyle = o.col; ctx.fill(); }
    pa.hitDots.push(o);
  });
  if (S.sel && S.sel.pane === pa.side) {
    const o = pa.hitDots.find(o => o.d.idx === S.sel.idx);
    if (o) { ctx.beginPath(); ctx.arc(o.x, o.y, 6.5, 0, 6.2832); ctx.strokeStyle = C.ink; ctx.lineWidth = 1.6; ctx.stroke(); }
  }
  pa.counts = counts;
}

/* ------------------------------------------------------------------ panes */
function visibleSides() { return !S.opt ? [0] : S.split ? [0, 1] : [S.side]; }
function buildPanes() {
  const s = sc();
  const flows = S.keys.map(k => variantOf(s, k).flow);
  const lay = layoutUnion(flows);
  const root = $('#panes');
  root.classList.toggle('is-split', S.opt && S.split);
  root.innerHTML = '';
  S.panes = [];
  S.H = Math.max(...flows.map(f => f.cohort.horizon));
  [0, 1].forEach(side => {
    const V = variantOf(s, S.keys[side]);
    const el = document.createElement('div');
    el.className = 'sim-pane';
    el.innerHTML = `<div class="sim-pane__tag"></div><div class="gwrap"><div data-k="svg"></div><canvas></canvas><div class="hit"></div></div>`;
    root.appendChild(el);
    const P = prepFlow(V.flow);
    const pa = {side, el, P, pos: lay.pos, W: lay.W, H: lay.H, V, sc: s,
      svgBox: $('[data-k=svg]', el), gw: $('.gwrap', el), cv: $('canvas', el), hit: $('.hit', el), counts: {}, hitDots: [], selNodes: null};
    pa.ctx = pa.cv.getContext('2d');
    pa.dots = prepPatients(P, lay.pos);
    pa.hasMissed = pa.dots.some(d => d.missed);
    S.panes.push(pa);
    wireHit(pa);
  });
  const tn = touchedNodes();
  S.panes.forEach(pa => { pa.touched = tn; });
  showPanes();
  sizeToTime();
  renderChrome();
}
function showPanes() {
  const vis = visibleSides();
  $('#panes').classList.toggle('is-split', vis.length === 2);
  S.panes.forEach(pa => {
    pa.el.style.display = vis.includes(pa.side) ? '' : 'none';
    $('.sim-pane__tag', pa.el).textContent = sideName(pa.side);
    pa.qT = null;
  });
  S.panes.forEach(fit);
  S.panes.forEach(renderPane);
  S.panes.forEach(pa => drawPane(pa, S.t));
}
function fit(pa) {
  const w = Math.max(200, pa.el.clientWidth || $('#panes').clientWidth);
  const top = $('#panes').getBoundingClientRect().top + window.scrollY;
  const bar = $('#bar').offsetHeight || 60;
  const availH = Math.max(380, innerHeight - top - bar - 16 - (S.opt && S.split ? 24 : 0));
  const k = S.big ? clamp(w / pa.W, .6, 1.4) : clamp(Math.min(w / pa.W, availH / pa.H), .45, 1.25);
  pa.gw.style.width = Math.round(pa.W * k) + 'px';
}

/* ------------------------------------------------------------------ hover, click */
function wireHit(pa) {
  const toLogical = ev => { const r = pa.gw.getBoundingClientRect(), k = pa.W / r.width; return {x: (ev.clientX - r.left) * k, y: (ev.clientY - r.top) * k}; };
  const nodeAt = pt => {
    for (const n of pa.P.F.graph.nodes) { const p = pa.pos[n.id]; if (p && Math.abs(pt.x - p.x) <= NODE_W / 2 && Math.abs(pt.y - p.y) <= NODE_H / 2) return n; }
    return null;
  };
  const edgeAt = pt => {
    let best = null, bd = 5;
    (pa.edgeGeo || []).forEach(g => g.pts.forEach(q => { const d = Math.hypot(q[0] - pt.x, q[1] - pt.y); if (d < bd) { bd = d; best = g.e; } }));
    return best;
  };
  pa.hit.addEventListener('mousemove', ev => {
    if (S.pin) return;
    const pt = toLogical(ev);
    const dot = nearestDot(pa, pt);
    if (dot) { pa.hit.style.cursor = 'pointer'; showTip(ev, dotTip(pa, dot)); return; }
    const n = nodeAt(pt);
    if (n) { pa.hit.style.cursor = 'pointer'; showTip(ev, nodeTip(pa, n)); return; }
    const e = edgeAt(pt);
    pa.hit.style.cursor = 'default';
    if (e) showTip(ev, edgeTip(pa, e)); else hideTip();
  });
  pa.hit.addEventListener('mouseleave', () => { if (!S.pin) hideTip(); });
  pa.hit.addEventListener('click', ev => {
    const pt = toLogical(ev), dot = nearestDot(pa, pt);
    if (dot) { unpin(); selectPatient(pa.side, dot.d.idx); return; }
    const n = nodeAt(pt), e = n ? null : edgeAt(pt);
    if (n || e) {
      S.pin = {side: pa.side, id: n ? n.id : e.id, edge: !n, x: ev.clientX, y: ev.clientY};
      showTip(ev, n ? nodeTip(pa, n) : edgeTip(pa, e));
      tip.classList.add('is-pinned');
      return;
    }
    unpin();
    if (S.sel) { S.sel = null; S.panes.forEach(p => p.selNodes = null); S.panes.forEach(renderPane); if (S.drawer === 'trace') closeDrawer(); }
  });
}
function nearestDot(pa, pt) {
  let best = null, bd = 7.5;
  pa.hitDots.forEach(o => { const dd = Math.hypot(o.x - pt.x, o.y - pt.y); if (dd < bd) { bd = dd; best = o; } });
  return best;
}
function selectPatient(side, idx) {
  const pa = S.panes[side], d = pa.dots.find(x => x.idx === idx);
  S.sel = {pane: side, idx};
  const nodes = new Set(), edges = new Set();
  const chain = d.p.v.filter(r => r[6]).sort((a, b) => a[1] - b[1]).map(r => r[0]);
  if (d.p.exit && !chain.includes(d.p.exit)) chain.push(d.p.exit);
  chain.forEach((n, i) => {
    nodes.add(n);
    if (i) pathBetween(pa.P, chain[i - 1], n, {}).forEach((x, j, a) => { nodes.add(x); if (j) edges.add(a[j - 1] + '>' + x); });
  });
  d.p.c.forEach(c => nodes.add(c[0]));
  pa.selNodes = {nodes, edges};
  S.panes.forEach(p => { if (p !== pa) p.selNodes = null; });
  S.panes.forEach(renderPane);
  openDrawer('trace');
}

const tip = $('#tip');
function showTip(ev, html) {
  tip.innerHTML = html; tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  // to the right of the pointer, so it does not cover the step it describes; flip left near the edge
  let x = ev.clientX + 18; if (x + w > innerWidth - 8) x = ev.clientX - w - 18;
  tip.style.left = clamp(x, 8, innerWidth - w - 8) + 'px';
  tip.style.top = clamp(ev.clientY - 10, 8, innerHeight - h - 70) + 'px';
}
function hideTip() { tip.hidden = true; tip.classList.remove('is-pinned'); }
function unpin() { S.pin = null; hideTip(); }
function refreshPinned() {
  if (!S.pin || tip.hidden) return;
  const pa = S.panes[S.pin.side];
  if (!pa) return;
  if (S.pin.edge) { const e = pa.P.edge[S.pin.id]; if (e) tip.innerHTML = edgeTip(pa, e); }
  else { const n = pa.P.node[S.pin.id]; if (n) tip.innerHTML = nodeTip(pa, n); }
}
function nodeTip(pa, n) {
  const F = pa.P.F, st = F.steps[n.id], dc = F.decisions[n.id], ex = F.exits[n.id], q = pa.q && pa.q[n.id];
  let h = `<b>${esc(n.label)}</b>`;
  if (pa.side === 1 || S.opt) h += ` <span class="m">· ${esc(sideName(pa.side).toLowerCase())}</span>`;
  if (q && n.kind !== 'exit') h += `<br><span class="k">Now, day ${Math.round(S.t)}</span><br><span class="m">${q.n} of the ${pa.dots.length} sampled patients waiting here for more than ${QUEUE.WAIT_MIN} days</span>`;
  h += `<br><span class="k">Whole run, all simulated patients</span>`;
  if (n.resource && F.resources[n.resource]) h += `<br><span class="m">${esc(F.resources[n.resource].label)}</span>`;
  if (st) {
    h += `<br><span class="m">${fmt(st.n)} patients through (${fmt(st.n_cancer)} with cancer)</span>`;
    if (st.wait_median != null) {
      h += `<br><span class="m">typical wait ${f1(st.wait_median)} d (one in ten wait over ${f1(st.wait_p90)} d); the step itself ${f1(st.service_median)} d</span>`;
      if (st.critical_n) h += `<br><span class="m">${pct(st.critical_share, 1)} of the time to treatment of treated cancers</span>`;
      const r = F.resources[n.resource];
      if (r && r.utilisation != null) h += `<br><span class="m">${r.capacity_per_day ? r.capacity_per_day + ' slots a day, ' : ''}${pct(r.utilisation)} booked</span>`;
    }
  }
  if (dc && dc.n) {
    h += `<br><span class="m">${fmt(dc.n)} decisions:</span>`;
    dc.options.forEach(o => { h += `<br><span class="m">${esc(shortOpt(F, o, 28))}: ${pct(dc.share[o])}</span>`; });
  }
  if (ex) h += `<br><span class="m">${fmt(ex.n)} patients end here${ex.outcome !== 'treatment' && ex.n_cancer ? `, of whom ${fmt(ex.n_cancer)} had cancer` : ''}</span>`;
  if (S.pin) h += `<br><span class="m">click elsewhere or press Esc to close</span>`;
  return h;
}
function edgeTip(pa, e) {
  const F = pa.P.F, a = pa.P.node[e.source], b = pa.P.node[e.target];
  const out = F.graph.edges.filter(x => x.source === e.source).reduce((s, x) => s + (x.n || 0), 0);
  let h = `<b>${esc(a.short)} → ${esc(b.short)}</b>`;
  if (isReturnNode(b)) h += `<br><span class="m">return: back to primary care</span>`;
  h += `<br><span class="k">Whole run, all simulated patients</span><br><span class="m">${fmt(e.n)} patients took this connection${out && e.n ? ` (${pct(e.n / out)} of those leaving ${esc(a.short)})` : ''}</span>`;
  return h;
}
function dotTip(pa, o) {
  const p = o.d.p;
  return `<b>Patient ${p.id}</b> <span class="m">(${esc(p.g.replace('_', '-'))}, ${p.cancer ? 'has cancer' : 'no cancer'})</span><br><span class="m">click for this patient's path</span>`;
}

/* ------------------------------------------------------------------ headline numbers */
function claimLink(id) { return id ? `<a href="research.html#${esc(id)}">how we know</a>` : ''; }
function renderHead() {
  const s = sc(), [A, B] = S.panes.map(p => p.P.F), two = S.opt, on = S.split ? -1 : S.side;
  const missedAny = s.variants.some(v => v.flow.metrics.missed_cancers);
  const val = (side, v, unit) => `<span class="sim-head__v${two && on >= 0 && on !== side ? ' is-off' : ''}">${v}${unit ? `<small>${unit}</small>` : ''}</span>`;
  const row = (label, a, b, unit, sub, small) => `<div class="sim-head__row${small ? ' sim-head__row--small' : ''}"><span class="label">${label}</span>
    <div class="sim-head__vals">${val(0, a, unit)}${two ? `<span class="sim-head__arrow">→</span>${val(1, b, unit)}` : ''}</div>${sub ? `<span class="sim-head__sub">${sub}</span>` : ''}</div>`;
  const share = F => (100 * F.metrics.share_within_target).toFixed(1);
  let sub = '';
  const N = window.START_DATA && START_DATA.norway, O = N && N.optimiser, bd = O && O.bands;
  if (s.published && bd && bd.observed) {
    sub = two && S.keys[1] === 'suggested' && S.keys[0] === 'observed'
      ? `best fit; across the ${O.n_settings} settings that fit today's pathway: ${pct(bd.observed.min)}–${pct(bd.observed.max)} today, ${pct(bd.optimiser_no_equipment.min)}–${pct(bd.optimiser_no_equipment.max)} after (median ${pct(bd.optimiser_no_equipment.median)})`
      : S.keys[0] === 'observed' && !two ? `best fit; ${pct(bd.observed.min)}–${pct(bd.observed.max)} across the ${O.n_settings} settings that fit` : 'at the best-fitting setting';
  }
  let h = row(`Treated within ${A.target_days} days`, share(A), share(B), '%', sub);
  h += row('Median days to treatment', f1(A.metrics.median_days_to_treatment), f1(B.metrics.median_days_to_treatment), '', '', true);
  if (missedAny) h += row('Cancers missed, per cohort', f1(A.metrics.missed_cancers), f1(B.metrics.missed_cancers), '', '', true);
  const cl = CLAIM[S.sid] || {};
  h += `<div class="sim-head__basis"><span class="sim-basis">Our simulation</span> whole run, ${fmt(A.totals.n)} simulated patients · ${claimLink(two ? cl.share : (cl.today || cl.share))}</div>`;
  $('#head').innerHTML = h;
  $('#head').classList.toggle('is-two', two);
}

/* ------------------------------------------------------------------ chrome: flip, legend, pair note, menu */
function renderChrome() {
  const s = sc(), V1 = S.panes[1].V, hasChanges = !!(V1.changes && V1.changes.length);
  $('#flip').hidden = !S.opt;
  $('#flip-today').textContent = sideName(0);
  $('#flip-after').textContent = sideName(1);
  [$('#flip-today'), $('#flip-after')].forEach((b, i) => b.setAttribute('aria-pressed', String(!S.split && S.side === i)));
  $('#flip-stamp').textContent = hasChanges ? (s.synthetic ? 'Saved optimiser run · held-out patients' : 'Saved optimiser run · best fit') : 'Saved simulation';
  const fl = $('#flip-link');
  fl.href = `index.html#${DASH_KEY[S.sid] || S.sid}/5`;
  fl.hidden = !hasChanges;
  const ob = $('#optimise');
  ob.textContent = S.opt ? 'Show the changes' : 'Optimise';
  ob.classList.toggle('is-done', S.opt);
  ob.classList.toggle('btn--primary', !S.opt);
  ob.classList.toggle('btn--secondary', S.opt);
  const dot = (c, ring) => `<i style="${ring ? `border:1.5px solid ${c};background:none` : `background:${c}`}"></i>`;
  $('#legend').innerHTML = `${dot(C.ink)}moving or being seen · ${dot(C.faint)}waiting · <span style="color:${C.mustardInk}">steps turn mustard, then brick, as patients pile up</span>` +
    (S.sid === 'finland' ? ` · <span style="color:${C.brown}">return: back to primary care</span>` : '');
  const note = pairNote();
  $('#pairnote').hidden = !note;
  $('#pairnote').innerHTML = note;
  $('#scn').value = S.sid;
  renderHead();
  if (S.drawer && S.drawer !== 'trace') openDrawer(S.drawer);
}
function pairNote() {
  const N = window.START_DATA && START_DATA.norway;
  if (S.sid !== 'norway' || !S.opt) return '';
  if (S.keys[0] === 'authors' && S.keys[1] === 'suggested')
    return `<b>Not like for like.</b> The authors' pathway includes their shorter PET-CT wait; the optimiser's pathway assumes no new equipment. Details, About this simulation, says more.`;
  if (S.keys[0] === 'observed' && S.keys[1] === 'faster_pet')
    return `The faster scanner alone: the model over-predicts it against the published figure. Details, Check against the published study.`;
  return '';
}

/* ------------------------------------------------------------------ Optimise */
let optTimer = null;
function optimise() {
  const V1 = S.panes[1].V, ch = V1.changes && V1.changes.length ? V1.changes : [V1.label];
  const card = $('#optcard'), list = $('#opt-list');
  clearTimeout(optTimer);
  card.classList.remove('is-leaving');
  card.hidden = false;
  $('#opt-title').textContent = V1.changes && V1.changes.length ? 'The optimiser changed the order of steps' : 'The pathway compared';
  const s = sc();
  $('#opt-note').innerHTML = s.synthetic
    ? 'A saved optimiser run, replayed: this page does not search live. Results are on simulated patients the search did not use.'
    : 'A saved optimiser run, replayed: this page does not search live. Started from today\'s pathway, no new equipment, best-fitting setting.';
  list.innerHTML = '';
  const already = S.opt;
  if (already) { ch.forEach(c => { const li = document.createElement('li'); li.textContent = c; list.appendChild(li); }); $('#opt-note').innerHTML += ' <span class="label">Esc or click to close</span>'; return; }
  S.touched = true; S.panes.forEach(renderPane);
  let i = 0;
  const next = () => {
    if (i >= ch.length) { optTimer = setTimeout(finishOptimise, 1100); return; }
    const li = document.createElement('li'), text = ch[i++];
    list.appendChild(li);
    let j = 0;
    const type = () => { j = Math.min(text.length, j + 3); li.textContent = text.slice(0, j); if (j < text.length) optTimer = setTimeout(type, 12); else optTimer = setTimeout(next, 250); };
    type();
  };
  next();
}
function finishOptimise() {
  const card = $('#optcard');
  card.classList.add('is-leaving');
  setTimeout(() => { card.hidden = true; card.classList.remove('is-leaving'); }, 300);
  S.touched = false; S.opt = true; S.side = 1;
  showPanes(); renderChrome();
}
function closeOptCard() {
  const card = $('#optcard');
  if (card.hidden) return false;
  if (!S.opt) { clearTimeout(optTimer); finishOptimise(); } else card.hidden = true;
  return true;
}
function flip(side) {
  if (S.split) S.split = false;
  S.side = side;
  showPanes(); renderChrome();
}

/* ------------------------------------------------------------------ Details menu and drawers */
const DRAWERS = {
  lost: ['Where time is lost', () => lostCard()],
  check: ['Check against the published study', () => validationCard()],
  pair: ['Compare other pathways', () => pairCard()],
  results: ['All results', () => resultsCard()],
  counts: ['Counts now', () => countsCard()],
  decisions: ['Decisions: what was chosen', () => decisionsCard()],
  about: ['About this simulation', () => aboutCard() + `<div class="card"><h3>Key</h3>${keyHtml()}<p>${renderNote()}</p></div>`],
  trace: ['Patient', () => traceCard()]};
function renderMenu() {
  const s = sc();
  const radios = LAYERS.map(([k, l]) => `<label><input type="radio" name="layer" value="${k}" ${S.layer === k ? 'checked' : ''}> ${l}</label>`).join('');
  const help = (LAYERS.find(l => l[0] === S.layer) || LAYERS[0])[2];
  const item = (k, l) => `<button type="button" class="sim-menu__link" data-drawer="${k}">${l}</button>`;
  $('#menu').innerHTML = `
    <div class="sim-menu__sec"><div class="label sim-menu__h">Show on the graph</div><div class="sim-menu__opts">${radios}</div><p class="sim-menu__help">${help}</p></div>
    <div class="sim-menu__sec"><div class="sim-menu__opts">
      <label><input type="checkbox" data-opt="deltas" ${S.deltas ? 'checked' : ''}> Show change per step</label>
      <label><input type="checkbox" data-opt="split" ${S.split ? 'checked' : ''}> Side by side</label>
      <label><input type="checkbox" data-opt="dense" ${S.dense ? 'checked' : ''}> Show all numbers on the graph</label>
      <label><input type="checkbox" data-opt="big" ${S.big ? 'checked' : ''}> Draw larger and scroll</label></div>
      <p class="sim-menu__help">Change per step and side by side compare today with after the change (they press Optimise first).</p></div>
    <div class="sim-menu__sec sim-menu__links">
      ${item('lost', 'Where time is lost')}${s.published ? item('check', 'Check against the published study') : ''}
      ${item('pair', 'Compare other pathways')}${item('results', 'All results')}
      ${item('counts', 'Counts now')}${item('decisions', 'Decisions: what was chosen')}
      ${item('about', 'About this simulation')}
      <a class="sim-menu__link" href="encounter.html">Primary-care loop (other page)</a>
      <a class="sim-menu__link" href="evidence.html">Evidence page</a>
      <a class="sim-menu__link" href="research.html">Where each claim comes from</a></div>`;
}
function toggleMenu(open) {
  const m = $('#menu'), b = $('#details');
  open = open == null ? m.hidden : open;
  if (open) renderMenu();
  m.hidden = !open;
  b.setAttribute('aria-expanded', String(open));
}
function openDrawer(k) {
  const d = DRAWERS[k];
  if (!d) return;
  if (k === 'trace' && !S.sel) return;
  S.drawer = k;
  const dr = $('#drawer');
  dr.innerHTML = `<button type="button" class="sim-drawer__x" data-close="1">Close</button>` + d[1]();
  dr.classList.add('drawer--open');
  dr.querySelectorAll('[data-hl]').forEach(el => el.addEventListener('click', () => { S.hl = S.hl === el.dataset.hl ? null : el.dataset.hl; S.panes.forEach(renderPane); }));
  dr.querySelectorAll('select[data-side]').forEach(el => el.addEventListener('change', () => {
    S.keys[+el.dataset.side] = el.value; S.sel = null; S.opt = true; buildPanes(); openDrawer('pair');
  }));
}
function closeDrawer() {
  const was = S.drawer;
  S.drawer = null;
  $('#drawer').classList.remove('drawer--open');
  if (was === 'trace' && S.sel) { S.sel = null; S.panes.forEach(p => p.selNodes = null); S.panes.forEach(renderPane); }
  return !!was;
}
function pairCard() {
  const s = sc();
  const opts = side => s.variants.map(v => `<option value="${v.key}" ${v.key === S.keys[side] ? 'selected' : ''}>${esc(v.label)}</option>`).join('');
  let h = `<div class="card"><h3>Compare other pathways</h3><p>The toggle compares two saved simulations of the same patients. Pick another pair here; the first is shown as the starting point, the second as the change.</p>
    <label class="label">First</label><select data-side="0">${opts(0)}</select><label class="label">Second</label><select data-side="1">${opts(1)}</select>`;
  if (s.published) h += `<p>Norway has four saved pathways: today's (observed), the optimiser's with no new equipment, the faster PET-CT scanner alone, and the authors' reordered pathway as we rebuilt it. There is no optimiser run with the faster scanner in this demo (decision D68).</p>`;
  return h + '</div>';
}
function resultsCard() {
  const [A, B] = S.panes.map(p => p.P.F);
  const r = (l, a, b) => `<tr><td>${l}</td><td>${a}</td><td>${b}</td></tr>`;
  const m = (F, k, f) => F.metrics[k] == null ? '–' : f(F.metrics[k]);
  let h = `<div class="card"><h3>All results</h3><table><tr><th></th><th>${esc(sideName(0))}</th><th>${esc(sideName(1))}</th></tr>`;
  h += r(`Treated within ${A.target_days} days`, m(A, 'share_within_target', x => pct(x, 1)), m(B, 'share_within_target', x => pct(x, 1)));
  h += r('Median days to treatment', m(A, 'median_days_to_treatment', f1), m(B, 'median_days_to_treatment', f1));
  h += r('Median days to diagnosis', m(A, 'median_days_to_diagnosis', f1), m(B, 'median_days_to_diagnosis', f1));
  h += r('Cancers missed, per cohort', m(A, 'missed_cancers', f1), m(B, 'missed_cancers', f1));
  h += r('Tests per patient', m(A, 'tests_per_patient', x => x.toFixed(2)), m(B, 'tests_per_patient', x => x.toFixed(2)));
  h += r('Invasive procedures per patient', m(A, 'invasive_per_patient', x => x.toFixed(2)), m(B, 'invasive_per_patient', x => x.toFixed(2)));
  h += r('Cost per patient (model units)', m(A, 'cost_per_patient', fmt), m(B, 'cost_per_patient', fmt));
  if (A.metrics.median_days_to_exit_noncancer != null) h += r('Median days to leave, no cancer', m(A, 'median_days_to_exit_noncancer', f1), m(B, 'median_days_to_exit_noncancer', f1));
  h += r('Simulated patients (all cohorts)', fmt(A.totals.n), fmt(B.totals.n));
  h += r('Cohorts', fmt(A.totals.cohorts), fmt(B.totals.cohorts));
  h += `</table><p>Per-cohort figures are means over the cohorts. All patients are simulated. Where each number may be quoted, and with which range, is on the research page.</p></div>`;
  return h;
}
function countsCard() {
  const ps = S.panes;
  const c = k => ps.map(p => `<b>${p.counts[k] || 0}</b>`).join('');
  return `<div class="card"><h3>Counts now, day ${Math.round(S.t)}</h3><p>The ${ps[0].dots.length} sampled patients, at this point in their own pathway.</p>
    <div class="sim-counts"><span></span><span class="h">${esc(sideName(0))}</span><span class="h">${esc(sideName(1))}</span>
    <span>waiting</span>${c('w')}<span>being seen</span>${c('s')}<span>moving</span>${c('moving')}<span>treated in time</span>${c('ok')}
    <span>treated late</span>${c('late')}<span>discharged</span>${c('home')}${ps.some(p => p.hasMissed) ? `<span>cancer missed</span>${c('missed')}` : ''}</div></div>`;
}
function keyHtml() {
  const d = (c, ring, r) => `<svg width="14" height="14"><circle cx="7" cy="7" r="${r || 4}" ${ring ? `fill="none" stroke="${c}" stroke-width="1.5"` : `fill="${c}"`}/></svg>`;
  return `<div class="sim-key">${d(C.ink)}<span>moving or being seen</span>${d(C.faint)}<span>waiting (darker the longer)</span>${d(C.ink, 0, 3)}<span>treated in time (beside the last step)</span>
    ${d(C.ink, 1)}<span>treated late</span>${d(C.brick, 1)}<span>cancer sent home</span>${d(C.faint, 0, 2)}<span>discharged</span>
    <svg width="18" height="12"><rect x="1" y="1" width="16" height="10" fill="${C.mustardTint}" stroke="${C.mustard}" stroke-width="2"/></svg><span>a queue is building: sampled patients who have waited here more than ${QUEUE.WAIT_MIN} days pass ${pct((QUEUE.share[S.sid] || [])[0])} of the sample</span>
    <svg width="18" height="12"><rect x="1" y="1" width="16" height="10" fill="${C.brickTint}" stroke="${C.brick}" stroke-width="2.5"/></svg><span>piled up: more than ${pct((QUEUE.share[S.sid] || [])[1])} of the sample</span>
    <svg width="18" height="12"><rect x="1" y="1" width="16" height="10" fill="none" stroke="${C.mustard}" stroke-width="2" stroke-dasharray="4 3"/></svg><span>a step the change touches</span>
    <svg width="18" height="12"><line x1="0" y1="6" x2="18" y2="6" stroke="${C.brown}" stroke-width="3"/></svg><span>return: back to primary care</span></div>
    <p>A pile is sampled patients who are waiting at the same point in their own pathway (the clock is days since each patient's first contact, not the calendar). The queue over the calendar year is the Details layer "queue over the year".</p>`;
}
function waitBasisNote() {
  const sc = D.scenarios.find(s => s.id === S.sid), wb = sc && sc.wait_basis;
  if (!wb || !wb.groups) return '';
  const P = wb.groups.published, A = wb.groups.assumption;
  const lst = G => G.steps.map(r => `${esc(r.step)} ${f1(r.days)} d`).join(', ');
  const src = G => G.steps.map(r => `${esc(r.step)}: ${esc(r.source)}`).join('; ');
  return `<div class="wb" id="wait-basis" style="margin-top:8px;font-size:12px"><b style="color:${C.ink}">Where these waits come from (today's pathway)</b>
    <p style="margin:4px 0"><b>From our simulation:</b> the days are computed from the simulated patients' paths.</p>
    <p style="margin:4px 0"><b>Set from published figures:</b> ${pct(P.share_of_waiting)} of the waiting days (${lst(P)}). <span title="${src(P)}" style="text-decoration:underline dotted">Sources</span>: ${src(P)}.</p>
    <p style="margin:4px 0"><b>Our assumption or placeholder:</b> ${pct(A.share_of_waiting)} of the waiting days (${lst(A)}).</p>
    <p style="margin:4px 0">${esc(wb.statement)}</p></div>`;
}
function lostCard() {
  const [A, B] = S.panes.map(p => p.P.F);
  // steps that appear on the graph in several variants (e.g. PET-CT ordered early or late) are added up under one name
  const group = F => {
    const by = {}, nodeShort = {};
    F.graph.nodes.forEach(n => { nodeShort[n.id] = n.short; });
    F.time_lost.forEach(t => {
      const k = nodeShort[t.node] || t.label, g = by[k] = by[k] || {wait: 0, wait_share: 0};
      g.wait += t.wait; g.wait_share += t.wait_share;
    });
    return by;
  };
  const ga = group(A), gb = group(B);
  const names = [...new Set(Object.keys(ga).concat(Object.keys(gb)))];
  const rows = names.map(k => ({k, a: ga[k], b: gb[k]}))
    .sort((x, y) => Math.max(y.a ? y.a.wait : 0, y.b ? y.b.wait : 0) - Math.max(x.a ? x.a.wait : 0, x.b ? x.b.wait : 0)).slice(0, 7);
  const mx = Math.max(.1, ...rows.map(r => Math.max(r.a ? r.a.wait : 0, r.b ? r.b.wait : 0)));
  const bar = (v, c) => v == null ? `<div class="bar2"><em style="color:${C.ink3}">not on path</em></div>` : `<div class="bar2"><i style="width:${100 * v / mx}%;--c:${c}"></i><em>${f1(v)} d</em></div>`;
  let h = `<div class="card"><h3>Where time is lost</h3><p>Days a treated cancer patient spends waiting at each step on their critical path, averaged over patients. Click a step to find it on the graph.</p><div class="lost">`;
  rows.forEach(r => {
    h += `<div class="nm" data-hl="${esc(r.k)}">${esc(r.k)}<span>${r.a ? pct(r.a.wait_share) : '–'} → ${r.b ? pct(r.b.wait_share) : '–'} of path</span></div>${bar(r.a ? r.a.wait : null, C.faint)}${bar(r.b ? r.b.wait : null, C.ink)}`;
  });
  const tot = g => Object.values(g).reduce((s, t) => s + t.wait, 0);
  h += `</div><p style="margin-top:10px">In our model, waiting adds up to <b>${f1(tot(ga))} d</b> (${esc(sideName(0).toLowerCase())}, grey bars) and <b>${f1(tot(gb))} d</b> (${esc(sideName(1).toLowerCase())}, black bars), per treated cancer patient.</p>`;
  h += waitBasisNote();
  return h + '</div>';
}
function validationCard() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  if (!sc.published) return '';
  const find = k => sc.variants.find(v => v.key === k);
  const g = k => { const v = find(k); return v ? v.flow.metrics.share_within_target : null; };
  const N = (window.START_DATA && window.START_DATA.norway) || null;
  const P = N && N.all_settings && N.all_settings.pred;
  const rng = o => o ? `${pct(o.min)} to ${pct(o.max)}` : null;
  const row = (what, sim, pub, tag, col) => `<tr><td>${what}</td><td style="color:${C.ink}">${pct(sim, 1)}</td><td>${pub}</td><td style="color:${col}">${tag}</td></tr>`;
  let h = `<div class="card trace"><h3>Check against the published study</h3>
    <table><tr><th>Pathway</th><th>Simulated</th><th>Published</th><th></th></tr>
    ${row('Observed', g('observed'), pct(sc.published.observed_share), 'fitted', C.ink)}
    ${row("Authors' reorder", g('authors'), pct(sc.published.authors_estimate_share) + '*', 'predicted', C.ink)}
    ${row('Faster scanner only', g('faster_pet'), pct(sc.published.faster_pet_share), 'over-predicted', C.mustard)}
    </table>
    <p style="margin-top:8px">Share of patients treated within ${sc.target_days} days, Stokstad et al. 2019 (one Norwegian centre). The model was fitted to the observed pathway only. *${pct(sc.published.authors_estimate_share)} is the authors' own model estimate, not an observed result.</p>`;
  h += `<p><b style="color:${C.ink}">The ${pct(sc.published.authors_estimate_share)} match is the best fit, not the only one.</b> ` +
    (P ? `Over all ${N.all_settings.accepted} settings that fit the observed data the authors' pathway comes out at ${rng(P.optimal)}, typically about ${pct(P.optimal.median)}. ` : '') +
    `The model also over-predicts the faster scanner alone (${pct(g('faster_pet'))} against ${pct(sc.published.faster_pet_share)} published${P ? '; ' + rng(P.faster_pet) + ' across settings' : ''}). Trust the ranking of reorderings, not their exact size.</p>`;
  const ne = find('suggested');
  const O = N && N.optimiser, ob = O && O.bands, SC = O && O.structure;
  const rb = x => x ? `${pct(x.min)} to ${pct(x.max)}, median ${pct(x.median)}` : null;
  if (SC) h += `<p style="margin-top:8px"><b style="color:${C.ink}">Structure check.</b> Read literally (treatment does not wait for the tissue sample; PET-CT ordered at the first visit, not at triage), the authors' pathway gives a median of ${pct(SC.literal_median)} over the ${SC.settings} settings, with ${SC.literal_in_published_ci} of ${SC.settings} inside the published ${pct(SC.published_ci[0])} to ${pct(SC.published_ci[1])} (the shipped version: ${SC.shipped_in_published_ci}). Only the paper's text was read, not its figures; the observed pathway was not recalibrated under that reading; the shipped scenario is unchanged.</p>`;
  if (ne && O) {
    const VP = window.START_DATA && window.START_DATA.validation && window.START_DATA.validation.published, ci = VP && VP.optimal && VP.optimal.ci95;
    h += `<p style="margin-top:8px"><b style="color:${C.ink}">What our optimiser did (a plausibility check).</b> Started from the observed pathway, with no new equipment and without being told the answer, it arrived at the authors' three timing changes plus a fourth, overlapping change: plan tissue sampling when the referral is triaged. That fourth change <b>needs a clinical check</b>. It did not improve on the authors' redesign.</p>
    <p><b style="color:${C.ink}">No new equipment:</b> <b style="color:${C.ink}">${pct(g('suggested'))}</b> at the best fit; ${rb(ob.optimiser_no_equipment)} over the ${O.n_settings} settings that fit (today: ${rb(ob.observed)}). Better than today in ${O.counts.noeq_beats_observed} of ${O.n_settings}, but better than the faster scanner alone in only ${O.counts.noeq_beats_scanner_alone} of ${O.n_settings}.</p>
    <p>The authors' ${pct(sc.published.authors_estimate_share)}${ci ? ` (${pct(ci[0])} to ${pct(ci[1])})` : ''} includes the shorter PET-CT wait; the optimiser's pathway does not, so the two are not a like-for-like pair.</p>`;
  }
  return h + '</div>';
}
function decisionsCard() {
  const [A, B] = S.panes.map(p => p.P.F);
  const ids = A.graph.nodes.filter(n => n.kind === 'decision').map(n => n.id);
  B.graph.nodes.forEach(n => { if (n.kind === 'decision' && !ids.includes(n.id)) ids.push(n.id); });
  let h = `<div class="card"><h3>Decisions: what was chosen</h3><p>Share of patients who got each option (bars) and the mean probability the decision source offered (number). Grey bars: ${esc(sideName(0).toLowerCase())}; black bars: ${esc(sideName(1).toLowerCase())}.</p>`;
  ids.forEach(id => {
    const da = A.decisions[id], db = B.decisions[id], F = da ? A : B, nd = F.graph.nodes.find(n => n.id === id), d0 = da || db;
    if (!d0 || !(d0.n || (db && db.n))) return;
    h += `<div class="dec"><div class="nm">${esc(nd.short)} <span class="m" style="font:10px var(--mono);color:${C.ink3}">${fmt(da ? da.n : 0)} / ${fmt(db ? db.n : 0)}</span></div>`;
    d0.options.forEach(o => {
      const sa = da && da.n ? da.share[o] : null, sb = db && db.n ? db.share[o] : null;
      const mk = (s, c, mp) => s == null ? '<div class="bar2"></div>' : `<div class="bar2"><i style="width:${100 * s}%;--c:${c}"></i><em>${pct(s)}${mp != null ? ' · p' + (100 * mp).toFixed(0) : ''}</em></div>`;
      h += `<div class="row"><span>${esc(shortOpt(F, o, 14))}</span>${mk(sa, C.faint, da ? da.mean_probability[o] : null)}${mk(sb, C.ink, db ? db.mean_probability[o] : null)}</div>`;
    });
    h += '</div>';
  });
  h += `<p>Where the pathway has a choice, a decision source picks the option. Here it is the scenario's rule table, a stand-in until the decision model is attached.</p></div>`;
  return h;
}
function traceCard() {
  const pa = S.panes[S.sel.pane], F = pa.P.F, d = pa.dots.find(x => x.idx === S.sel.idx), p = d.p;
  const nm = id => { const n = F.graph.nodes.find(x => x.id === id); return n ? n.short : id; };
  const rows = p.v.slice().sort((a, b) => a[1] - b[1]);
  let h = `<div class="card trace"><h3>Patient ${p.id} <span class="x">close</span></h3>
    <div class="sum"><b>${p.cancer ? 'Has cancer' : 'No cancer'}</b> · ${esc(p.g.replace('_', '-'))} · age ${p.age}<br>
    ${p.out === 'treatment' ? `treatment starts on <b>day ${f1(p.t_treat)}</b> (${p.t_treat <= F.target_days ? 'within' : 'after'} the ${F.target_days}-day target)` :
      p.out === 'discharged' ? `discharged on <b>day ${f1(p.t_exit)}</b>${p.cancer ? ' <b style="color:' + C.brick + '">cancer not found</b>' : ''}` : esc(String(p.out))}
    ${p.t_diag != null ? `<br>diagnosis on day ${f1(p.t_diag)}` : ''}</div>
    <table><tr><th>Step</th><th>Waited</th><th>Took</th><th>Result</th></tr>`;
  rows.forEach(r => {
    h += `<tr class="${r[6] ? 'crit' : ''}"><td>${esc(nm(r[0]))}</td><td>${f1(r[2] - r[1])} d</td><td>${f1(r[4] - r[2])} d</td><td>${r[5] == null ? (F.graph.nodes.find(x => x.id === r[0]).kind === 'exit' ? '' : 'unclear') : r[5] ? 'positive' : 'negative'}</td></tr>`;
  });
  h += '</table>';
  if (p.c.length) {
    h += `<p style="margin:10px 0 4px;font:600 9px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:${C.ink3}">Decisions</p>`;
    p.c.forEach(c => {
      h += `<p style="margin:0 0 4px"><b style="color:${C.ink}">${esc(nm(c[0]))}</b> at day ${f1(c[1])}: chose <b style="color:${C.ink}">${esc(nm(c[2]))}</b><br><span style="font:10.5px var(--mono)">${Object.entries(c[4]).map(([o, q]) => `${esc(shortOpt(F, o, 22))} ${pct(q)}`).join(' · ')}</span></p>`;
    });
  }
  h += `<p style="margin-top:8px"><span style="color:${C.mustard}">●</span> on the critical path: the steps that set this patient's time to the end.</p></div>`;
  return h;
}
function aboutCard() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  const V = S.panes.map(p => p.V);
  let h = `<div class="card"><h3>What you are looking at</h3>
    <p>Each dot is one simulated patient, starting on day 0 at first contact. Dots wait (grey, darker the longer they wait) and are seen (black) at the steps; treated patients land beside the last step, as a filled dot if in time and a ring if late. A brick ring is a cancer that was sent home.</p>
    <p>Today: the pathway as it runs now (or the first one you picked under Compare other pathways). After the change: the same patients on the changed pathway (or the second one you picked). Numbers in the headline card and on hover count every simulated patient (${fmt(S.panes[0].P.F.totals.n)}); the moving dots are a sample of ${S.panes[0].P.F.cohort.size}, and so are the counts under Details, Counts now. The clock is days since each patient's own first contact.</p>${S.panes[0].P.F.cohort.strata.other ? `<p>The sample has ${S.panes[0].P.F.cohort.strata.cancer} patients with cancer and ${S.panes[0].P.F.cohort.strata.other} without, so that some reach treatment; in the full run only ${pct(S.panes[0].P.F.totals.n_cancer / S.panes[0].P.F.totals.n, 1)} have cancer.</p>` : ''}`;
  V.forEach((v, i) => { if (v.note) h += `<p><b style="color:${i ? C.ink : C.faint}">${esc(v.label)}.</b> ${esc(v.note)}</p>`; });
  const ch = V[1].changes && V[1].changes.length ? V[1].changes : null;
  if (ch) h += `<p><b>Changes in the pathway after the change</b><br>${ch.map(esc).join('<br>')}</p>`;
  return h + '</div>';
}

function renderNote() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  const [A, B] = S.panes.map(p => p.P.F);
  let h = '';
  const st = A.cohort.strata;
  h += `<b>All patients are simulated.</b> The graph counts all ${fmt(A.totals.n)} simulated patients (${fmt(A.totals.cohorts)} cohorts); the moving dots are a sample of ${A.cohort.size} (${st.cancer} with cancer${st.other ? ', ' + st.other + ' without' : ''}), so the live counts under Details count the sample, not the whole run. Time on the slider is days since each patient's first contact. `;
  if (sc.synthetic) h += `<b>This is a synthetic Finnish county</b>, not measured Finnish data: parameters are sourced or labelled as assumptions (see the dashboard). The change shown reorders steps only (no new capacity, no fast lane).`;
  if (sc.published) {
    h += `<b>Norway:</b> see Details, Check against the published study. `;
    const O = window.START_DATA && window.START_DATA.norway && window.START_DATA.norway.optimiser, bd = O && O.bands;
    if (S.keys[0] === 'authors' && S.keys[1] === 'suggested')
      h += `<b>About this pair:</b> not like for like. The authors' pathway, as in the paper, includes their shorter PET-CT wait; the optimiser's pathway assumes no new equipment. Our version of the authors' pathway also makes treatment wait for a tissue sample that only starts after the tumour board, which the paper does not. `;
    else if (S.keys[0] === 'observed' && S.keys[1] === 'suggested' && bd)
      h += `<b>About this pair:</b> today against the optimiser's pathway with no new equipment, at the best-fitting setting. Over the ${O.n_settings} settings that fit the observed data the optimiser gives ${pct(bd.optimiser_no_equipment.min)} to ${pct(bd.optimiser_no_equipment.max)} (median ${pct(bd.optimiser_no_equipment.median)}) against ${pct(bd.observed.min)} to ${pct(bd.observed.max)} today. `;
  }
  h += `Findings are simulated and are not clinical advice.`;
  return h;
}
/* ------------------------------------------------------------------ playback */
function sizeToTime() {
  const sl = $('#slider');
  sl.max = S.H; sl.step = S.H / 1000;
  const sp = $('#speed'), list = SPEEDS.includes(S.speed) ? SPEEDS : SPEEDS.concat([S.speed]).sort((a, b) => a - b);
  sp.innerHTML = list.map(m => `<option value="${m}" ${m === S.speed ? 'selected' : ''}>${m} days/s</option>`).join('');
}
function setPlaying(p) {
  S.playing = p;
  $('#play').textContent = p ? 'Pause' : (S.t >= S.H ? 'Replay' : 'Play');
}
let last = performance.now(), lastSlow = 0;
function frame(now) {
  const dt = Math.min(.25, (now - last) / 1000); last = now;
  if (S.playing) {
    S.t += dt * S.speed;
    if (S.t >= S.H) { S.t = S.H; setPlaying(false); }
  }
  $('#slider').value = S.t;
  const dd = String(Math.round(S.t)).padStart(3, '0');
  if ($('#day').textContent !== dd) $('#day').textContent = dd;
  const vis = visibleSides();
  S.panes.forEach(pa => { if (vis.includes(pa.side)) drawPane(pa, S.t); });
  if (now - lastSlow > 250) {
    lastSlow = now;
    if (S.drawer === 'counts') { S.panes.forEach(pa => { if (!vis.includes(pa.side)) drawPane(pa, S.t); }); openDrawer('counts'); }
    refreshPinned();
  }
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ start */
function init() {
  readTokens();
  if (window.Site) { Site.nav('simulator'); Site.footer(); }
  if (!D) { $('#panes').innerHTML = '<p class="caption">data/flow_bundle.js not found. Run: python demo/export_flow.py</p>'; return; }
  const q = new URLSearchParams(location.search);
  S.sid = q.get('s') || D.scenarios[0].id;
  if (!D.scenarios.find(s => s.id === S.sid)) S.sid = D.scenarios[0].id;
  if (q.get('layer') && LAYERS.some(l => l[0] === q.get('layer'))) S.layer = q.get('layer');
  // ?compare, ?left/?right (a pair was asked for) and ?view= open with Optimise already applied
  const view = q.get('view');
  S.opt = q.has('compare') || q.has('left') || q.has('right') || view === 'both' || view === 'left' || view === 'right';
  S.split = view === 'both';
  S.side = view === 'left' ? 0 : 1;
  if (!S.opt) S.side = 0;
  if (q.has('paused')) S.playing = false;
  if (q.get('day')) S.t = Math.max(0, +q.get('day') || 0);
  const sp = parseFloat(q.get('speed'));
  if (sp > 0 && sp <= 64) S.speed = sp;
  S.big = q.has('large');
  S.dense = q.has('numbers');
  S.tall = S.dense;
  $('#scn').innerHTML = D.scenarios.map(s => `<option value="${s.id}">${esc(s.id === 'norway' ? 'Norway · published study' : 'Finland · synthetic')}</option>`).join('') +
    '<option value="__encounter">Primary-care loop ›</option>';
  setScenario(S.sid, q);
  S.t = Math.min(S.t, S.H);
  $('#scn').addEventListener('change', e => {
    if (e.target.value === '__encounter') { location.href = 'encounter.html'; return; }
    S.t = 0; S.opt = false; S.side = 0; S.split = false; setPlaying(true); closeDrawer(); unpin(); setScenario(e.target.value);
  });
  $('#play').onclick = () => { if (S.t >= S.H) S.t = 0; setPlaying(!S.playing); };
  $('#slider').oninput = e => { S.t = +e.target.value; setPlaying(false); };
  $('#speed').onchange = e => { S.speed = +e.target.value; };
  $('#optimise').onclick = () => { toggleMenu(false); optimise(); };
  $('#optcard').addEventListener('click', () => { if (S.opt) $('#optcard').hidden = true; });
  $('#flip-today').onclick = () => flip(0);
  $('#flip-after').onclick = () => flip(1);
  $('#details').onclick = e => { e.stopPropagation(); toggleMenu(); };
  $('#menu').addEventListener('change', e => {
    const t = e.target;
    if (t.name === 'layer') { S.layer = t.value; unpin(); S.panes.forEach(renderPane); renderMenu(); return; }
    const k = t.dataset.opt;
    if (k === 'deltas') { S.deltas = t.checked; if (S.deltas && !S.opt) { S.opt = true; S.side = 1; showPanes(); renderChrome(); } else S.panes.forEach(renderPane); }
    else if (k === 'split') { S.split = t.checked; if (S.split) S.opt = true; showPanes(); renderChrome(); }
    else if (k === 'dense') { S.dense = t.checked; S.tall = S.dense; buildPanes(); }
    else if (k === 'big') { S.big = t.checked; S.panes.forEach(fit); }
  });
  $('#menu').addEventListener('click', e => {
    e.stopPropagation();
    const b = e.target.closest('[data-drawer]');
    if (b) { toggleMenu(false); openDrawer(b.dataset.drawer); }
  });
  $('#drawer').addEventListener('click', e => { if (e.target.closest('[data-close]')) closeDrawer(); });
  document.addEventListener('click', e => {
    if (!$('#menu').hidden && !e.target.closest('#menu') && !e.target.closest('#details')) toggleMenu(false);
    if (e.target.closest && e.target.closest('button')) e.target.closest('button').blur();
  });
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT' && e.target.type !== 'range') return;
    if (e.code === 'Space') { e.preventDefault(); $('#play').click(); }
    else if (e.key === 'r') { S.t = 0; setPlaying(true); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); S.t = Math.min(S.H, S.t + S.H / 100); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); S.t = Math.max(0, S.t - S.H / 100); }
    else if (e.key === '+' || e.key === '=') { S.big = true; S.panes.forEach(fit); }
    else if (e.key === '-') { S.big = false; S.panes.forEach(fit); }
    else if (e.key === 'Escape') {
      if (closeOptCard()) return;
      if (!$('#menu').hidden) { toggleMenu(false); return; }
      if (S.pin) { unpin(); return; }
      closeDrawer();
    }
  });
  let rz = 0;
  window.addEventListener('resize', () => { cancelAnimationFrame(rz); rz = requestAnimationFrame(() => S.panes.forEach(pa => { fit(pa); drawPane(pa, S.t); })); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => S.panes.forEach(fit));
  setPlaying(S.playing);
  requestAnimationFrame(frame);
}
function setScenario(sid, q) {
  S.sid = sid;
  const s = sc();
  S.keys = [s.default_pair[0], s.default_pair[1]];
  if (q && q.get('left') && variantOf(s, q.get('left'))) S.keys[0] = q.get('left');
  if (q && q.get('right') && variantOf(s, q.get('right'))) S.keys[1] = q.get('right');
  S.sel = null; S.hl = null;
  document.title = 'Simulator: ' + (sid === 'norway' ? 'a Norwegian hospital, rebuilt from a published study' : 'a synthetic Finnish county');
  buildPanes();
}
window.__flow = S;
init();
})();
