"""``GET /resources/{type}/{id}`` (docs/04 section 7.1)."""

from __future__ import annotations

from typing import Any

from ehr_mip.api.schemas.common import (
    ApiModel,
    Interpretation,
    PatientRef,
    ResourceRef,
    Severity,
)


class Section(ApiModel):
    heading: str
    body: str


class ObservationRow(ApiModel):
    resource_id: str
    name: str
    value: str
    unit: str | None
    interpretation: Interpretation | None
    reference_range: str | None


class DetailIssue(ApiModel):
    severity: Severity
    code: str
    message: str
    path: str


class ResourceDetail(ApiModel):
    resource: ResourceRef
    patient: PatientRef
    text: str | None
    sections: list[Section]
    observations: list[ObservationRow]
    issues: list[DetailIssue]
    fhir: dict[str, Any]
