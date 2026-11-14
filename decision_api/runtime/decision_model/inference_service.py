"""Scoring, visible-evidence pathway proposals and explicit human corrections."""
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from .inference_schema import ScoreRequest, Question, Choice
from .tree import choose_action, validate_tree, node_request


def now():
    return datetime.now(timezone.utc).isoformat()


class DecisionStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        with self.db:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, decision_id TEXT NOT NULL, document TEXT NOT NULL)')

    def save(self, document):
        with self.lock, self.db:
            self.db.execute('INSERT INTO decisions VALUES (?,?)', (document['id'], json.dumps(document)))

    def get(self, identifier):
        with self.lock:
            row = self.db.execute('SELECT document FROM decisions WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise KeyError('Unknown decision ID')
        return json.loads(row[0])

    def review(self, identifier, review):
        decision = self.get(identifier)
        question = next((q for q in decision['questions'] if q['id'] == review.question_id), None)
        if question is None or review.action_id not in {c['id'] for c in question['choices']}:
            raise ValueError('Reviewed action must belong to the recorded question')
        document = dict(id=uuid.uuid4().hex, decision_id=identifier, created_at=now(),
                        **review.model_dump(), proposed_action_id=question['proposed_action_id'],
                        is_correction=review.action_id != question['proposed_action_id'])
        with self.lock, self.db:
            self.db.execute('INSERT INTO reviews VALUES (?,?,?)',
                            (document['id'], identifier, json.dumps(document)))
        return document

    def export_reviews(self):
        # A review collection, not an automatically labelled training split.
        with self.lock:
            rows = self.db.execute('SELECT r.document,d.document FROM reviews r JOIN decisions d ON r.decision_id=d.id ORDER BY r.rowid').fetchall()
        return [dict(artifact_type='reviewed_decision', review=json.loads(review),
                     decision=json.loads(decision)) for review, decision in rows]

    def close(self):
        self.db.close()


class ImageStore:
    max_bytes = 10 * 1024**2

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data):
        from PIL import Image
        import io
        if not data or len(data) > self.max_bytes:
            raise ValueError('Image must contain between 1 byte and 10 MiB')
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 25_000_000:
                    raise ValueError('Image exceeds 25 megapixels')
                image.verify()
        except (OSError, SyntaxError, Image.DecompressionBombError) as error:
            raise ValueError('Invalid image') from error
        identifier = uuid.uuid4().hex
        path = self.root/(identifier+'.image')
        path.write_bytes(data)
        return dict(id=identifier, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))

    def resolve(self, identifiers):
        paths, records = [], []
        for identifier in identifiers:
            if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
                raise ValueError('Unknown image ID; upload photos through /v1/images')
            path = self.root/(identifier+'.image')
            if not path.is_file():
                raise ValueError('Unknown image ID; upload photos through /v1/images')
            paths.append(path)
            records.append(dict(id=identifier, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        return paths, records


class DecisionService:
    def __init__(self, predictor, store, images):
        self.predictor, self.store, self.images = predictor, store, images

    def score(self, request, *, pathway=None):
        started = time.perf_counter()
        paths, image_records = self.images.resolve(request.image_ids)
        questions = [dict(question=q.text, choices=[c.text for c in q.choices],
                          candidate_format=q.candidate_format) for q in request.questions]
        result = self.predictor.predict(request.context, questions, images=paths)
        probabilities = result['probabilities']
        if len(probabilities) != len(request.questions):
            raise RuntimeError('Backend returned the wrong question count')
        answers = []
        for question, values in zip(request.questions, probabilities):
            try:
                if any(type(p) not in (float, int) for p in values):
                    raise ValueError('Scores must be numbers')
                index = choose_action([c.model_dump() for c in question.choices], values)
            except (ValueError, TypeError) as error:
                raise RuntimeError('Backend returned invalid candidate probabilities') from error
            ranked = sorted(values, reverse=True)
            answers.append(dict(id=question.id, text=question.text, candidate_format=question.candidate_format,
                choices=[dict(**c.model_dump(), score=float(p)) for c, p in zip(question.choices, values)],
                proposed_action_id=question.choices[index].id,
                score_margin=float(ranked[0]-ranked[1])))
        response = dict(id=uuid.uuid4().hex, created_at=now(), case_id=request.case_id,
                        backend=dict(self.predictor.metadata), score_kind='candidate_softmax',
                        requires_review=True, questions=answers, cache=result.get('cache', {}),
                        latency_ms=round((time.perf_counter()-started)*1000, 3))
        if pathway is not None:
            response['pathway'] = pathway
            chosen = answers[0]['proposed_action_id']
            response['proposed_next_node_id'] = pathway['allowed_next_nodes'][chosen]
        document = dict(response, input=dict(context=request.context, image_assets=image_records))
        self.store.save(document)
        return response

    def propose(self, request):
        tree = request.workflow.model_dump(exclude_none=True)
        validate_tree(tree)
        if request.node_id not in tree['nodes']:
            raise ValueError('Unknown workflow node')
        node = tree['nodes'][request.node_id]
        if node.get('terminal'):
            raise ValueError('Terminal workflow nodes have no choices to score')
        history, position = [], tree['root']
        for completed in request.history:
            if completed.node_id != position:
                raise ValueError('Completed history does not follow the workflow')
            action = next((a for a in tree['nodes'][position]['actions'] if a['id'] == completed.action_id), None)
            if action is None:
                raise ValueError('Completed history contains an unknown action')
            history.append(action)
            position = action['next']
        if history and position != request.node_id:
            raise ValueError('Completed history does not reach the requested node')
        visible = [e for e in request.case.evidence if e.available_at_step <= request.case.step]
        context = request.case.context
        if visible:
            context += '\nAvailable observations:\n' + '\n'.join(
                f'[{e.source_id}] {e.text}' for e in visible)
        context, _ = node_request(tree, request.node_id, context, history)
        score_request = ScoreRequest(context=context, case_id=request.case.case_id,
            image_ids=request.case.image_ids,
            questions=[Question(id=request.node_id, text=node['question'],
                choices=[Choice(id=a['id'], text=a['description']) for a in node['actions']])])
        # Neither future observations nor hidden simulator fields enter the audit record.
        provenance = dict(workflow_id=request.workflow.id, workflow_version=request.workflow.version,
                          workflow_sha256=hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest(),
                          node_id=request.node_id, step=request.case.step,
                          visible_source_ids=[e.source_id for e in visible],
                          allowed_next_nodes={a['id']: a['next'] for a in node['actions']})
        return self.score(score_request, pathway=provenance)
