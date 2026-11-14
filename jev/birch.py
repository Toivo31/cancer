"""The team's decision model (checkpoint 2350, the "Birch" API) as a JEV backend.

The model is deployed on Modal; the owner's local proxy (``python -m decision_api.server``) holds the key
and exposes ``POST /api/decision/pathway``. This module turns a :class:`DecisionRequest` built from a
patient record into one pathway-propose call, and the answer (relative candidate scores over the offered
actions) into ``probs``. Nothing here ever sees or sends a key.

Owner's rules (decision_api/README.md, INTEGRATION_PROMPT.md), built in as guards:

* visible information only (what the record holds; checked again on the payload before every send);
* no bulk cohort inference and no polling: a hard call budget, a disk cache, concurrency 1, no retries,
  a stop after repeated failures, a single-option decision is never sent;
* the model proposes and a person reviews: ``python -m jev.walk`` is the review loop;
* about 5-7 s per warm call, a cold start about 6 minutes, it costs money while it runs: failures are
  loud errors, never a silent fallback (``BirchUnavailable`` carries the proxy's own message).

Checkpoint 2350 (WP-W8-1): with no key, the owner's proxy forwards to the hosted gateway, whose limits are
6 submissions a minute and 120 an hour (shared by everyone using it), a request body of at most 32,000 bytes
(measured as ``json.dumps``) and a case context of at most 12,000 characters; natively a node takes at most
16 actions (checked on the pinned backend; a mock does not model it). Requests over these limits fail here,
before sending. :func:`pinned_backend` returns the owner's
bridge (``decision_api.jev_bridge``), which refuses any answer or cache entry not from step 2350 with the
pinned weight hash; the factory (``birch``), :func:`policy_for_world` and ``jev.walk`` use it for live calls.

The API returns scores only, no rationale. ``probs`` are the scores renormalised over the offered ids;
``record_note`` and ``assessment`` stay empty. :class:`BirchPolicy` writes a labelled template line into
the record so the log shows who proposed what.
"""

from __future__ import annotations

import re

import hashlib
import http.client
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import urllib.parse
from collections import Counter
from pathlib import Path

from patient_engine.card import HIDDEN_FIELD_NAMES

from .adapter import BackendPolicy
from .contract import BackendError, BackendInfo, ContractError, DecisionRequest, DecisionResponse

DEFAULT_URL = "http://127.0.0.1:8771"
PATH = "/api/decision/pathway"
DEFAULT_MAX_CALLS = 50
MAX_CONCURRENCY = 4              # the owner does not know the endpoint's limit; default 1, at most 4
MAX_NOTE_CHARS = 2000
DEFAULT_TIMEOUT = 660.0           # the hosted gateway's documented overall wait (a cold start takes minutes)
MAX_FAILURES_IN_A_ROW = 2         # after this many failed calls in a row nothing more is sent
GATEWAY_MAX_BODY_BYTES = 32000    # decision_api/hosted.py: len(json.dumps(body)) > 32000 -> 422
GATEWAY_MAX_CONTEXT_CHARS = 12000 # decision_api/hosted.py: case.context longer than this -> 422
MAX_ACTIONS_PER_NODE = 16         # native schema (runtime/decision_model/inference_schema.py)
MAX_BODY_BYTES = GATEWAY_MAX_BODY_BYTES
GATEWAY_MIN_INTERVAL = 10.0       # seconds between live submissions: the gateway accepts 6 a minute (120 an hour)
MAX_EVIDENCE_CHARS = 3000
CHECKPOINT = 2350
CHECKPOINT_SHA256 = "22570c201a9e3d25dcdf7aa904770a568328e034ccb5ac89623784707a7323e8"
DEFAULT_CACHE_DIR = f"runs/jev_cache/checkpoint-{CHECKPOINT}-{CHECKPOINT_SHA256[:12]}"   # never the old 1138 cache
WORKFLOW_ID = "primary-care-encounter"
PROTOCOL = ("Synthetic primary-care encounter. Propose one allowed next action for a clinician to review; "
            "nothing is ordered, treated or referred automatically.")
