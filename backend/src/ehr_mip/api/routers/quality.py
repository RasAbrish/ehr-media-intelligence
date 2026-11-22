"""Data quality endpoints (docs/04 section 8, P1)."""

from __future__ import annotations

import sqlite3
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ehr_mip.api import quality_views
from ehr_mip.api.deps import AppState, get_conn, get_state
from ehr_mip.api.schemas.common import Problem, ResourceType, Severity
from ehr_mip.api.schemas.quality import (
    AuditEntryWithPatient,
    Page,
    QualityOverview,
    QuarantineItem,
    ValidationIssueItem,
)

router = APIRouter(prefix="/quality", tags=["quality"])
ERRORS: dict[int | str, dict[str, Any]] = {422: {"model": Problem}, 429: {"model": Problem}}
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get(
    "/overview",
    response_model=QualityOverview,
    responses=ERRORS,
    summary="Ingestion, validation and summary KPIs",
)
async def quality_overview(conn: sqlite3.Connection = Depends(get_conn)) -> QualityOverview:
    return quality_views.overview(conn)


@router.get(
    "/validation",
    response_model=Page[ValidationIssueItem],
    responses=ERRORS,
    summary="Validation issues",
)
async def validation_issues(
    severity: Annotated[list[Severity], Query()] = [],  # noqa: B006
    resource_type: Annotated[list[ResourceType], Query()] = [],  # noqa: B006
    code: Annotated[str | None, Query(max_length=100)] = None,
    page: PageNumber = 1,
    page_size: PageSize = 50,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    return quality_views.validation_issues(
        conn,
        severities=list(severity),
        resource_types=list(resource_type),
        code=code,
        page=page,
        page_size=page_size,
        today=state.today(),
    )


@router.get(
    "/audit",
    response_model=Page[AuditEntryWithPatient],
    responses=ERRORS,
    summary="Audit log with masked values",
)
async def audit_log(
    rule: Annotated[str | None, Query(max_length=100, description="Prefix, e.g. date.")] = None,
    stage: Annotated[list[Literal["read", "clean", "identity", "dedupe"]], Query()] = [],  # noqa: B006
    severity: Annotated[list[Severity], Query()] = [],  # noqa: B006
    patient_key: UUID | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 50,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    return quality_views.quality_audit(
        conn,
        rule=rule,
        stages=list(stage),
        severities=list(severity),
        patient_key=str(patient_key) if patient_key else None,
        page=page,
        page_size=page_size,
        today=state.today(),
    )


@router.get(
    "/quarantine",
    response_model=Page[QuarantineItem],
    responses=ERRORS,
    summary="Quarantined records with masked previews",
)
async def quarantine(
    page: PageNumber = 1,
    page_size: PageSize = 50,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    return quality_views.quarantine(conn, page=page, page_size=page_size)
