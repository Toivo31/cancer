"""Explicit single paid inference smoke. Saves a pending job before polling; never replays POST."""
import json,time
from pathlib import Path
import requests
base='https://cancer123--birch-decision-1138-demo.us-east.modal.run/api/decision'
origin='https://cancer123--equal-care-pathways-web.us-east.modal.run'
out=Path(__file__).parent/'artifacts/live-check.json';out.parent.mkdir(exist_ok=True)
if out.exists():
 old=json.loads(out.read_text())
 if old.get('delivery')=='pending':
  data=old;print('Resuming existing accepted job',data['status_url'],flush=True)
 else:
  print('A completed live check already exists; no additional inference submitted.');raise SystemExit(0)
else:
 payload={'context':'A clinic reserves the earliest available appointment for urgent referrals. Patient A needs routine follow-up. Patient B has an urgent referral.','questions':[{'id':'website-live-check','text':'Who should receive the earliest appointment?','choices':[{'id':'a','text':'Patient A'},{'id':'b','text':'Patient B'}]}]}
 r=requests.post(base+'/score',json=payload,headers={'Origin':origin},timeout=90)
 print('Submission',r.status_code,'CORS',r.headers.get('access-control-allow-origin'),flush=True);r.raise_for_status();data=r.json();out.write_text(json.dumps(data,indent=2))
deadline=time.monotonic()+660;last_print=0
while data.get('delivery')=='pending':
 if time.monotonic()>deadline:raise TimeoutError('Accepted job remains pending; saved status_url can be resumed without replaying POST')
 if time.monotonic()-last_print>30:print('Waiting for accepted job',data['status_url'],flush=True);last_print=time.monotonic()
 time.sleep(2);r=requests.get(base+data['status_url'],timeout=60);r.raise_for_status();data=r.json();out.write_text(json.dumps(data,indent=2))
d=data.get('decision',data);assert d['backend']['step']==2350;assert len(d['questions'][0]['choices'])==2
print('PASS actual live model: checkpoint',d['backend']['step'],'proposal',d['questions'][0]['proposed_action_id'],flush=True)
