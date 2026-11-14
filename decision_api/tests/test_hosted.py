import importlib.util
import time
import unittest
from unittest.mock import patch

@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'),'Optional FastAPI runtime')
class HostedTests(unittest.TestCase):
    def test_job_polls_without_replaying_inference_and_public_metadata(self):
        from fastapi.testclient import TestClient
        from decision_api.hosted import create_app
        import threading
        ready=threading.Event()
        class Fake:
            def __init__(self):self.calls=[]
            def call(self,method,route,body=None):
                self.calls.append((method,route,body))
                if route=='/reason':ready.wait(5)
                return {'answer':route}
        api=Fake();client=TestClient(create_app(api))
        self.assertEqual(client.get('/api/decision/examples').json(),{'answer':'/examples'})
        result=client.post('/api/decision/reason',json={'example_id':'pathway'});
        self.assertEqual(result.status_code,202)
        ready.set()
        url='/api/decision'+result.json()['status_url']
        for _ in range(100):
            result=client.get(url)
            if result.status_code!=202:break
            time.sleep(.01)
        self.assertEqual(result.json(),{'answer':'/reason'})
        self.assertEqual(sum(route=='/reason' for _,route,_ in api.calls),1)
        self.assertEqual(client.get(url).json(),result.json())
        self.assertEqual(client.post('/api/decision/score',json={'context':'x'*12001}).status_code,422)
        fast=client.post('/api/decision/score',json={'context':'Visible'})
        self.assertEqual(fast.status_code,200);self.assertEqual(fast.json(),{'answer':'/score'})
        self.assertEqual(sum(route=='/score' for _,route,_ in api.calls),1)
        self.assertEqual(client.post('/api/decision/unknown',json={}).status_code,404)
        self.assertEqual(client.get('/decision-assets/client.js').status_code,200)
        self.assertEqual(client.options('/api/decision/reason',headers={'Origin':'https://demo.example','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'}).headers['access-control-allow-origin'],'*')
    def test_secretless_project_uses_hosted_gateway(self):
        from decision_api.server import HostedDecisionAPI,from_environment
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d,patch.dict('os.environ',{'BIRCH_API_KEY':'','BIRCH_API_KEY_FILE':d+'/missing','BIRCH_DECISION_MODE':'live'}):
            self.assertIsInstance(from_environment(),HostedDecisionAPI)

class ResultRedirectTests(unittest.TestCase):
    def test_native_result_redirect_polls_same_call_with_get(self):
        import io,json
        from urllib.error import HTTPError
        from decision_api.server import DecisionAPI
        class Reply(io.BytesIO):
            status=200
        class Upstream:
            def __init__(self):self.calls=[]
            def open(self,request,timeout):
                self.calls.append(request)
                if len(self.calls)==1:
                    raise HTTPError(request.full_url,303,'Result',{'Location':request.full_url+'?__modal_result=test'},io.BytesIO())
                return Reply(json.dumps({'id':'accepted-once'}).encode())
        upstream=Upstream();api=DecisionAPI(api_key='test-secret',opener=upstream)
        self.assertEqual(api.remote('/v1/score',{'context':'visible'}),{'id':'accepted-once'})
        self.assertEqual([r.get_method() for r in upstream.calls],['POST','GET'])
        self.assertIsNone(upstream.calls[1].data)
