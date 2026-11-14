/* Encounter-loop page. No build step; data comes from data/encounter_bundle.js (window.ENC_DATA), written by
   demo/export_encounter.py. Everything shown is simulated. The hidden truth (D.truth) is read only after the
   viewer switches on "Reveal truth (teaching view)". */
(function () {
'use strict';
const D = window.ENC_DATA;
const $ = (s, r) => (r || document).querySelector(s);
/* Colours: the theme tokens (demo/theme.css), read once at start (Site.tokens() when site.js is loaded). The
   fallbacks are the same paper-theme values. Meaning: mustard = waiting, brick = wrong (left with symptoms, a
   treatment that matches no true condition), brown = the hidden truth (teaching view), ink = everything else. */
const C = (function () {
  const fb = {paper: '#F4F0E4', card: '#FBF9F2', inset: '#EAE5D6', ink: '#1E1D1A', ink2: '#4F4B43', ink3: '#67625A',
    faint: '#9C978C', line: '#CDC7B6', mustard: '#B8902F', mustardInk: '#7E5E12', mustardTint: '#F1E4BD', brick: '#9E3B2A', brown: '#6A4B30'};
  const names = {paper: '--paper', card: '--card', inset: '--inset', ink: '--ink', ink2: '--ink-2', ink3: '--ink-3', faint: '--faint',
    line: '--line', mustard: '--mustard', mustardInk: '--mustard-ink', mustardTint: '--mustard-tint', brick: '--brick', brown: '--brown'};
  const cs = getComputedStyle(document.documentElement), o = {};
  Object.keys(names).forEach(k => { const v = cs.getPropertyValue(names[k]).trim(); o[k] = v || fb[k]; });
  return o;
})();
const rgb = h => { const m = /^#?([0-9a-f]{6})$/i.exec(String(h).trim()); if (!m) return [128, 128, 128]; const n = parseInt(m[1], 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
const rgba = (h, a) => `rgba(${rgb(h).join(',')},${a})`;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const fmt = n => n == null ? '–' : Math.round(n).toLocaleString('en-US');
const f1 = x => x == null ? '–' : (Math.round(x * 10) / 10).toFixed(1);
const pct = (x, d) => x == null ? '–' : (100 * x).toFixed(d == null ? 0 : d) + '%';
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const SPEEDS = [0.5, 1, 2, 4, 8];   // days per second, as in the simulator (flow.html); default 2
const S = {t: 0, playing: true, rate: 2, layer: 'flow', truth: false, sel: null, H: 100, hitDots: []};
let NW = 108, NH = 40, W = 1040, HH = 640;
let nodes, pos, nid, edges, geo, pats, byId;
// dot colour by state: waiting, being seen or tested, at home, finished (the finish colour comes from END_COL)
const STATE_COL = [C.mustard, C.ink, C.faint, C.ink];
const END_COL = {h_treat: C.ink, end_resolved: C.faint, end_symptoms: C.brick, end_horizon: C.ink3};
const KIND_STROKE = {role: C.ink2, referral: C.ink, treat: C.ink3, start: C.ink3, rest: C.ink3, test: C.ink3, hosp: C.ink3, end: C.ink3};

function init() {
  if (!D) { document.querySelector('main').innerHTML = '<p class="cmd">data/encounter_bundle.js not found. Run: python demo/export_encounter.py</p>'; return; }
  if (window.Site && Site.nav) Site.nav('simulator');
  // D69 claim label: link to the research register entry (research.html#<claim id>, lane L9). Built here, like the
  // Overview's claim links, so the static page has no link to a file that may not be merged yet.
  const st = $('#assumed'); if (st && st.dataset.claim) st.href = 'research.html#' + st.dataset.claim;
  W = D.size.w; HH = D.size.h; NW = D.size.node_w; NH = D.size.node_h;
  nodes = D.nodes; pos = {}; nid = {};
  nodes.forEach((n, i) => { pos[n.id] = n; nid[n.id] = i; });
  edges = D.edges; geo = {};
  edges.forEach(e => { geo[e.id] = geometry(pos[e.source], pos[e.target], e); });
  byId = {};
  pats = D.patients.map((p, i) => { byId[p.id] = i; p.idx = i; p.end = p.path.length ? p.path[p.path.length - 1][0] : 0; return p; });
  S.H = Math.ceil(Math.min(Math.max(...pats.map(p => p.end), 30), 450) / 10) * 10;
  const q = new URLSearchParams(location.search);
  if (q.get('layer')) S.layer = q.get('layer');
  if (q.has('truth')) S.truth = true;
  if (q.has('paused')) S.playing = false;
  if (q.get('day')) S.t = +q.get('day');
  $('#layers').innerHTML = [['flow', 'Flow'], ['time', 'Time at step']].map(([k, l]) => `<button class="chip" aria-pressed="${k === S.layer}" data-l="${k}">${l}</button>`).join('');
  $('#layers').addEventListener('click', e => { const b = e.target.closest('[data-l]'); if (!b) return; S.layer = b.dataset.l; document.querySelectorAll('#layers .chip').forEach(c => c.setAttribute('aria-pressed', String(c === b))); renderGraph(); renderLegend(); });
  $('#truth').onclick = () => setTruth(!S.truth);
  $('#play').onclick = () => { if (S.t >= S.H) S.t = 0; S.playing = !S.playing; $('#play').textContent = S.playing ? 'Pause' : 'Play'; };
  $('#restart').onclick = () => { S.t = 0; S.playing = true; $('#play').textContent = 'Pause'; };
  $('#slider').oninput = e => { S.t = +e.target.value; S.playing = false; $('#play').textContent = 'Play'; };
  $('#speed').onchange = e => { S.rate = +e.target.value; };
  const sl = $('#slider'); sl.max = S.H; sl.step = S.H / 1000;
  $('#speed').innerHTML = SPEEDS.map(m => `<option value="${m}" ${m === S.rate ? 'selected' : ''}>${m} days/s</option>`).join('');
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); $('#play').click(); }
    else if (e.key === 'r') $('#restart').click();
    else if (e.key === 't') setTruth(!S.truth);
    else if (e.key === 'ArrowRight') S.t = Math.min(S.H, S.t + S.H / 100);
    else if (e.key === 'ArrowLeft') S.t = Math.max(0, S.t - S.H / 100);
  });
  document.addEventListener('click', e => { if (e.target.closest && e.target.closest('button')) e.target.closest('button').blur(); });
  wireHit(); renderLegend(); renderFooter();
  window.addEventListener('resize', () => { fit(); });
  renderGraph(); renderResults(); renderNote(); fit();
  const p0 = q.get('p');
  if (p0 && byId[p0] != null) { S.sel = byId[p0]; renderGraph(); } renderSide();
  setTruth(S.truth, true);
  if (!S.playing) $('#play').textContent = 'Play';
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ geometry */
function rayRect(c, to) {
  const dx = to.x - c.x, dy = to.y - c.y;
  if (!dx && !dy) return {x: c.x, y: c.y};
  const t = Math.min((NW / 2 + 2) / Math.abs(dx || 1e-9), (NH / 2 + 2) / Math.abs(dy || 1e-9));
  return {x: c.x + dx * t, y: c.y + dy * t};
}
function geometry(a, b, e) {
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
  let k = 17;
  if (e && e.target === 'first') k = -len * .32;           // the return edge: a wide arc underneath
  const c = {x: (a.x + b.x) / 2 + (-dy / len) * k, y: (a.y + b.y) / 2 + (dx / len) * k};
  const p0 = rayRect(a, c), p1 = rayRect(b, c);
  const pts = [];
  for (let i = 0; i <= 24; i++) { const u = i / 24, v = 1 - u; pts.push({x: v * v * p0.x + 2 * u * v * c.x + u * u * p1.x, y: v * v * p0.y + 2 * u * v * c.y + u * u * p1.y}); }
  return {p0, c, p1, pts};
}
function along(g, u) {
  const f = clamp(u, 0, 1) * (g.pts.length - 1), i = Math.min(g.pts.length - 2, Math.floor(f)), w = f - i;
  return {x: g.pts[i].x + (g.pts[i + 1].x - g.pts[i].x) * w, y: g.pts[i].y + (g.pts[i + 1].y - g.pts[i].y) * w};
}

