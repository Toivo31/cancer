"""Agent-friendly, dependency-free hosted API client: python -m decision_api.agent --reason."""
import argparse
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .server import TEAM_URL


def call(route, payload=None, *, base_url=TEAM_URL, timeout=660):
    deadline=time.monotonic()+timeout
    method='GET' if payload is None else 'POST'
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Accepted job still pending; do not automatically resubmit inference')
        request=Request(base_url.rstrip('/')+'/api/decision'+route,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'},method=method)
        try:
            with urlopen(request,timeout=min(30,remaining)) as response:result=json.load(response)
        except HTTPError as e:
            raise RuntimeError(f'HTTP {e.code}: {e.read(4000).decode()}') from None
        if result.get('delivery')!='pending':return result
        import re
        if not re.fullmatch(r'/jobs/[a-f0-9]{32}',result.get('status_url','')):raise ValueError('Invalid hosted job URL')
        route=result['status_url'];payload=None;method='GET'
        time.sleep(min(1,max(0,deadline-time.monotonic())))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default=TEAM_URL)
    p.add_argument('--example',default='pathway',choices=['pathway','example-1','example-2','example-3'])
    p.add_argument('--reason',action='store_true')
    p.add_argument('--tokens',type=int,default=128)
    p.add_argument('--instructions',default='')
    p.add_argument('--saved',action='store_true',help='Recorded output; does not start GPU')
    p.add_argument('--request',help='Visible context/questions request JSON file; never an old decision')
    args=p.parse_args()
    if args.saved:
        result=call('/examples/'+args.example+'/decision',base_url=args.url)
    else:
        payload={'reasoning':{'enabled':args.reason,'max_tokens':args.tokens,'additional_prompt':args.instructions}}
        if args.request:
            from pathlib import Path
            payload['request']=json.loads(Path(args.request).read_text())
            payload['reasoning']['max_tool_calls']=0 # Custom patients are never bound to the unrelated demo record.
        else:payload['example_id']=args.example
        if args.example!='pathway':payload['reasoning']['max_tool_calls']=0
        result=call('/reason',payload,base_url=args.url)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
