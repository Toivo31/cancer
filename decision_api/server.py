"""Stdlib-only demo proxy: python -m decision_api.server [--fixture]."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit, urljoin
from urllib.request import build_opener, HTTPRedirectHandler, Request

ROOT = Path(__file__).resolve().parent
WEB = ROOT/'web'
DEFAULT_URL = 'https://cancer123--birch-decision-1138-inference-web.us-east.modal.run'
TEAM_URL = 'https://cancer123--birch-decision-1138-demo.us-east.modal.run'
MAX_BODY = 512 * 1024


class APIError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward the server credential to a redirect target.


class DecisionAPI:
    def __init__(self, *, mode='live', base_url=DEFAULT_URL, api_key='', opener=None):
        if mode not in ('live', 'fixture'):
            raise ValueError('BIRCH_DECISION_MODE must be live or fixture')
        parsed = urlsplit(base_url)
        if (parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.modal.run')
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('BIRCH_API_URL must be a root HTTPS Modal URL')
        self.mode, self.base_url, self.api_key = mode, base_url.rstrip('/'), api_key.strip()
        self.opener = opener or build_opener(NoRedirect())
        self.fixture = None
        self._prepared_samples = {}
        if mode == 'fixture':
            from .fixture import Fixture
            self.fixture = Fixture()

    def examples(self):
        return dict(mode=self.mode, credential_configured=bool(self.api_key),
            reasoning=dict(default_enabled=False,preview_available=True,live_available=os.environ.get('BIRCH_NATIVE_REFINEMENT_ENABLED')=='1'),
            pathway=json.loads((WEB/'pathway.json').read_text()),
            score=json.loads((WEB/'score.json').read_text()),
            photos=json.loads((WEB/'samples/catalog.json').read_text()))

    def remote(self, path, body=None):
        if os.environ.get('BIRCH_DECISION_PAUSED') == '1':
            raise APIError(503, 'Decision service paused by the operator')
        if not self.api_key:
            raise APIError(503, 'Set BIRCH_API_KEY on your backend, or use --fixture for offline development')
        data = None if body is None else json.dumps(body).encode()
        headers = {'Authorization': 'Bearer '+self.api_key}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(self.base_url+path, data=data, headers=headers)
        deadline=time.monotonic()+650
        for redirects in range(5):
            try:
                with self.opener.open(request, timeout=max(1,deadline-time.monotonic())) as response:
                    if not 200 <= response.status < 300:
                        raise APIError(503, 'Model may still be starting. Retry shortly.')
                    return json.load(response)
            except HTTPError as error:
                if error.code==303 and redirects<4 and time.monotonic()<deadline:
                    location=urljoin(request.full_url,error.headers.get('Location',''))
                    old,new=urlsplit(request.full_url),urlsplit(location)
                    # Modal's result redirect polls THIS accepted call. Never replay
                    # its POST or carry the credential to another host/path.
                    if new.scheme==old.scheme=='https' and new.netloc==old.netloc and new.path==old.path and new.query and not new.fragment and not new.username:
                        request=Request(location,headers={'Authorization':'Bearer '+self.api_key},method='GET')
                        continue
                if 300 <= error.code < 400:
                    raise APIError(503, 'Model may still be starting. Retry shortly.') from None
                try:
                    detail = json.loads(error.read(4000)).get('detail', 'Remote inference failed')
                except (ValueError, AttributeError):
                    detail = 'Remote inference unavailable; no substitute scores generated'
                raise APIError(error.code, detail) from None
            except (URLError, TimeoutError, socket.timeout, json.JSONDecodeError):
                raise APIError(503, 'Model unavailable or still starting. Retry shortly; no substitute scores generated.') from None
        raise APIError(503,'Model result wait timed out; do not automatically resubmit the request')

    def prepare_sample(self,sample):
        if self.fixture:return self.fixture.prepare(sample)
        identifier=sample['id']
        if identifier not in self._prepared_samples:
            self._prepared_samples[identifier]=self.remote('/demo/samples/'+identifier+'/prepare',{})
        return dict(self._prepared_samples[identifier])

    def reasoning_call(self, body, *, preview=False):
        from .reasoning import refine,settings,PatientTools,DemoGenerator
        if not isinstance(body,dict) or set(body)-{'request','example_id','patient','as_of_step','reasoning'}:
            raise APIError(422,'Send a request or example_id plus reasoning settings; never a raw decision')
        if ('request' in body)==('example_id' in body):
            raise APIError(422,'Provide exactly one of request or example_id')
        cfg=settings(body.get('reasoning'))
        if cfg['enabled'] and cfg['max_tool_calls'] and 'request' in body and not body.get('patient'):
            raise APIError(422,'Bind an authorized patient record before enabling retrieval for a custom case')
        catalog=self.examples()
        sample=None
        if 'request' in body:
            request=json.loads(json.dumps(body['request']))
        elif body['example_id']=='pathway':
            request=catalog['pathway']
        else:
            sample=next((s for s in catalog['photos']['examples'] if s['id']==body['example_id']),None)
            if sample is None: raise APIError(404,'Unknown reasoning example')
            request=dict(catalog['score'],context=sample['context'],case_id='demo-'+sample['id'],image_ids=[])
        if not isinstance(request,dict): raise APIError(422,'request must be an object')
        if 'workflow' not in request:
            if set(request)-{'context','case_id','questions','image_ids'} or any('score' in c for q in request.get('questions',[]) for c in q.get('choices',[])):
                raise APIError(422,'Send visible context and choices, not old decisions or scores')
        if cfg['enabled'] and not preview and self.fixture is None and not catalog['reasoning']['live_available']:
            raise APIError(503,'Live shared-base refinement is not enabled yet; use the labelled tool preview or turn reasoning off')
        if sample and not preview:
            asset=self.prepare_sample(sample)
            request['image_ids']=[asset['id']]
        step=body.get('as_of_step',request.get('case',{}).get('step',1))
        patient=body.get('patient','sim:demo-record')
        if self.fixture is None and not preview and cfg['enabled']:
            return self.remote('/v1/context/reason',dict(request=request,patient=patient,as_of_step=step,reasoning=cfg))
        tools=generator=None
        if cfg['enabled']:
            if 'case' in request and step!=request['case']['step']:
                raise APIError(422,'Retrieval step must match pathway case.step')
            if cfg['max_tool_calls']: tools=PatientTools(patient,as_of_step=step)
            generator=DemoGenerator(patient)
        refined=refine(request,options=cfg,tools=tools,generator=generator)
        if preview: return dict(delivery='scripted_tool_preview',refinement=refined['refinement'])
        prepared=refined['request']
        if self.fixture:
            decision=self.fixture.propose(prepared,allow_refined_context=cfg['enabled']) if 'workflow' in prepared else self.fixture.score(prepared)
        else:
            decision=self.remote('/v1/pathway/propose' if 'workflow' in prepared else '/v1/score',prepared)
        return dict(decision=decision,refinement=refined['refinement'])

    def call(self, method, route, body=None):
        if method=='POST' and route in ('/reason','/refine-preview'):
            return self.reasoning_call(body,preview=route=='/refine-preview')
        if route == '/examples' and method == 'GET':
            return self.examples()  # No remote call, including in live mode.
        saved = re.fullmatch(r'/examples/(pathway|example-[123])/decision', route)
        if saved and method == 'GET':
            record = json.loads((WEB/'precomputed.json').read_text())['entries'][saved[1]]
            return dict(delivery='precomputed', example_id=saved[1], **record)
        if method == 'POST' and route == '/score':
            if not isinstance(body, dict) or set(body)-{'context', 'case_id', 'questions', 'image_ids'}:
                raise APIError(422, 'Send visible context and allowed choices, not a previous model decision')
            if any('score' in choice for q in body.get('questions', []) for choice in q.get('choices', [])):
                raise APIError(422, 'Choices need IDs and text, not previous scores')
        mapping = {('GET', '/health'): '/healthz', ('POST', '/score'): '/v1/score',
                   ('POST', '/pathway'): '/v1/pathway/propose'}
        sample = re.fullmatch(r'/samples/(example-[123])/score', route)
        decision = re.fullmatch(r'/decisions/([a-f0-9]{32})(/review)?', route)
        if sample and method == 'POST':
            if not isinstance(body, dict) or set(body)-{'context', 'case_id', 'questions'}:
                raise APIError(422, 'Photo examples accept only context, case_id and questions')
            example = next(s for s in self.examples()['photos']['examples'] if s['id'] == sample[1])
            asset = self.prepare_sample(example)
            payload = dict(self.examples()['score'], context=asset['context'], image_ids=[asset['id']], case_id='demo-'+sample[1])
            payload.update(body)
            return self.fixture.score(payload) if self.fixture else self.remote('/v1/score', payload)
        if decision and ((method == 'GET' and not decision[2]) or (method == 'POST' and decision[2])):
            if self.fixture:
                return self.fixture.review(decision[1], body) if decision[2] else self.fixture.decision(decision[1])
            return self.remote('/v1'+route, body)
        if (method, route) not in mapping:
            raise APIError(404, 'Unknown decision API route')
        if self.fixture:
            if route == '/health':
                return dict(ready=True, backend=self.fixture.metadata)
            return self.fixture.propose(body) if route == '/pathway' else self.fixture.score(body)
        return self.remote(mapping[method, route], body)


class HostedDecisionAPI:
    """Project-side relay to the hosted credential holder; no local secrets needed."""
    mode = 'live'
    def __init__(self, base_url=TEAM_URL, opener=None):
        parsed=urlsplit(base_url)
        if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.modal.run') or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('BIRCH_TEAM_URL must be a root HTTPS Modal URL')
        self.base_url=base_url.rstrip('/');self.opener=opener or build_opener(NoRedirect())
    def call(self,method,route,body=None):
        if os.environ.get('BIRCH_DECISION_PAUSED')=='1':raise APIError(503,'Decision service paused by the operator')
        from .agent import call
        try:return call(route,body,base_url=self.base_url)
        except (RuntimeError,TimeoutError,URLError) as error:
            raise APIError(503,str(error)) from None


def from_environment():
    if os.environ.get('BIRCH_DECISION_MODE','live')=='live' and not os.environ.get('BIRCH_API_KEY') and not os.environ.get('BIRCH_API_KEY_FILE'):
        return HostedDecisionAPI(os.environ.get('BIRCH_TEAM_URL',TEAM_URL))
    token = os.environ.get('BIRCH_API_KEY', '')
    if not token:
        path = Path(os.environ.get('BIRCH_API_KEY_FILE', str(Path.home()/'.config/birch/demo-api-key')))
        if path.is_file():
            token = path.read_text().strip()
    if not token and os.environ.get('BIRCH_DECISION_MODE','live')=='live':
        return HostedDecisionAPI(os.environ.get('BIRCH_TEAM_URL',TEAM_URL))
    return DecisionAPI(mode=os.environ.get('BIRCH_DECISION_MODE', 'live'),
                       base_url=os.environ.get('BIRCH_API_URL', DEFAULT_URL), api_key=token)


_DEFAULT = None


def handle_request(handler, api=None):
    """Return True when handled. Call first in an existing handler's GET/POST."""
    path = unquote(urlsplit(handler.path).path)
    is_api = path.startswith('/api/decision/')
    if not (is_api or path in ('/decision', '/decision/') or path.startswith('/decision-assets/')):
        return False
    def send(status, body, content_type='application/json'):
        data = json.dumps(body).encode() if content_type == 'application/json' else body
        handler.send_response(status)
        handler.send_header('Content-Type', content_type)
        handler.send_header('Content-Length', str(len(data)))
        handler.send_header('Cache-Control', 'no-store')
        handler.end_headers()
        try:
            handler.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass
    try:
        if not is_api:
            if handler.command != 'GET':
                raise APIError(405, 'Use GET for demo assets')
            if path in ('/decision', '/decision/'):
                target = WEB/'index.html'
            else:
                relative = path[len('/decision-assets/'):]
                if relative in ('client.js', 'widget.js'):
                    target = ROOT/relative
                else:
                    target = (WEB/relative).resolve()
                    if not target.is_relative_to(WEB):
                        raise APIError(404, 'Unknown asset')
            if not target.is_file():
                raise APIError(404, 'Unknown asset')
            content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            if target.suffix == '.js':
                content_type = 'text/javascript'
            send(200, target.read_bytes(), content_type)
            return True
        # Keep a localhost backend's credential out of foreign browser origins.
        host = urlsplit('//'+handler.headers.get('Host', '')).hostname
        allowed_hosts = os.environ.get('BIRCH_ALLOWED_HOSTS', '127.0.0.1,localhost,::1').split(',')
        if '*' not in allowed_hosts and host not in {h.strip() for h in allowed_hosts}:
            raise APIError(403, 'Add this demo hostname to BIRCH_ALLOWED_HOSTS')
        origin = handler.headers.get('Origin')
        if (origin and urlsplit(origin).netloc != handler.headers.get('Host')) or handler.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise APIError(403, 'Use the decision API from this app origin')
        global _DEFAULT
        if api is None:
            if _DEFAULT is None:
                _DEFAULT = from_environment()
            api = _DEFAULT
        body = None
        if handler.command == 'POST':
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 <= length <= MAX_BODY:
                raise APIError(413, 'Decision request exceeds 512 KiB')
            body = json.loads(handler.rfile.read(length) or b'{}')
            if not isinstance(body, dict):
                raise APIError(422, 'Send a JSON object')
        send(200, api.call(handler.command, path[len('/api/decision'):], body))
    except APIError as error:
        send(error.status, dict(detail=error.detail))
    except KeyError:
        send(404, dict(detail='Unknown decision or missing required field'))
    except (ValueError, TypeError, AttributeError):
        send(422, dict(detail='Invalid decision request; check question IDs, choices and JSON fields'))
    return True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not handle_request(self):
            self.send_response(302); self.send_header('Location', '/decision'); self.end_headers()
    def do_POST(self):
        if not handle_request(self):
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--fixture', action='store_true')
    args = parser.parse_args()
    if args.fixture:
        os.environ['BIRCH_DECISION_MODE'] = 'fixture'
    global _DEFAULT
    _DEFAULT = from_environment()
    print(f'Decision adapter on http://127.0.0.1:{args.port}/decision ({_DEFAULT.mode}); no GPU starts until an explicit API call', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
