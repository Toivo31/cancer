/** Optional reference UI. Use client.js directly if your demo already has its own components. */
import {createDecisionClient} from './client.js';
const add = (tag, text, parent) => {
  const node = document.createElement(tag); node.textContent = text;
  if (parent) parent.append(node); return node;
};
export class BirchDecision extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode: 'open'});
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;font:14px/1.5 var(--decision-font,system-ui,sans-serif);color:var(--decision-ink,#252621)}
      [hidden]{display:none!important}*{box-sizing:border-box}.panel{border:1px solid var(--decision-border,#dcd9d0);background:var(--decision-background,#fff);padding:22px;border-radius:8px}
      header{display:flex;align-items:center;justify-content:space-between;gap:15px}h2{margin:0;font-size:20px}h3{font-size:16px}.badge{font-size:12px;background:#f0f0e8;padding:5px 9px;border-radius:4px}
      label{display:block;margin:12px 0 5px}button,select,input{font:inherit;padding:9px;border:1px solid #c7c9bf;border-radius:4px;background:white;color:inherit}select,input,textarea{width:100%}input[type=checkbox]{width:auto}textarea{font:inherit;min-height:65px}.refinement{white-space:pre-wrap;overflow-wrap:anywhere}.reasoning{margin-top:14px;border:1px solid #dcd9d0;padding:12px}
      button{cursor:pointer}button.primary{background:#30382b;color:white}.buttons{display:flex;gap:10px;flex-wrap:wrap;margin-top:15px}button:disabled{opacity:.5;cursor:default}
      .muted{font-size:12px;color:#666b60}.status{min-height:22px}img{display:block;width:100%;max-height:230px;object-fit:contain;background:#f6f6f1;margin:12px 0}.context{white-space:pre-wrap}
      .question{margin-top:20px;border-top:1px solid #dadcd2;padding-top:12px}.choice{margin:14px 0}.choice p{margin:0 0 5px}progress{width:100%;height:8px;accent-color:#677e56}
      details{margin-top:12px}summary{cursor:pointer}a{color:inherit}button:focus-visible,select:focus-visible{outline:3px solid #9baf8d;outline-offset:2px}
    </style><section class="panel" part="panel"><header><h2>Decision review</h2><span class="badge" id="mode">Saved examples</span></header>
    <p class="muted">Compare allowed choices. A person reviews every proposal; nothing is executed automatically.</p>
    <label for="example">Example</label><select id="example"><option value="pathway">Synthetic pathway intake</option></select>
    <img id="photo" hidden alt="Selected PAD-UFES-20 skin lesion example"><p id="source" class="muted"></p><h3 id="question"></h3>
    <details><summary>Available information</summary><p id="context" class="context"></p></details>
    <div class="reasoning"><label><input id="reasoning" type="checkbox"> Enable context refinement (off by default)</label>
    <div id="reasoning-options" hidden><label for="token-budget">Generation budget (new tokens, total)</label><select id="token-budget"><option>64</option><option selected>128</option><option>256</option><option>512</option></select>
    <label for="additional-prompt">Additional instructions (optional)</label><textarea id="additional-prompt" maxlength="2000" placeholder="Give a quick review of the available history before scoring the question."></textarea>
    <p class="muted">The question is automatically added. Retrieval is limited to the permitted synthetic record.</p><button id="preview">Preview tool flow (scripted, no GPU)</button></div><p id="reasoning-info" class="muted"></p></div>
    <details id="refinement" hidden><summary>Context refinement and tool evidence</summary><p id="refinement-info"></p><ol id="tool-trace"></ol><p id="refined-context" class="refinement"></p></details>
    <div class="buttons"><button id="saved">Show saved example</button><button id="run" class="primary">Run live model</button></div>
    <p id="status" role="status" aria-live="polite" class="status"></p><div id="results"></div>
    <p class="muted">Scores compare the supplied choices; they are not calibrated disease probabilities. Dataset photos are training examples.</p></section>`;
  }
  $(id) { return this.shadowRoot.getElementById(id); }
  set request(value) {
    this._generation = (this._generation || 0) + 1; this._pending?.abort();
    this._custom = value ? JSON.parse(JSON.stringify(value)) : null;
    if (!this._custom) { this.$('example').value = 'pathway'; this.$('example').querySelector('[value="custom"]')?.remove(); }
    if (this._examples) this._input();
  }
  get request() { return this._custom ? JSON.parse(JSON.stringify(this._custom)) : null; }
  async connectedCallback() {
    if (this._connected) return; this._connected = true;
    this.api = createDecisionClient({baseUrl: this.getAttribute('api-base') || '/api/decision'});
    this.$('saved').onclick = () => this._load(false);
    this.$('run').onclick = () => this._load(true);
    this.$('reasoning').onchange = () => { this.$('reasoning-options').hidden = !this.$('reasoning').checked; if (!this.$('reasoning').checked) this.$('refinement').hidden=true; this._busy(false); };
    this.$('preview').onclick = () => this._preview();
    this.$('example').onchange = () => { this._generation = (this._generation || 0) + 1; this._pending?.abort(); this._custom = null; this.$('example').querySelector('[value="custom"]')?.remove(); this._input(); this._load(false); };
    try {
      this._examples = await this.api.examples(); // Local metadata only; never wakes a GPU.
      for (const sample of this._examples.photos.examples) {
        const option = add('option', sample.title+' · skin photo', this.$('example')); option.value = sample.id;
      }
      this._input();
      if (!this._custom) await this._load(false); // A recorded model output, not a live call.
    } catch(error) { this.$('status').textContent = error.message; }
  }
  _input() {
    const sampleId = this._custom ? 'custom' : this.$('example').value;
    if (this._custom && !this.$('example').querySelector('[value="custom"]')) {
      const option = add('option', 'Current patient / configured workflow', this.$('example')); option.value = 'custom';
    }
    if (this._custom) this.$('example').value = 'custom';
    const photo = this._examples.photos.examples.find(s => s.id === sampleId);
    this.$('photo').hidden = !photo;
    this.$('source').replaceChildren();
    if (photo) {
      this.$('photo').src = photo.url;
      const link = add('a', `${this._examples.photos.attribution} · ${this._examples.photos.license}`, this.$('source'));
      link.href = this._examples.photos.source;
    }
    let context, question;
    if (this._custom) {
      const payload = this._custom;
      context = payload.context || payload.case?.context || '';
      if (payload.case) context += '\n'+(payload.case.evidence || []).filter(e => e.available_at_step <= payload.case.step).map(e => e.text).join('\n');
      question = payload.questions?.[0]?.text || payload.workflow?.nodes[payload.node_id]?.question || 'Review allowed choices';
    } else if (photo) {
      context = photo.context; question = this._examples.score.questions[0].text;
    } else {
      const p = this._examples.pathway;
      context = p.case.context+'\n'+p.case.evidence.filter(e => e.available_at_step <= p.case.step).map(e => e.text).join('\n');
      question = p.workflow.nodes[p.node_id].question;
    }
    this.$('context').textContent = context; this.$('question').textContent = question;
    this.$('results').replaceChildren(); this.$('refinement').hidden=true;
    if (photo) this.$('reasoning').checked=false;
    this.$('reasoning').disabled=!!photo; this._photoExample=!!photo;
    this.$('reasoning-options').hidden=!this.$('reasoning').checked; this._busy(false);
  }
  _busy(value) {
    this._loading = value;
    this.shadowRoot.querySelectorAll('button,select,input,textarea').forEach(node => node.disabled = value);
    this.$('saved').disabled = value || !!this._custom;
    this.$('run').disabled = value || (!this._examples?.credential_configured && this._examples?.mode !== 'fixture');
    this.$('reasoning').disabled=value||!!this._photoExample;
    const unavailable=this.$('reasoning').checked&&!this._examples?.reasoning?.live_available&&this._examples?.mode!=='fixture';
    if (unavailable) this.$('run').disabled=true;
    this.$('reasoning-info').textContent=this._photoExample ? 'Patient-record refinement uses the synthetic pathway example; these dataset photos have no linked records.' : unavailable ? 'Live refinement is not enabled here. Preview the tool flow or turn refinement off.' : '';
    this.$('run').textContent = this._examples?.mode === 'fixture' ? 'Run scripted fixture' : 'Run live model';
  }
  _reasoningInput() {
    const body=this._custom ? {request:this._custom} : {example_id:this.$('example').value};
    if (this._custom && !this.patient) throw new Error('Set the permitted patient record reference before refining a custom case.');
    body.patient=this.patient || 'sim:demo-record';
    body.as_of_step=this._custom?.case?.step ?? 1;
    body.reasoning={enabled:this.$('reasoning').checked,max_tokens:Number(this.$('token-budget').value),
      max_rounds:3,max_tool_calls:2,additional_prompt:this.$('additional-prompt').value};
    return body;
  }
  _showRefinement(refinement) {
    this.$('refinement').hidden=false;
    this.$('refinement-info').textContent=`${refinement.mode==='scripted_tool_demo' ? 'Scripted tool preview; not Nemotron-generated text' : 'Frozen pretrained Nemotron context refinement'} · ${refinement.tokens_used}/${refinement.budget.max_tokens} generated tokens · ${refinement.tool_calls_used} tool calls · ${refinement.stop_reason}`;
    this.$('tool-trace').replaceChildren();
    for (const event of refinement.trace) add('li',event.tool ? `${event.tool}(patient): ${event.status} · ${(event.response?.entries || []).map(e=>e.source_id).join(', ')}` : `${event.status}${event.summary ? ': '+event.summary : ''}`,this.$('tool-trace'));
    this.$('refined-context').textContent=refinement.context;
  }
  async _preview() {
    if (this._loading) return;
    const generation=this._generation=(this._generation||0)+1; this._busy(true);
    try {
      const result=await this.api.refinePreview(this._reasoningInput());
      if (generation!==this._generation) return;
      this._showRefinement(result.refinement);
      this.$('status').textContent='Scripted tool-flow preview with actual synthetic retrieval. Saved scores have not been recomputed; no model was called.';
    } catch(error) { if (generation===this._generation) this.$('status').textContent=error.message; }
    finally { if (generation===this._generation) this._busy(false); }
  }
  async _load(live) {
    if (this._loading) return;
    const generation = this._generation = (this._generation || 0) + 1;
    this._pending = new AbortController(); const options = {signal: this._pending.signal};
    this._busy(true);
    this.$('results').replaceChildren();
    this.$('status').textContent = live ? 'Starting or scoring… a cold start can take about six minutes. Retry after a startup timeout.' : 'Loading saved example…';
    try {
      let result, delivery;
      if (!live) {
        const saved = await this.api.precomputed(this.$('example').value, options);
        result = saved.decision; delivery = 'precomputed';
      } else if (this.$('reasoning').checked) {
        const reasoned=await this.api.reason(this._reasoningInput(),options);
        result=reasoned.decision;
        if (generation===this._generation) this._showRefinement(reasoned.refinement);
      } else if (this._custom) {
        result = this._custom.workflow ? await this.api.propose(this._custom, options) : await this.api.score(this._custom, options);
      } else {
        result = this.$('example').value === 'pathway' ? await this.api.propose(this._examples.pathway, options) : await this.api.scoreExample(this.$('example').value, {}, options);
      }
      if (generation !== this._generation) return;
      delivery ||= result.backend.mode === 'fixture' ? 'fixture' : 'live';
      this._render(result, delivery);
      this.$('status').textContent = delivery === 'precomputed' ? `Saved model output · ${new Date(result.created_at).toLocaleString()} · no live inference was called.` : delivery === 'fixture' ? 'Scripted fixture data; not model inference.' : 'Live proposal ready for review.';
      this.dispatchEvent(new CustomEvent('decision-result', {bubbles: true, composed: true, detail: {delivery, decision: result}}));
    } catch(error) { if (generation === this._generation) this.$('status').textContent = error.message+(error.retryable ? ' You can retry, or choose Show saved example.' : ''); }
    finally { if (generation === this._generation) this._busy(false); }
  }
  _render(result, delivery) {
    this.$('mode').textContent = `${delivery === 'precomputed' ? 'Saved example' : delivery === 'fixture' ? 'Fixture' : 'Live model'} · checkpoint ${result.backend.step ?? '—'}`;
    const results = this.$('results'); results.replaceChildren();
    for (const question of result.questions) {
      const section = add('section', '', results); section.className = 'question'; section.setAttribute('part', 'question');
      add('h3', question.text, section);
      for (const choice of question.choices) {
        const row = add('div', '', section); row.className = 'choice'; row.setAttribute('part', 'choice');
        add('p', `${choice.id === question.proposed_action_id ? 'Proposed: ' : ''}${choice.text} · ${(choice.score*100).toFixed(1)}%`, row);
        const progress = add('progress', '', row); progress.max = 1; progress.value = choice.score; progress.setAttribute('aria-label', choice.text+' relative score');
      }
      const label = add('label', 'Your reviewed choice', section), select = add('select', '', label);
      for (const choice of question.choices) { const option = add('option', choice.text, select); option.value = choice.id; }
      select.value = question.proposed_action_id;
      const who = add('label', 'Reviewer label', section), reviewer = add('input', '', who); reviewer.placeholder = 'Name or demo label'; reviewer.maxLength = 128;
      const button = add('button', delivery === 'precomputed' ? 'Compare my choice' : 'Record review', section);
      const feedback = add('p', '', section); feedback.setAttribute('role', 'status');
      button.onclick = async () => {
        if (this._loading) return;
        const review = {question_id: question.id, action_id: select.value, reviewer: reviewer.value.trim()};
        if (!review.reviewer) { feedback.textContent = 'Enter a reviewer label.'; return; }
        const generation = this._generation; this._busy(true);
        try {
          const saved = delivery !== 'precomputed' ? await this.api.review(result.id, review) : null;
          if (generation !== this._generation) return;
          feedback.textContent = saved ? 'Review recorded. Original proposal preserved; no action executed.' : 'Compared locally. Saved example unchanged; nothing sent to the API.';
          this.dispatchEvent(new CustomEvent('decision-review', {bubbles: true, composed: true, detail: {delivery, persisted: !!saved, review: saved || review, decisionId: result.id, caseId: result.case_id}}));
        } catch(error) { if (generation === this._generation) feedback.textContent = error.message; }
        finally { if (generation === this._generation) this._busy(false); }
      };
    }
  }
}
if (!customElements.get('birch-decision')) customElements.define('birch-decision', BirchDecision);
