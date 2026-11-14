import copy
import hashlib
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from decision_api.server import DecisionAPI, Handler, ROOT, handle_request


class Reply(io.BytesIO):
    status = 200
    def __init__(self, data): super().__init__(json.dumps(data).encode())


class RecordingUpstream:
    def __init__(self): self.calls = []
    def open(self, request, timeout):
        self.calls.append(request)
        if request.full_url.endswith('/prepare'):
            return Reply(dict(id='b'*32, context='Published visible example context'))
        if request.full_url.endswith('/healthz'):
            return Reply(dict(ready=True, backend=dict(mode='model')))
        return Reply(json.loads((ROOT/'web/precomputed.json').read_text())['entries']['example-1']['decision'])


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.upstream = RecordingUpstream()
        self.api = DecisionAPI(mode='live', api_key='server-only-secret', opener=self.upstream)
        api = lambda: self.api
        class TestHandler(Handler):
            def do_GET(handler):
                if not handle_request(handler, api()): handler.send_error(404)
            def do_POST(handler):
                if not handle_request(handler, api()): handler.send_error(404)
            def log_message(self, *args): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = 'http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
    def request(self, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base+path, data=data, headers=headers or {})
        try:
            with urlopen(request, timeout=5) as response: return response.status, response.read()
        except HTTPError as error: return error.code, error.read()

    def test_saved_examples_assets_do_not_call_gpu_or_reveal_key(self):
        for path in ['/decision', '/decision-assets/client.js', '/decision-assets/widget.js', '/decision-assets/samples/example-1.png', '/api/decision/examples']:
            status, body = self.request(path); self.assertEqual(status, 200, path)
            self.assertNotIn(b'server-only-secret', body)
        status, body = self.request('/api/decision/examples/example-2/decision')
        saved = json.loads(body)
        self.assertEqual(saved['delivery'], 'precomputed')
        self.assertEqual(saved['decision']['backend']['mode'], 'model')
        self.assertEqual(saved['decision']['backend']['step'], 1138)
        self.assertFalse(self.upstream.calls)
        self.assertNotIn(b'type="file"', self.request('/decision')[1])

    def test_original_medical_images_match_attributed_catalog(self):
        catalog = json.loads((ROOT/'web/samples/catalog.json').read_text())
        self.assertEqual(catalog['license'], 'CC BY 4.0')
        for sample in catalog['examples']:
            status, data = self.request(sample['url'])
            self.assertEqual(status, 200)
            self.assertEqual(hashlib.sha256(data).hexdigest(), sample['sha256'])

    def test_photo_live_flow_registers_bundled_image_then_scores_without_upload(self):
        status, body = self.request('/api/decision/samples/example-2/score', {})
        self.assertEqual(status, 200, body)
        self.assertEqual(len(self.upstream.calls), 2)
        self.assertTrue(self.upstream.calls[0].full_url.endswith('/demo/samples/example-2/prepare'))
        self.assertTrue(self.upstream.calls[1].full_url.endswith('/v1/score'))
        payload = json.loads(self.upstream.calls[1].data)
        self.assertEqual(payload['image_ids'], ['b'*32])
        self.assertEqual(payload['questions'][0]['candidate_format'], 'inline')
        for request in self.upstream.calls:
            self.assertEqual(request.get_header('Authorization'), 'Bearer server-only-secret')
        self.assertNotIn(b'server-only-secret', body)

    def test_reject_raw_decisions_and_old_scores_before_remote_call(self):
        saved = json.loads((ROOT/'web/precomputed.json').read_text())['entries']['pathway']['decision']
        self.assertEqual(self.request('/api/decision/score', saved)[0], 422)
        payload = json.loads((ROOT/'web/score.json').read_text())
        payload['questions'][0]['choices'][0]['score'] = .8
        self.assertEqual(self.request('/api/decision/score', payload)[0], 422)
        self.assertFalse(self.upstream.calls)

    def test_origin_host_and_static_path_boundaries(self):
        self.assertEqual(self.request('/api/decision/health', headers={'Origin': 'https://other.example'})[0], 403)
        self.assertEqual(self.request('/api/decision/health', headers={'Host': 'other.example'})[0], 403)
        for path in ['/decision-assets/../server.py', '/decision-assets/%2e%2e/server.py', '/api/decision/../../secret']:
            self.assertEqual(self.request(path)[0], 404, path)
        self.assertFalse(self.upstream.calls)

    def test_missing_key_and_operator_pause_never_fall_back(self):
        self.api = DecisionAPI(mode='live', api_key='', opener=self.upstream)
        self.assertEqual(self.request('/api/decision/health')[0], 503)
        self.api.api_key = 'server-only-secret'
        with patch.dict(os.environ, {'BIRCH_DECISION_PAUSED': '1'}):
            self.assertEqual(self.request('/api/decision/health')[0], 503)
            self.assertEqual(self.request('/api/decision/examples/pathway/decision')[0], 200)
        self.assertFalse(self.upstream.calls)

    def test_fixture_trace_and_append_only_reviews(self):
        self.api = DecisionAPI(mode='fixture')
        payload = json.loads((ROOT/'web/score.json').read_text())
        status, body = self.request('/api/decision/score', payload)
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        self.assertEqual(result['backend']['mode'], 'fixture')
        review = dict(question_id='skin-category', action_id='malignant', reviewer='test')
        endpoint='/api/decision/decisions/'+result['id']
        self.assertEqual(self.request(endpoint+'/review', dict(review, action_id='unknown'))[0], 422)
        self.assertTrue(json.loads(self.request(endpoint+'/review', review)[1])['is_correction'])
        self.assertEqual(self.request(endpoint+'/review', review)[0], 200)
        self.assertEqual(len(self.api.fixture.reviews), 2)
        trace = json.loads(self.request(endpoint)[1])
        self.assertEqual(trace['questions'], result['questions'])
        self.assertEqual(trace['input']['context'], payload['context'])
        payload['questions'][0]['text']='Unknown fixture question'
        self.assertEqual(self.request('/api/decision/score', payload)[0], 422)

    def test_fixture_pathway_omits_future_observations(self):
        self.api = DecisionAPI(mode='fixture')
        payload = json.loads((ROOT/'web/pathway.json').read_text())
        status, body = self.request('/api/decision/pathway', payload)
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        trace = self.api.fixture.decision(result['id'])
        self.assertNotIn('future simulator observation', json.dumps(trace))
        self.assertEqual(result['proposed_next_node_id'], 'await-review')
        payload['workflow']['nodes']['intake']['actions'][0]['next']='intake'
        self.assertEqual(self.request('/api/decision/pathway', payload)[0], 422)

    def test_remote_failures_keep_status_and_do_not_forward_redirects(self):
        class ErrorUpstream:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 503, 'starting', {}, io.BytesIO(b'{"detail":"starting"}'))
        self.api.opener = ErrorUpstream()
        status, body = self.request('/api/decision/health')
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)['detail'], 'starting')
        self.assertNotIn(b'fixture', body)

    def test_existing_demo_can_mount_routes_without_changing_its_examples(self):
        try:
            from note_reader.server import Handler as ProjectHandler
        except ImportError as error:
            self.skipTest('Existing project dependencies unavailable: '+str(error))
        from decision_api import server
        with patch.object(server, '_DEFAULT', self.api):
            app = ThreadingHTTPServer(('127.0.0.1', 0), ProjectHandler)
            thread = threading.Thread(target=app.serve_forever, daemon=True); thread.start()
            try:
                with urlopen('http://127.0.0.1:'+str(app.server_port)+'/api/examples') as response:
                    self.assertIsInstance(json.load(response), list)
                with urlopen('http://127.0.0.1:'+str(app.server_port)+'/api/decision/examples') as response:
                    self.assertIn('photos', json.load(response))
            finally:
                app.shutdown(); app.server_close(); thread.join()
