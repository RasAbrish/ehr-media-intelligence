"""Read models → contract schemas. No SQL and no business rules beyond formatting."""

from __future__ import annotations

from datetime import date
from typing import Any

from ehr_mip.api.schemas.common import DOC_TYPES, REPORT_CATEGORIES, PatientRef, ResourceRef
from ehr_mip.db.read_models import IssueRow, PatientRow, ResourceRow

_GENDERS = {"male", "female", "other", "unknown"}
_INTERPRETATIONS = {"LL", "L", "N", "H", "HH"}


def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def patient_ref(patient: PatientRow, today: date) -> PatientRef:
    return PatientRef(
        patient_key=patient.patient_key,
        display_name=patient.display_name,
        mrn=patient.mrn,
        birth_date=iso(patient.birth_date),
        age=patient.age(today),
        gender=patient.gender if patient.gender in _GENDERS else "unknown",  # type: ignore[arg-type]
        identity_conflict=patient.identity_conflict,
    )


def subtype_of(resource_type: str, subtype: str | None) -> Any:
    """Only document types (DocumentReference) and report categories (DiagnosticReport)."""
    if resource_type == "DocumentReference" and subtype in DOC_TYPES:
        return subtype
    if resource_type == "DiagnosticReport" and subtype in REPORT_CATEGORIES:
        return subtype
    return None


def title_of(row: ResourceRow) -> str:
    if row.title:
        return row.title
    if row.resource_type == "Encounter":
        return f"{(row.subtype or 'unknown').capitalize()} encounter"
    return row.resource_type


def resource_ref(row: ResourceRow, issues: list[IssueRow]) -> ResourceRef:
    return ResourceRef(
        resource_type=row.resource_type,  # type: ignore[arg-type]
        resource_id=row.resource_id,
        date=iso(row.date),
        title=title_of(row),
        subtype=subtype_of(row.resource_type, row.subtype),
        is_valid=not any(i.severity == "error" for i in issues),
    )


def interpretation_of(resource: dict[str, Any]) -> Any:
    for concept in resource.get("interpretation") or []:
        for coding in concept.get("coding") or []:
            if coding.get("code") in _INTERPRETATIONS:
                return coding["code"]
    return None


def reference_id(reference: dict[str, Any] | None) -> str | None:
    value = (reference or {}).get("reference")
    return str(value).removeprefix("urn:uuid:") if value else None


def _number(value: Any) -> str:
    return f"{value:g}" if isinstance(value, int | float) else str(value)


def observation_value(resource: dict[str, Any]) -> tuple[str, str | None]:
    quantity = resource.get("valueQuantity")
    if quantity:
        return f"{quantity.get('comparator', '')}{_number(quantity.get('value'))}", quantity.get(
            "unit"
        )
    return str(resource.get("valueString") or ""), None


def reference_range(resource: dict[str, Any]) -> str | None:
    ranges = resource.get("referenceRange") or []
    if not ranges:
        return None
    low = (ranges[0].get("low") or {}).get("value")
    high = (ranges[0].get("high") or {}).get("value")
    if low is not None and high is not None:
        return f"{_number(low)} to {_number(high)}"
    if high is not None:
        return f"up to {_number(high)}"
    if low is not None:
        return f"at least {_number(low)}"
    text = ranges[0].get("text")
    return str(text) if text else None


def summary_line(row: ResourceRow) -> str | None:
    if row.resource_type == "Observation":
        return row.text
    if row.resource_type == "DiagnosticReport":
        return row.resource.get("conclusion") or title_of(row)
    if row.resource_type == "DocumentReference":
        return row.resource.get("description") or title_of(row)
    return title_of(row)
