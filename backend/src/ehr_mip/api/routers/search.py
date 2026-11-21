"""``POST /search`` (docs/04 section 5.1, docs/02 sections 6.1 and 8.1)."""

from __future__ import annotations

import sqlite3
import time
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from ehr_mip.api.deps import AppState, get_conn, get_search, get_state
from ehr_mip.api.errors import validation_problem
from ehr_mip.api.mappers import patient_ref, subtype_of
from ehr_mip.api.schemas.common import Problem, ResourceRef, SearchableType, SearchMode
from ehr_mip.api.schemas.search import AppliedFilters, SearchRequest, SearchResponse, SearchResult
from ehr_mip.cache.backend import safe_get, safe_set
from ehr_mip.db.read_models import PatientReader
from ehr_mip.observability.metrics import CACHE_REQUESTS, SEARCH_LATENCY
from ehr_mip.search.chunker import SUMMARY_TITLE
from ehr_mip.search.filters import SearchFilters
from ehr_mip.search.highlights import mrn_digits
from ehr_mip.search.service import SearchOutcome, SearchService, cache_key, hydrate

router = APIRouter(tags=["search"])
ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"


def _date(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise validation_problem(
            f"query.{field}", f"{field} must be a real date (YYYY-MM-DD)"
        ) from None


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        413: {"model": Problem},
        422: {"model": Problem},
        429: {"model": Problem},
        503: {"model": Problem},
    },
    summary="Semantic search across FHIR records and AI summaries",
)
async def search(  # noqa: PLR0913, PLR0917 (query parameters of the contract)
    request: Request,
    response: Response,
    body: SearchRequest,
    resource_type: Annotated[list[SearchableType], Query()] = [],  # noqa: B006 (FastAPI default)
    date_from: Annotated[str | None, Query(pattern=ISO_DATE)] = None,
    date_to: Annotated[str | None, Query(pattern=ISO_DATE)] = None,
    top_k: Annotated[int | None, Query(ge=1, le=20)] = None,
    mode: SearchMode | None = None,
    patient_key: UUID | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
    service: SearchService = Depends(get_search),
) -> SearchResponse:
    started = time.perf_counter()
    start, end = _date(date_from, "date_from"), _date(date_to, "date_to")
    if start and end and end < start:
        raise validation_problem("query.date_to", "date_to must be on or after date_from")
    settings = state.settings
    mode = mode or settings.search_mode
    top_k = top_k or settings.search_default_top_k
    filters = SearchFilters(
        resource_types=tuple(dict.fromkeys(resource_type)),
        date_from=start,
        date_to=end,
        patient_key=str(patient_key) if patient_key else None,
    )
    version = service.refresh(conn)
    digits = mrn_digits(body.query)
    mrn_patients = [p.patient_key for p in PatientReader(conn).by_mrn(digits)] if digits else []

    key = cache_key(version, body.query, filters, top_k, mode, mrn_patients)
    payload = await safe_get(state.cache, key)
    if payload is not None:
        outcome, hit = SearchOutcome.from_bytes(payload), True
    else:
        outcome = await run_in_threadpool(
            service.rank, body.query, filters, top_k=top_k, mode=mode, mrn_patients=mrn_patients
        )
        hit = False
        await safe_set(state.cache, key, outcome.to_bytes(), settings.search_cache_ttl_s)
    CACHE_REQUESTS.labels(cache="search", result="hit" if hit else "miss").inc()

    hydrate_started = time.perf_counter()
    hydrated = hydrate(conn, outcome.results)
    today = state.today()
    results = [
        SearchResult(
            rank=position,
            score=h.ranked.score,
            semantic_score=h.ranked.semantic_score,
            match_type=h.ranked.match_type,
            patient=patient_ref(h.patient, today),
            resource=ResourceRef(
                resource_type=h.ranked.resource_type,  # type: ignore[arg-type]
                resource_id=h.ranked.resource_id,
                date=h.ranked.date or None,
                title=h.ranked.title or SUMMARY_TITLE,
                subtype=subtype_of(h.ranked.resource_type, h.ranked.subtype),
                is_valid=h.is_valid,
            ),
            snippet=h.ranked.snippet,
            highlights=h.ranked.highlights,
            summary_snippet=h.summary_snippet,
        )
        for position, h in enumerate(hydrated, start=1)
    ]
    timings = {**outcome.timings, "hydrate": (time.perf_counter() - hydrate_started) * 1000}
    request.state.server_timing.update(timings)
    took = time.perf_counter() - started
    SEARCH_LATENCY.labels(mode=mode, cache="hit" if hit else "miss").observe(took)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return SearchResponse(
        query=body.query,
        took_ms=round(took * 1000),
        total=len(results),
        mode=mode,
        filters=AppliedFilters(
            resource_type=list(filters.resource_types),
            date_from=date_from,
            date_to=date_to,
            patient_key=filters.patient_key,
        ),
        results=results,
    )
