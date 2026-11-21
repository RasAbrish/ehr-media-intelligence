"""Response security headers for the JSON API (docs/09 section 5.1)."""

from __future__ import annotations

API_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
)
HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
NO_STORE = (b"cache-control", b"no-store")
# Interactive docs (dev only, off in prod) load Swagger UI assets, so they skip the CSP.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
