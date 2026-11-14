"""Input guards that need to see the raw request body (finding F3) and a helper for stored values.

Python's JSON parser accepts ``NaN``, ``Infinity`` and numbers such as ``1e999`` that overflow to infinity, none of which is
JSON. They poison a stored document (every later run holds a non-finite metric and the list of runs cannot be encoded).
``RejectNonFinite`` refuses such a body with 422 ``invalid_document`` and a problem that names the field.
"""

from __future__ import annotations

import asyncio
import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.responses import JSONResponse

from . import errors

BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
MAX_PROBLEMS = 10


class _NonFinite:
    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


def _parse_float(s: str):
    v = float(s)
    return v if math.isfinite(v) else _NonFinite(s)


def find_non_finite(text: bytes | str) -> list[tuple[list, str]] | None:
    """Paths (and the offending text) of every non-finite number in a JSON text; ``[]``-free ``None`` when it is not
    JSON at all (the route's own parser then reports that) and an empty list when it is clean."""
    try:
        doc = json.loads(text, parse_constant=_NonFinite, parse_float=_parse_float)
    except RecursionError:
        return None
    except ValueError:
        lines = [x for x in text.splitlines() if x.strip()]       # a JSON-lines upload (datasets)
        if len(lines) < 2:
            return None
        try:
            doc = [json.loads(x, parse_constant=_NonFinite, parse_float=_parse_float) for x in lines]
        except (ValueError, RecursionError):
            return None
    found: list[tuple[list, str]] = []
    stack = [([], doc)]
    while stack and len(found) < MAX_PROBLEMS:
        path, v = stack.pop()
        if isinstance(v, _NonFinite):
            found.append((path, v.text))
        elif isinstance(v, dict):
            stack.extend(([*path, k], x) for k, x in v.items())
        elif isinstance(v, list):
            stack.extend(([*path, i], x) for i, x in enumerate(v))
    return found


def scrub_non_finite(v):
    """A copy of a stored value with NaN and infinities replaced by ``None``, so rows written before F3 was closed
    still encode as JSON."""
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: scrub_non_finite(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [scrub_non_finite(x) for x in v]
    return v


class RejectNonFinite:
    """ASGI middleware: buffers a (size-limited, so put it inside ``BodyLimit``) JSON body and replays it."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in BODY_METHODS:
            return await self.app(scope, receive, send)
        chunks, more = [], True
        while more:
            try:
                msg = await receive()
            except errors.PayloadTooLarge as e:        # raised by BodyLimit's counting receive for a streamed body
                return await JSONResponse(errors.body(e.code, e.message), status_code=413)(scope, receive, send)
            if msg["type"] != "http.request":      # disconnect
                return await self.app(scope, _replay([msg]), send)
            chunks.append(msg.get("body", b""))
            more = msg.get("more_body", False)
        body = b"".join(chunks)
        bad = find_non_finite(body) if body else None
        if bad:
            problems = [{"severity": "error", "code": "non_finite_number",
                         "message": f"{'.'.join(map(str, p)) or 'body'}: {t} is not a valid JSON number; use a finite number",
                         "path": [str(x) for x in p]} for p, t in bad]
            return await JSONResponse(errors.body("invalid_document", "The document contains NaN or Infinity", problems),
                                      status_code=422)(scope, receive, send)
        await self.app(scope, _replay([{"type": "http.request", "body": body, "more_body": False}]), send)


def _replay(messages):
    it = iter(messages)

    async def receive():
        try:
            return next(it)
        except StopIteration:
            return {"type": "http.disconnect"}
    return receive


# ------------------------------------------------------------------------------------------ outbound calls (F5)
INTERACTIVE_JEV_TIMEOUT = 1.0      # seconds; a JEV call made while a web request waits is never allowed longer, and not retried
OFFLOAD_WORKERS = 4                # threads for work that may call a JEV while a request waits
OFFLOAD_PENDING = 16               # running plus waiting; more than that is refused (429), not queued without bound

_POOL = ThreadPoolExecutor(OFFLOAD_WORKERS, thread_name_prefix="offload")
_PENDING = threading.BoundedSemaphore(OFFLOAD_PENDING)


async def offload(fn, *args, **kwargs):
    """Run ``fn`` in a small dedicated pool with the tight JEV limits, and wait without holding a thread of the
    server's shared pool. Slow or silent JEV calls then cannot take the other routes (``/api/health`` included) down:
    the event loop stays free, the shared pool stays free, and only this pool (and its 16 places) is affected."""
    if not _PENDING.acquire(blocking=False):
        raise errors.ApiError(429, "busy", "Too many requests that call a decision service are waiting; try again in a moment")

    def work():
        try:
            try:
                from jev.factory import call_limits
            except ImportError:      # no jev in this build: nothing to limit
                return fn(*args, **kwargs)
            with call_limits(INTERACTIVE_JEV_TIMEOUT, 0):
                return fn(*args, **kwargs)
        finally:
            _PENDING.release()
    return await asyncio.get_running_loop().run_in_executor(_POOL, work)
