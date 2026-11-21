"""Patient detail and resources (docs/04 sections 6.2 and 6.3)."""

from __future__ import annotations

from typing import Literal

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
