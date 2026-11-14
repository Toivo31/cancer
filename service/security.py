"""Access control, abuse limits and the outbound-host check for a hosted instance (spec 07; tickets M7-2, M7-6).

Everything here is configured by environment variables, read when the app is built (``install``) and again,
cheaply, per request, so a test can change them with ``monkeypatch.setenv``.

========================  =====================================================================================
``PATHWAY_ACCESS_TOKEN``  The one shared token. Sent as ``Authorization: Bearer <token>`` (or ``X-Pathway-Token``).
                          Never accepted in a URL, so it cannot end up in an access log.
``PATHWAY_PUBLIC_READ``   ``1``: visitors without the token may read (GET) and use the calculations that store
                          nothing (validate, try a decision, compare). Writes and job starts still need the token.
``PATHWAY_READ_ONLY``     ``1``: nobody writes, token or not (a frozen instance for the judging period).
``PATHWAY_REQUIRE_AUTH``  ``1`` (set by the Docker image): refuse to start unless a token (16+ characters) or
                          public-read mode is configured. Unset (local development): no token means open access,
                          and ``/api/access`` says so.
``JEV_ALLOWED_HOSTS``     Comma separated ``host`` or ``host:port`` entries a decision policy of kind ``http`` may
                          call. Empty (default): none. Link-local and cloud-metadata addresses are refused even
                          when listed.
``JEV_DEFAULT_URL``       A JEV address the web app may offer; its host is allowed implicitly.
``PATHWAY_RATE_PER_MIN``  Requests per minute per client address for ``/api`` (default 600, 0 = off).
``PATHWAY_JOB_STARTS_PER_MIN``  Run, optimisation, dataset, model and apply requests per minute per client (6).
``PATHWAY_MAX_ACTIVE_JOBS``     Queued plus running jobs above which new ones are refused (default 4 x PATHWAY_MAX_JOBS).
``PATHWAY_AUTH_FAILURES_PER_MIN``  Requests with a missing or wrong token per client address per minute (10).
``PATHWAY_MIN_FREE_MB``   Writes are refused (507) when the data volume has less free space (default 200, 0 = off).
``PATHWAY_SYNTHETIC_ONLY``  ``1`` (default): the web app shows the synthetic-data notice. ``PATHWAY_DATA_NOTICE``
                          replaces its text.
========================  =====================================================================================

The request and job limits apply whenever the instance is not in open mode (no token, no flags: a laptop), so
local development and the test suite are not throttled.

The client address is what ASGI reports; run uvicorn with ``--proxy-headers --forwarded-allow-ips`` set to the
address of your reverse proxy (see the runbook) or every visitor shares the proxy's address and its budget.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import math
import os
import re
import shutil
import socket
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from fastapi.responses import JSONResponse

from . import errors

log = logging.getLogger("pathway.security")

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PUBLIC_API_PATHS = frozenset({"/api/health", "/api/access"})
PUBLIC_OTHER_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})
# POST routes that compute and answer but store nothing: usable in read-only and public-read modes.
_PURE_POST = re.compile(r"^/api/projects/[^/]+/(validate|decide|compare)$")
# POST routes that start background work (or store uploads): limited per client and by the number of active jobs.
_JOB_START = re.compile(r"^/api/projects/[^/]+/(runs|optimisations|datasets|models|optimisations/[^/]+/apply)$")

DEFAULT_NOTICE = ("This instance holds synthetic data and simulator output only. Do not upload patient data, "
                  "personal data or anything you would not publish.")
MIN_TOKEN_CHARS = 16


class ConfigError(RuntimeError):
    """The environment asks for something unsafe or unreadable; the service refuses to start."""


class HostNotAllowed(ValueError):
    """A decision policy names a host the operator has not allowed. A ValueError so that the existing policy
    plumbing reports it as an invalid decision policy (422) with this message."""
    code = "host_not_allowed"


# ---------------------------------------------------------------------------------------------- configuration
def _flag(env, name: str) -> bool:
    return str(env.get(name, "")).strip().lower() in ("1", "true", "yes", "on")


def _int(env, name: str, default: int) -> int:
    v = str(env.get(name, "")).strip()
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, not {v!r}") from None


def _split_host(entry: str) -> tuple[str, int | None]:
    """``host``, ``host:port``, ``[v6]`` or ``[v6]:port`` -> (lower-case host, port or None)."""
    e = entry.strip().lower()
    if not e or any(c in e for c in "/\\@ \t?#") or "://" in e:
        raise ConfigError(f"allowed JEV host {entry!r}: write host or host:port, without scheme, path or credentials")
    try:
        u = urllib.parse.urlsplit("//" + e)
        host, port = u.hostname, u.port
    except ValueError:
        raise ConfigError(f"allowed JEV host {entry!r} is not a valid host[:port]") from None
    if not host:
        raise ConfigError(f"allowed JEV host {entry!r} is not a valid host[:port]")
    return host.rstrip("."), port


@dataclass(frozen=True)
class SecurityConfig:
    token: str | None = None
    public_read: bool = False
    read_only: bool = False
    require_auth: bool = False
    rate_per_min: int = 600
    job_starts_per_min: int = 6
    max_active_jobs: int | None = None          # None: 4 x the worker count
    auth_failures_per_min: int = 10
    min_free_mb: int = 200
    jev_allowed: tuple[tuple[str, int | None], ...] = ()
    jev_default_url: str | None = None
    synthetic_only: bool = True
    notice: str = DEFAULT_NOTICE

    @classmethod
    def from_env(cls, env=None) -> "SecurityConfig":
        env = os.environ if env is None else env
        token = (env.get("PATHWAY_ACCESS_TOKEN") or "").strip() or None
        allowed = [_split_host(x) for x in str(env.get("JEV_ALLOWED_HOSTS", "")).split(",") if x.strip()]
        default_url = (env.get("JEV_DEFAULT_URL") or "").strip() or None
        if default_url:
            host, port = _url_host_port(default_url)            # raises HostNotAllowed (a ValueError) when malformed
            allowed.append((host, port))
        cfg = cls(
            token=token, public_read=_flag(env, "PATHWAY_PUBLIC_READ"), read_only=_flag(env, "PATHWAY_READ_ONLY"),
            require_auth=_flag(env, "PATHWAY_REQUIRE_AUTH"),
            rate_per_min=_int(env, "PATHWAY_RATE_PER_MIN", 600),
            job_starts_per_min=_int(env, "PATHWAY_JOB_STARTS_PER_MIN", 6),
            max_active_jobs=_int(env, "PATHWAY_MAX_ACTIVE_JOBS", 0) or None,
            auth_failures_per_min=_int(env, "PATHWAY_AUTH_FAILURES_PER_MIN", 10),
            min_free_mb=_int(env, "PATHWAY_MIN_FREE_MB", 200),
            jev_allowed=tuple(dict.fromkeys(allowed)), jev_default_url=default_url,
            synthetic_only=not str(env.get("PATHWAY_SYNTHETIC_ONLY", "1")).strip().lower() in ("0", "false", "no", "off"),
            notice=(env.get("PATHWAY_DATA_NOTICE") or "").strip() or DEFAULT_NOTICE)
        cfg.check()
        return cfg

    def check(self) -> None:
        if self.require_auth and not self.token and not (self.public_read or self.read_only):
            raise ConfigError("PATHWAY_REQUIRE_AUTH is set but there is no PATHWAY_ACCESS_TOKEN. Set a token "
                              "(for example `openssl rand -hex 24`), or PATHWAY_PUBLIC_READ=1 for a read-only instance.")
        if self.token and len(self.token) < MIN_TOKEN_CHARS and self.require_auth:
            raise ConfigError(f"PATHWAY_ACCESS_TOKEN is shorter than {MIN_TOKEN_CHARS} characters; "
                              "generate one with `openssl rand -hex 24`.")

    @property
    def open_mode(self) -> bool:
        """No token and no restriction: every caller may do everything (local development only)."""
        return not self.token and not self.public_read and not self.read_only

    @property
    def mode(self) -> str:
        if self.read_only:
            return "read_only"
        if self.open_mode:
            return "open"
        return "public_read" if self.public_read else "token"


_cache: tuple[tuple, SecurityConfig] | None = None
_ENV_NAMES = ("PATHWAY_ACCESS_TOKEN", "PATHWAY_PUBLIC_READ", "PATHWAY_READ_ONLY", "PATHWAY_REQUIRE_AUTH", "PATHWAY_RATE_PER_MIN",
              "PATHWAY_JOB_STARTS_PER_MIN", "PATHWAY_MAX_ACTIVE_JOBS", "PATHWAY_AUTH_FAILURES_PER_MIN", "PATHWAY_MIN_FREE_MB",
              "JEV_ALLOWED_HOSTS", "JEV_DEFAULT_URL", "PATHWAY_SYNTHETIC_ONLY", "PATHWAY_DATA_NOTICE")


def config() -> SecurityConfig:
    """The configuration for the current environment (cached until one of the variables changes)."""
    global _cache
    key = tuple(os.environ.get(n) for n in _ENV_NAMES)
    if _cache is None or _cache[0] != key:
        _cache = (key, SecurityConfig.from_env())
    return _cache[1]


# ---------------------------------------------------------------------------------------------- JEV host allowlist
# Refused even when the operator lists them: cloud metadata services hand out credentials.
_ALWAYS_BLOCKED = tuple(ipaddress.ip_network(n) for n in (
    "169.254.0.0/16", "fe80::/10", "100.100.100.200/32", "192.0.0.192/32", "fd00:ec2::/32", "0.0.0.0/8", "::/128"))


def _url_host_port(url: str) -> tuple[str, int]:
    """The host and port the HTTP backend would connect to; parsed the way ``jev.http.HttpBackend`` parses."""
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        raise HostNotAllowed("JEV url: missing or too long")
    if re.search(r"[\s\\\x00-\x1f\x7f]", url):
        raise HostNotAllowed("JEV url: spaces, backslashes and control characters are not allowed")
    try:
        u = urllib.parse.urlparse(url if "//" in url else "http://" + url)
        host, port = u.hostname, u.port
    except ValueError:
        raise HostNotAllowed("JEV url: cannot be parsed") from None
    if u.scheme not in ("http", "https") or not host:
        raise HostNotAllowed("JEV url: use http:// or https:// and a host name")
    if u.username is not None or u.password is not None or "@" in u.netloc:
        raise HostNotAllowed("JEV url: credentials in the address are not allowed")
    return host.rstrip(".").lower(), port or (443 if u.scheme == "https" else 80)


def _blocked_address(ip) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (any(ip in n for n in _ALWAYS_BLOCKED if n.version == ip.version)
            or ip.is_unspecified or ip.is_multicast or ip.is_link_local)


def check_jev_url(url: str, cfg: SecurityConfig | None = None, where: str = "decision_policy") -> None:
    """Raise :class:`HostNotAllowed` unless the server may call this JEV address.

    The host (and port, when the allowlist entry has one) must be listed in ``JEV_ALLOWED_HOSTS``. A listed name is
    then resolved the way the connection will resolve it, and refused if any address is link-local, unspecified,
    multicast or a known cloud-metadata address. Loopback and private addresses are the operator's call: listing
    ``jev:9000`` or ``127.0.0.1:9100`` is how a JEV next to the service is allowed.
    """
    cfg = cfg or config()
    try:
        host, port = _url_host_port(url)
    except HostNotAllowed as e:
        raise HostNotAllowed(f"{where}: {e}") from None
    if not any(h == host and (p is None or p == port) for h, p in cfg.jev_allowed):
        hint = ("this server allows no JEV hosts (JEV_ALLOWED_HOSTS is empty)" if not cfg.jev_allowed
                else "it is not on this server's list of JEV hosts")
        raise HostNotAllowed(f"{where}: the JEV host '{host}:{port}' cannot be used, {hint}. "
                             "Ask the operator to add it to JEV_ALLOWED_HOSTS.")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise HostNotAllowed(f"{where}: the JEV host '{host}' cannot be resolved") from None
    for info in infos:
        addr = info[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise HostNotAllowed(f"{where}: the JEV host '{host}' resolves to an address that cannot be checked") from None
        if _blocked_address(ip):
            raise HostNotAllowed(f"{where}: the JEV host '{host}' resolves to {ip}, which is never allowed "
                                 "(link-local and cloud-metadata addresses)")


def _is_http(backend) -> bool:
    return backend == "http" or (isinstance(backend, str) and backend.startswith(("http://", "https://")))


def policy_urls(dp: dict | None) -> list[tuple[str, str]]:
    """Every ``(where, url)`` a decision policy could make the server call, mirroring ``jev.prepare``: the default
    backend (``"http"`` with ``url``, or the URL itself) and each decision point that names an http backend."""
    if not isinstance(dp, dict):
        return []
    out: list[tuple[str, str]] = []
    backend = dp.get("backend")
    if _is_http(backend):
        out.append(("decision_policy", backend if backend != "http" else dp.get("url")))
    points = dp.get("points")
    for name, spec in (points.items() if isinstance(points, dict) else ()):
        if isinstance(spec, dict) and _is_http(spec.get("backend")):
            b = spec["backend"]
            out.append((f"decision_policy.points.{name}", b if b != "http" else (spec.get("url") or dp.get("url"))))
    return [(w, u) for w, u in out if u is not None]    # a missing url is reported by jev itself


def check_decision_policy(dp: dict | None) -> None:
    """The hook ``service.policy`` and ``service.prepare`` call before ``jev.prepare``: refuse any decision policy
    whose http backend points somewhere the operator has not allowed."""
    for where, url in policy_urls(dp):
        check_jev_url(url, where=where)


# ---------------------------------------------------------------------------------------------- limits
class Limiter:
    """Token buckets keyed by name; in memory (one process: the service runs as one, see service/runtime.py)."""

    def __init__(self, clock=time.monotonic, max_keys: int = 5000):
        self._clock, self._max, self._b = clock, max_keys, {}

    def take(self, key: str, per_minute: int, burst: int | None = None) -> tuple[bool, float]:
        """``(allowed, seconds until a request would be allowed)``. ``per_minute <= 0`` switches the limit off."""
        if per_minute <= 0:
            return True, 0.0
        cap, rate, now = float(burst or per_minute), per_minute / 60.0, self._clock()
        tokens, then = self._b.get(key, (cap, now))
        tokens = min(cap, tokens + (now - then) * rate)
        ok = tokens >= 1.0
        self._b[key] = (tokens - 1.0 if ok else tokens, now)
        if len(self._b) > self._max:
            self._prune(now)
        return ok, 0.0 if ok else (1.0 - tokens) / rate

    def _prune(self, now: float) -> None:
        for k in [k for k, (_, t) in self._b.items() if now - t > 120]:
            del self._b[k]
        while len(self._b) > self._max:               # still too many fresh keys: drop the oldest
            self._b.pop(next(iter(self._b)))


class _Disk:
    """Free space of the data volume, looked at most every few seconds."""

    def __init__(self, path: Path):
        self.path, self._at, self._free = Path(path), 0.0, None

    def free_mb(self) -> float:
        now = time.monotonic()
        if self._free is None or now - self._at > 5:
            p = self.path
            while not p.exists() and p != p.parent:
                p = p.parent
            self._free, self._at = shutil.disk_usage(p).free / 1e6, now
        return self._free


# ---------------------------------------------------------------------------------------------- the middleware
def _bearer(headers: dict) -> bytes | None:
    auth = headers.get(b"authorization", b"")
    if auth[:7].lower() == b"bearer ":
        tok = auth[7:].strip()
        if tok:
            return tok
    return headers.get(b"x-pathway-token", b"").strip() or None


def _client(scope) -> str:
    c = scope.get("client")
    return c[0] if c else "unknown"


class Guard:
    """Pure ASGI middleware: token, read-only and public-read modes, rate and job limits, free-space check.

    Only ``/api`` is guarded: the built web app and the API docs are public (they carry no data), so the page can
    load and ask for the token. Responses under ``/api`` are marked ``no-store``; every response gets the small set
    of safe headers below.
    """

    HEADERS = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"no-referrer")]

    def __init__(self, app, limiter: Limiter | None = None):
        self.app, self.limiter = app, limiter or Limiter()
        self._disk: _Disk | None = None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"].upper()
        is_api = path == "/api" or path.startswith("/api/")

        async def secured_send(msg):
            if msg["type"] == "http.response.start":
                extra = list(self.HEADERS) + ([(b"cache-control", b"no-store")] if is_api else [])
                have = {k.lower() for k, _ in msg["headers"]}
                msg = {**msg, "headers": list(msg["headers"]) + [h for h in extra if h[0] not in have]}
            await send(msg)

        if not is_api:
            return await self.app(scope, receive, secured_send)

        cfg = config()
        app = scope.get("app")
        client = _client(scope)
        headers = {k.lower(): v for k, v in scope["headers"]}
        supplied = _bearer(headers)
        authed = bool(cfg.token) and supplied is not None and hmac.compare_digest(supplied, cfg.token.encode())
        state = scope.setdefault("state", {})
        pure = method == "POST" and bool(_PURE_POST.match(path))
        write = method not in SAFE_METHODS and not pure
        public_path = path in PUBLIC_API_PATHS

        # who may do this?
        allowed = authed or cfg.open_mode or public_path or (cfg.public_read and not write)
        if not allowed:
            ok, wait = self.limiter.take(f"authfail:{client}", cfg.auth_failures_per_min)
            if not ok:
                return await self._refuse(429, "too_many_attempts", "Too many requests without a valid access token; wait a minute.",
                                          scope, receive, secured_send, wait)
            if supplied is not None:
                log.info("denied %s %s from %s: wrong token", method, path, client)
                return await self._refuse(401, "invalid_token", "The access token is not valid.", scope, receive, secured_send)
            log.info("denied %s %s from %s: no token", method, path, client)
            return await self._refuse(401, "unauthorized", "This needs the access token (Authorization: Bearer <token>).",
                                      scope, receive, secured_send)
        if supplied is not None and not authed and not cfg.open_mode and public_path:
            self.limiter.take(f"authfail:{client}", cfg.auth_failures_per_min)         # guesses at the token cost the same everywhere
        can_write = (authed or cfg.open_mode) and not cfg.read_only
        state["pathway_access"] = {"authenticated": authed or (cfg.open_mode and not cfg.token), "can_write": can_write}

        if write and cfg.read_only and not public_path:
            return await self._refuse(403, "read_only", "This instance is read-only: nothing can be created, changed or started.",
                                      scope, receive, secured_send)
        if not cfg.open_mode and (not public_path or path == "/api/access"):
            ok, wait = self.limiter.take(f"api:{client}", cfg.rate_per_min)
            if not ok:
                return await self._refuse(429, "rate_limited", "Too many requests; slow down.", scope, receive, secured_send, wait)
        if not cfg.open_mode and method == "POST" and _JOB_START.match(path):
            ok, wait = self.limiter.take(f"jobs:{client}", cfg.job_starts_per_min)
            if not ok:
                return await self._refuse(429, "rate_limited", f"At most {cfg.job_starts_per_min} jobs can be started per minute.",
                                          scope, receive, secured_send, wait)
            active, cap = self._active_jobs(app, cfg)
            if active is not None and active >= cap:
                return await self._refuse(429, "too_many_jobs", f"{active} jobs are already queued or running (limit {cap}); try again when some finish.",
                                          scope, receive, secured_send, 10.0)
        if write and method != "DELETE" and cfg.min_free_mb > 0 and self._low_disk(app, cfg):
            return await self._refuse(507, "storage_full", "The data volume is nearly full; nothing new can be stored. "
                                      "Delete projects you do not need or ask the operator to free space.", scope, receive, secured_send)
        await self.app(scope, receive, secured_send)

    # -------------------------------------------------------------------------------------- helpers
    @staticmethod
    def _active_jobs(app, cfg: SecurityConfig) -> tuple[int | None, int]:
        """Queued plus running jobs, when the job runner exists (duck-typed: this file does not import it)."""
        try:
            c = app.state.runtime.runner.counts()
            workers = app.state.services.settings.max_jobs
            return int(c.get("queued", 0)) + int(c.get("running", 0)), cfg.max_active_jobs or max(4, 4 * int(workers))
        except Exception:      # noqa: BLE001 - no runtime yet means no jobs yet
            return None, 0

    def _low_disk(self, app, cfg: SecurityConfig) -> bool:
        try:
            if self._disk is None:
                self._disk = _Disk(app.state.services.settings.data_dir)
            return self._disk.free_mb() < cfg.min_free_mb
        except Exception:      # noqa: BLE001 - never block on a failed check of the check
            return False

    @staticmethod
    async def _refuse(status: int, code: str, message: str, scope, receive, send, retry_after: float | None = None):
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(max(1, math.ceil(retry_after)))
        if status == 401:
            headers["WWW-Authenticate"] = 'Bearer realm="pathway"'
        await JSONResponse(errors.body(code, message), status_code=status, headers=headers)(scope, receive, send)


def install(app) -> None:
    """Register the guard on ``app`` (the one line ``service/app.py`` needs). Fails at start-up, not at the first request,
    when the environment is unsafe or unreadable."""
    cfg = config()
    app.add_middleware(Guard)
    if cfg.open_mode:
        log.warning("OPEN MODE: no PATHWAY_ACCESS_TOKEN and no read-only flag; anyone who can reach this port can read and "
                    "write. Fine on a laptop, not on a server.")
    else:
        log.info("access mode %s (token %s, %d JEV hosts allowed)", cfg.mode, "set" if cfg.token else "not set", len(cfg.jev_allowed))
