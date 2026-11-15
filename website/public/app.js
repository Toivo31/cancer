import {createDecisionClient} from './client.js?v=20261115-4';
import {render as renderResults} from './results.js?v=20261115-4';
const $=id=>document.getElementById(id);
const api=createDecisionClient({baseUrl:'https://cancer123--birch-decision-1138-demo.us-east.modal.run/api/decision',fetch:(...args)=>globalThis.fetch(...args)});
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pages=['manifesto','simulation','jev','appendix'];
function route(){let page=location.hash.slice(1).split('/')[0];if(page==='try')page='jev';if(!pages.includes(page))page='manifesto';
  for(const id of pages)$('page-'+id).hidden=id!==page;
  document.querySelectorAll('nav a').forEach(a=>{const on=a.hash==='#'+page;a.classList.toggle('active',on);if(on)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('sim-frame').contentWindow?.postMessage({type:'simulation-visibility',visible:page==='simulation'},location.origin);
  window.scrollTo(0,0);}
window.addEventListener('hashchange',route);route();
// Appendix and manifesto links such as #appendix work through the same router.
const PRESETS={
  gp:{context:'A 67-year-old woman, former smoker with 30 pack-years, has had a cough for four weeks and a fever since the weekend. CRP is 88 mg/L. A chest X-ray shows consolidation in the right lower lobe and no separate lesion.',question:'What should the GP do next?',choices:'Start antibiotics and repeat the X-ray in six weeks\nOrder a chest CT\nRefer urgently to a lung specialist\nNo further action'},
  sampling:{context:'A CT has found a 17 mm lesion in the outer part of the right lung, and the tumour board wants a tissue sample. The CT-guided biopsy list is fully booked for the next three weeks, while bronchoscopy has slots this week.',question:'Which sampling method should be booked?',choices:'CT-guided needle biopsy\nBronchoscopy\nEBUS-guided needle aspiration'},
  clear:{context:'',question:'',choices:''}};
let version=0,busy=false;
function ready(){version++;$('custom-result').innerHTML='<div class="empty-state"><span>✳</span><h3>Ready for your question.</h3><p>Choose an example or write your own, then compute live.</p></div>';}
function setPreset(k){const p=PRESETS[k];$('context').value=p.context;$('question').value=p.question;$('choices').value=p.choices;ready();}
document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>setPreset(b.dataset.preset));
setPreset('gp');
for(const id of ['context','question','choices'])$(id).addEventListener('input',ready);
function choices(value){const rows=value.split('\n').map(s=>s.trim()).filter(Boolean);if(rows.length<2||rows.length>8)throw Error('Enter 2–8 possible answers, one per line.');return rows.map((text,i)=>({id:'answer-'+i,text}));}
$('custom-form').onsubmit=async e=>{e.preventDefault();if(busy)return;const out=$('custom-result'),v=++version;
  try{const context=$('context').value.trim(),text=$('question').value.trim();if(!context||!text)throw Error('Enter both a situation and a question.');
    const request={context,questions:[{id:'custom',text,choices:choices($('choices').value)}]};
    busy=true;document.querySelectorAll('.live-call').forEach(b=>b.disabled=true);
    out.innerHTML='<div class="loading" role="status">Computing on Modal.<p>A cold start can take several minutes. Keep this page open; this submission will not be replayed.</p></div>';
    const data=await api.score(request);if(v===version)renderResults('custom-result',data,false,{$,api,esc});
  }catch(err){if(v===version){out.innerHTML=`<div class="error" role="alert">${esc(err.message)}</div>`;if(err.jobStatusUrl){const a=document.createElement('a');a.href=err.jobStatusUrl;a.textContent='Check accepted job status ↗';a.target='_blank';a.rel='noopener';out.append(a);}}}
  finally{busy=false;document.querySelectorAll('.live-call').forEach(b=>b.disabled=false);}};
