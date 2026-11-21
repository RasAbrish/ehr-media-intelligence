"""Pure ASGI middleware: request context, security headers, body limit (docs/09 section 5).

Pure ASGI (not ``BaseHTTPMiddleware``) keeps the per-request overhead small and lets
these headers reach every response, including 413 and 429 problems.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ehr_mip.api.errors import PROBLEM_TYPE, problem_body
from ehr_mip.api.security_headers import API_HEADERS, DOCS_PATHS, HSTS, NO_STORE

log = structlog.get_logger("ehr_mip.api.access")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return str(value.decode("latin-1"))
    return None


def server_timing(stages: dict[str, float], total_ms: float) -> str:
    parts = [f"total;dur={total_ms:.1f}"]
    parts += [f"{name};dur={ms:.1f}" for name, ms in stages.items()]
    return ", ".join(parts)


class RequestContextMiddleware:
    """Request id, timing, security headers, ``no-store`` default and one access log line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = _header(scope, b"x-request-id")
        request_id = incoming if incoming and _REQUEST_ID.match(incoming) else str(uuid.uuid4())
        state: dict[str, Any] = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["server_timing"] = {}
        started = time.perf_counter()
        status_code = 500
        path: str = scope["path"]
        is_docs = path.startswith(DOCS_PATHS)

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                total = (time.perf_counter() - started) * 1000
                headers.append((b"x-request-id", request_id.encode()))
                headers.append(
                    (b"server-timing", server_timing(state["server_timing"], total).encode())
                )
                headers += [
                    h for h in API_HEADERS if not (is_docs and h[0].startswith(b"content-sec"))
                ]
                if scope.get("scheme") == "https":
                    headers.append(HSTS)
                if b"cache-control" not in names:
                    headers.append(NO_STORE)
                message["headers"] = headers
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                route = scope.get("route")
                log.info(
                    "request",
                    method=scope["method"],
                    route=getattr(route, "path", path),
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )


class BodyLimitMiddleware:
    """Refuse bodies over ``max_bytes`` with 413, whether or not Content-Length is sent."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in BODY_METHODS:
            await self.app(scope, receive, send)
            return
        declared = _header(scope, b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await self._refuse(scope, send)
            return
        # Read the body up to the limit, then replay it to the app.
        chunks: list[bytes] = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await self._refuse(scope, send)
                return
            chunks.append(chunk)
            more = bool(message.get("more_body", False))
        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)

    async def _refuse(self, scope: Scope, send: Send) -> None:
        body = problem_body(
            status=413,
            code="payload_too_large",
            title="Payload too large",
            detail=f"Request body is larger than {self.max_bytes // 1024} KB.",
            instance=scope["path"],
            request_id=str(scope.get("state", {}).get("request_id", "")),
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", PROBLEM_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