TEMPLATE_NOTE = "Decision model proposal (checkpoint {step}); the API returns scores, no written rationale."
#: JSON keys that must never appear anywhere in what we send (hidden-side names, and ids that point at the card).
FORBIDDEN_KEYS = frozenset(HIDDEN_FIELD_NAMES) | {"card_id", "condition", "primary_condition", "gold", "label_truth"}
_SEX = {"f": "female", "m": "male"}


class BirchError(BackendError):
    """Base class of every error from this backend."""


class BirchBudgetExceeded(BirchError):
    """The call budget is used up; nothing was sent."""


class BirchUnavailable(BirchError):
    """The proxy or the model did not give a usable answer (down, paused, cold, timed out, 4xx/5xx)."""


class BirchVisibilityError(BirchError):
    """The payload would carry something the model must not see; nothing was sent."""


def _words(s) -> str:
    return str(s).replace("_", " ")


# =============================================================================================== mapping

def _payload_text(payload: dict):
    """Every string of the payload with its path (keys included)."""
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                yield f"{path}.{k}", k
                yield from walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, f"{path}[{i}]")
        elif isinstance(o, str):
            yield path, o
    yield from walk(payload, "$")


def public_phrases(catalogue, care=None) -> frozenset:
    """Labels the record legitimately shows (test, output, variable and action labels). A condition
    word inside one of these (\"Spirometry with reversibility (definitive for COPD, asthma)\") is public
    catalogue text, not a leak, so the id check ignores it."""
    out = set()
    for t in getattr(catalogue, "tests", {}).values():
        out.add(getattr(t, "label", "") or "")
        out.add(t.id.replace("_", " "))
        for o in getattr(t, "outputs", ()):
            out.add(getattr(o, "label", "") or "")
            out.add(o.id.replace("_", " "))                 # record_text falls back to the output id
    for v in getattr(catalogue, "variables", {}).values():
        out.add(getattr(v, "label", "") or "")
    for a in getattr(care, "actions", {}).values() if care is not None else ():
        out.add(getattr(a, "label", "") or "")
    return frozenset(x for x in out if x)


def check_visible(payload: dict, forbidden_values: frozenset | set = frozenset(),
                  public: frozenset | set = frozenset()) -> None:
    """Refuse a payload with hidden-side names, future evidence, or a forbidden id (invariant I1).

    Keys are checked at every level against :data:`FORBIDDEN_KEYS`. ``forbidden_values`` (the catalogue's
    condition ids, when known) must not appear in the case text or the evidence text. Evidence must
    be available at or before ``case.step``.
    """
    case = payload.get("case", {})
    step = case.get("step")
    for path, s in _payload_text(payload):
        last = path.rsplit(".", 1)[-1]
        if s == last and last in FORBIDDEN_KEYS:          # a key (the walk yields keys as their own value)
            raise BirchVisibilityError(f"hidden-side field name {s!r} at {path}")
    for e in case.get("evidence", []):
        if not isinstance(e.get("available_at_step"), int) or e["available_at_step"] > step:
            raise BirchVisibilityError(f"evidence {e.get('source_id')!r} is not available at step {step}")
    if forbidden_values:
        texts = [case.get("context", "")] + [e.get("text", "") for e in case.get("evidence", [])]
        phrases = sorted(public, key=len, reverse=True)
        for t in texts:
            t = t.lower()
            for ph in phrases:                      # public catalogue labels may name a condition
                t = t.replace(ph.lower(), " ")
            for bad in forbidden_values:
                if re.search(r"(?<![a-z0-9_])" + re.escape(bad.lower()) + r"(?![a-z0-9_])", t):
                    raise BirchVisibilityError(f"condition id {bad!r} in the text sent to the model")


