"""Explicit, scripted examples for UI development. Never a live-model fallback."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import uuid

ROOT = Path(__file__).resolve().parent


class Fixture:
    def __init__(self):
        raw = (ROOT/'fixture.json').read_bytes()
        self.spec = json.loads(raw)['questions']
        self.metadata = dict(mode='fixture', model='scripted-integration-fixture',
                             checkpoint_sha256=hashlib.sha256(raw).hexdigest(), step=None)
        self.decisions, self.reviews, self.assets = {}, [], {}
        self.lock = threading.RLock()

    def prepare(self, sample):
        identifier = uuid.uuid4().hex
        with self.lock:
            self.assets[identifier] = dict(id=identifier, sha256=sample['sha256'])
        return dict(id=identifier, context=sample['context'])

    def score(self, body, *, pathway=None, destination=None):
        if set(body)-{'context', 'case_id', 'image_ids', 'questions'}:
            raise ValueError('Unknown scoring fields')
        if not isinstance(body.get('context'), str) or not body['context'].strip():
            raise ValueError('A visible context is required')
        questions = body.get('questions', [])
        if not 1 <= len(questions) <= 32 or len({q['id'] for q in questions}) != len(questions):
            raise ValueError('Use distinct question IDs')
        scored = []
        for q in questions:
            choices = q['choices']
            if len({c['id'] for c in choices}) != len(choices):
                raise ValueError('Choice IDs must be distinct')
            known = self.spec.get(q['text'])
            if known is None or len(choices) != len(known) or {c['text'] for c in choices} != set(known):
                raise ValueError('No exact fixture for these choices; use live mode for custom questions')
            mode = q.get('candidate_format', 'newline')
            if mode not in ('newline', 'inline'):
                raise ValueError('Unknown candidate format')
            values = [dict(c, score=known[c['text']]) for c in choices]
            ranked = sorted(values, key=lambda c: (-c['score'], c['id']))
            scored.append(dict(id=q['id'], text=q['text'], candidate_format=mode, choices=values,
                               proposed_action_id=ranked[0]['id'], score_margin=ranked[0]['score']-ranked[1]['score']))
        with self.lock:
            if any(i not in self.assets for i in body.get('image_ids', [])):
                raise ValueError('Choose a bundled photo example')
            identifier = uuid.uuid4().hex
            result = dict(id=identifier, created_at=datetime.now(timezone.utc).isoformat(),
                          case_id=body.get('case_id'), backend=self.metadata,
                          requires_review=True, score_kind='candidate_softmax', questions=scored,
                          cache=dict(enabled=False), latency_ms=0.0)
            if pathway:
                result.update(pathway=pathway, proposed_next_node_id=destination)
            trace = deepcopy(result)
            trace['input'] = dict(context=body['context'], questions=deepcopy(questions),
                                  image_assets=[self.assets[i] for i in body.get('image_ids', [])])
            self.decisions[identifier] = trace
            return deepcopy(result)

    def propose(self, body):
        bundled = json.loads((ROOT/'web/pathway.json').read_text())
        if body != bundled:
            raise ValueError('Fixture pathway accepts only the bundled synthetic graph; use live mode to change it')
        case, graph, node_id = body['case'], body['workflow'], body['node_id']
        node = graph['nodes'][node_id]
        visible = [e for e in case['evidence'] if e['available_at_step'] <= case['step']]
        context = case['context']+'\n'+'\n'.join(e['text'] for e in visible)+'\n'+node['protocol']
        payload = dict(context=context, case_id=case['case_id'], questions=[dict(
            id=node_id, text=node['question'], choices=[dict(id=a['id'], text=a['description']) for a in node['actions']])])
        result = self.score(payload)
        chosen = result['questions'][0]['proposed_action_id']
        result['proposed_next_node_id'] = next(a['next'] for a in node['actions'] if a['id'] == chosen)
        result['pathway'] = dict(workflow_id=graph['id'], workflow_version=graph['version'], node_id=node_id,
                                 visible_source_ids=[e['source_id'] for e in visible])
        with self.lock:
            self.decisions[result['id']].update(pathway=result['pathway'], proposed_next_node_id=result['proposed_next_node_id'])
        return result

    def decision(self, identifier):
        with self.lock:
            return deepcopy(self.decisions[identifier])

    def review(self, identifier, body):
        if set(body)-{'question_id', 'action_id', 'reviewer', 'note'} or not str(body.get('reviewer', '')).strip():
            raise ValueError('Review needs question_id, action_id and a reviewer label')
        with self.lock:
            trace = self.decisions[identifier]
            question = next((q for q in trace['questions'] if q['id'] == body['question_id']), None)
            if question is None or body['action_id'] not in {c['id'] for c in question['choices']}:
                raise ValueError('Review must choose an action that was scored')
            event = dict(id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
                         decision_id=identifier, note='', **{k:v for k,v in body.items() if k != 'note'})
            event.update(note=body.get('note', ''), proposed_action_id=question['proposed_action_id'],
                         is_correction=body['action_id'] != question['proposed_action_id'])
            self.reviews.append(event)
            return deepcopy(event)
