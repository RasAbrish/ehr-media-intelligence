"""FastAPI app factory (docs/02 sections 3 and 9).

Lifespan: apply the schema once, load and warm the embedder, open Chroma, build the
BM25 index. Components can be injected for tests (a hash embedder and a temporary
Chroma directory), so tests never download a model.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, closing

import structlog
from chromadb.api import ClientAPI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from ehr_mip import __version__
from ehr_mip.api.deps import AppState
from ehr_mip.api.errors import register_error_handlers
from ehr_mip.api.middleware import BodyLimitMiddleware, RequestContextMiddleware
from ehr_mip.api.rate_limit import RateLimitMiddleware
from ehr_mip.api.routers import patients, resources, search, system
from ehr_mip.cache.backend import CacheBackend, build_cache
from ehr_mip.config import Settings, get_settings
from ehr_mip.db.connection import connect
from ehr_mip.logging import configure_logging
from ehr_mip.observability.log_redaction import redact_phi
from ehr_mip.search.embedder import Embedder, SentenceTransformerEmbedder
from ehr_mip.search.service import SearchService
from ehr_mip.search.vector_store import VectorStore, open_client

log = structlog.get_logger(__name__)
MAX_BODY_BYTES = 16 * 1024
EXPOSED_HEADERS = ["X-Request-ID", "X-Cache", "Server-Timing", "ETag", "Retry-After",
                   "RateLimit-Limit", "RateLimit-Remaining", "RateLimit-Reset"]  # fmt: skip


def _default_embedder(settings: Settings) -> Embedder:
    return SentenceTransformerEmbedder(settings.embedding_model, settings.hf_home)


def create_app(
    settings: Settings | None = None,
    *,
    embedder_factory: Callable[[Settings], Embedder] = _default_embedder,
    chroma_client: ClientAPI | None = None,
    cache: CacheBackend | None = None,
    configure_logs: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    if configure_logs:
        configure_logging(settings.log_level, extra_processors=[redact_phi])
    state = AppState(settings=settings, cache=cache or build_cache(settings))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with closing(connect(settings.sqlite_path)) as conn:  # schema once, then per request
            try:
                embedder = embedder_factory(settings)
                store = VectorStore(chroma_client or open_client(settings.chroma_dir))
                state.search = SearchService(store, embedder)
                state.embedder_model = embedder.model_name
                state.search.refresh(conn)
            except Exception as error:
                state.search = None
                state.embedder_error = type(error).__name__
                log.error("search_unavailable", error_type=type(error).__name__)
        app.state.ehr = state
        log.info("api_started", version=__version__, search_ready=state.search is not None)
        yield
        log.info("api_stopping")

    prod = settings.env == "prod"
    app = FastAPI(
        title="EHR Media Intelligence API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if prod else "/docs",
        redoc_url=None if prod else "/redoc",
        openapi_url=None if prod else "/openapi.json",
    )
    app.state.ehr = state
    register_error_handlers(app)
    for router in (system.router, search.router, patients.router, resources.router):
        app.include_router(router)
    Instrumentator(should_group_status_codes=False, excluded_handlers=["/metrics"]).instrument(
        app
    ).expose(app, include_in_schema=False)

    # Starlette runs the last added middleware first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID", "X-Client-Id", "If-None-Match"],
        expose_headers=EXPOSED_HEADERS,
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(RateLimitMiddleware, enabled=settings.rate_limit_enabled)
    app.add_middleware(RequestContextMiddleware)
    # Outermost: the client IP the rate limiter sees comes from X-Forwarded-For only when
    # the direct peer is a trusted proxy (FORWARDED_ALLOW_IPS), never from any caller.
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=[h.strip() for h in settings.forwarded_allow_ips.split(",") if h.strip()],
    )
    return app
