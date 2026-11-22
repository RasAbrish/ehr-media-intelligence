"""``/health`` and ``/ready`` (docs/04 sections 4.1 and 4.2, FR-9.3)."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Response

from ehr_mip import __version__
from ehr_mip.api import quality_views
from ehr_mip.api.deps import AppState, get_conn, get_state
from ehr_mip.api.schemas.system import (
    CacheStatus,
    Check,
    EmbedderCheck,
    HealthResponse,
    LastRun,
    LlmCheck,
    ReadyChecks,
    ReadyCounts,
    ReadyFlags,
    ReadyResponse,
    StatsResponse,
    VectorStoreCheck,
)
from ehr_mip.db.read_models import StatusReader
from ehr_mip.search.vector_store import COLLECTION

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/stats", response_model=StatsResponse, summary="Counts for the top bar")
async def stats(response: Response, conn: sqlite3.Connection = Depends(get_conn)) -> StatsResponse:
    response.headers["Cache-Control"] = "max-age=5"
    return quality_views.stats(conn)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse, "description": "A required component failed"}},
    summary="Readiness with component checks",
)
async def ready(
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> ReadyResponse:
    settings = state.settings
    try:
        mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
        reader = StatusReader(conn)
        counts = reader.counts()
        last = reader.last_run()
        sqlite = Check(ok=True, detail=mode)
    except sqlite3.Error as error:
        sqlite = Check(ok=False, detail=type(error).__name__)
        counts, last, reader = {"patients": 0, "resources": 0, "summaries": 0}, None, None

    search = state.search
    chunks = 0
    if search is not None:
        try:
            if reader is not None:
                search.refresh(conn)
            chunks = search.chunk_count()
            vector = VectorStoreCheck(
                ok=True,
                detail=f"collection {COLLECTION}" + ("" if chunks else " (empty)"),
                chunks=chunks,
            )
        except Exception as error:
            vector = VectorStoreCheck(ok=False, detail=type(error).__name__, chunks=0)
        embedder = EmbedderCheck(ok=True, detail="warm", model=state.embedder_model)
    else:
        vector = VectorStoreCheck(ok=False, detail="not loaded", chunks=0)
        embedder = EmbedderCheck(
            ok=False, detail=state.embedder_error or "not loaded", model=settings.embedding_model
        )

    provider = settings.effective_llm_provider
    llm = LlmCheck(
        ok=True,
        detail="api key present" if provider == "anthropic" else "extractive fallback (no API key)",
        provider=provider,
        model=settings.llm_model if provider == "anthropic" else None,
    )
    if search is not None:
        index_version = search.index_version or 0
    else:
        index_version = reader.index_version() if reader is not None else 0
    cache_ok = await state.cache.ping()
    required_ok = sqlite.ok and vector.ok and embedder.ok
    degraded = provider == "extractive" or chunks == 0 or not cache_ok
    status: Literal["ready", "degraded", "not_ready"] = (
        "not_ready" if not required_ok else "degraded" if degraded else "ready"
    )
    if not required_ok:
        response.status_code = 503
    return ReadyResponse(
        status=status,
        checks=ReadyChecks(sqlite=sqlite, vector_store=vector, embedder=embedder, llm=llm),
        counts=ReadyCounts(**counts, chunks=chunks),
        last_run=LastRun(
            run_id=last["run_id"],
            finished_at=last["finished_at"],
            status="succeeded" if last["finished_at"] else "running",
        )
        if last
        else None,
        flags=ReadyFlags(
            search_mode=settings.search_mode,
            index_observations=settings.index_observations,
            admin_enabled=settings.enable_admin_endpoints,
            cache_backend=state.cache.name,
            feedback_enabled=settings.feedback_enabled,
        ),
        cache=CacheStatus(
            backend=state.cache.name,
            ok=cache_ok,
            index_version=index_version,
        ),
    )
