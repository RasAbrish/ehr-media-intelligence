"""Patients: directory, detail, resources, summary, audit and feedback (docs/04 section 6, 9a)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response

from ehr_mip.api import quality_views, views
from ehr_mip.api.deps import AppState, get_conn, get_state
from ehr_mip.api.errors import ApiProblem, validation_problem
from ehr_mip.api.schemas.common import Problem, ResourceType, Severity
from ehr_mip.api.schemas.patients import (
    FeedbackTotalsOut,
    PatientDetail,
    PatientListItem,
    PatientResourcesResponse,
    SummaryFeedbackRequest,
    SummaryFeedbackResponse,
)
from ehr_mip.api.schemas.quality import AuditEntryItem, Page
from ehr_mip.api.schemas.summary import ClinicalSummaryResponse
from ehr_mip.cache.backend import safe_get, safe_set
from ehr_mip.errors import SummaryNotFoundError
from ehr_mip.observability.metrics import CACHE_REQUESTS
from ehr_mip.summarization.cache import SummaryCache
from ehr_mip.summarization.feedback import DuplicateFeedbackError, FeedbackRepository

router = APIRouter(prefix="/patients", tags=["patients"])
PATIENT_CACHE_TTL_S = 300
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem},
    422: {"model": Problem},
    429: {"model": Problem},
}

LIST_ERRORS: dict[int | str, dict[str, Any]] = {422: {"model": Problem}, 429: {"model": Problem}}


@router.get(
    "",
    response_model=Page[PatientListItem],
    responses=LIST_ERRORS,
    summary="Paginated patient directory",
)
async def patient_directory(
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    sort: Literal["name", "mrn", "birth_date", "last_activity", "resource_count"] = "last_activity",
    order: Literal["asc", "desc"] = "desc",
    conflict_only: bool = False,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    return quality_views.directory(
        conn,
        q=q.strip() if q and q.strip() else None,
        sort=sort,
        descending=order == "desc",
        conflict_only=conflict_only,
        page=page,
        page_size=page_size,
        today=state.today(),
    )


@router.get(
    "/{patient_key}/audit",
    response_model=Page[AuditEntryItem],
    responses=NOT_FOUND,
    summary="Audit entries for one patient (PHI masked)",
)
async def patient_audit(
    patient_key: UUID,
    severity: Annotated[list[Severity], Query()] = [],  # noqa: B006 (FastAPI default)
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    key = str(patient_key)
    views.patient_and_bundle(conn, key)  # 404 for unknown patients
    return quality_views.patient_audit(
        conn, key, severities=list(severity), page=page, page_size=page_size
    )


@router.post(
    "/{patient_key}/summary/feedback",
    status_code=201,
    response_model=SummaryFeedbackResponse,
    responses={**NOT_FOUND, 409: {"model": Problem}},
    summary="Rate the summary version currently served",
)
async def summary_feedback(
    patient_key: UUID,
    body: SummaryFeedbackRequest,
    x_client_id: Annotated[str | None, Header(max_length=64)] = None,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> SummaryFeedbackResponse:
    if not state.settings.feedback_enabled:
        raise ApiProblem(404, "not_found", "Not found", "Summary feedback is turned off.")
    key = str(patient_key)
    views.patient_and_bundle(conn, key)
    repository = FeedbackRepository(conn)
    version = repository.summary_version(key, body.cache_key)
    if version is None:
        raise validation_problem(
            "body.cache_key", "cache_key does not identify a summary of this patient"
        )
    if body.rating == "not_helpful" and body.reason is None:
        raise validation_problem("body.reason", "reason is required when the rating is not_helpful")
    comment = body.comment.strip() if body.comment and body.comment.strip() else None
    try:
        feedback_id = repository.record(
            patient_key=key,
            cache_key=body.cache_key,
            prompt_version=version,
            rating=body.rating,
            reason=body.reason if body.rating == "not_helpful" else None,
            comment=comment,
            client_id=x_client_id,
            at=datetime.now(UTC),
        )
    except DuplicateFeedbackError:
        raise ApiProblem(
            409,
            "feedback_duplicate",
            "Feedback already recorded",
            "This browser already rated this summary version.",
        ) from None
    totals = repository.totals(body.cache_key)
    return SummaryFeedbackResponse(
        id=feedback_id,
        cache_key=body.cache_key,
        rating=body.rating,
        totals=FeedbackTotalsOut(helpful=totals.helpful, not_helpful=totals.not_helpful),
    )


async def _cached(state: AppState, key: str, response: Response) -> Response | None:
    """A cached JSON body as a response (X-Cache: HIT), or None and X-Cache: MISS."""
    value = await safe_get(state.patient_cache, key)
    CACHE_REQUESTS.labels(cache="patient", result="hit" if value else "miss").inc()
    response.headers["X-Cache"] = "HIT" if value is not None else "MISS"
    if value is None:
        return None
    return Response(value, media_type="application/json", headers=dict(response.headers))


@router.get(
    "/{patient_key}",
    response_model=PatientDetail,
    responses=NOT_FOUND,
    summary="Patient detail for the drawer header",
)
async def patient_detail(
    patient_key: UUID,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> PatientDetail | Response:
    key = str(patient_key)
    patient, bundle = views.patient_and_bundle(conn, key)
    cache_key = f"ehr-mip:patient:{bundle.bundle_hash}:{key}:detail"
    hit = await _cached(state, cache_key, response)
    if hit is not None:
        return hit
    detail = views.patient_detail(conn, patient, bundle, state.today())
    await safe_set(
        state.patient_cache, cache_key, detail.model_dump_json().encode(), PATIENT_CACHE_TTL_S
    )
    return detail


@router.get(
    "/{patient_key}/resources",
    response_model=PatientResourcesResponse,
    responses=NOT_FOUND,
    summary="Linked FHIR resources for the drawer table",
)
async def patient_resources(
    patient_key: UUID,
    response: Response,
    resource_type: Annotated[list[ResourceType], Query()] = [],  # noqa: B006 (FastAPI default)
    sort: Literal["date", "type", "title"] = "date",
    order: Literal["asc", "desc"] = "desc",
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> PatientResourcesResponse | Response:
    key = str(patient_key)
    _, bundle = views.patient_and_bundle(conn, key)
    types = views.listable_types(resource_type)
    variant = f"{','.join(sorted(types))}:{sort}:{order}"
    cache_key = f"ehr-mip:patient:{bundle.bundle_hash}:{key}:resources:{variant}"
    hit = await _cached(state, cache_key, response)
    if hit is not None:
        return hit
    result = views.patient_resources(conn, key, types, sort, order)
    await safe_set(
        state.patient_cache, cache_key, result.model_dump_json().encode(), PATIENT_CACHE_TTL_S
    )
    return result


@router.get(
    "/{patient_key}/summary",
    response_model=ClinicalSummaryResponse,
    responses={**NOT_FOUND, 304: {"description": "ETag matches; not modified"}},
    summary="Latest AI summary for the current bundle",
)
async def patient_summary(
    patient_key: UUID,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
    conn: sqlite3.Connection = Depends(get_conn),
) -> ClinicalSummaryResponse | Response:
    key = str(patient_key)
    _, bundle = views.patient_and_bundle(conn, key)
    summary = SummaryCache(conn).latest(key, bundle.bundle_hash)
    if summary is None:
        msg = "Summary not generated. Run the pipeline."
        raise SummaryNotFoundError(msg)
    etag = f'"{bundle.bundle_hash}:{summary.prompt_version}"'
    if if_none_match and etag in {tag.strip() for tag in if_none_match.split(",")}:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    data = summary.model_dump(mode="json", exclude={"self_reported_confidence"})
    return ClinicalSummaryResponse.model_validate({**data, "cached": True})
