"""RFC 9457 problem+json for every error (docs/04 sections 2.3 and 2.4).

Domain exceptions map to a status and code here, in one place. Unhandled errors
return a generic 500 with the request id; the stack trace stays in the server log.
"""

from __future__ import annotations

import traceback
from typing import Any

import orjson
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ehr_mip.errors import (
    EhrMipError,
    NotReadyError,
    PatientNotFoundError,
    ResourceNotFoundError,
    SearchIndexEmptyError,
    SummaryNotFoundError,
)

log = structlog.get_logger(__name__)
PROBLEM_BASE = "https://ehr-mip.local/problems/"
PROBLEM_TYPE = "application/problem+json"

_DOMAIN: dict[type[EhrMipError], tuple[int, str]] = {
    PatientNotFoundError: (404, "Patient not found"),
    ResourceNotFoundError: (404, "Resource not found"),
    SummaryNotFoundError: (404, "Summary not generated"),
    SearchIndexEmptyError: (503, "Search index is empty"),
    NotReadyError: (503, "Service not ready"),
}
_HTTP: dict[int, tuple[str, str]] = {
    404: ("not_found", "Not found"),
    405: ("method_not_allowed", "Method not allowed"),
    413: ("payload_too_large", "Payload too large"),
}


class ApiProblem(Exception):  # noqa: N818 (it is a response, not an error condition)
    """Raise from routers for problems with no domain exception (422 rules, 413, 429)."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str,
        *,
        errors: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status, self.code, self.title, self.detail = status, code, title, detail
        self.errors = errors or []
        self.headers = headers or {}


def validation_problem(loc: str, message: str) -> ApiProblem:
    return ApiProblem(
        422,
        "validation_error",
        "Request validation failed",
        message,
        errors=[{"loc": loc, "message": message, "type": "value_error"}],
    )


def problem_body(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    instance: str,
    request_id: str,
    errors: list[dict[str, str]] | None = None,
) -> bytes:
    return orjson.dumps(
        {
            "type": PROBLEM_BASE + code,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance,
            "code": code,
            "request_id": request_id,
            "errors": errors or [],
        }
    )


def request_id_of(scope_state: dict[str, Any] | Any) -> str:
    if isinstance(scope_state, dict):
        return str(scope_state.get("request_id", ""))
    return str(getattr(scope_state, "request_id", ""))


def _response(request: Request, problem: ApiProblem) -> Response:
    body = problem_body(
        status=problem.status,
        code=problem.code,
        title=problem.title,
        detail=problem.detail,
        instance=request.url.path,
        request_id=request_id_of(request.state),
        errors=problem.errors,
    )
    return Response(
        body, status_code=problem.status, media_type=PROBLEM_TYPE, headers=problem.headers
    )


def _message(error: dict[str, Any]) -> str:
    message = str(error.get("msg", "Invalid value"))
    return message.removeprefix("Value error, ")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def _problem(request: Request, exc: ApiProblem) -> Response:
        return _response(request, exc)

    @app.exception_handler(EhrMipError)
    async def _domain(request: Request, exc: EhrMipError) -> Response:
        status, title = _DOMAIN.get(type(exc), (500, "Internal server error"))
        if status == 500:  # noqa: PLR2004
            log.error("unhandled_domain_error", error_type=type(exc).__name__)
            return _response(
                request, ApiProblem(500, "internal_error", title, "An unexpected error occurred.")
            )
        return _response(request, ApiProblem(status, exc.code, title, str(exc)))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> Response:
        errors = [
            {
                "loc": ".".join(str(part) for part in error.get("loc", ())),
                "message": _message(error),
                "type": str(error.get("type", "value_error")),
            }
            for error in exc.errors()
        ]
        detail = errors[0]["message"] if errors else "Invalid request"
        return _response(
            request,
            ApiProblem(422, "validation_error", "Request validation failed", detail, errors=errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> Response:
        code, title = _HTTP.get(exc.status_code, ("http_error", "Request failed"))
        detail = exc.detail if isinstance(exc.detail, str) else title
        if exc.status_code == 404 and detail == "Not Found":  # noqa: PLR2004
            detail = f"No route for {request.method} {request.url.path}"
        return _response(
            request,
            ApiProblem(exc.status_code, code, title, detail, headers=dict(exc.headers or {})),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        # Frames only (file, line, function): exception messages and locals may hold PHI.
        frames = [
            f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} {f.name}"
            for f in traceback.extract_tb(exc.__traceback__)
        ]
        log.error("unhandled_error", error_type=type(exc).__name__, frames=frames[-8:])
        return _response(
            request,
            ApiProblem(
                500, "internal_error", "Internal server error", "An unexpected error occurred."
            ),
        )
