"""Fixed-window rate limits with ``RateLimit-*`` headers (docs/09 section 5.2, FR-6.2).

Uses the ``limits`` library (the engine slowapi wraps) directly so responses carry
the ``RateLimit-Limit``, ``RateLimit-Remaining`` and ``RateLimit-Reset`` headers the
contract names. Storage is in memory; Phase 6 adds Redis.
"""

from __future__ import annotations

import math
import re
import time

from limits import RateLimitItem, parse
from limits.storage import MemoryStorage, Storage
from limits.strategies import FixedWindowRateLimiter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ehr_mip.api.errors import PROBLEM_TYPE, problem_body
from ehr_mip.observability.metrics import RATE_LIMITED

_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("search", re.compile(r"^/search/?$"), "60/minute"),
    ("regenerate", re.compile(r"^/patients/[^/]+/summary/regenerate/?$"), "5/minute"),
    ("feedback", re.compile(r"^/patients/[^/]+/summary/feedback/?$"), "20/minute"),
    ("patients", re.compile(r"^/(patients|resources)(/|$)"), "120/minute"),
)
_DEFAULT = ("default", "300/minute")
_METHODS = {"search": "POST", "regenerate": "POST", "feedback": "POST"}


def rule_for(method: str, path: str) -> tuple[str, RateLimitItem]:
    for name, pattern, limit in _RULES:
        wanted = _METHODS.get(name, "GET")
        if pattern.match(path) and method == wanted:
            return name, parse(limit)
    return _DEFAULT[0], parse(_DEFAULT[1])


class RateLimitMiddleware:
    def __init__(
        self, app: ASGIApp, *, enabled: bool = True, storage: Storage | None = None
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.limiter = FixedWindowRateLimiter(storage or MemoryStorage())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return
        route, item = rule_for(scope["method"], scope["path"])
        client = scope.get("client")
        key = client[0] if client else "unknown"
        allowed = self.limiter.hit(item, route, key)
        stats = self.limiter.get_window_stats(item, route, key)
        reset = max(math.ceil(stats.reset_time - time.time()), 0)
        headers = [
            (b"ratelimit-limit", str(item.amount).encode()),
            (b"ratelimit-remaining", str(max(stats.remaining, 0)).encode()),
            (b"ratelimit-reset", str(reset).encode()),
        ]
        if not allowed:
            RATE_LIMITED.labels(route=route).inc()
            body = problem_body(
                status=429,
                code="rate_limited",
                title="Too many requests",
                detail=f"Rate limit of {item.amount} per minute exceeded. Retry in {reset} s.",
                instance=scope["path"],
                request_id=str(scope.get("state", {}).get("request_id", "")),
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", PROBLEM_TYPE.encode()),
                        (b"content-length", str(len(body)).encode()),
                        (b"retry-after", str(max(reset, 1)).encode()),
                        *headers,
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *headers]
            await send(message)

        await self.app(scope, receive, send_wrapper)
