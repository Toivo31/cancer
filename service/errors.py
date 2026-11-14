"""One error shape for the whole API: ``{"error": {"code", "message", "problems"?}}`` (spec 03)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorBody(BaseModel):
    code: str
    message: str
    problems: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Raise anywhere in a route: status, a short machine code, a sentence for people, optional problem list."""

    def __init__(self, status: int, code: str, message: str, problems: list[dict] | None = None):
        self.status, self.code, self.message, self.problems = status, code, message, problems
        super().__init__(message)


class PayloadTooLarge(ApiError):
    def __init__(self, limit: int):
        super().__init__(413, "payload_too_large", f"The request is larger than the {limit} byte limit")


def not_found(what: str, ident: str) -> ApiError:
    return ApiError(404, "not_found", f"No {what} '{ident}'")


def body(code: str, message: str, problems: list[dict] | None = None) -> dict:
    d: dict = {"code": code, "message": message}
    if problems is not None:
        d["problems"] = problems
    return {"error": d}


# responses to advertise in OpenAPI so the web client's generated types know the error shape
ERROR_RESPONSES = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
                   413: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return JSONResponse(body(e.code, e.message, e.problems), status_code=e.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(e.status_code, "http_error")
        return JSONResponse(body(code, str(e.detail)), status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        problems = [{"severity": "error", "code": "schema", "message": f"{'.'.join(str(x) for x in err['loc'][1:])}: {err['msg']}"
                     if len(err["loc"]) > 1 else err["msg"], "path": [str(x) for x in err["loc"]]} for err in e.errors()]
        return JSONResponse(body("invalid_request", "The request does not match the expected shape", problems), status_code=422)
