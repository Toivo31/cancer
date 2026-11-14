"""Credential-holding hosted team gateway. No Modal login is required by callers."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
import uuid
from .server import DecisionAPI, APIError, ROOT, WEB, MAX_BODY


def create_app(api=None):
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    api = api or __import__('decision_api.server', fromlist=['from_environment']).from_environment()
    app = FastAPI(title='Birch team decision API', description='No Modal account or API key needed. Quick calls return a result; longer calls return a job to poll at GET /api/decision/jobs/{id}. Generated evidence summaries and relative candidate scores require review.')
    app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['GET','POST'],allow_headers=['Content-Type'])
    jobs={};lock=threading.Lock();starts=[];pool=ThreadPoolExecutor(max_workers=1)

    @app.get('/')
    @app.get('/decision')
    def panel(): return FileResponse(WEB/'index.html')

    @app.get('/decision-assets/{name}')
    def script(name:str):
        if name not in ('client.js','widget.js'): return JSONResponse({'detail':'Unknown asset'},404)
        return FileResponse(ROOT/name,media_type='text/javascript')

    @app.get('/agent.md',include_in_schema=False)
    def agent_brief():return FileResponse(ROOT/'HOSTED_API.md',media_type='text/markdown')

    app.mount('/decision-assets',StaticFiles(directory=WEB),name='assets')

    def run(identifier,method,route,body):
        try:
            result=api.call(method,route,body);status=200
        except APIError as e:result={'detail':e.detail};status=e.status
        except (ValueError,KeyError,TypeError):result={'detail':'Invalid decision request'};status=422
        except Exception:result={'detail':'Inference unavailable; no substitute scores generated'};status=503
        with lock:jobs[identifier].update(result=result,http_status=status)

    def pending(identifier):
        return JSONResponse(dict(delivery='pending',job_id=identifier,status_url='/jobs/'+identifier),202,headers={'Retry-After':'1'})

    @app.get('/api/decision/jobs/{identifier}')
    def job(identifier:str):
        with lock:record=jobs.get(identifier)
        if record is None:return JSONResponse({'detail':'Job expired; do not automatically resubmit scoring'},404)
        if 'result' not in record:return pending(identifier)
        return JSONResponse(record['result'],record['http_status'])

    @app.api_route('/api/decision/{route:path}',methods=['GET','POST'],include_in_schema=False)
    async def call(route:str,request:Request):
        body=None
        if request.method=='POST':
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>MAX_BODY:return JSONResponse({'detail':'Request exceeds 512 KiB'},413)
            try:
                body=json.loads(raw or b'{}')
                if not isinstance(body,dict):raise ValueError()
                # Keep the public demo workload small; full native API stays authenticated.
                target=body.get('request',body)
                if isinstance(target,dict):
                    context=target.get('case',{}).get('context',target.get('context',''))
                    questions=target.get('questions',[])
                    if len(json.dumps(target))>32000 or len(context)>12000 or len(questions)>4 or any(len(q.get('choices',[]))>8 for q in questions):
                        raise ValueError()
            except (ValueError,TypeError,AttributeError):return JSONResponse({'detail':'Invalid demo request or context/question budget exceeded'},422)
        route='/'+route
        local=request.method=='GET' and (route=='/examples' or (route.startswith('/examples/') and route.endswith('/decision')))
        local=local or route=='/refine-preview'
        if local:
            try:
                result=api.call(request.method,route,body)
                if route=='/examples' and isinstance(result,dict):
                    from urllib.parse import urljoin
                    for photo in result.get('photos',{}).get('examples',[]):
                        photo['url']=urljoin(str(request.base_url),photo['url'])
                return JSONResponse(result)
            except (APIError,ValueError,TypeError,KeyError) as e:return JSONResponse({'detail':str(e)},getattr(e,'status',422))
        allowed=(request.method=='GET' and (route=='/health' or route.startswith('/decisions/'))) or (request.method=='POST' and (route in ('/reason','/score','/pathway') or (route.startswith('/samples/') and route.endswith('/score')) or (route.startswith('/decisions/') and route.endswith('/review'))))
        if not allowed:return JSONResponse({'detail':'Unknown decision API route'},404)
        now=time.time()
        with lock:
            for key in list(jobs):
                if 'result' in jobs[key] and now-jobs[key]['created']>1800:del jobs[key]
            starts[:]=[t for t in starts if now-t<3600]
            active=sum('result' not in j for j in jobs.values())
            if active>=3 or len(starts)>=120 or sum(now-t<60 for t in starts)>=6:
                return JSONResponse({'detail':'Demo busy; wait before submitting another request'},429,headers={'Retry-After':'60'})
            identifier=uuid.uuid4().hex;jobs[identifier]={'created':now};starts.append(now)
        future=pool.submit(run,identifier,request.method,route,body)
        # Return quick cached results directly; retain job polling for long calls.
        # Shielding keeps an accepted request alive when this short wait ends.
        import asyncio
        try:
            await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),timeout=.5)
            with lock:record=jobs[identifier]
            return JSONResponse(record['result'],record['http_status'])
        except asyncio.TimeoutError:
            return pending(identifier)
    # Publish concrete paths and a copyable payload instead of a catch-all route.
    from fastapi.openapi.utils import get_openapi
    def schema():
        spec=get_openapi(title=app.title,version='1.1.0',description=app.description,routes=app.routes)
        for route,method,example in [
            ('examples','get',None),('health','get',None),
            ('reason','post',{'example_id':'pathway','reasoning':{'enabled':True,'max_tokens':128,'additional_prompt':'Give a quick evidence review.'}}),
            ('score','post',{'context':'Synthetic patient visible intake.','questions':[{'id':'next','text':'What should be reviewed next?','choices':[{'id':'history','text':'Review available history'},{'id':'missing','text':'Request missing information'}]}]}),
            ('pathway','post',json.loads((WEB/'pathway.json').read_text()))]:
            operation={'summary':route,'responses':{'200':{'description':'Result or local metadata'},'202':{'description':'Accepted job: poll status_url under /api/decision'},'429':{'description':'Demo busy'}}}
            if example is not None:operation['requestBody']={'required':True,'content':{'application/json':{'schema':{'type':'object'},'example':example}}}
            spec['paths']['/api/decision/'+route]={method:operation}
        return spec
    app.openapi=schema
    return app
