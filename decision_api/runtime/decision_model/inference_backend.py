"""Immutable model inference with bounded, checkpoint-local representation reuse."""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import threading


class FixturePredictor:
    """Exact recorded responses for integration checks; never a model fallback."""
    def __init__(self, path):
        raw = Path(path).read_bytes()
        self.spec = json.loads(raw)
        if self.spec.get('synthetic') is not True:
            raise ValueError('Fixture responses must be explicitly synthetic')
        self.metadata = dict(mode='fixture', model='scripted-integration-fixture',
                             checkpoint_sha256=hashlib.sha256(raw).hexdigest(), step=None)

    def predict(self, context, questions, images=()):
        result = []
        for question in questions:
            recorded = self.spec['questions'].get(question['question'])
            if recorded is None or set(recorded) != set(question['choices']):
                raise ValueError('No exact fixture for this question and candidate set; use a model backend')
            result.append([recorded[c] for c in question['choices']])
        return dict(probabilities=result, cache=dict(context_hits=0, candidate_hits=0,
                                                   enabled=False))


class CachedPredictor:
    def __init__(self, model, metadata, cache_bytes=64 * 1024**2):
        if cache_bytes < 0:
            raise ValueError('Cache budget cannot be negative')
        self.model = model.eval()
        self.metadata = dict(metadata, mode='model')
        self.limit = cache_bytes
        self.cache = OrderedDict()
        self.bytes = 0
        self.lock = getattr(model, '_prediction_lock', threading.Lock())

    def _get(self, key):
        value = self.cache.pop(key, None)
        if value is not None:
            self.cache[key] = value
        return value

    def _put(self, key, value):
        value = value.detach().cpu().clone()
        size = value.numel() * value.element_size()
        if size > self.limit or not self.limit:
            return
        previous = self.cache.pop(key, None)
        if previous is not None:
            self.bytes -= previous.numel() * previous.element_size()
        while self.cache and self.bytes + size > self.limit:
            _, old = self.cache.popitem(last=False)
            self.bytes -= old.numel() * old.element_size()
        self.cache[key] = value
        self.bytes += size

    def predict(self, context, questions, images=()):
        import torch
        # Read bytes as well as paths: replacing a photo must invalidate reuse.
        image_hashes = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in images]
        context_key = ('context', hashlib.sha256(json.dumps([context, image_hashes]).encode()).hexdigest())
        texts, lookup, indices = [], {}, []
        for question in questions:
            positions = []
            for choice in question['choices']:
                separator = ' | candidate: ' if question.get('candidate_format') == 'inline' else '\nCandidate answer: '
                text = f"Question: {question['question']}{separator}{choice}"
                if text not in lookup:
                    lookup[text] = len(texts)
                    texts.append(text)
                positions.append(lookup[text])
            indices.append(positions)
        candidate_keys = [('candidate', hashlib.sha256(text.encode()).hexdigest()) for text in texts]
        with self.lock, torch.inference_mode():
            self.model.eval()
            device = next(self.model.head.parameters()).device
            context_value = self._get(context_key)
            context_hit = context_value is not None
            if not context_hit:
                context_value = self.model.encode_context(context, images)
                self._put(context_key, context_value)
            values = [self._get(key) for key in candidate_keys]
            hits = sum(v is not None for v in values)
            missing = [i for i, value in enumerate(values) if value is None]
            if missing:
                encoded = self.model.encode([texts[i] for i in missing])
                for row, index in enumerate(missing):
                    values[index] = encoded[row:row+1]
                    self._put(candidate_keys[index], values[index])
            candidates = torch.cat([v.to(device) for v in values])
            context_value = context_value.to(device)
            probabilities = []
            for index in indices:
                logits = self.model.head(context_value, candidates[index].unsqueeze(0))
                probabilities.append(logits.float().softmax(-1)[0].tolist())
        return dict(probabilities=probabilities,
                    cache=dict(enabled=bool(self.limit), context_hits=int(context_hit),
                               candidate_hits=hits, candidate_count=len(texts), bytes=self.bytes,
                               max_bytes=self.limit))


def checkpoint_predictor(checkpoint, *, layout=None, cache_bytes=64 * 1024**2):
    from .predict import load_predictor
    path = Path(checkpoint)
    record = json.loads((path/'state.json').read_text())
    manifest = json.loads((path/'sha256.json').read_text())
    runtime = dict(prefix_cache_bytes=0)
    if layout:
        runtime['gpu_layout'] = layout
        runtime['gpu_max_memory'] = '44GiB' if layout == '8x48gb' else '84GiB'
    model = load_predictor(path, runtime_config=runtime)
    metadata = dict(model=record['config']['model'], revision=record['config']['revision'],
                    training_identity=record['identity'], step=record['state']['step'],
                    checkpoint_sha256=manifest['trainable.safetensors'])
    return CachedPredictor(model, metadata, cache_bytes)
