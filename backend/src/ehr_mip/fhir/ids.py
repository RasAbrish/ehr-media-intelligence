"""FHIR ids are the deterministic UUIDv5 keys from ``ehr_mip.ids`` (ADR-004)."""

from __future__ import annotations

from ehr_mip.ids import (
    NAMESPACE,
    document_key,
    encounter_key,
    make_key,
    patient_key,
    report_key,
    result_key,
)

__all__ = [
    "NAMESPACE",
    "document_key",
    "encounter_key",
    "make_key",
    "patient_key",
    "reference",
    "report_key",
    "result_key",
]


def reference(resource_id: str) -> str:
    """Bundle-internal reference and ``fullUrl`` for a resource id."""
    return f"urn:uuid:{resource_id}"
