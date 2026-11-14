"""Deployed-site Firefox smoke. Start geckodriver --port 4445 first.
API calls are intercepted in-browser: this test does not start paid inference.
"""
import base64,json,os,time
from pathlib import Path
import requests

BASE=os.environ.get('WEBDRIVER_URL','http://127.0.0.1:4445')
SITE=os.environ.get('WEBSITE_URL','https://cancer123--equal-care-pathways-web.us-east.modal.run/?release=20261115-3')
profile=Path.home()/'snap/firefox/common/equal-care-slides-qa';profile.mkdir(parents=True,exist_ok=True)
r=requests.post(BASE+'/session',json={'capabilities':{'alwaysMatch':{'browserName':'firefox','moz:firefoxOptions':{'args':['-headless','-profile',str(profile)]}}}},timeout=60)
r.raise_for_status();sid=r.json()['value']['sessionId'];url=BASE+'/session/'+sid
checks=[]
def cmd(path,data):
 r=requests.post(url+path,json=data,timeout=90);
 if not r.ok: raise RuntimeError(r.text)
 v=r.json()['value']
 if isinstance(v,dict) and 'error' in v:raise RuntimeError(v)
 return v
def js(s):return cmd('/execute/sync',{'script':s,'args':[]})
def wait(s,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if js(s):return
  time.sleep(.15)
 raise AssertionError(s)
def check(name,s):
 assert js(s), (name,js('return [document.getElementById("custom-result").textContent,Array.from(document.scripts).map(s=>s.src)]'))
 checks.append(name)
def click(id):js('document.getElementById('+json.dumps(id)+').click()')
def route(s):js('location.hash='+json.dumps(s));time.sleep(.2)
def screenshot(name):
 v=requests.get(url+'/screenshot',timeout=30).json()['value'];out=Path(__file__).parent/'artifacts';out.mkdir(exist_ok=True);(out/name).write_bytes(base64.b64decode(v))
try:
 cmd('/window/rect',{'width':1440,'height':1000});cmd('/url',{'url':SITE})
 wait('return document.querySelectorAll("#photo-result .score-row").length===2')
 wait('return document.getElementById("sim-frame").contentDocument.querySelectorAll(".patient").length>20')
 check('desktop slide fits viewport','return document.documentElement.scrollHeight<=innerHeight+2')
 check('exactly three slides','return document.querySelectorAll("main>.page").length===3')
 check('simulation has no controls','return document.getElementById("sim-frame").contentDocument.querySelectorAll("button,input,select").length===0')
 check('branching graph','return document.getElementById("sim-frame").contentDocument.querySelectorAll(".edge").length>12')
 before=js('return document.getElementById("sim-frame").contentDocument.querySelector(".patient").getAttribute("cx")');time.sleep(.5)
 assert before!=js('return document.getElementById("sim-frame").contentDocument.querySelector(".patient").getAttribute("cx")');checks.append('patient animation moves')
 screenshot('simulation-desktop.png')
 click('next');wait('return !document.getElementById("studio").hidden')
 check('desktop decision slide fits viewport','return document.documentElement.scrollHeight<=innerHeight+2')
 # Intercept only the external decision API, retaining real assets and the production SDK.
 js(r'''window.calls=[];window.pendingResult=null;window.slow=false;window.originalFetch=window.fetch;
 window.fetch=async(url,init={})=>{
 if(!String(url).includes('birch-decision-1138-demo'))return originalFetch(url,init);
 const path=String(url).split('/api/decision')[1],body=init.body?JSON.parse(init.body):null;window.calls.push({path,body});
 const reply=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json'}});
 if(path.startsWith('/decisions/'))return reply({id:'review-recorded'});
 if(path.startsWith('/jobs/'))return reply(window.pendingResult);
 const request=body.request||body;
 const q=request.questions?.[0]||{id:'intake',text:'Which next step?',choices:[{id:'review',text:'Review history'},{id:'complete',text:'Request information'}]};
 const decision={id:'0123456789abcdef0123456789abcdef',backend:{mode:'model',step:2350},questions:[{...q,choices:q.choices.map((c,i)=>({...c,score:i===0?.8:.2/(q.choices.length-1)})),proposed_action_id:q.choices[0].id}]};
 if(path==='/reason')return reply({decision,refinement:{trace:[{tool:'retrieve_test_results',response:{finding:'Synthetic test result'}},{summary:'Test evidence summary'}],tool_calls_used:1,tokens_used:30,stop_reason:'summary_complete'}});
 if(window.slow)await new Promise(r=>setTimeout(r,700));
 if(!window.pendingResult){window.pendingResult=decision;return reply({delivery:'pending',status_url:'/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},202);}
 return reply(decision);
 };''')
 js('document.getElementById("text-form").requestSubmit()');wait('return document.querySelectorAll("#text-result .score-row").length===3')
 check('text uses live score endpoint','return calls.filter(x=>x.path==="/score").length===1')
 check('accepted job polled without repeating POST','return calls.some(x=>x.path.startsWith("/jobs/"))')
 check('all supplied text choices sent','return calls.find(x=>x.path==="/score").body.questions[0].choices.length===3')
 js('document.querySelector("#text-result .review input").value="demo reviewer";document.querySelector("#text-result .review button").click()')
 wait('return document.querySelector("#text-result .review p").textContent.includes("recorded separately")')
 check('human review is separate','return calls.some(x=>x.path.includes("/review")&&x.body.reviewer==="demo reviewer")')
 click('retrieval-tab');check('recorded retrieval source separated','return document.querySelectorAll("#text-result .evidence").length>=2')
 click('retrieval-live');wait('return document.getElementById("text-result").textContent.includes("Test evidence summary")')
 check('retrieval native reasoning contract','return calls.some(x=>x.path==="/reason"&&x.body.example_id==="pathway"&&x.body.reasoning.enabled)')
 route('studio/photo');js('document.getElementById("photo-select").value="example-2";document.getElementById("photo-select").dispatchEvent(new Event("change"))')
 check('original photo saved score','return document.getElementById("photo-result").textContent.includes("60.1%")')
 js('document.getElementById("photo-context").value="Updated synthetic context";document.getElementById("photo-context").dispatchEvent(new Event("input"));document.getElementById("photo-form").requestSubmit()')
 wait('return document.getElementById("photo-result").textContent.includes("LIVE MODEL RESULT")')
 check('photo live preserves image and custom context','return calls.some(x=>x.path==="/samples/example-2/score"&&x.body.context==="Updated synthetic context"&&x.body.questions[0].candidate_format==="inline")')
 click('photo-saved');check('saved photo restores original context','return document.getElementById("photo-context").value.includes("age: 55")')
 route('studio/custom');js('document.getElementById("choices").value="Only one";document.getElementById("custom-form").requestSubmit()')
 check('choice count validation','return document.getElementById("custom-result").textContent.includes("2–8")')
 js(r'document.getElementById("choices").value="First\nSecond";document.getElementById("question").value="A custom question?";document.getElementById("custom-form").requestSubmit()')
 wait('return document.getElementById("custom-result").textContent.includes("LIVE MODEL RESULT")')
 check('custom input sent to live model','return calls.some(x=>x.path==="/score"&&x.body.questions[0].text==="A custom question?")')
 js('document.getElementById("refine").checked=true;document.getElementById("custom-form").requestSubmit()');wait('return calls.some(x=>x.path==="/reason"&&x.body.request?.questions[0].id==="custom")')
 check('custom refinement disables patient tools','return calls.filter(x=>x.path==="/reason").at(-1).body.reasoning.max_tool_calls===0')
 wait('return !document.querySelector("#custom-form .live-call").disabled')
 js('window.slow=true;document.getElementById("refine").checked=false;document.getElementById("custom-form").requestSubmit();document.getElementById("question").value="Changed while waiting";document.getElementById("question").dispatchEvent(new Event("input"))');time.sleep(1)
 check('late reply cannot overwrite edited input','return !document.getElementById("custom-result").textContent.includes("LIVE MODEL RESULT")')
 screenshot('studio-desktop.png');route('manifesto');check('manifesto remains placeholder','return document.getElementById("manifesto").textContent.includes("PLACEHOLDER")')
 cmd('/window/rect',{'width':390,'height':844});route('studio/photo');check('mobile has no outer overflow','return document.documentElement.scrollWidth<=innerWidth');screenshot('studio-mobile.png')
 route('simulation');check('mobile simulation stays within slide','return document.documentElement.scrollWidth<=innerWidth');screenshot('simulation-mobile.png')
 print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
finally:requests.delete(url,timeout=20)
