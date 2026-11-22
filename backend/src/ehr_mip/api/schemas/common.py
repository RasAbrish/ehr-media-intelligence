"""Shared contract objects (docs/04 section 2). Optional fields are present as null."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ResourceType = Literal[
    "Patient", "Encounter", "DocumentReference", "DiagnosticReport", "Observation"
]
SearchableType = Literal["DocumentReference", "DiagnosticReport", "Observation", "ClinicalSummary"]
Gender = Literal["male", "female", "other", "unknown"]
DocType = Literal[
    "discharge_summary",
    "progress_note",
    "consult_note",
    "imaging_report",
    "lab_report",
    "pathology_report",
    "scanned_document",
]
ReportCategory = Literal["LAB", "RAD", "PAT"]
Severity = Literal["info", "warning", "error"]
AnomalySeverity = Literal["low", "moderate", "high"]
ConfidenceLevel = Literal["low", "medium", "high"]
SearchMode = Literal["semantic", "hybrid"]
SearchSort = Literal["relevance", "newest"]
MatchType = Literal["semantic", "lexical", "hybrid", "mrn"]
SummaryProvider = Literal["anthropic", "groq", "extractive"]
RunStatus = Literal["queued", "running", "succeeded", "failed"]
Interpretation = Literal["LL", "L", "N", "H", "HH"]
EvidenceType = Literal["DocumentReference", "DiagnosticReport", "Observation", "Encounter"]

DOC_TYPES: frozenset[str] = frozenset(DocType.__args__)  # type: ignore[attr-defined]
REPORT_CATEGORIES: frozenset[str] = frozenset(ReportCategory.__args__)  # type: ignore[attr-defined]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatientRef(ApiModel):
    patient_key: str
    display_name: str
    mrn: str
    birth_date: str | None
    age: int | None
    gender: Gender
    identity_conflict: bool


class ResourceRef(ApiModel):
    resource_type: Literal[
        "DocumentReference", "DiagnosticReport", "Observation", "ClinicalSummary", "Encounter"
    ]
    resource_id: str
    date: str | None
    title: str
    subtype: DocType | ReportCategory | None
    is_valid: bool


class EvidenceRef(ApiModel):
    resource_type: EvidenceType
    resource_id: str


class FieldError(ApiModel):
    loc: str
    message: str
    type: str


class Problem(ApiModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: list[FieldError]
