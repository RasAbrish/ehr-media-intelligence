"""Intermediate representation for Task 1 (docs/03-DATA-MODEL.md section 3)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class AdministrativeGender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class EncounterClass(StrEnum):
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    EMERGENCY = "emergency"
    VIRTUAL = "virtual"
    UNKNOWN = "unknown"


class DocType(StrEnum):
    DISCHARGE_SUMMARY = "discharge_summary"
    PROGRESS_NOTE = "progress_note"
    CONSULT_NOTE = "consult_note"
    IMAGING_REPORT = "imaging_report"
    LAB_REPORT = "lab_report"
    PATHOLOGY_REPORT = "pathology_report"
    SCANNED_DOCUMENT = "scanned_document"


LabFlag = Literal["LL", "L", "N", "H", "HH"]
Severity = Literal["info", "warning", "error"]
Stage = Literal["read", "clean", "identity", "dedupe"]
SourceFormat = Literal["json", "csv", "txt"]
RecordKind = Literal["patient", "encounter", "document", "lab_result"]
Mrn = Annotated[str, StringConstraints(pattern=r"^\d{8}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class _RawModel(BaseModel):
    """Keeps whitespace: these models record what was found, exactly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RawRecord(_RawModel):
    source_file: str
    source_format: SourceFormat
    source_locator: str
    kind: RecordKind
    payload: dict[str, Any]


class Address(_Model):
    line: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None


class CleanPatient(_Model):
    patient_key: str
    mrn: Mrn
    secondary_mrns: list[Mrn] = Field(default_factory=list)
    family_name: str | None
    given_names: list[str] = Field(default_factory=list)
    birth_date: date | None
    gender: AdministrativeGender
    phone: str | None = None
    address: Address | None = None
    source_record_ids: list[str]
    identity_conflict: bool = False


class CleanEncounter(_Model):
    encounter_key: str
    patient_key: str
    source_encounter_id: str | None
    encounter_class: EncounterClass
    period_start: datetime | date | None
    period_end: datetime | date | None


class CleanDocument(_Model):
    document_key: str
    patient_key: str
    encounter_key: str | None
    doc_type: DocType
    title: str
    author: str | None
    document_date: datetime | date | None
    text: str
    content_hash: str
    source_record_id: str


class CleanLabResult(_Model):
    result_key: str
    patient_key: str
    encounter_key: str | None
    report_key: str
    test_name: str
    loinc: str | None
    value: float | None
    value_raw: str
    unit: str | None
    ref_low: float | None
    ref_high: float | None
    flag: LabFlag | None
    collected_at: datetime | date | None
    source_record_id: str


class AuditEntry(_RawModel):
    record_id: str
    patient_key: str | None
    stage: Stage
    field: str | None
    rule: str
    before: str | None
    after: str | None
    severity: Severity
    message: str


class QuarantinedRecord(_RawModel):
    source_locator: str
    reason: str
    payload: dict[str, Any]


class IngestionStats(_Model):
    records_read: dict[str, int]
    patients: int
    encounters: int
    documents: int
    lab_results: int
    lab_reports: int
    duplicates_exact: int
    duplicates_near: int
    duplicates_lab: int
    identities_merged: int
    identity_conflicts: int
    quarantined: int
    audit_by_rule: dict[str, int]
    audit_by_severity: dict[str, int]


class IngestionResult(_Model):
    patients: list[CleanPatient]
    encounters: list[CleanEncounter]
    documents: list[CleanDocument]
    lab_results: list[CleanLabResult]
    audit: list[AuditEntry]
    quarantine: list[QuarantinedRecord]
    stats: IngestionStats