/* ------------------------------------------------------------------ the graph (svg) */
function renderGraph() {
  const maxE = Math.max(1, ...edges.map(e => e.n));
  const maxD = Math.max(.1, ...nodes.map(n => n.dwell || 0));
  const sel = S.sel != null ? selSets(pats[S.sel]) : null;
  let svg = `<svg viewBox="0 0 ${W} ${HH}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="The encounter loop">`;
  // region frames
  const box = (list, label, pad) => {
    if (!list.length) return '';
    const x0 = Math.min(...list.map(n => n.x)) - NW / 2 - pad, x1 = Math.max(...list.map(n => n.x)) + NW / 2 + pad;
    const y0 = Math.min(...list.map(n => n.y)) - NH / 2 - pad - 14, y1 = Math.max(...list.map(n => n.y)) + NH / 2 + pad;
    return `<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" rx="0" fill="none" stroke="${C.line}" stroke-dasharray="3 5"/><text x="${x0 + 8}" y="${y0 + 11}" class="mono" font-size="10" letter-spacing="1.2" fill="${C.ink3}">${label}</text>`;
  };
  svg += box(nodes.filter(n => n.kind === 'test'), 'TESTS', 8);
  svg += box(nodes.filter(n => n.hospital), 'HOSPITAL', 8);
  let labels = '';
  edges.forEach(e => {
    const g = geo[e.id], w = .8 + 5.2 * Math.sqrt(e.n / maxE), ret = e.target === 'first';
    const on = sel && sel.edges.has(e.id);
    const col = on ? C.ink : ret ? C.ink2 : C.ink3;
    const op = on ? .95 : .16 + .4 * Math.sqrt(e.n / maxE);
    svg += `<path d="M${g.p0.x.toFixed(1)},${g.p0.y.toFixed(1)} Q${g.c.x.toFixed(1)},${g.c.y.toFixed(1)} ${g.p1.x.toFixed(1)},${g.p1.y.toFixed(1)}" fill="none" stroke="${col}" stroke-opacity="${op.toFixed(2)}" stroke-width="${(on ? Math.max(w, 2.5) : w).toFixed(1)}"${ret && !on ? ' stroke-dasharray="7 5"' : ''}/>`;
    const dx = g.p1.x - g.c.x, dy = g.p1.y - g.c.y, l = Math.hypot(dx, dy) || 1, ux = dx / l, uy = dy / l, s = 4 + Math.min(w, 5);
    svg += `<path d="M${g.p1.x.toFixed(1)},${g.p1.y.toFixed(1)} l${(-ux * s - uy * s * .55).toFixed(1)},${(-uy * s + ux * s * .55).toFixed(1)} l${(uy * s * 1.1).toFixed(1)},${(-ux * s * 1.1).toFixed(1)} z" fill="${col}" fill-opacity="${Math.min(1, op + .2).toFixed(2)}"/>`;
    if (e.n > .12 * maxE || ret) {
      const m = along(g, .5);
      labels += `<text x="${(m.x + 4).toFixed(1)}" y="${(m.y - 3).toFixed(1)}" class="mono" font-size="10" fill="${ret ? C.ink : C.ink3}" stroke="${C.card}" stroke-width="3" paint-order="stroke">${ret ? 'returns ' : ''}${fmt(e.n)}</text>`;
    }
  });
  svg += labels;
  nodes.forEach(n => {
    const x = n.x - NW / 2, y = n.y - NH / 2;
    let fill = C.card, stroke = KIND_STROKE[n.kind] || C.ink3, sw = 1;
    if (n.id === 'h_treat') { stroke = C.ink; sw = 1.6; }
    if (n.id === 'end_symptoms') stroke = C.brick;
    let line2 = n.n ? fmt(n.n) + ' patients' : '';
    if (S.layer === 'time' && n.dwell != null) {
      const a = clamp(Math.sqrt(n.dwell / maxD), 0, 1);
      fill = rgba(C.mustard, (.06 + .5 * a).toFixed(3));
      if (a > .5) stroke = C.mustardInk;
      line2 = `median ${f1(n.dwell)} d`;
    } else if (S.layer === 'time') line2 = n.n ? fmt(n.n) + ' patients' : '';
    if (sel && sel.nodes.has(n.id)) { stroke = C.ink; sw = 2.2; }
    const words = n.label.split(' '); const lines = ['']; words.forEach(w_ => { const cur = lines[lines.length - 1]; if ((cur + ' ' + w_).trim().length <= 19) lines[lines.length - 1] = (cur + ' ' + w_).trim(); else lines.push(w_); });
    const ls = lines.slice(0, 2); if (lines.length > 2) ls[1] = ls[1].slice(0, 17) + '…';
    const ty = ls.length === 1 ? y + 16 : y + 14;
    svg += `<g data-id="${n.id}"><rect x="${x}" y="${y}" width="${NW}" height="${NH}" rx="${n.kind === 'role' ? 20 : 4}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
    ls.forEach((l, i) => { svg += `<text x="${n.x}" y="${ty + i * 11.5}" text-anchor="middle" font-size="11" font-weight="600" fill="${C.ink}">${esc(l)}</text>`; });
    if (line2) svg += `<text x="${n.x}" y="${y + NH - 5}" text-anchor="middle" class="mono" font-size="9.5" fill="${C.ink3}">${line2}</text>`;
    svg += '</g>';
  });
  $('#svgbox').innerHTML = svg + '</svg>';
}
function selSets(p) {
  const ns = new Set(), es = new Set();
  p.path.forEach((r, i) => { const id = nodes[r[1]].id; ns.add(id); if (i) { const a = nodes[p.path[i - 1][1]].id; if (a !== id) es.add(a + '>' + id); } });
  return {nodes: ns, edges: es};
}
function fit() {
  const gw = $('#gw'), pane = $('#pane');
  const top = pane.getBoundingClientRect().top + scrollY;
  const availH = Math.max(430, innerHeight - Math.min(top, 330) - 70);
  const w = Math.min(pane.clientWidth - 2, availH * W / HH * 1.15);
  gw.style.width = Math.round(Math.max(w, 300)) + 'px';
}

/* ------------------------------------------------------------------ dots */
function at(p, t) {
  const P = p.path;
  if (!P.length || t < P[0][0]) return null;
  let lo = 0, hi = P.length - 1;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (P[m][0] <= t) lo = m; else hi = m - 1; }
  const r = P[lo], Tt = Math.max(.8, S.H / 200);
  let tr = null;
  if (lo > 0 && P[lo - 1][1] !== r[1] && t < r[0] + Tt) {
    const a = nodes[P[lo - 1][1]].id, b = nodes[r[1]].id, g = geo[a + '>' + b];
    const u = (t - r[0]) / Tt;
    if (g) tr = along(g, u); else { const A = pos[a], B = pos[b]; tr = {x: A.x + (B.x - A.x) * u, y: A.y + (B.y - A.y) * u}; }
  }
  return {r, i: lo, tr, since: (() => { let j = lo; while (j > 0 && P[j - 1][1] === r[1]) j--; return P[j][0]; })()};
}
const cv = $('#cv'), ctx = cv.getContext('2d');
function draw(t) {
  const gw = $('#gw'), cw = gw.clientWidth, ch = gw.clientHeight, dpr = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(ch * dpr)) { cv.width = Math.round(cw * dpr); cv.height = Math.round(ch * dpr); }
  const k = cw / W * dpr;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height); ctx.setTransform(k, 0, 0, k, 0, 0);
  const groups = {}, draws = [];
  const cnt = {w: 0, s: 0, home: 0, move: 0, tx: 0, res: 0, sym: 0, hor: 0};
  pats.forEach(p => {
    const r = at(p, t);
    if (!r) return;
    const st = r.r[2], node = nodes[r.r[1]];
    if (r.tr) { cnt.move++; draws.push({x: r.tr.x, y: r.tr.y, col: C.ink3, r: 2.4, p}); return; }
    if (st === 0) cnt.w++; else if (st === 1) cnt.s++; else if (st === 2) cnt.home++;
    else if (node.id === 'h_treat') cnt.tx++; else if (node.id === 'end_resolved') cnt.res++; else if (node.id === 'end_symptoms') cnt.sym++; else cnt.hor++;
    (groups[node.id] = groups[node.id] || []).push({p, st, since: r.since});
  });
  Object.keys(groups).forEach(id => {
    const arr = groups[id].sort((a, b) => a.since - b.since || a.p.idx - b.p.idx), n = arr.length, p0 = pos[id];
    const big = n > 40, sx = big ? 4.1 : 5.9, rs = big ? 3.7 : 5.2, perRow = Math.floor((NW - 6) / sx);
    arr.forEach((o, i) => {
      const c = i % perRow, rr = Math.floor(i / perRow);
      const x = p0.x - NW / 2 + 5 + c * sx + (rr % 2 ? sx / 2 : 0), y = p0.y - NH / 2 - 4 - rr * rs;
      let col = o.st === 3 ? (END_COL[id] || C.ink) : STATE_COL[o.st];
      if (o.st === 0) { const wt = clamp((t - o.since) / 30, 0, 1), a = rgb(C.mustard), b = rgb(C.mustardInk); col = `rgb(${a.map((v, j) => Math.round(v + (b[j] - v) * wt)).join(',')})`; }
      draws.push({x, y, col, r: big ? 1.9 : 2.5, p: o.p});
    });
  });
  S.hitDots = draws;
  draws.forEach(o => {
    ctx.beginPath(); ctx.arc(o.x, o.y, o.r, 0, 6.2832); ctx.fillStyle = o.col; ctx.fill();
    if (S.truth && D.truth[o.p.id] && D.truth[o.p.id].cancer) { ctx.beginPath(); ctx.arc(o.x, o.y, o.r + 2, 0, 6.2832); ctx.strokeStyle = C.brown; ctx.lineWidth = 1.3; ctx.stroke(); }
  });
  if (S.sel != null) {
    const o = draws.find(o => o.p.idx === S.sel);
    if (o) { ctx.beginPath(); ctx.arc(o.x, o.y, 7, 0, 6.2832); ctx.strokeStyle = C.ink; ctx.lineWidth = 1.6; ctx.stroke(); }
  }
  return cnt;
}
let lastCnt = '';
function counters(c) {
  const h = `<span><i style="background:${C.mustard}"></i>waiting <b>${c.w}</b></span><span><i style="background:${C.ink}"></i>being seen or tested <b>${c.s}</b></span><span><i style="background:${C.faint}"></i>at home <b>${c.home}</b></span><span><i style="background:${C.ink3}"></i>moving <b>${c.move}</b></span><span><i style="background:${END_COL.h_treat}"></i>treatment started <b>${c.tx}</b></span><span><i style="background:${END_COL.end_resolved}"></i>left, gone <b>${c.res}</b></span><span><i style="background:${END_COL.end_symptoms}"></i>left, symptoms persist <b>${c.sym}</b></span><span><i style="background:${END_COL.end_horizon}"></i>at one year <b>${c.hor}</b></span><span>day <b>${Math.round(S.t)}</b> · sample of ${pats.length}</span>`;
  if (h !== lastCnt) { $('#counters').innerHTML = h; lastCnt = h; }
}

/* ------------------------------------------------------------------ interaction */
const tip = $('#tip');
function showTip(ev, html) { tip.innerHTML = html; tip.hidden = false; const w = tip.offsetWidth, h = tip.offsetHeight; tip.style.left = clamp(ev.clientX + 16, 8, innerWidth - w - 8) + 'px'; tip.style.top = clamp(ev.clientY + 14, 8, innerHeight - h - 8) + 'px'; }
function wireHit() {
  const hit = $('#hit'), gw = $('#gw');
  const toL = ev => { const r = gw.getBoundingClientRect(), k = W / r.width; return {x: (ev.clientX - r.left) * k, y: (ev.clientY - r.top) * k}; };
  const near = pt => { let b = null, bd = 7.5; S.hitDots.forEach(o => { const d = Math.hypot(o.x - pt.x, o.y - pt.y); if (d < bd) { bd = d; b = o; } }); return b; };
  hit.addEventListener('mousemove', ev => {
    const pt = toL(ev), d = near(pt);
    if (d) { hit.style.cursor = 'pointer'; showTip(ev, `<b>Patient ${d.p.id}</b><br><span class="m">${esc(d.p.g)}</span><br><span class="m">click to read the record</span>`); return; }
    hit.style.cursor = 'default';
    const n = nodes.find(n => Math.abs(pt.x - n.x) <= NW / 2 && Math.abs(pt.y - n.y) <= NH / 2);
    if (n) showTip(ev, nodeTip(n)); else tip.hidden = true;
  });
  hit.addEventListener('mouseleave', () => { tip.hidden = true; });
  hit.addEventListener('click', ev => { const d = near(toL(ev)); if (d) select(d.p.idx); else if (S.sel != null) { S.sel = null; renderGraph(); renderSide(); } });
}
function nodeTip(n) {
  let h = `<b>${esc(n.label)}</b>`;
  if (n.long) h += `<br><span class="m">${esc(n.long)}</span>`;
  if (n.tests) h += `<br><span class="m">${n.tests.map(esc).join(', ')}</span>`;
  h += `<br><span class="m">${fmt(n.n)} patients, ${fmt(n.visits)} visits (all ${fmt(D.n)} simulated patients)</span>`;
  if (n.dwell != null) h += `<br><span class="m">median ${f1(n.dwell)} days at this step per visit</span>`;
  return h;
}
function setTruth(on, quiet) {
  S.truth = on;
  const b = $('#truth'); b.setAttribute('aria-pressed', on ? 'true' : 'false');
  b.textContent = on ? 'Truth revealed (teaching view)' : 'Reveal truth (teaching view)';
  if (!quiet || on) renderSide();
  renderLegend();
}
function select(i) {
  S.sel = i; S.t = 0; S.playing = true; $('#play').textContent = 'Pause';
  renderGraph(); renderSide();
}

/* ------------------------------------------------------------------ patient panel */
function renderSide() {
  const side = $('#side');
  let h = `<div class="card enc-card"><h3>Example patients</h3><p>Picked automatically from the whole run. ${S.truth ? 'Teaching captions on.' : 'Captions describe only what the record shows.'}</p><div class="enc-ex">`;
  D.examples.forEach(e => {
    const cap = S.truth && D.truth[e.id] && D.truth[e.id].caption ? D.truth[e.id].caption : e.label;
    const on = S.sel != null && pats[S.sel].id === e.id;
    h += `<button data-p="${e.id}" class="${on ? 'on' : ''}">${esc(cap)}<small>patient ${e.id}${S.truth ? '' : ''}</small></button>`;
  });
  h += `</div><p style="margin:8px 0 0">Or click any dot in the graph.</p></div>`;
  if (S.sel != null) {
    const p = pats[S.sel], tr = S.truth ? D.truth[p.id] : null;
    h += `<div class="card enc-card" id="recard"><h3>Patient ${p.id} <span class="enc-x" id="close">close</span></h3><div class="enc-sum"><b>${esc(p.g)}</b><br>${p.ep} episode${p.ep > 1 ? 's' : ''} · ${outcomeText(p)}<br><span id="nowat"></span></div>`;
    if (tr) {
      h += `<div class="enc-truthbox"><h4>Hidden truth · teaching view</h4>Actually had: <b>${tr.conditions.map(esc).join(', ')}</b>${tr.cancer ? ' <b>(cancer)</b>' : ''}<br>`;
      h += tr.treatments.length ? tr.treatments.map(x => `${esc(x.label)} on day ${f1(x.day)}: ${x.matched ? '<b>matches one of the true conditions</b>' : '<span class="bad">matches none of them</span>'}`).join('<br>') : 'No treatment started in primary care.';
      h += `<br><span class="quiet">The clinicians never see this; the record below is all they have.</span></div>`;
    }
    h += `<div class="enc-key"><span><i></i>mechanical log (typed by the simulator, never edited)</span><span><i class="a"></i><em>assessment (the decider's words: interpretation)</em></span></div><div class="enc-rec" id="rec">`;
    p.lines.forEach((l, i) => {
      const mk = tr && tr.marks && tr.marks[i] != null ? `<span class="enc-mk ${tr.marks[i] ? 'ok' : 'bad'}">${tr.marks[i] ? 'treatment matches a true condition' : 'treatment matches none of the true conditions'}</span>` : '';
      h += `<div class="enc-ln ${l[1] ? 'a' : 'm'}" data-i="${i}" data-t="${l[0]}">${l[1] ? '<b>assessment</b>' : ''}${esc(l[2])}${mk}</div>`;
    });
    h += '</div>' + proposalsHtml(p) + '</div>';
  } else h += `<div class="card enc-card"><h3>Patient record</h3><p>Nothing selected. A record has two layers: the <span class="enc-ln m" style="display:inline;padding:0 4px">mechanical log</span> (what happened, typed by the simulator) and the clinicians' <em>assessments</em> (their working diagnosis and plan, in their own words).</p></div>`;
  side.innerHTML = h;
  side.querySelectorAll('.enc-ex button').forEach(b => b.onclick = () => select(byId[b.dataset.p]));
  const cl = $('#close'); if (cl) cl.onclick = () => { S.sel = null; renderGraph(); renderSide(); };
  side.querySelectorAll('.enc-ln[data-i]').forEach(el => el.onclick = () => el.classList.toggle('open'));
  lastVis = -2;
}
function proposalsHtml(p) {
  // Slot for the decision model's proposals (bundle field p.proposals, optional; the exporter leaves it empty unless given a file).
  let h = `<h3 style="margin-top:14px">Decision model proposals</h3>`;
  if (!p.proposals || !p.proposals.length) return h + `<p>None in this bundle yet. When present: per decision, the offered actions with scores, the model's proposal and what was chosen.</p>`;
  p.proposals.forEach(d => {
    const mx = Math.max(1e-9, ...d.options.map(o => o.score || 0));
    h += `<div class="enc-prop"><div class="ph"><b>${esc(String(d.decision_point || '').replace(/_/g, ' '))}</b><span class="dl ${esc(d.delivery || '')}">${esc(d.delivery || '')}</span></div>`;
    d.options.forEach(o => {
      h += `<div class="enc-po${o.id === d.proposed ? ' pr' : ''}"><span>${esc(o.label || o.id)}${o.id === d.proposed ? ' <i>proposed</i>' : ''}${o.id === d.chosen ? ' <i class="ch">chosen</i>' : ''}</span><em>${o.score == null ? '–' : (+o.score).toFixed(2)}</em><u style="width:${Math.max(2, 100 * (o.score || 0) / mx)}%"></u></div>`;
    });
    h += '</div>';
  });
  return h;
}
function outcomeText(p) {
  return ({treatment: 'treatment started', left_resolved: 'left, symptoms gone', left_with_symptoms: 'left with symptoms and did not return', undiagnosed_at_horizon: 'still in primary care at 1 year'})[p.out] || p.out;
}
let lastVis = -2;
function updateRecord() {
  if (S.sel == null) return;
  const rec = $('#rec'); if (!rec) return;
  const t = S.t, p = pats[S.sel];
  let n = 0; p.lines.forEach(l => { if (l[0] <= t + 1e-6) n++; });
  if (n === lastVis) return;
  lastVis = n;
  const els = rec.children;
  for (let i = 0; i < els.length; i++) { els[i].classList.toggle('future', i >= n); els[i].classList.toggle('now', i === n - 1 && n > 0); }
  const r = at(p, t);
  $('#nowat').textContent = r ? 'day ' + Math.round(t) + ': ' + nodes[r.r[1]].label : '';
  if (n > 0 && els[n - 1] && S.playing) { const c = $('#side-wrap'), el = els[n - 1]; const top = el.getBoundingClientRect().top - c.getBoundingClientRect().top + c.scrollTop; if (top < c.scrollTop || top > c.scrollTop + c.clientHeight - 60) c.scrollTop = Math.max(0, top - 120); }
}

/* ------------------------------------------------------------------ results */
function renderResults() {
  const R = D.results, o = R.overall;
  const OC = [['treatment', 'Treatment started', END_COL.h_treat], ['left_resolved', 'Left, symptoms gone', END_COL.end_resolved], ['left_with_symptoms', 'Left, symptoms persist', END_COL.end_symptoms], ['undiagnosed_at_horizon', 'Still in primary care at one year', END_COL.end_horizon]];
  let h = `<h3 class="finding">What this one run shows: a description of the loop, not the numbers to quote</h3><p class="enc-small">${fmt(o.n)} simulated patients, ${fmt(o.cancers)} with lung cancer. One seed and no warm-up; the multi-seed report (next section) gives the numbers to quote.</p><div class="enc-res">`;
  [[pct(o.cancer_treated_share), 'of cancers reach treatment'], [pct(o.cancer_within_target_share), `of cancers treated within ${D.target_days} days`],
   [f1(o.cancer_median_days_to_referral), 'median days to referral (cancers)'], [f1(o.cancer_median_days_to_diagnosis), 'median days to diagnosis'],
   [f1(o.cancer_median_days_to_treatment), 'median days to treatment'], [o.cancer_left_with_symptoms + ' of ' + o.cancers, 'cancers left with symptoms, not followed up'],
   [o.gp_encounters_per_patient, 'GP visits per patient'], [o.nurse_encounters_per_patient, 'nurse visits per patient'], [o.episodes_per_patient, 'episodes per patient'],
   [pct(o.referral_share), `referred (${fmt(o.noncancer_referred)} without cancer)`], [o.tests_per_patient, 'tests per patient'], ['€' + fmt(o.cost_per_patient_eur), 'cost per patient']]
    .forEach(([v, l]) => { h += `<div class="k"><b>${v}</b><span>${l}</span></div>`; });
  h += '</div>';
  const tot = OC.reduce((s, [k]) => s + (o.outcomes[k] || 0), 0) || 1;
  h += `<div class="enc-obar">${OC.map(([k, l, c]) => `<i style="width:${100 * (o.outcomes[k] || 0) / tot}%;background:${c}" title="${l}"></i>`).join('')}</div><div class="enc-olg">${OC.map(([k, l, c]) => `<span><i style="background:${c}"></i>${l} <b>${fmt(o.outcomes[k] || 0)}</b></span>`).join('')}</div>`;
  h += `<table class="enc-gt"><tr><th>Group</th><th>Patients</th><th>Cancers</th><th>Treated</th><th>In ${D.target_days} d</th><th>Median days to treatment</th><th>GP visits</th><th>Tests</th><th>€ per patient</th></tr>`;
  const GN = {age: 'Age', sex: 'Sex', smoking: 'Smoking', region: 'Region'};
  Object.keys(R.by_group).forEach(g => {
    h += `<tr class="gh"><td colspan="9">${GN[g] || g}</td></tr>`;
    Object.keys(R.by_group[g]).forEach(k => {
      const s = R.by_group[g][k]; if (!s.n) return;
      h += `<tr><td>${esc(k === 'f' ? 'female' : k === 'm' ? 'male' : k)}</td><td>${fmt(s.n)}</td><td>${fmt(s.cancers)}</td><td>${pct(s.cancer_treated_share)}</td><td>${pct(s.cancer_within_target_share)}</td><td>${f1(s.cancer_median_days_to_treatment)}</td><td>${s.gp_encounters_per_patient}</td><td>${s.tests_per_patient}</td><td>${fmt(s.cost_per_patient_eur)}</td></tr>`;
    });
  });
  h += `</table><p class="enc-small" style="margin-top:8px">Cancer columns rest on few patients per group (${fmt(o.cancers)} in all), so differences between groups are noisy. From the run's own report: <code>python -m pathway_sim run scenarios/finland_encounter.yaml</code>.</p>`;
  $('#results').innerHTML = h;
}
function renderNote() {
  const c = pats.filter(p => D.truth[p.id] && D.truth[p.id].cancer).length;
  $('#note').innerHTML = `<b>All patients are simulated.</b> Counts on the graph, edge thickness and the tables use all ${fmt(D.n)} simulated patients; the moving dots are a sample of ${pats.length} (about ${Math.round(100 * c / pats.length)}% with cancer, far above the real ${pct(D.n_cancer / D.n, 1)}, so that some reach treatment). Time is days since each patient's own first contact. Decisions come from placeholder tables; the numbers show how the loop behaves, not Finnish measurements. Findings are simulated and are not clinical advice. Run ${esc(D.generated_at)}, seed ${D.seed}.` + multiSeedNote();
}

function renderLegend() {
  let h = `<span><i style="background:${C.mustard}"></i>waiting</span><span><i style="background:${C.ink}"></i>being seen or tested</span><span><i style="background:${C.faint}"></i>at home</span><span><i style="background:${C.brick}"></i>left, symptoms persist</span>`;
  if (S.layer === 'time') h += `<span><i style="background:${C.mustardTint};border:1px solid ${C.mustardInk};border-radius:0"></i>step shade: median days there</span>`;
  if (S.truth) h += `<span><i class="ring"></i>has cancer (hidden truth)</span>`;
  $('#legend').innerHTML = h;
}
function renderFooter() {
  const t = `Synthetic patients only · not clinically reviewed · decisions assumed (placeholder tables) · numbers read from data/encounter_bundle.js, run ${D.generated_at}`;
  if (window.Site && Site.footer) Site.footer(t); else $('#footer').textContent = t;
}

/* ------------------------------------------------------------------ playback */
let last = performance.now();
function frame(now) {
  const dt = (now - last) / 1000; last = now;
  if (S.playing) {
    S.t += Math.min(dt, .25) * S.rate;
    if (S.t >= S.H) { S.t = S.H; S.playing = false; $('#play').textContent = 'Replay'; }
  }
  $('#slider').value = S.t; $('#day').textContent = String(Math.round(S.t)).padStart(3, '0');
  counters(draw(S.t));
  updateRecord();
  requestAnimationFrame(frame);
}
window.__enc = S;
init();
})();

