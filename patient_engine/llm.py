"""Language-model client for the patient engine (WP-C1-2).

One small client for any OpenAI-compatible ``/chat/completions`` endpoint, standard library only
for HTTP. Environment: ``LLM_BASE_URL`` (required), ``LLM_MODEL`` (required), ``LLM_API_KEY``
(optional for local servers). Request shape copied from ``technique_classifier/llm.py``; that
package is not imported.

What it adds over a bare call:

* ``complete_json(system, user, schema, key=...)`` returns a dict that validates against ``schema``;
  when the answer is not JSON or fails the schema, the errors are sent back and the model retries
  (``max_repairs`` times).
* Retry with backoff on 429, 5xx and connection errors; ``Retry-After`` is honoured.
* ``Budget``: hard cap on calls and tokens, checked before a request is sent.
* On-disk cache keyed by sha256 of (model, system, user, schema, temperature): a rerun on the same
  cache directory makes no network call for prompts already answered.
* ``CallLog``: append-only JSON-lines file, one line per call. The API key is never written to it,
  to a cache file or to an exception message.
* ``map``: bounded concurrency with threads, results in request order.

Offline use (tests, pipeline development)::

    >>> from patient_engine.llm import FakeLLMClient
    >>> schema = {"type": "object", "required": ["age"], "properties": {"age": {"type": "integer"}}}
    >>> fake = FakeLLMClient([{"age": "sixty"}, {"age": 60}])      # first answer is invalid
    >>> fake.complete_json("You write cards.", "One card.", schema, key="card-1")
    {'age': 60}
    >>> len(fake.calls)                                            # one repair round happened
    2
    >>> FakeLLMClient(lambda system, user, schema: {"age": 41}).complete_json("s", "u", schema, key="k")
    {'age': 41}

Schema validation uses ``jsonschema`` when it is installed, otherwise a minimal validator for
``type``, ``required``, ``enum``, ``properties`` and ``items`` (see ``VALIDATOR``).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

try:  # optional
    import jsonschema as _jsonschema
except Exception:  # pragma: no cover - depends on environment
    _jsonschema = None

VALIDATOR = "jsonschema" if _jsonschema is not None else "minimal"


class LLMError(RuntimeError):
    """Base class for client errors. Messages never contain the API key."""


class LLMConfigError(LLMError):
    """Environment is incomplete (for example ``LLM_BASE_URL`` is not set)."""


class BudgetExceeded(LLMError):
    """The next call would pass the call or token cap; no request was sent."""


class LLMHTTPError(LLMError):
    """The endpoint kept failing after the allowed attempts."""


class LLMOutputError(LLMError):
    """The model never produced a valid answer within the allowed repairs."""


# ---------------------------------------------------------------- schema validation

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


def _minimal_errors(value: Any, schema: dict, path: str) -> list[str]:
    errs: list[str] = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES.get(x, lambda v: True)(value) for x in types):
            return [f"{path}: expected {'/'.join(types)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errs.append(f"{path}: missing required property {name!r}")
        for name, sub in schema.get("properties", {}).items():
            if name in value and isinstance(sub, dict):
                errs.extend(_minimal_errors(value[name], sub, f"{path}.{name}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            errs.extend(_minimal_errors(item, schema["items"], f"{path}[{i}]"))
    return errs


def validation_errors(value: Any, schema: dict) -> list[str]:
    """Human-readable schema violations (empty list when valid)."""
    if _jsonschema is not None:
        v = _jsonschema.Draft202012Validator(schema)
        out = []
        for e in sorted(v.iter_errors(value), key=lambda e: list(map(str, e.absolute_path))):
            where = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in e.absolute_path)
            out.append(f"{where}: {e.message[:300]}")
        return out
    return _minimal_errors(value, schema, "$")


# ---------------------------------------------------------------- budget and log


class Budget:
    """Thread-safe cap on model calls and tokens. ``None`` means unlimited."""

    def __init__(self, max_calls: int | None = None, max_tokens: int | None = None):
        self.max_calls, self.max_tokens = max_calls, max_tokens
        self.calls = 0
        self.tokens = 0
        self._lock = threading.Lock()

    def reserve(self) -> None:
        """Count one call, or raise ``BudgetExceeded`` before it is made."""
        with self._lock:
            if self.max_calls is not None and self.calls >= self.max_calls:
                raise BudgetExceeded(f"call budget exhausted ({self.calls}/{self.max_calls})")
            if self.max_tokens is not None and self.tokens >= self.max_tokens:
                raise BudgetExceeded(f"token budget exhausted ({self.tokens}/{self.max_tokens})")
            self.calls += 1

    def add_tokens(self, n: int) -> None:
        with self._lock:
            self.tokens += max(0, int(n))

    def snapshot(self) -> dict:
        with self._lock:
            return {"calls": self.calls, "tokens": self.tokens,
                    "max_calls": self.max_calls, "max_tokens": self.max_tokens}


class CallLog:
    """Append-only JSON-lines log, one line per call; safe across threads. ``path=None`` keeps lines in memory only."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, **fields: Any) -> None:
        entry = {"ts": round(time.time(), 3), **fields}
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.entries.append(entry)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")


