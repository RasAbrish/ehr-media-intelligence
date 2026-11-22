"""Patient detail and resources (docs/04 sections 6.2 and 6.3)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ehr_mip.api.schemas.common import ApiModel, Interpretation, PatientRef, ResourceRef, Severity


class Identifier(ApiModel):
    system: str
    value: str
    use: Literal["usual", "old"]


class AddressOut(ApiModel):
    line: str | None
    city: str | None
    state: str | None
    postal_code: str | None


class BundleStatus(ApiModel):
    is_valid: bool
    error_count: int
    warning_count: int
    bundle_hash: str


class ResourceCounts(ApiModel):
    Encounter: int
    DocumentReference: int
    DiagnosticReport: int
    Observation: int


class DataQuality(ApiModel):
    audit_entries: int
    warnings: int
    errors: int


class PatientDetail(PatientRef):
    family_name: str | None
    given_names: list[str]
    identifiers: list[Identifier]
    phone: str | None
    address: AddressOut | None
    bundle: BundleStatus
    counts: ResourceCounts
    first_activity: str | None
    last_activity: str | None
    data_quality: DataQuality


class ResourceIssue(ApiModel):
    severity: Severity
    code: str
    message: str


class PatientResourceItem(ResourceRef):
    status: str
    encounter_id: str | None
    summary_line: str | None
    interpretation: Interpretation | None
    issues: list[ResourceIssue]


class PatientResourcesResponse(ApiModel):
    patient_key: str
    total: int
    items: list[PatientResourceItem]


class AnomalyCounts(ApiModel):
    high: int
    moderate: int
    low: int


class PatientListItem(PatientRef):
    last_activity: str | None
    resource_count: int
    has_summary: bool
    chief_concern: str | None
    anomaly_counts: AnomalyCounts


class SummaryFeedbackRequest(ApiModel):
    cache_key: str = Field(min_length=1, max_length=128)
    rating: Literal["helpful", "not_helpful"]
    reason: Literal["inaccurate", "missing_information", "too_long", "unclear", "other"] | None
    comment: str | None = Field(max_length=280)


class FeedbackTotalsOut(ApiModel):
    helpful: int
    not_helpful: int


class SummaryFeedbackResponse(ApiModel):
    id: int
    cache_key: str
    rating: Literal["helpful", "not_helpful"]
    totals: FeedbackTotalsOut