/* This page shows ONE illustration run (one seed, no warm-up). The multi-seed report is a different, longer run of the same loop. */
function multiSeedNote() {
  const R = window.START_DATA && window.START_DATA.encounter_results, c = R && R.consistency;
  const pc = x => (100 * x).toFixed(0) + '%';
  let h = ` <b>This is one illustration run.</b> The loop's queues fill up as a run gets longer, so a longer run gives different numbers.`;
  if (c && c.within90 && c.within90.loop && c.ref_med && c.ref_med.loop)
    h += ` The multi-seed report (docs/encounter_results.md: ${R.seeds.length} seeds of ${R.n} patients, ${Math.round(R.warmup_days)}-day warm-up) gives ${pc(c.within90.loop.mean)} of cancers treated within 90 days (range ${pc(c.within90.loop.lo)} to ${pc(c.within90.loop.hi)}) and a median of ${Math.round(c.ref_med.loop.mean)} days to referral. Quote that report for the number; use this page to see how the loop behaves.`;
  const k = window.START_DATA && window.START_DATA.encounter_consistency;
  if (k && k.tuning) h += ` The loop agrees with the calibrated chain on ${k.tuning.passed} of ${k.tuning.total} checks on the tuning seeds${k.fresh ? ', ' + k.fresh.passed + ' of ' + k.fresh.total + ' on fresh seeds' : ''}${k.pooled ? ', ' + k.pooled.passed + ' of ' + k.pooled.total + ' pooled' : ''}, only just.`;
  return h;
}