def _background_words(bg: dict) -> str:
    parts = []
    for k, v in bg.items():
        if v is None:
            continue
        if k == "sex":
            parts.append(_SEX.get(str(v).lower(), str(v)))
        elif k == "age":
            parts.append(f"age {v}")
        else:
            parts.append(f"{_words(k)} {_words(v)}")
    return ", ".join(parts)


def case_text(ctx: dict, reported_labels: list[str] | None = None) -> str:
    """Background and presenting complaint in plain words (from the context's revealed keys only)."""
    bits = ["Patient in Finnish primary care (synthetic)."]
    bg = _background_words(ctx.get("background") or {"age": ctx.get("age")})
    if bg:
        bits.append(f"Background: {bg}.")
    rep = reported_labels if reported_labels is not None else [_words(r) for r in (ctx.get("presenting") or {}).get("reported", [])]
    if rep:
        bits.append("Reported at first contact: " + ", ".join(rep) + ".")
    role = ctx.get("role")
    if role:
        bits.append(f"Deciding now: {_role_name(role)}, episode {ctx.get('episode', 1)}.")
    return " ".join(bits)


def _role_name(role: str) -> str:
    return {"nurse": "nurse", "gp": "GP", "specialist": "specialist"}.get(role, str(role))


def evidence_from_context(ctx: dict) -> tuple[list[dict], int]:
    """Fallback when the request carries no rendered record: items from the context's revealed keys.

    One item for the findings asked so far, one per result, one per mechanical note. Steps are the order
    in which the items are listed (results and notes interleaved by time)."""
    items: list[tuple[float, str, str]] = []
    found = ctx.get("found") or {}
    if found:
        said = ", ".join(_words(k) if v is True else f"no {_words(k)}" if v is False else f"{_words(k)} {v}"
                         for k, v in found.items() if v is not None)
        items.append((-1.0, "found", f"Findings so far: {said}."))
    for i, o in enumerate(ctx.get("observations") or []):
        # values only, never the free-text report (review w7 B1: a model-written report may carry the hidden plan)
        vals = o.get("values") or {}
        text = ", ".join((_words(k) if v else f"no {_words(k)}") if isinstance(v, bool) else f"{_words(k)} {v}"
                         for k, v in vals.items() if v is not None)
        if o.get("status") not in (None, "ok"):
            text = "not diagnostic, needs repeating"
        text = text or str(o.get("status", ""))
        items.append((float(o.get("t_days", 0.0)), f"result{i + 1}", f"Result, {_words(o.get('test'))}: {text}"))
    for n in ctx.get("notes") or []:
        items.append((float(n.get("t_days", 0.0)), n.get("id", "note"), f"Note: {n.get('text', '')}"))
    items.sort(key=lambda x: x[0])
    ev = [{"source_id": f"record:{k + 1}:{sid}", "available_at_step": k + 1, "text": t[:MAX_EVIDENCE_CHARS]}
          for k, (_, sid, t) in enumerate(items)]
    return ev, max(1, len(ev))


def map_request(req: DecisionRequest, include_assessments: bool = False) -> dict:
    """The body of one ``POST /api/decision/pathway`` call for ``req``.

    ``req.context['record_text']`` (put there by :class:`BirchPolicy`) holds ``case`` (plain words) and
    ``lines`` (``[{"step": i, "kind": ..., "text": ...}]``, one per record entry rendered by
    ``patient_engine.record_text``). Without it the evidence is derived from the context's revealed keys.
    The case id is the request id (it is not part of the cache key).
    """
    ctx = req.context
    rt = ctx.get("record_text")
    if rt:
        lines = [x for x in rt["lines"] if include_assessments or x.get("kind") != "assessment"]
        ev = [{"source_id": f"record:{x['step']}:{x.get('kind', 'entry')}", "available_at_step": int(x["step"]),
               "text": str(x["text"])[:MAX_EVIDENCE_CHARS]} for x in lines]
        step = max([e["available_at_step"] for e in ev], default=1)
        context = rt["case"]
    else:
        ev, step = evidence_from_context(ctx)
        context = case_text(ctx)
    node = req.decision_point
    role = ctx.get("role")
    who = _role_name(role) if role else "clinician"
    actions, nodes = [], {}
    for o in req.options:
        desc = o.get("label") or _words(o["id"])
        nxt = f"after-{o['id']}"
        actions.append({"id": o["id"], "description": desc, "next": nxt})
        nodes[nxt] = {"terminal": True}
    nodes = {node: {"question": f"What should the {who} do next for this patient?", "protocol": PROTOCOL,
                    "actions": actions}, **nodes}
    return {"case": {"case_id": req.request_id, "context": context, "step": step, "evidence": ev},
            "workflow": {"id": WORKFLOW_ID, "version": "1", "root": node, "nodes": nodes}, "node_id": node}


