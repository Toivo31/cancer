"""HTTP client for a JEV service (``POST /v1/decide``, spec 02).

One keep-alive connection, a timeout (default 2 s), one retry after a network error or a 5xx.
``on_error="fail"`` (default) raises :class:`BackendError` and the run stops with the message;
``"fallback_stub"`` answers from a fallback backend (a stub built from the flowchart) and counts
every fallback in :meth:`HttpBackend.summary`. Failures are never silent.

When the service declares ``context_fields`` for the model (``GET /v1/models``) and is not
declared non-deterministic, answers are memoised on (decision point, those fields, offered options).
"""

from __future__ import annotations

import http.client
import json
import logging
import socket
import urllib.parse

from .contract import (BackendError, BackendInfo, ContractError, DecisionBackend, DecisionRequest,
                       DecisionResponse, check_responses, decode_response, encode_request)
from .fields import ResponseCache

log = logging.getLogger("jev")
ON_ERROR = ("fail", "fallback_stub")


class HttpBackend:
    def __init__(self, url: str, model: str | None = None, timeout: float = 2.0, retries: int = 1,
                 cache: bool = True, on_error: str = "fail", fallback: DecisionBackend | None = None,
                 max_cache: int = 200_000):
        if on_error not in ON_ERROR:
            raise ValueError(f"on_error must be one of {ON_ERROR}")
        if on_error == "fallback_stub" and fallback is None:
            raise ValueError("on_error='fallback_stub' needs a fallback backend")
        u = urllib.parse.urlparse(url if "//" in url else "http://" + url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError(f"bad JEV url {url!r}")
        self.url, self.scheme, self.host, self.port = url, u.scheme, u.hostname, u.port or (443 if u.scheme == "https" else 80)
        self.prefix = u.path.rstrip("/")
        self.model, self.timeout, self.retries = model, timeout, retries
        self.on_error, self.fallback = on_error, fallback
        self.use_cache, self.max_cache = cache, max_cache
        self._conn: http.client.HTTPConnection | None = None
        self._info: BackendInfo | None = None
        self._cache: ResponseCache | None = None
        self.requests_sent = self.http_calls = self.fallbacks = 0
        self.last_error: str | None = None

    # ------------------------------------------------------------------ transport
    def _connect(self):
        cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
        self._conn = cls(self.host, self.port, timeout=self.timeout)
        self._conn.connect()
        self._conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # no 40 ms Nagle stalls

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _call(self, method: str, path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json", "Connection": "keep-alive"}
        last = None
        for attempt in range(self.retries + 1):
            try:
                if self._conn is None:
                    self._connect()
                self.http_calls += 1
                self._conn.request(method, self.prefix + path, body=data, headers=headers)
                r = self._conn.getresponse()
                raw = r.read()
            except (OSError, http.client.HTTPException) as e:        # includes timeouts, refused, reset
                self.close()
                last = f"{type(e).__name__}: {e}"
                continue
            if r.status >= 500:
                last = f"HTTP {r.status} from {self.url}{path}"
                continue
            if r.status >= 400:                                      # our request is wrong: do not retry
                raise BackendError(f"JEV at {self.url} rejected the request ({r.status}): {raw[:300].decode(errors='replace')}")
            try:
                return json.loads(raw)
            except ValueError:
                raise BackendError(f"JEV at {self.url}{path} sent something that is not JSON") from None
        raise BackendError(f"JEV at {self.url} did not answer ({last}) after {self.retries + 1} attempts")

    # ------------------------------------------------------------------ backend protocol
    def info(self) -> BackendInfo:
        if self._info is None:
            try:
                self._fetch_info()
            except BackendError as e:
                if self.on_error != "fallback_stub":
                    raise
                self._on_error(e, [])                  # remembered in last_error; run goes on with the fallback
                self._info = BackendInfo("http", self.model or "unreachable", True, None, {"url": self.url})
        return self._info

    def _fetch_info(self) -> None:
        body = self._call("GET", "/v1/models")
        models = body.get("models") if isinstance(body, dict) else None
        if not isinstance(models, list) or not models:
            raise BackendError(f"JEV at {self.url} lists no models")
        m = next((x for x in models if x.get("id") == self.model), None) if self.model else models[0]
        if m is None:
            raise BackendError(f"JEV at {self.url} has no model {self.model!r}; it offers {[x.get('id') for x in models]}")
        self.model = m["id"]
        fields = m.get("context_fields")
        det = m.get("deterministic", True)
        self._info = BackendInfo("http", self.model, bool(det), list(fields) if fields is not None else None,
                                 {"url": self.url})
        if self.use_cache and fields is not None and det is not False:
            self._cache = ResponseCache(fields, self.max_cache)

    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]:
        self.info()
        out: list[DecisionResponse | None] = [None] * len(requests)
        todo: dict = {}                                   # key -> indices of requests waiting for it
        order: list = []
        for i, q in enumerate(requests):
            key = self._cache.key(q) if self._cache else ("nocache", i)
            hit = self._cache.get(key, q.request_id) if self._cache else None
            if hit is not None:
                out[i] = hit
                continue
            if key not in todo:
                todo[key] = []
                order.append((key, q))
            todo[key].append(i)
        if order:
            sent = [q for _, q in order]
            try:
                got = self._remote(sent)
            except BackendError as e:
                got = self._on_error(e, sent)
            for (key, q), resp in zip(order, got):
                if self._cache is not None and resp.explanation != "fallback":
                    self._cache.misses += 1
                    self._cache.put(key, resp)
                for i in todo[key]:
                    out[i] = DecisionResponse(requests[i].request_id, dict(resp.probs), resp.explanation)
        return out  # type: ignore[return-value]

    def _remote(self, sent: list[DecisionRequest]) -> list[DecisionResponse]:
        self.requests_sent += len(sent)
        body = self._call("POST", "/v1/decide", encode_request(self.model, sent))
        try:
            _, resp = decode_response(body)
            return check_responses(sent, resp)
        except ContractError as e:
            raise BackendError(f"JEV at {self.url} broke the contract: {e}") from None

    def _on_error(self, err: BackendError, sent: list[DecisionRequest]) -> list[DecisionResponse]:
        self.last_error = str(err)
        if self.on_error == "fail":
            raise err
        self.fallbacks += len(sent)
        if self.fallbacks == len(sent):
            log.warning("JEV unavailable, answering from the fallback stub: %s", err)
        return [DecisionResponse(r.request_id, r.probs, "fallback") for r in self.fallback.decide(sent)]

    def summary(self) -> dict:
        s = {"requests_sent": self.requests_sent, "http_calls": self.http_calls}
        if self._cache is not None:
            s["cache_hits"], s["cache_misses"] = self._cache.hits, self._cache.misses
        if self.fallbacks:
            s["fallbacks"], s["last_error"] = self.fallbacks, self.last_error
        return s
