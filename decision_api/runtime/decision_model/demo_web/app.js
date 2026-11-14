const $ = id => document.getElementById(id);
let task = 'pathway', busy = false, templates;
async function api(path, payload, raw) {
  const headers = {};
  if ($('token').value) headers.Authorization = `Bearer ${$('token').value}`;
  if (payload !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {method: payload !== undefined || raw ? 'POST' : 'GET', headers,
    body: raw || (payload === undefined ? undefined : JSON.stringify(payload)), cache: 'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${JSON.stringify(data.detail || data)}`);
  return data;
}
function backendLabel(backend) { return `${backend.mode.toUpperCase()} · ${backend.model}${backend.quantization ? ' · NF4' : ''}`; }
function el(tag, text, parent) { const node = document.createElement(tag); node.textContent = text; if(parent) parent.append(node); return node; }
function status(text, error = false) { if (error && /Remote inference unavailable|HTTP 50[234]/.test(text)) text += ' The model may still be starting. Wait a moment, then retry.'; $('status').textContent = text; $('status').className = error ? 'error' : ''; }
function lock(value) { busy = value; document.querySelectorAll('button').forEach(b => b.disabled = value); }
function selectTask(next) {
  if (busy) return;
  task = next;
  document.querySelectorAll('[data-task]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.task === task)));
  $('request').value = JSON.stringify(templates[task], null, 2);
  $('photo-fields').hidden = task !== 'photo';
  $('score').textContent = task === 'pathway' ? 'Propose next step' : 'Score all choices';
  $('task-help').textContent = task === 'pathway' ? 'Synthetic workflow. Future observations are filtered by the API; a proposal never advances the pathway.' : task === 'photo' ? 'Choose a ready-made dataset example. Fixture scores do not depend on photo content.' : 'Score one or more questions on shared context. Fixture mode accepts only recorded questions and choices.';
  status('');
}
async function render(result) {
  $('mode').textContent = backendLabel(result.backend);
  $('results').replaceChildren();
  el('p', `Decision ${result.id} · ${result.latency_ms.toFixed(1)} ms · review required`, $('results'));
  for (const question of result.questions) {
    const section = el('section', '', $('results')); section.className = 'question';
    el('h3', question.text, section);
    for (const choice of question.choices) {
      const row = el('div', '', section); row.className = 'choice';
      el('p', `${choice.id === question.proposed_action_id ? 'Proposed · ' : ''}${choice.text} — ${(choice.score * 100).toFixed(1)}%`, row);
      const bar = el('div', '', row); bar.className = 'bar';
      el('span', '', bar).style.width = `${choice.score * 100}%`;
    }
    const label = el('label', 'Reviewed choice', section);
    const select = el('select', '', label);
    for (const choice of question.choices) { const option = el('option', choice.text, select); option.value = choice.id; }
    select.value = question.proposed_action_id;
    const reviewerLabel = el('label', 'Reviewer audit label', section);
    const reviewer = el('input', '', reviewerLabel); reviewer.placeholder = 'Your name or demo label'; reviewer.maxLength = 128;
    const noteLabel = el('label', 'Review note (optional)', section);
    const note = el('textarea', '', noteLabel); note.rows = 2; note.maxLength = 4000;
    const save = el('button', 'Record acceptance / correction', section);
    const feedback = el('p', '', section); feedback.setAttribute('role', 'status');
    save.onclick = async () => {
      if (busy) return;
      if (!reviewer.value.trim()) { feedback.textContent = 'Enter a reviewer label.'; return; }
      lock(true);
      try {
        const review = await api(`/v1/decisions/${result.id}/review`, {question_id:question.id, action_id:select.value, reviewer:reviewer.value.trim(), note:note.value});
        feedback.textContent = `Recorded ${review.is_correction ? 'correction' : 'acceptance'}. Original proposal preserved. No action executed.`;
        await trace(result.id);
      } catch(error) { feedback.textContent = error.message; }
      finally { lock(false); }
    };
  }
  if (result.proposed_next_node_id) el('p', `Proposed destination: ${result.proposed_next_node_id}. Session state has not advanced.`, $('results'));
  await trace(result.id);
}
async function trace(id) {
  const data = await api(`/v1/decisions/${id}`);
  $('trace').textContent = JSON.stringify(data, null, 2); $('audit').hidden = false;
}
$('score').onclick = async () => {
  if (busy) return;
  lock(true); status('Scoring…'); $('results').replaceChildren(); $('audit').hidden = true;
  try {
    const payload = JSON.parse($('request').value);
    if (task === 'photo') {
      const sample = await api(`/demo/samples/${$('sample').value}/prepare`, {});
      payload.image_ids = [sample.id];
      payload.context = sample.context;
      payload.case_id = `demo-${$('sample').value}`;
    }
    const result = await api(task === 'pathway' ? '/v1/pathway/propose' : '/v1/score', payload);
    await render(result); status('Proposal ready for review.');
  } catch(error) { status(error.message, true); }
  finally { lock(false); }
};
async function init() {
  lock(true); $('reconnect').hidden = true; status('Connecting to the model. Starting it can take a few minutes.');
  try {
    const [health, pathway, photo, catalog] = await Promise.all([api('/healthz'), api('/demo/examples/pathway'), api('/demo/examples/score'), api('/demo/samples/catalog.json')]);
    for (const sample of catalog.examples) { const option = el('option', sample.title, $('sample')); option.value = sample.id; }
    const showSample = () => {
      const sample = catalog.examples.find(s => s.id === $('sample').value);
      $('sample-preview').src = sample.url;
      $('sample-source').replaceChildren();
      const link = el('a', `${catalog.attribution} · ${catalog.license}`, $('sample-source')); link.href = catalog.source;
    };
    $('sample').onchange = showSample; showSample();
    $('mode').textContent = backendLabel(health.backend);
    templates = {pathway, photo, generic:photo}; lock(false); selectTask('pathway');
    document.querySelectorAll('[data-task]').forEach(b => b.onclick = () => selectTask(b.dataset.task));
  } catch(error) { $('mode').textContent = 'Starting or unavailable'; status(error.message, true); $('reconnect').hidden = false; $('reconnect').disabled = false; }
}
$('reconnect').onclick = init;
init();
