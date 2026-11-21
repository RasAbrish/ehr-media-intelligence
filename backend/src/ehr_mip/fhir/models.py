"""Task 2 models: validation issues, built bundles and the resource index rows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["info", "warning", "error"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidationIssue(_Model):
    patient_key: str
    resource_type: str
    resource_id: str | None
    path: str | None
    severity: Severity
    code: str
    message: str


class ResourceRow(_Model):
    """One row of ``fhir_resources``: a resource plus fields for listing and search."""

    resource_id: str
    patient_key: str
    resource_type: str
    resource_date: str | None
    title: str | None
    subtype: str | None
    text_content: str | None
    resource: dict[str, Any]


class BuiltBundle(_Model):
    patient_key: str
    bundle: dict[str, Any]
    bundle_hash: str
    rows: list[ResourceRow]


class BundleValidation(_Model):
    patient_key: str
    is_valid: bool
    error_count: int
    warning_count: int
    info_count: int
    issues: list[ValidationIssue] = Field(default_factory=list)


class NormalizedBundle(_Model):
    built: BuiltBundle
    validation: BundleValidation