# ---------------------------------------------------------------- helpers

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n?\s*```\s*$", re.S)


def parse_json_text(raw: str) -> Any:
    """Parse model output as JSON: strips markdown fences, tolerates prose around one object."""
    raw = (raw or "").strip()
    m = _FENCE.match(raw)
    if m:
        raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m2 = re.search(r"\{.*\}|\[.*\]", raw, re.S)
        if m2:
            return json.loads(m2.group(0))
        raise


def _sleep(seconds: float) -> None:  # module level so tests can patch it
    time.sleep(seconds)


def _hash(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


# ---------------------------------------------------------------- shared client logic


class _BaseClient:
    model: str

    def __init__(self, *, budget: Budget | None = None, cache_dir: str | Path | None = None,
                 log: CallLog | str | Path | None = None, default_temperature: float | None = None):
        self.budget = budget or Budget()
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        if log is None and self.cache_dir:
            log = self.cache_dir / "calls.jsonl"
        self.log = log if isinstance(log, CallLog) else CallLog(log)
        self.default_temperature = default_temperature

    # subclasses: one request, no retries of the content. Returns (text, usage dict).
    def _chat(self, messages: list[dict], temperature: float | None, schema: dict) -> tuple[str, dict]:
        raise NotImplementedError

    def _system_with_schema(self, system: str, schema: dict) -> str:
        return (system.rstrip() + "\n\nReturn one JSON object only (no prose, no code fences) that "
                "validates against this JSON Schema:\n" + json.dumps(schema, sort_keys=True))

    def _scrub(self, text: str) -> str:
        return text

    def _cache_path(self, h: str) -> Path | None:
        return self.cache_dir / f"{h}.json" if self.cache_dir else None

    def complete_json(self, system: str, user: str, schema: dict, *, key: str,
                      temperature: float | None = None, max_repairs: int = 2) -> dict:
        """Ask for a JSON object that validates against ``schema``; return it as a dict.

        ``key`` is a caller label (for example ``card-17:g1``) written to the call log. On an answer
        that is not JSON or fails the schema, the errors are sent back, up to ``max_repairs`` times.
        """
        if temperature is None:
            temperature = self.default_temperature
        h = _hash(self.model, system, user, schema, temperature)
        cp = self._cache_path(h)
        if cp and cp.exists():
            try:
                cached = json.loads(cp.read_text(encoding="utf-8"))
                self.log.write(key=key, prompt_hash=h, model=self.model, outcome="cache_hit",
                               tokens_in=0, tokens_out=0, latency_s=0.0)
                return cached
            except (OSError, json.JSONDecodeError):
                pass  # unreadable cache entry: ask again

        messages = [{"role": "system", "content": self._system_with_schema(system, schema)},
                    {"role": "user", "content": user}]
        last_problem = ""
        for attempt in range(max_repairs + 1):
            t0 = time.monotonic()
            try:
                self.budget.reserve()
            except BudgetExceeded as e:
                self.log.write(key=key, prompt_hash=h, model=self.model, outcome="budget_exceeded",
                               attempt=attempt, error=str(e))
                raise
            try:
                text, usage = self._chat(messages, temperature, schema)
            except LLMError as e:
                self.log.write(key=key, prompt_hash=h, model=self.model, outcome="http_error", attempt=attempt,
                               latency_s=round(time.monotonic() - t0, 3), error=self._scrub(str(e))[:300])
                raise
            tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
            self.budget.add_tokens(usage.get("total_tokens") or ((tin or 0) + (tout or 0)))
            problems: list[str] = []
            obj: Any = None
            try:
                obj = parse_json_text(text)
                problems = validation_errors(obj, schema)
            except (json.JSONDecodeError, ValueError) as e:
                problems = [f"the answer was not valid JSON ({str(e)[:120]})"]
            outcome = "ok" if not problems else ("not_json" if obj is None else "schema_invalid")
            self.log.write(key=key, prompt_hash=h, model=self.model, outcome=outcome, attempt=attempt,
                           tokens_in=tin, tokens_out=tout, latency_s=round(time.monotonic() - t0, 3))
            if not problems:
                if cp:
                    tmp = cp.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")   # a cache dir may be shared
                    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                    os.replace(tmp, cp)
                return obj
            last_problem = "; ".join(problems[:5])
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Your answer did not validate. Problems: " + "; ".join(problems[:10])
                 + "\nReturn the corrected JSON object only."}]
        raise LLMOutputError(f"no valid answer for {key!r} after {max_repairs} repairs: {last_problem}")

    def map(self, requests: Iterable[dict], concurrency: int = 4, *, return_exceptions: bool = False) -> list:
        """Run ``complete_json(**request)`` for each request dict, ``concurrency`` at a time.

        Results come back in request order. With ``return_exceptions=True`` a failed request yields
        its exception in place; otherwise the first failure (in order) is raised after all finish.
        """
        reqs = list(requests)

        def run(r: dict):
            try:
                return self.complete_json(**r)
            except Exception as e:  # noqa: BLE001 - reported to caller
                return e

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            out = list(pool.map(run, reqs))
        if not return_exceptions:
            for o in out:
                if isinstance(o, Exception):
                    raise o
        return out


# ---------------------------------------------------------------- real client


class LLMClient(_BaseClient):
    """OpenAI-compatible chat client. Build with :meth:`from_env` or pass values directly."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, *,
                 budget: Budget | None = None, cache_dir: str | Path | None = None,
                 log: CallLog | str | Path | None = None, timeout: float = 300.0,
                 max_attempts: int = 5, backoff_base: float = 1.0, backoff_max: float = 60.0,
                 json_schema_mode: bool = False, max_tokens: int | None = 16000,
                 default_temperature: float | None = None):
        super().__init__(budget=budget, cache_dir=cache_dir, log=log, default_temperature=default_temperature)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key or None
        self.timeout, self.max_attempts = timeout, max(1, max_attempts)
        self.backoff_base, self.backoff_max = backoff_base, backoff_max
        self.json_schema_mode = json_schema_mode
        self.max_tokens = max_tokens

    def __repr__(self) -> str:  # never show the key
        return f"LLMClient(base_url={self.base_url!r}, model={self.model!r})"

    @classmethod
    def from_env(cls, *, budget: Budget | None = None, cache_dir: str | Path | None = None,
                 log: CallLog | str | Path | None = None, **kw: Any) -> "LLMClient":
        """Read ``LLM_BASE_URL``, ``LLM_MODEL`` and ``LLM_API_KEY`` (key optional). Raises ``LLMConfigError``."""
        base, model = os.environ.get("LLM_BASE_URL"), os.environ.get("LLM_MODEL")
        missing = [n for n, v in (("LLM_BASE_URL", base), ("LLM_MODEL", model)) if not v]
        if missing:
            raise LLMConfigError(
                f"language-model endpoint is not configured: set {' and '.join(missing)} "
                "(and LLM_API_KEY if the endpoint needs one). Use FakeLLMClient for offline work.")
        return cls(base, model, os.environ.get("LLM_API_KEY"), budget=budget, cache_dir=cache_dir, log=log, **kw)

    def _scrub(self, text: str) -> str:
        return text.replace(self._api_key, "***") if self._api_key else text

    def _ssl_context(self) -> ssl.SSLContext | None:
        if not self.base_url.startswith("https"):
            return None
        ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        return ssl.create_default_context(cafile=ca) if ca else None

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), self.backoff_max)
            except ValueError:
                pass
        return min(self.backoff_base * (2 ** attempt), self.backoff_max)

    def _chat(self, messages: list[dict], temperature: float | None, schema: dict) -> tuple[str, dict]:
        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if self.max_tokens:
            body["max_tokens"] = self.max_tokens
        body["response_format"] = ({"type": "json_schema", "json_schema": {"name": "answer", "schema": schema, "strict": False}}
                                   if self.json_schema_mode else {"type": "json_object"})
        data_bytes = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        ctx = self._ssl_context()
        last = ""
        for attempt in range(self.max_attempts):
            retry_after = None
            req = urllib.request.Request(self.base_url + "/chat/completions", data=data_bytes,
                                         method="POST", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
                    data = json.loads(r.read())
                choice = data["choices"][0]
                content = (choice.get("message") or {}).get("content") or ""
                if not content.strip():  # reasoning models can spend the whole budget thinking
                    raise LLMHTTPError(f"empty answer from the model (finish_reason={choice.get('finish_reason')})")
                return content, data.get("usage") or {}
            except urllib.error.HTTPError as e:
                if e.code != 429 and not 500 <= e.code < 600:
                    snippet = self._scrub(e.read()[:300].decode("utf-8", "replace"))
                    raise LLMHTTPError(f"LLM API error {e.code}: {snippet}") from None
                last = f"HTTP {e.code}"
                retry_after = e.headers.get("Retry-After") if e.headers else None
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last = f"connection problem ({type(e).__name__})"
            except (KeyError, IndexError, json.JSONDecodeError):
                raise LLMHTTPError("unexpected response shape from the endpoint") from None
            if attempt + 1 < self.max_attempts:
                _sleep(self._delay(attempt, retry_after))
        raise LLMHTTPError(f"LLM endpoint failed after {self.max_attempts} attempts (last: {last})")


# ---------------------------------------------------------------- fake client


class FakeLLMClient(_BaseClient):
    """Offline stand-in with the same methods. No network, no key.

    ``responses`` is either a list (answers served in order; a dict is serialised, a string is
    used as is) or a function ``fn(system, user, schema)`` returning a dict or a string. On a
    repair round ``user`` is the correction message, so a function can tell. ``calls`` records
    ``(system, user)`` pairs. Budget, cache, log and the repair loop behave as in ``LLMClient``.
    """

    def __init__(self, responses: list | Callable[[str, str, dict], Any], *, model: str = "fake",
                 budget: Budget | None = None, cache_dir: str | Path | None = None,
                 log: CallLog | str | Path | None = None, default_temperature: float | None = None):
        super().__init__(budget=budget, cache_dir=cache_dir, log=log, default_temperature=default_temperature)
        self.model = model
        self._fn = responses if callable(responses) else None
        self._queue = None if callable(responses) else list(responses)
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def _chat(self, messages: list[dict], temperature: float | None, schema: dict) -> tuple[str, dict]:
        with self._lock:
            self.calls.append((messages[0]["content"], messages[-1]["content"]))
            if self._fn is None:
                if not self._queue:
                    raise LLMError("FakeLLMClient has no more canned responses")
                out = self._queue.pop(0)
        if self._fn is not None:
            out = self._fn(messages[0]["content"], messages[-1]["content"], schema)
        return (out if isinstance(out, str) else json.dumps(out)), {}