def check_limits(payload: dict, rid: str = "request", max_actions: int | None = MAX_ACTIONS_PER_NODE) -> None:
    """Refuse, before sending, a request the hosted gateway or the native model would reject (nothing is trimmed:
    no silent change to what the model sees). The body is measured as the gateway measures it."""
    size = len(json.dumps(payload))
    if size > GATEWAY_MAX_BODY_BYTES:
        raise BirchError(f"{rid}: request is {size} bytes as json.dumps; the hosted gateway refuses more than "
                         f"{GATEWAY_MAX_BODY_BYTES} bytes (a long record: fewer or shorter evidence items, or the "
                         "owner's authenticated endpoint); nothing was sent")
    ctx = payload.get("case", {}).get("context", "")
    if len(ctx) > GATEWAY_MAX_CONTEXT_CHARS:
        raise BirchError(f"{rid}: case context is {len(ctx)} characters; the hosted gateway refuses more than "
                         f"{GATEWAY_MAX_CONTEXT_CHARS}; nothing was sent")
    node = payload.get("workflow", {}).get("nodes", {}).get(payload.get("node_id"), {})
    n = len(node.get("actions", []))
    if max_actions is not None and n > max_actions:
        raise BirchError(f"{rid}: node {payload.get('node_id')!r} offers {n} actions; the model takes at most "
                         f"{max_actions} per node (WP-W8-2); nothing was sent")


def cache_key(payload: dict) -> str:
    """Hash of everything that decides the answer (the case id is left out: the same record gives the same call)."""
    p = json.loads(json.dumps(payload))
    p["case"].pop("case_id", None)
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _rationale(resp: dict, q: dict) -> str | None:
    """The model's own short rationale when the API sends one (per question, else per response); None otherwise.
    Read from ``rationale`` or ``explanation``; it becomes the record note (decision D49)."""
    for src in (q, resp):
        for k in ("rationale", "explanation"):
            v = src.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()[:MAX_NOTE_CHARS]
    return None


# =============================================================================================== backend

