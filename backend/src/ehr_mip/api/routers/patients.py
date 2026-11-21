"""Patient detail, resources and summary (docs/04 sections 6.2 to 6.4)."""

from __future__ import annotations

import sqlite3
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response

from ehr_mip.api import views
from ehr_mip.api.deps import AppState, get_conn, get_state
from ehr_mip.api.schemas.common import Problem, ResourceType
from ehr_mip.api.schemas.patients import PatientDetail, PatientResourcesResponse
from ehr_mip.api.schemas.summary import ClinicalSummaryResponse
from ehr_mip.cache.backend import safe_get, safe_set
from ehr_mip.errors import SummaryNotFoundError
from ehr_mip.observability.metrics import CACHE_REQUESTS
from ehr_mip.summarization.cache import SummaryCache

router = APIRouter(prefix="/patients", tags=["patients"])
PATIENT_CACHE_TTL_S = 300
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem},
    422: {"model": Problem},
    429: {"model": Problem},
}


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
    await safe_set(state.patient_cache, cache_key, detail.model_dump_json().encode(),
                   PATIENT_CACHE_TTL_S)  # fmt: skip
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
    await safe_set(state.patient_cache, cache_key, result.model_dump_json().encode(),
                   PATIENT_CACHE_TTL_S)  # fmt: skip
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
