"""Application factory and wiring.  ``uvicorn service.app:app --port 8000``  (API page at ``/docs``).

Routers are discovered: every module in ``service/routes/`` with a ``router`` is mounted under ``/api``.
Modules may define ``on_startup(app)`` / ``on_shutdown(app)``. Shared objects (settings, store) are reached
through ``service.deps``; nothing is imported from this file by the routers.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import errors, routes, security
from .config import Settings
from .deps import Services
from .store import Conflict, NotFound

API_VERSION = "0.1"


class BodyLimit:
    """Refuses bodies over the document limit (413), by Content-Length and by bytes actually read."""

    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope["headers"]).get(b"content-length")
        if length and length.isdigit() and int(length) > self.limit:
            return await JSONResponse(errors.body("payload_too_large", f"The request is larger than the {self.limit} byte limit"),
                                      status_code=413)(scope, receive, send)
        seen, exceeded = 0, False

        async def counted():
            nonlocal seen, exceeded
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.limit:
                    exceeded = True
                    raise errors.PayloadTooLarge(self.limit)
            return msg

        payload = json.dumps(errors.body("payload_too_large", f"The request is larger than the {self.limit} byte limit")).encode()

        async def guarded_send(msg):
            # The route may have turned the exception into its own error response; replace it with the 413.
            if exceeded and msg["type"] == "http.response.start":
                msg = {"type": "http.response.start", "status": 413,
                       "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]}
            elif exceeded and msg["type"] == "http.response.body":
                msg = {"type": "http.response.body", "body": payload}
            await send(msg)

        await self.app(scope, counted, guarded_send)


def _route_modules():
    for info in pkgutil.iter_modules(routes.__path__):
        yield importlib.import_module(f"{routes.__name__}.{info.name}")


def create_app(settings: Settings | None = None) -> FastAPI:
    modules = list(_route_modules())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for m in modules:
            if hasattr(m, "on_startup"):
                m.on_startup(app)
        yield
        for m in reversed(modules):
            if hasattr(m, "on_shutdown"):
                m.on_shutdown(app)

    app = FastAPI(title="Pathway platform API", version=API_VERSION, lifespan=lifespan,
                  description="Documents, projects, runs and optimisations for the care-pathway simulator. "
                              "Errors always look like {\"error\": {\"code\", \"message\", \"problems\"?}}.")
    app.state.services = Services(settings or Settings())
    errors.install(app)

    @app.exception_handler(NotFound)
    async def _nf(_, e: NotFound):
        return JSONResponse(errors.body("not_found", f"Not found: {e}"), status_code=404)

    @app.exception_handler(Conflict)
    async def _conflict(_, e: Conflict):
        return JSONResponse(errors.body(e.code, str(e)), status_code=409)

    @app.get("/api/health", tags=["service"])
    def health():
        return {"ok": True, "api_version": API_VERSION}

    for m in modules:
        if getattr(m, "router", None) is not None:
            app.include_router(m.router, prefix="/api")

    app.add_middleware(BodyLimit, limit=app.state.services.settings.max_document_bytes)
    security.install(app)                         # token, read-only mode, rate limits (spec 07); outermost, so it runs first

    web = app.state.services.settings.web_dir
    if (web / "index.html").exists():            # the built web app, when there is one (M3-1)
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


app = create_app()