class BirchBackend:
    """A ``DecisionBackend`` that asks the decision model (checkpoint :data:`CHECKPOINT`) through the local proxy.

    ``max_calls`` is a hard limit on calls sent (failed ones count: they cost GPU time). Answers are cached on
    disk under ``cache_dir`` (``None`` = no cache); only answers whose ``backend.mode`` is ``model`` are cached
    and served unless ``allow_non_model`` (tests against a mock server, the offline demo). One call at a time.
    """

    def __init__(self, url: str = DEFAULT_URL, *, max_calls: int = DEFAULT_MAX_CALLS, cache_dir: str | Path | None = DEFAULT_CACHE_DIR,
                 timeout: float = DEFAULT_TIMEOUT, include_assessments: bool = False, allow_non_model: bool = False,
                 forbidden_values=(), checkpoint: int = CHECKPOINT, concurrency: int = 1, min_interval: float = 0.0,
                 max_actions: int | None = None):
        u = urllib.parse.urlparse(url if "//" in url else "http://" + url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError(f"bad Birch proxy url {url!r}")
        if u.hostname.endswith(".modal.run"):
            raise ValueError("talk to the local proxy (python -m decision_api.server), which holds the key; "
                             "this backend never sends a key to the model directly")
        if not float(timeout) > 0 or max_calls < 0:
            raise ValueError("timeout must be positive and max_calls >= 0")
        self.scheme, self.host, self.port = u.scheme, u.hostname, u.port or (443 if u.scheme == "https" else 80)
        self.path = u.path.rstrip("/") if u.path.rstrip("/").endswith("/pathway") else u.path.rstrip("/") + PATH
        self.url = f"{u.scheme}://{u.netloc}{self.path}"
        self.max_calls, self.timeout = int(max_calls), float(timeout)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.include_assessments, self.allow_non_model = include_assessments, allow_non_model
        self.forbidden_values = frozenset(forbidden_values)
        self.public_phrases: frozenset = frozenset()
        self.checkpoint = checkpoint
        if not 1 <= int(concurrency) <= MAX_CONCURRENCY:
            raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
        self.concurrency = int(concurrency)
        if not float(min_interval) >= 0:
            raise ValueError("min_interval must be >= 0 seconds")
        self.min_interval = float(min_interval)       # spacing between live submissions (gateway rate limit)
        self._last_send: float | None = None
        self.max_actions = max_actions                # actions per node the model takes (None: not checked, e.g. a mock)
        self._slots = threading.BoundedSemaphore(self.concurrency)   # live calls in flight
        self._state = threading.RLock()               # counters, budget, cache files
        self.calls = self.failures = self.cache_hits = self.single_option = 0
        self._in_a_row = 0
        self.latencies: list[float] = []              # model-side latency_ms of live calls
        self.wall: list[float] = []                   # our wall time per live call, seconds
        self.backends_seen: Counter = Counter()
        self.last_error: str | None = None
        self.last_response: dict | None = None        # raw proxy answer of the latest decision (for the walk tool)
        self.last_payload: dict | None = None
        self.last_cached = False

    # ------------------------------------------------------------------ protocol
    def info(self) -> BackendInfo:
        return BackendInfo("birch", f"birch-{self.checkpoint}", True, None, {"url": self.url, "max_calls": self.max_calls})

    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]:
        if self.concurrency == 1 or len(requests) < 2:
            return [self._decide_one(r) for r in requests]        # one at a time, in order
        with ThreadPoolExecutor(self.concurrency) as ex:
            return list(ex.map(self._decide_one, requests))       # at most `concurrency` calls in flight, order kept

    def summary(self) -> dict:
        s = {"calls": self.calls, "max_calls": self.max_calls, "cache_hits": self.cache_hits,
             "single_option_decisions": self.single_option, "failures": self.failures}
        if self.latencies:
            lat = sorted(self.latencies)
            s["latency_ms_median"] = round(lat[len(lat) // 2], 1)
            s["latency_ms_max"] = round(lat[-1], 1)
            s["wall_seconds"] = round(sum(self.wall), 1)
        if self.backends_seen:
            s["backend"] = dict(self.backends_seen)
        if self.last_error:
            s["last_error"] = self.last_error
        return s

    # ------------------------------------------------------------------ one decision
    def _decide_one(self, req: DecisionRequest) -> DecisionResponse:
        ids = req.option_ids
        if len(ids) == 1:                                        # nothing to propose: never pay for it
            with self._state:
                self.single_option += 1
            return DecisionResponse(req.request_id, {ids[0]: 1.0}, "single option, model not asked")
        payload = map_request(req, self.include_assessments)
        check_visible(payload, self.forbidden_values, self.public_phrases)
        check_limits(payload, req.request_id, self.max_actions)   # gateway and native limits: fail before sending
        body = json.dumps(payload, ensure_ascii=False).encode()
        key = cache_key(payload)
        with self._slots:
            with self._state:
                resp = self._cache_get(key)                      # a second worker with the same key finds the first one's answer
                cached = resp is not None
                if cached:
                    self.cache_hits += 1
                else:
                    self._admit(req.request_id)                  # budget and failure breaker, counted before sending
            if not cached:
                resp = self._call(body, req.request_id)
                with self._state:
                    self._cache_put(key, payload, resp)
        self.last_payload, self.last_response, self.last_cached = payload, resp, cached
        return self._to_response(req, payload, resp, cached)

    def _to_response(self, req: DecisionRequest, payload: dict, resp: dict, cached: bool) -> DecisionResponse:
        try:
            q = resp["questions"][0]
            scores = {c["id"]: float(c["score"]) for c in q["choices"]}
        except (KeyError, IndexError, TypeError, ValueError):
            raise BirchError(f"{req.request_id}: the model answer has no questions[0].choices[].score") from None
        offered = req.option_ids
        if q.get("id") != payload["node_id"] or set(scores) != set(offered):
            raise BirchError(f"{req.request_id}: the answer scores {sorted(scores)} for {q.get('id')!r}, "
                             f"not the offered {offered} for {payload['node_id']!r}")
        total = sum(scores.values())
        if not total > 0 or any(v < 0 or v != v for v in scores.values()):
            raise BirchError(f"{req.request_id}: scores cannot be turned into probabilities: {scores}")
        probs = {o: scores[o] / total for o in offered}
        b = resp.get("backend") or {}
        with self._state:
            self.backends_seen[f"{b.get('mode')}:{b.get('step')}"] += 1
        seen = (resp.get("pathway") or {}).get("visible_source_ids")
        sent = {e["source_id"] for e in payload["case"]["evidence"]}
        extra = sorted(set(seen or []) - sent)
        if extra:
            raise BirchError(f"{req.request_id}: the model reports evidence we did not send: {extra}")
        lat = resp.get("latency_ms")
        sha = str(b.get("checkpoint_sha256") or "")[:12]
        expl = (f"birch step {b.get('step')}{' sha ' + sha if sha else ''} ({b.get('mode')}); proposed {q.get('proposed_action_id')}, margin "
                f"{q.get('score_margin', 0):.3f}; " + ("cached" if cached else f"{lat if lat is not None else '?'} ms"))
        return DecisionResponse(req.request_id, probs, expl, record_note=_rationale(resp, q))

    # ------------------------------------------------------------------ the call
    def _admit(self, rid: str) -> None:
        if self._in_a_row >= MAX_FAILURES_IN_A_ROW:
            raise BirchUnavailable(f"{rid}: stopped after {self._in_a_row} failed calls in a row ({self.last_error}); "
                                   "start or fix the proxy/model and begin a new run")
        if self.calls >= self.max_calls:
            raise BirchBudgetExceeded(f"{rid}: call budget of {self.max_calls} used up; raise --max-calls on purpose "
                                      "(each call costs GPU time) or rerun to use the cache")
        self.calls += 1                                                   # counted before sending: failures cost too
        if self.min_interval and self._last_send is not None:             # pace submissions (6 a minute at the gateway)
            wait = self._last_send + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        self._last_send = time.monotonic()

    def _call(self, body: bytes, rid: str) -> dict:
        t0 = time.monotonic()
        conn = None
        try:
            cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
            conn = cls(self.host, self.port, timeout=self.timeout)       # no proxies, no keep-alive, no retry
            conn.request("POST", self.path, body=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
            r = conn.getresponse()
            raw = r.read(4 << 20)
            status = r.status
        except (OSError, http.client.HTTPException) as e:                 # refused, reset, timed out
            self._fail(f"{rid}: no answer from {self.url} ({type(e).__name__}: {e}); is `python -m decision_api.server` running, "
                       "and is the model warm (a cold start takes about 6 minutes)?")
        finally:
            if conn is not None:
                conn.close()
        with self._state:
            self.wall.append(time.monotonic() - t0)
        if status != 200:
            try:
                detail = json.loads(raw).get("detail", "")
            except (ValueError, AttributeError):
                detail = ""
            self._fail(f"{rid}: HTTP {status} from the decision proxy: {detail or 'no detail'}")
        try:
            resp = json.loads(raw)
            b = resp.get("backend") or {}
        except (ValueError, AttributeError):
            self._fail(f"{rid}: the decision proxy sent something that is not JSON")
        if b.get("mode") != "model" and not self.allow_non_model:
            self._fail(f"{rid}: the proxy answered from backend mode {b.get('mode')!r}, not the model "
                       "(is it running with --fixture?); scripted scores are not used here")
        with self._state:
            self._in_a_row = 0
            if isinstance(resp.get("latency_ms"), (int, float)):
                self.latencies.append(float(resp["latency_ms"]))
        return resp

    def _fail(self, msg: str):
        with self._state:
            self.failures += 1
            self._in_a_row += 1
            self.last_error = msg
        raise BirchUnavailable(msg)

    # ------------------------------------------------------------------ disk cache
    def _cache_get(self, key: str) -> dict | None:
        if self.cache_dir is None:
            return None
        f = self.cache_dir / f"{key}.json"
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            return None
        resp = d.get("response") if isinstance(d, dict) else None
        if not isinstance(resp, dict) or d.get("key") != key:
            return None
        if (resp.get("backend") or {}).get("mode") != "model" and not self.allow_non_model:
            return None
        return resp

    def _cache_put(self, key: str, payload: dict, resp: dict) -> None:
        if self.cache_dir is None:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(json.dumps({"key": key, "response": resp, "saved_at": time.time()}))
            with open(self.cache_dir / "calls.jsonl", "a") as f:                  # a plain ledger of live calls
                f.write(json.dumps({"t": time.time(), "key": key, "node": payload["node_id"],
                                    "latency_ms": resp.get("latency_ms"), "mode": (resp.get("backend") or {}).get("mode")}) + "\n")
        except OSError:
            pass                                   # a cache that cannot be written only costs calls on the next run


# =============================================================================================== policy

class BirchPolicy(BackendPolicy):
    """Engine policy over a :class:`BirchBackend`: puts the record, rendered as words, into the request.

    ``catalogue`` and ``care`` (optional) give labels for findings, tests and actions; without them ids
    become words. ``choose_with_note`` adds a labelled template note and ``plan`` (the model wrote none).
    """

    def __init__(self, backend: BirchBackend, mode: str = "argmax", scenario=None, flowchart=None, catalogue=None, care=None,
                 **kw):
        super().__init__(backend, mode=mode, scenario=scenario, flowchart=flowchart, **kw)
        self.vocab, self.care = catalogue, care
        if catalogue is not None and not backend.forbidden_values:
            backend.forbidden_values = frozenset(getattr(catalogue, "conditions", {}))
        if catalogue is not None and not backend.public_phrases:
            backend.public_phrases = public_phrases(catalogue, care)

    def request_for(self, view, options: list[str]) -> DecisionRequest:
        req = super().request_for(view, options)
        for o in req.options:                                      # action labels from the care model
            a = getattr(self.care, "actions", {}).get(o["id"]) if self.care is not None else None
            if a is not None and getattr(a, "label", ""):
                o["label"] = a.label
        rec = getattr(view, "record", None)
        if rec is not None and rec.entries:
            from patient_engine.record_text import render
            entries = [e for e in rec.entries if e.kind != "assessment" or backend_wants(self.backend)]
            lines = render(type(rec)(rec.patient_id, dict(rec.background), entries), self.catalogue, self.care)
            ctx = req.context
            labels = [_label(self.vocab, v) for v in (ctx.get("presenting") or {}).get("reported", [])]
            req.context = {**ctx, "record_text": {
                "case": case_text(ctx, labels),
                "lines": [{"step": i + 1, "kind": e.kind, "text": t} for i, (e, t) in enumerate(zip(entries, lines))]}}
        return req

    def choose_with_note(self, view, options: list[str]):
        probs, said, assessment = super().choose_with_note(view, options)
        if said:                                       # the model wrote a rationale: it is the note
            return probs, said, assessment or {"plan": "{action}"}
        note = TEMPLATE_NOTE.format(step=self.backend.checkpoint) + (f" {self.last_explanation}." if self.last_explanation else "")
        return probs, note, {"plan": "{action}"}


def backend_wants(b) -> bool:
    return bool(getattr(b, "include_assessments", False))


def _label(catalogue, vid: str) -> str:
    v = getattr(catalogue, "variables", {}).get(vid) if catalogue is not None else None
    return v.label if v is not None and getattr(v, "label", "") else _words(vid)


# =============================================================================================== factory hooks

def parse_spec(spec: str) -> str | None:
    """``birch`` -> default proxy url, ``birch+http://host:port`` -> that url, anything else -> None."""
    if spec == "birch":
        return DEFAULT_URL
    if spec.startswith("birch+"):
        return spec[len("birch+"):]
    return None


def pinned_backend(**kw) -> BirchBackend:
    """The owner's bridge (``decision_api.jev_bridge.backend``): a :class:`BirchBackend` that accepts only answers
    and cache entries from step :data:`CHECKPOINT` with weight hash :data:`CHECKPOINT_SHA256`. Live calls are
    paced :data:`GATEWAY_MIN_INTERVAL` seconds apart unless ``min_interval`` says otherwise."""
    try:
        from decision_api import jev_bridge
    except ImportError as e:
        raise BirchError("decision_api/jev_bridge.py is missing: bring the owner's decision_api/ from origin/main "
                         "(docs/platform/jev-birch.md, Install and run)") from e
    if (jev_bridge.STEP, jev_bridge.SHA256) != (CHECKPOINT, CHECKPOINT_SHA256):
        raise BirchError(f"the owner's bridge pins step {jev_bridge.STEP} ({jev_bridge.SHA256[:12]}), jev.birch expects "
                         f"{CHECKPOINT} ({CHECKPOINT_SHA256[:12]}): update CHECKPOINT and CHECKPOINT_SHA256 together")
    kw.setdefault("min_interval", GATEWAY_MIN_INTERVAL)
    kw.setdefault("max_actions", MAX_ACTIONS_PER_NODE)
    return jev_bridge.backend(**kw)


def backend_from_config(cfg: dict) -> BirchBackend:
    """From a factory config: ``url``, ``max_calls``, ``cache_dir``, ``timeout``, ``include_assessments``,
    ``min_interval``. The pinned bridge unless ``allow_non_model`` (a mock or test server)."""
    kw = dict(url=cfg.get("url") or DEFAULT_URL, max_calls=int(cfg.get("max_calls", DEFAULT_MAX_CALLS)),
              cache_dir=cfg.get("cache_dir", DEFAULT_CACHE_DIR),
              timeout=float(cfg.get("birch_timeout", DEFAULT_TIMEOUT)),
              include_assessments=bool(cfg.get("include_assessments", False)),
              concurrency=int(cfg.get("concurrency", 1)))
    if "min_interval" in cfg:
        kw["min_interval"] = float(cfg["min_interval"])
    if cfg.get("allow_non_model"):
        return BirchBackend(allow_non_model=True, **kw)
    return pinned_backend(**kw)


def policy_for_world(world, url: str | None = None, **kw) -> BirchPolicy:
    """A Birch policy for an encounter world (``pathway_sim.encounter.load_world``), labels from its care model,
    on the pinned bridge (checkpoint :data:`CHECKPOINT`)."""
    be = pinned_backend(url=url or DEFAULT_URL, forbidden_values=frozenset(world.catalogue.conditions), **kw)
    be.public_phrases = public_phrases(world.catalogue, getattr(world, "care", None))
    return BirchPolicy(be, catalogue=world.catalogue, care=world.care)
