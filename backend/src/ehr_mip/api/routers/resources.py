"""``GET /resources/{resource_type}/{resource_id}`` (docs/04 section 7.1)."""

from __future__ import annotations

import sqlite3
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from ehr_mip.api import views
from ehr_mip.api.deps import AppState, get_conn, get_state
from ehr_mip.api.schemas.common import Problem
from ehr_mip.api.schemas.resources import ResourceDetail

router = APIRouter(prefix="/resources", tags=["resources"])
DetailType = Literal["Encounter", "DocumentReference", "DiagnosticReport", "Observation"]


@router.get(
    "/{resource_type}/{resource_id}",
    response_model=ResourceDetail,
    responses={404: {"model": Problem}, 422: {"model": Problem}, 429: {"model": Problem}},
    summary="One resource with decoded text and its FHIR JSON",
)
async def resource_detail(
    resource_type: DetailType,
    resource_id: UUID,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> ResourceDetail:
    return views.resource_detail(conn, resource_type, str(resource_id), state.today())
