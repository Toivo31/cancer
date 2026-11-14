/* Flowchart simulation page. No build step; data comes from data/flow_bundle.js (window.FLOW_DATA).
   Format of one flow document: docs/platform/flow-format.md (flow/1). Everything shown is simulated. */
(function () {
'use strict';
const D = window.FLOW_DATA;
const $ = (s, r) => (r || document).querySelector(s);
const C = {night: '#0A0F14', panel: '#16222F', line: '#2C3F52', text: '#EAF1F8', muted: '#A8B8C9', dim: '#6F8296',
  coral: '#FF9A7A', mint: '#55E3B0', amber: '#FFC04D', blue: '#62B0FF', red: '#FF5D73'};
let NODE_W = 108, NODE_H = 42, SLOT = 118, LAYER_H = 76;
const MARGIN_X = 12, MARGIN_T = 44;
const fmt = n => n == null ? '–' : Math.round(n).toLocaleString('en-US');
const f1 = x => x == null ? '–' : (Math.round(x * 10) / 10).toFixed(1);
const pct = (x, d) => x == null ? '–' : (100 * x).toFixed(d == null ? 0 : d) + '%';
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

const LAYERS = [['flow', 'Flow'], ['time', 'Time'], ['queues', 'Queues'], ['decisions', 'Decisions']];
const S = {sid: null, keys: [null, null], layer: 'flow', t: 0, playing: true, rate: 1, compare: false, split: true,
  sel: null, hl: null, panes: [], H: 100, base: 4};

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
  NODE_H = dense ? 38 : 42; LAYER_H = dense ? 56 : 76;
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
  return {d: `M${x1},${y1} C${x1},${y1 + dy} ${x2},${y2 - dy} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2};
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

function globalMax(key) {
  let m = 1e-9;
  S.panes.forEach(pa => { const f = key(pa.P.F); if (f > m) m = f; });
  return m;
}

function nodeMetric(pa, id) {
  const st = pa.P.F.steps[id];
  return st || null;
}

function renderPane(pa) {
  const F = pa.P.F, pos = pa.pos, layer = S.layer, side = pa.side;
  const other = S.panes[1 - side] ? S.panes[1 - side].P.F : null;
  const accent = side === 0 ? C.coral : C.mint;
  const maxE = globalMax(f => Math.max(1, ...f.graph.edges.map(e => e.n)));
  const maxWait = globalMax(f => Math.max(.1, ...Object.values(f.steps).map(s => s.wait_median || 0)));
  const maxQ = globalMax(f => Math.max(.1, ...Object.values(f.queues).map(q => q.peak)));
  let svg = `<svg viewBox="0 0 ${pa.W} ${pa.H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Flowchart">`;
  const otherEdges = other ? new Set(other.graph.edges.map(e => e.id)) : new Set();
  const myEdges = new Set(F.graph.edges.map(e => e.id));
  const selNodes = S.sel && S.sel.pane === side ? pa.selNodes : null;
  // edges
  let labels = '';
  F.graph.edges.forEach(e => {
    const a = pos[e.source], b = pos[e.target];
    if (!a || !b) return;
    const c = curve(a, b);
    const w = e.n ? .8 + 5.2 * Math.sqrt(e.n / maxE) : 1;
    const isNew = S.compare && !otherEdges.has(e.id);
    const col = isNew ? C.mint : accent;
    const op = e.n ? (.2 + .4 * Math.sqrt(e.n / maxE)) : .12;
    const onSel = selNodes && selNodes.edges.has(e.id);
    svg += `<path d="${c.d}" fill="none" stroke="${onSel ? C.amber : col}" stroke-opacity="${onSel ? .95 : op}" stroke-width="${onSel ? Math.max(w, 2.5) : w}" ${e.n ? '' : 'stroke-dasharray="3 4"'} ${isNew ? 'stroke-dasharray="6 3"' : ''}/>`;
    if (e.n > .2 * maxE && (layer === 'flow' || layer === 'decisions') && Math.abs(b.y - a.y) < LAYER_H * 1.6)
      labels += `<text x="${c.mx + 5}" y="${c.my + 3}" class="mono" font-size="9.5" fill="${C.muted}" stroke="${C.panel}" stroke-width="3" paint-order="stroke">${fmt(e.n)}</text>`;
  });
  if (S.compare && other) {
    other.graph.edges.forEach(e => {
      if (myEdges.has(e.id)) return;
      const a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      svg += `<path d="${curve(a, b).d}" fill="none" stroke="${C.coral}" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="2 5"/>`;
    });
  }
  svg += labels;
  // nodes
  const maxCrit = globalMax(f => Math.max(.1, ...Object.values(f.steps).map(s => s.critical_share || 0)));
  F.graph.nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const st = F.steps[n.id], dc = F.decisions[n.id], ex = F.exits[n.id];
    const x = p.x - NODE_W / 2, y = p.y - NODE_H / 2;
    let fill = '#0E161F', stroke = C.line, sw = 1;
    if (n.kind === 'exit') { fill = n.outcome === 'treatment' ? 'rgba(85,227,176,.10)' : '#0E161F'; stroke = n.outcome === 'treatment' ? C.mint : C.dim; }
    if (n.kind === 'decision') stroke = C.blue;
    if (n.kind === 'milestone') stroke = C.muted;
    let line2 = '', spark = '';
    const otherSt = other && other.steps[n.id];
    if (layer === 'flow') {
      if (st) line2 = fmt(st.n) + ' patients';
      if (dc && dc.n) { const top = Object.entries(dc.share).sort((a, b) => b[1] - a[1])[0]; line2 = fmt(dc.n) + ' decisions'; }
    } else if (layer === 'time') {
      if (st && st.wait_median != null) {
        const a = clamp(Math.sqrt((st.wait_median || 0) / maxWait), 0, 1);
        fill = `rgba(255,192,77,${(.05 + .5 * a).toFixed(3)})`;
        stroke = a > .5 ? C.amber : C.line;
        line2 = `wait ${f1(st.wait_median)} d${st.critical_share ? ' · ' + pct(st.critical_share) : ''}`;
        if (st.critical_share) sw = 1 + 2.4 * Math.sqrt(st.critical_share / maxCrit);
      } else if (st) line2 = fmt(st.n) + ' patients';
    } else if (layer === 'queues') {
      const q = F.queues[n.id];
      if (q) {
        const a = clamp(Math.sqrt(q.mean / maxQ), 0, 1);
        fill = `rgba(98,176,255,${(.04 + .32 * a).toFixed(3)})`;
        const w = NODE_W - 12, h = 7, xs = q.y.length;
        let d = '';
        q.y.forEach((v, i) => { d += (i ? 'L' : 'M') + (x + 6 + w * i / (xs - 1)).toFixed(1) + ',' + (y + NODE_H - 3 - h * Math.min(1, v / maxQ)).toFixed(1); });
        spark = `<path d="${d}" fill="none" stroke="${C.blue}" stroke-width="1.2"/>`;
        line2 = `peak ${fmt(q.peak)} waiting`;
      } else if (st) line2 = fmt(st.n) + ' patients';
    } else if (layer === 'decisions') {
      if (n.kind === 'decision' && dc && dc.n) {
        const top = Object.entries(dc.share).sort((a, b) => b[1] - a[1]);
        line2 = `${pct(top[0][1])} ${shortOpt(F, top[0][0], 11)}`;
        stroke = C.blue; sw = 2; fill = 'rgba(98,176,255,.12)';
      } else { line2 = st ? fmt(st.n) : ''; }
    }
    if (S.compare && otherSt && side === 1 && st && (st.critical_wait != null) && otherSt.critical_wait != null) {
      const dlt = (st.critical_wait + st.critical_service) - (otherSt.critical_wait + otherSt.critical_service);
      const col = Math.abs(dlt) < .3 ? C.muted : dlt < 0 ? C.mint : C.coral;
      line2 = `<tspan fill="${col}" font-weight="700">${dlt > 0 ? '+' : '−'}${f1(Math.abs(dlt))} d</tspan> on path`;
      if (Math.abs(dlt) >= .3) stroke = col;
    }
    if (S.compare && side === 1 && !otherSt && !(other && other.decisions[n.id]) && n.kind !== 'exit') { stroke = C.mint; sw = 2; }
    if (S.compare && n.kind === 'exit' && ex && other && other.exits[n.id]) {
      const dn = ex.n - other.exits[n.id].n;
      if (side === 1 && dn) line2 = `<tspan fill="${dn > 0 ? C.mint : C.coral}" font-weight="700">${dn > 0 ? '+' : '−'}${fmt(Math.abs(dn))}</tspan> patients`;
    }
    if (n.kind === 'exit' && ex && !S.compare) line2 = fmt(ex.n) + ' patients' + (ex.n_cancer && ex.outcome !== 'treatment' ? ` (${fmt(ex.n_cancer)} cancer)` : '');
    if (selNodes && selNodes.nodes.has(n.id)) { stroke = C.amber; sw = 2; }
    if (S.hl === n.short) { stroke = C.text; sw = 2.5; }
    const lines = wrap(dn(F, n), 18);
    const ty = lines.length === 1 ? y + 15 : y + 13;
    const shape = n.kind === 'decision'
      ? `<rect x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H}" rx="21" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`
      : `<rect x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H}" rx="4" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
    svg += `<g data-id="${n.id}">${shape}`;
    lines.forEach((l, i) => { svg += `<text x="${p.x}" y="${ty + i * 11.5}" text-anchor="middle" font-size="10.5" font-weight="${n.kind === 'step' ? 600 : 700}" fill="${C.text}">${esc(l)}</text>`; });
    if (line2) svg += `<text x="${p.x}" y="${y + NODE_H - (spark ? 12 : 6)}" text-anchor="middle" class="mono" font-size="9" fill="${C.muted}">${line2}</text>`;
    svg += spark + '</g>';
  });
  svg += '</svg>';
  pa.svgBox.innerHTML = svg;
}

function dn(F, n) {
  if (!F._dup) { const c = {}; F.graph.nodes.forEach(x => { c[x.short] = (c[x.short] || 0) + 1; }); F._dup = c; }
  return F._dup[n.short] > 1 ? n.label : n.short;
}
function shortOpt(F, id, n) {
  const nd = F.graph.nodes.find(x => x.id === id);
  const s = nd ? dn(F, nd) : id;
  return s.length > n + 2 ? s.slice(0, n) + '…' : s;
}

/* ------------------------------------------------------------------ canvas dots */
const STATE_COL = {w: C.amber, s: C.blue, ok: C.mint, late: '#7B8FA3', home: '#4E6074'};
function drawPane(pa, t) {
  const cv = pa.cv, ctx = pa.ctx;
  const cw = pa.gw.clientWidth, ch = pa.gw.clientHeight, dpr = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(ch * dpr)) { cv.width = Math.round(cw * dpr); cv.height = Math.round(ch * dpr); }
  const k = cw / pa.W * dpr;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.setTransform(k, 0, 0, k, 0, 0);
  const Tt = Math.max(.8, S.H / 200), groups = {};
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
      draws.push({x: r.tr.x, y: r.tr.y, col: C.text, r: 2.4, d});
    } else {
      const kind = g.s === 0 ? 'w' : 's';
      counts[kind]++;
      (groups[g.n] = groups[g.n] || []).push({d, g, kind, arr: g.arr});
    }
  });
  pa.hitDots = [];
  const pile = pa.pileCache;
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
      let col = STATE_COL[o.kind] || C.muted, ring = false;
      if (o.kind === 'missed') { col = C.red; ring = true; }
      if (o.kind === 'w') {
        const wt = clamp((t - o.g.t0) / 30, 0, 1);
        col = `rgb(${mix([255, 192, 77], [255, 138, 60], wt).join(',')})`;
      }
      draws.push({x, y, col, r: ring ? 2.1 : ((big || isExit) ? 1.8 : 2.5), ring, d: o.d, kind: o.kind});
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
    if (o) { ctx.beginPath(); ctx.arc(o.x, o.y, 6.5, 0, 6.2832); ctx.strokeStyle = C.text; ctx.lineWidth = 1.4; ctx.stroke(); }
  }
  pa.counts = counts;
}

function updateCounters(pa) {
  const c = pa.counts;
  pa.counterBox.innerHTML = `<span style="color:${C.dim}">sample of ${c.n}:</span>` +
    `<span><i style="background:${C.amber}"></i>waiting <b>${c.w}</b></span>` +
    `<span><i style="background:${C.blue}"></i>served <b>${c.s}</b></span>` +
    `<span><i style="background:${C.mint}"></i>treated on time <b>${c.ok}</b></span>` +
    `<span><i style="background:#7B8FA3"></i>treated late <b>${c.late}</b></span>` +
    `<span><i style="background:#4E6074"></i>discharged <b>${c.home}</b></span>` +
    (pa.hasMissed ? `<span><i style="border:1.5px solid ${C.red}"></i>cancer missed <b>${c.missed}</b></span>` : '');
}

/* ------------------------------------------------------------------ panes */
function variantOf(sc, key) { return sc.variants.find(v => v.key === key); }

function buildPanes() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  const flows = S.keys.map(k => variantOf(sc, k).flow);
  const lay = layoutUnion(flows);
  const root = $('#panes');
  root.className = 'panes' + (S.view === 'both' ? ' split' : '');
  root.innerHTML = '';
  S.panes = [];
  S.H = Math.max(...flows.map(f => f.cohort.horizon));
  [0, 1].forEach(side => {
    const V = variantOf(sc, S.keys[side]);
    const hidden = S.view !== 'both' && side !== (S.view === 'left' ? 0 : 1);
    const el = document.createElement('section');
    el.className = 'pane ' + (side ? 'right' : 'left');
    el.style.display = hidden ? 'none' : '';
    const opts = sc.variants.map(v => `<option value="${v.key}" ${v.key === S.keys[side] ? 'selected' : ''}>${esc(v.label)}</option>`).join('');
    el.innerHTML = `<div class="phead"><div class="sel"><span class="tag">${side ? 'After the change' : 'Today'} <span class="delta" data-k="delta"></span></span><select data-side="${side}">${opts}</select></div>
      <div class="big" data-k="big"></div><div class="kv" data-k="kv"></div></div>
      <div class="counters" data-k="counters"></div>
      <div class="gwrap"><div data-k="svg"></div><canvas></canvas><div class="hit"></div></div>`;
    root.appendChild(el);
    const P = prepFlow(V.flow);
    const pa = {side, el, P, pos: lay.pos, W: lay.W, H: lay.H, V, sc,
      svgBox: $('[data-k=svg]', el), gw: $('.gwrap', el), cv: $('canvas', el), hit: $('.hit', el),
      counterBox: $('[data-k=counters]', el), counts: {}, hitDots: [], selNodes: null};
    pa.ctx = pa.cv.getContext('2d');
    pa.dots = prepPatients(P, lay.pos);
    pa.hasMissed = pa.dots.some(d => d.missed);
    const arrCache = new Map();
    pa.arrive = (d, g) => g.arr;
    S.panes.push(pa);
    const F = V.flow;
    $('[data-k=big]', el).innerHTML = `<span class="num">${(100 * F.metrics.share_within_target).toFixed(1)}</span><small>%</small>`;
    $('[data-k=kv]', el).innerHTML = `<span>treated within ${F.target_days} days</span><span><b>${f1(F.metrics.median_days_to_treatment)} d</b> median to treatment</span><span><b>${fmt(F.totals.missed_cancers)}</b> cancers sent home · ${fmt(F.totals.n)} patients</span>`;
    $('select', el).addEventListener('change', e => { S.keys[side] = e.target.value; S.sel = null; buildPanes(); });
    wireHit(pa);
  });
  S.panes.forEach(fit);
  const a = S.panes[0].V.flow.metrics.share_within_target, b = S.panes[1].V.flow.metrics.share_within_target;
  const dl = $('[data-k=delta]', S.panes[1].el);
  const d = 100 * (b - a);
  dl.textContent = (d >= 0 ? '+' : '−') + Math.abs(d).toFixed(1) + ' pp vs left';
  dl.style.color = d >= 0 ? C.mint : C.coral; dl.style.borderColor = d >= 0 ? C.mint : C.coral;
  $('[data-k=delta]', S.panes[0].el).style.display = 'none';
  S.panes.forEach(renderPane);
  sizeToTime();
  renderSide();
  renderNote();
  S.panes.forEach(pa => { drawPane(pa, S.t); updateCounters(pa); });
}

function fit(pa) {
  const w = pa.el.clientWidth - 2, availH = S.big ? 1e9 : Math.max(430, innerHeight - 310);
  const sc = clamp(Math.min(w / pa.W, availH / pa.H), .5, 1.05);
  pa.gw.style.width = Math.round(pa.W * sc) + 'px';
  pa.gw.style.margin = '0 auto';
}
function wireHit(pa) {
  const toLogical = ev => { const r = pa.gw.getBoundingClientRect(), k = pa.W / r.width; return {x: (ev.clientX - r.left) * k, y: (ev.clientY - r.top) * k}; };
  const nodeAt = pt => {
    for (const n of pa.P.F.graph.nodes) { const p = pa.pos[n.id]; if (Math.abs(pt.x - p.x) <= NODE_W / 2 && Math.abs(pt.y - p.y) <= NODE_H / 2) return n; }
    return null;
  };
  pa.hit.addEventListener('mousemove', ev => {
    const pt = toLogical(ev);
    const dot = nearestDot(pa, pt);
    if (dot) { pa.hit.style.cursor = 'pointer'; showTip(ev, dotTip(pa, dot)); return; }
    const n = nodeAt(pt);
    pa.hit.style.cursor = 'default';
    if (n) showTip(ev, nodeTip(pa, n)); else hideTip();
  });
  pa.hit.addEventListener('mouseleave', hideTip);
  pa.hit.addEventListener('click', ev => {
    const pt = toLogical(ev), dot = nearestDot(pa, pt);
    if (dot) selectPatient(pa.side, dot.d.idx);
    else { S.sel = null; S.panes.forEach(p => p.selNodes = null); S.panes.forEach(renderPane); renderSide(); }
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
  renderSide();
}

/* ------------------------------------------------------------------ tooltips */
const tip = $('#tip');
function showTip(ev, html) {
  tip.innerHTML = html; tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = clamp(ev.clientX + 16, 8, innerWidth - w - 8) + 'px';
  tip.style.top = clamp(ev.clientY + 14, 8, innerHeight - h - 8) + 'px';
}
function hideTip() { tip.hidden = true; }
function nodeTip(pa, n) {
  const F = pa.P.F, st = F.steps[n.id], dc = F.decisions[n.id], ex = F.exits[n.id];
  let h = `<b>${esc(n.label)}</b><br><span class="m">${esc(n.stage.replace('_', ' '))}${n.resource && F.resources[n.resource] ? ' · ' + esc(F.resources[n.resource].label) : ''}</span>`;
  if (st) {
    h += `<br><span class="m">${fmt(st.n)} patients (${fmt(st.n_cancer)} with cancer)</span>`;
    if (st.wait_median != null) {
      h += `<br><span class="m">wait: median ${f1(st.wait_median)} d, 90th pct ${f1(st.wait_p90)} d<br>service and report: median ${f1(st.service_median)} d</span>`;
      if (st.critical_n) h += `<br><span class="m">on the critical path for ${fmt(st.critical_n)} treated cancers: ${f1(st.critical_wait)} d waiting, ${f1(st.critical_service)} d service per patient (${pct(st.critical_share, 1)} of time to treatment)</span>`;
      const r = F.resources[n.resource];
      if (r && r.utilisation != null) h += `<br><span class="m">${esc(r.label)}: ${r.capacity_per_day ? r.capacity_per_day + ' a day, ' : ''}${pct(r.utilisation)} booked</span>`;
    }
  }
  if (dc && dc.n) {
    h += `<br><span class="m">${fmt(dc.n)} decisions. Chosen share (mean probability offered):</span>`;
    dc.options.forEach(o => { h += `<br><span class="m">${esc(shortOpt(F, o, 28))}: ${pct(dc.share[o])} (${dc.mean_probability[o] == null ? '–' : pct(dc.mean_probability[o])})</span>`; });
    h += ``;
  }
  if (ex) h += `<br><span class="m">${fmt(ex.n)} patients end here (${esc(String(ex.outcome).replace('_', ' '))})${ex.outcome !== 'treatment' && ex.n_cancer ? `, of whom ${fmt(ex.n_cancer)} had cancer` : ''}</span>`;
  return h;
}
function dotTip(pa, o) {
  const p = o.d.p;
  return `<b>Patient ${p.id}</b> <span class="m">(cohort ${p.cohort}, ${esc(p.g.replace('_', '-'))}, ${p.cancer ? 'has cancer' : 'no cancer'})</span><br><span class="m">click for the trace</span>`;
}

/* ------------------------------------------------------------------ side panel */
function renderSide() {
  const side = $('#side');
  let h = '';
  if (S.sel) h += traceCard();
  h += layerCard();
  h += lostCard();
  h += validationCard();
  if (S.layer === 'decisions') h += decisionsCard();
  h += aboutCard();
  side.innerHTML = h;
  side.querySelectorAll('[data-hl]').forEach(el => el.addEventListener('click', () => { S.hl = S.hl === el.dataset.hl ? null : el.dataset.hl; S.panes.forEach(renderPane); }));
  const x = $('.x', side);
  if (x) x.addEventListener('click', () => { S.sel = null; S.panes.forEach(p => p.selNodes = null); S.panes.forEach(renderPane); renderSide(); });
}
const HELP = {
  flow: ['Flow', 'Line thickness and the numbers show how many simulated patients took each connection. Exits show where patients end up.'],
  time: ['Time', 'Amber fill: median days a patient waits at the step. The number after it is the step\'s share of the time to treatment; a thicker outline means more of it.'],
  queues: ['Queues', 'The line in each step is the number of patients waiting there over the simulated year (not the replay clock); peak is its highest point. Dots above a step are patients waiting now.'],
  decisions: ['Decisions', 'Rounded steps are decision points. They show the share of patients who got each option; the side panel compares today with after.']};
function layerCard() {
  const [t, d] = HELP[S.layer];
  return `<div class="card"><h3>Layer: ${t}</h3><p style="margin:0">${d}</p></div>`;
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
  const bar = (v, c) => v == null ? `<div class="bar2"><em style="color:${C.dim}">not on path</em></div>` : `<div class="bar2"><i style="width:${100 * v / mx}%;--c:${c}"></i><em>${f1(v)} d</em></div>`;
  let h = `<div class="card"><h3>Where time is lost</h3><p>Days a treated cancer patient spends waiting at each step on their critical path, averaged over patients. Click a step to find it on the graph.</p><div class="lost">`;
  rows.forEach(r => {
    h += `<div class="nm" data-hl="${esc(r.k)}">${esc(r.k)}<span>${r.a ? pct(r.a.wait_share) : '–'} → ${r.b ? pct(r.b.wait_share) : '–'} of path</span></div>${bar(r.a ? r.a.wait : null, C.coral)}${bar(r.b ? r.b.wait : null, C.mint)}`;
  });
  const tot = g => Object.values(g).reduce((s, t) => s + t.wait, 0);
  h += `</div><p style="margin-top:10px">Waiting adds up to <b style="color:${C.coral}">${f1(tot(ga))} d</b> on the left and <b style="color:${C.mint}">${f1(tot(gb))} d</b> on the right, per treated cancer patient.</p></div>`;
  return h;
}
function validationCard() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  if (!sc.published) return '';
  const g = k => sc.variants.find(v => v.key === k).flow.metrics.share_within_target;
  const row = (what, sim, pub, tag, col) => `<tr><td>${what}</td><td style="color:${C.text}">${pct(sim, 1)}</td><td>${pub}</td><td style="color:${col}">${tag}</td></tr>`;
  return `<div class="card trace"><h3>Check against the published study</h3>
    <table><tr><th>Pathway</th><th>Simulated</th><th>Published</th><th></th></tr>
    ${row('Observed', g('observed'), pct(sc.published.observed_share), 'fitted', C.mint)}
    ${row("Authors' reorder", g('authors'), pct(sc.published.authors_estimate_share) + '*', 'predicted', C.mint)}
    ${row('Faster scanner only', g('faster_pet'), pct(sc.published.faster_pet_share), 'missed', C.amber)}
    </table>
    <p style="margin-top:8px">Share of 100 patients treated within 42 days, Stokstad et al. 2019 (one Norwegian centre). The model was fitted to the observed pathway only. *80% is the authors' own model estimate, not an observed result.</p></div>`;
}
function decisionsCard() {
  const [A, B] = S.panes.map(p => p.P.F);
  const ids = A.graph.nodes.filter(n => n.kind === 'decision').map(n => n.id);
  B.graph.nodes.forEach(n => { if (n.kind === 'decision' && !ids.includes(n.id)) ids.push(n.id); });
  let h = `<div class="card"><h3>Decisions: what was chosen</h3><p>Share of patients who got each option (bars) and the mean probability the decision source offered (number). Today vs after the change.</p>`;
  ids.forEach(id => {
    const da = A.decisions[id], db = B.decisions[id], F = da ? A : B, nd = F.graph.nodes.find(n => n.id === id), d0 = da || db;
    if (!d0 || !(d0.n || (db && db.n))) return;
    h += `<div class="dec"><div class="nm">${esc(nd.short)} <span class="m" style="font:10px var(--mono);color:${C.dim}">${fmt(da ? da.n : 0)} / ${fmt(db ? db.n : 0)}</span></div>`;
    d0.options.forEach(o => {
      const sa = da && da.n ? da.share[o] : null, sb = db && db.n ? db.share[o] : null;
      const mk = (s, c, mp) => s == null ? '<div class="bar2"></div>' : `<div class="bar2"><i style="width:${100 * s}%;--c:${c}"></i><em>${pct(s)}${mp != null ? ' · p' + (100 * mp).toFixed(0) : ''}</em></div>`;
      h += `<div class="row"><span>${esc(shortOpt(F, o, 14))}</span>${mk(sa, C.coral, da ? da.mean_probability[o] : null)}${mk(sb, C.mint, db ? db.mean_probability[o] : null)}</div>`;
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
      p.out === 'discharged' ? `discharged on <b>day ${f1(p.t_exit)}</b>${p.cancer ? ' <b style="color:' + C.red + '">cancer not found</b>' : ''}` : esc(String(p.out))}
    ${p.t_diag != null ? `<br>diagnosis on day ${f1(p.t_diag)}` : ''}</div>
    <table><tr><th>Step</th><th>Waited</th><th>Took</th><th>Result</th></tr>`;
  rows.forEach(r => {
    h += `<tr class="${r[6] ? 'crit' : ''}"><td>${esc(nm(r[0]))}</td><td>${f1(r[2] - r[1])} d</td><td>${f1(r[4] - r[2])} d</td><td>${r[5] == null ? (F.graph.nodes.find(x => x.id === r[0]).kind === 'exit' ? '' : 'unclear') : r[5] ? 'positive' : 'negative'}</td></tr>`;
  });
  h += '</table>';
  if (p.c.length) {
    h += `<p style="margin:10px 0 4px;font:600 9px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:${C.dim}">Decisions</p>`;
    p.c.forEach(c => {
      h += `<p style="margin:0 0 4px"><b style="color:${C.text}">${esc(nm(c[0]))}</b> at day ${f1(c[1])}: chose <b style="color:${C.blue}">${esc(nm(c[2]))}</b><br><span style="font:10.5px var(--mono)">${Object.entries(c[4]).map(([o, q]) => `${esc(shortOpt(F, o, 22))} ${pct(q)}`).join(' · ')}</span></p>`;
    });
  }
  h += `<p style="margin-top:8px"><span style="color:${C.amber}">●</span> on the critical path: the steps that set this patient's time to the end.</p></div>`;
  return h;
}
function aboutCard() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  const V = S.panes.map(p => p.V);
  let h = `<div class="card"><h3>What you are looking at</h3>
    <p>Each dot is one simulated patient, starting on day 0 at first contact. Dots wait (amber) and are served (blue) at the steps; treated patients land on the right of the last step, mint if in time.</p>
    <p>Left: the pathway as it runs today. Right: the same patients with the change. Numbers on the graph count every simulated patient (${fmt(S.panes[0].P.F.totals.n)}); the moving dots are a sample of ${S.panes[0].P.F.cohort.size}, and so are the live counters above each graph. The clock is days since each patient's own first contact.</p>`;
  V.forEach((v, i) => { if (v.note) h += `<p><b style="color:${i ? C.mint : C.coral}">${esc(v.label)}.</b> ${esc(v.note)}</p>`; });
  const ch = V[1].changes && V[1].changes.length ? V[1].changes : null;
  if (ch) h += `<p><b>Changes in the right pathway</b><br>${ch.map(esc).join('<br>')}</p>`;
  return h + '</div>';
}

function renderNote() {
  const sc = D.scenarios.find(s => s.id === S.sid);
  const [A, B] = S.panes.map(p => p.P.F);
  let h = '';
  const st = A.cohort.strata;
  h += `<b>All patients are simulated.</b> The graph counts all ${fmt(A.totals.n)} simulated patients (${fmt(A.totals.cohorts)} cohorts); the moving dots are a sample of ${A.cohort.size} (${st.cancer} with cancer${st.other ? ', ' + st.other + ' without' : ''}), so the live counters above the graph count the sample, not the whole run. Time on the slider is days since each patient's first contact. `;
  if (sc.synthetic) h += `<b>This is a synthetic Finnish county</b>, not measured Finnish data: parameters are sourced or labelled as assumptions (see the dashboard). The change shown reorders steps only (no new capacity, no fast lane).`;
  if (sc.published) h += `<b>Norway:</b> see the check against the published study in the side panel. `;
  h += `Findings are simulated and are not clinical advice.`;
  $('#note').innerHTML = h;
}

/* ------------------------------------------------------------------ playback */
function sizeToTime() {
  const sl = $('#slider');
  sl.max = S.H; sl.step = S.H / 1000;
  S.base = Math.max(1, S.H / 40);
  const sp = $('#speed');
  sp.innerHTML = [.5, 1, 2, 4].map(m => `<option value="${m}" ${m === S.rate ? 'selected' : ''}>${f1(S.base * m)} days/s</option>`).join('');
}
let last = performance.now();
function frame(now) {
  const dt = (now - last) / 1000; last = now;
  if (S.playing) {
    S.t += dt * S.base * S.rate;
    if (S.t >= S.H) { S.t = S.H; S.playing = false; $('#play').textContent = 'Replay'; }
  }
  $('#slider').value = S.t; $('#day').textContent = Math.round(S.t);
  S.panes.forEach(pa => { if (pa.el.style.display !== 'none') { drawPane(pa, S.t); if (!pa._cu || now - pa._cu > 90) { updateCounters(pa); pa._cu = now; } } });
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ chrome */
function init() {
  if (!D) { document.body.innerHTML = '<p style="padding:30px;font:14px monospace;color:#EAF1F8">data/flow_bundle.js not found. Run: python demo/export_flow.py</p>'; return; }
  const q = new URLSearchParams(location.search);
  S.sid = q.get('s') || D.scenarios[0].id;
  if (!D.scenarios.find(s => s.id === S.sid)) S.sid = D.scenarios[0].id;
  if (q.get('layer')) S.layer = q.get('layer');
  if (q.has('compare')) S.compare = true;
  if (q.has('paused')) S.playing = false;
  if (q.get('day')) S.t = +q.get('day');
  S.view = q.get('view') || (innerWidth >= 1700 ? 'both' : 'right');
  S.big = q.has('large') || innerHeight < 950;
  setScenario(S.sid, q);
  $('#scn').innerHTML = D.scenarios.map(s => `<button class="chip sc ${s.id === S.sid ? 'on' : ''}" data-s="${s.id}">${esc(s.id === 'norway' ? 'Norway (validation)' : 'Finland (synthetic)')}</button>`).join('');
  $('#scn').addEventListener('click', e => { const b = e.target.closest('[data-s]'); if (!b) return; document.querySelectorAll('#scn .chip').forEach(c => c.classList.toggle('on', c === b)); S.t = 0; S.playing = true; $('#play').textContent = 'Pause'; setScenario(b.dataset.s); });
  $('#layers').innerHTML = LAYERS.map(([k, l]) => `<button class="chip ${k === S.layer ? 'on' : ''}" data-l="${k}">${l}</button>`).join('');
  $('#layers').addEventListener('click', e => { const b = e.target.closest('[data-l]'); if (!b) return; S.layer = b.dataset.l; document.querySelectorAll('#layers .chip').forEach(c => c.classList.toggle('on', c === b)); S.panes.forEach(renderPane); renderSide(); });
  $('#zoom').onclick = () => { S.big = !S.big; $('#zoom').classList.toggle('on', S.big); S.panes.forEach(fit); };
  $('#cmp').classList.toggle('on', S.compare);
  $('#cmp').onclick = () => { S.compare = !S.compare; $('#cmp').classList.toggle('on', S.compare); S.panes.forEach(renderPane); };
  const vb = $('#view'), VL = {both: 'View: both', left: 'View: today', right: 'View: after'};
  vb.textContent = VL[S.view];
  vb.onclick = () => { S.view = {both: 'left', left: 'right', right: 'both'}[S.view]; vb.textContent = VL[S.view]; buildPanes(); };
  $('#zoom').classList.toggle('on', S.big);
  $('#play').onclick = () => { if (S.t >= S.H) S.t = 0; S.playing = !S.playing; $('#play').textContent = S.playing ? 'Pause' : 'Play'; };
  $('#restart').onclick = () => { S.t = 0; S.playing = true; $('#play').textContent = 'Pause'; };
  $('#slider').oninput = e => { S.t = +e.target.value; S.playing = false; $('#play').textContent = 'Play'; };
  $('#speed').onchange = e => { S.rate = +e.target.value; };
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); $('#play').click(); }
    else if (e.key === 'r') $('#restart').click();
    else if (e.key === 'ArrowRight') { S.t = Math.min(S.H, S.t + S.H / 100); }
    else if (e.key === 'ArrowLeft') { S.t = Math.max(0, S.t - S.H / 100); }
  });
  $('#legend').innerHTML = `<span><i style="background:${C.amber}"></i>waiting</span><span><i style="background:${C.blue}"></i>being served</span><span><i style="background:${C.mint}"></i>treated in time</span><span><i style="background:#7B8FA3"></i>treated late</span><span><i style="border:1.5px solid ${C.red}"></i>cancer sent home</span>`;
  window.addEventListener('resize', () => S.panes.forEach(pa => { fit(pa); drawPane(pa, S.t); }));
  if (!S.playing) $('#play').textContent = 'Play';
  requestAnimationFrame(frame);
}
function setScenario(sid, q) {
  S.sid = sid;
  const sc = D.scenarios.find(s => s.id === sid);
  S.keys = [sc.default_pair[0], sc.default_pair[1]];
  if (q && q.get('left')) S.keys[0] = q.get('left');
  if (q && q.get('right')) S.keys[1] = q.get('right');
  S.sel = null; S.hl = null;
  $('#title').textContent = sid === 'norway' ? 'Where time is lost: a Norwegian hospital, rebuilt from a published study' : 'Where time is lost: a synthetic Finnish county';
  buildPanes();
}
window.__flow = S;
init();
})();
