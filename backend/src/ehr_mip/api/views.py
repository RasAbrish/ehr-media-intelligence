"""Read views behind the patient and resource endpoints (docs/04 sections 6 and 7).

Routers stay thin: they validate input, handle caching and HTTP details, and call
these functions, which assemble contract objects from the read models.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import date

from ehr_mip.api.mappers import (
    interpretation_of,
    iso,
    observation_value,
    patient_ref,
    reference_id,
    reference_range,
    resource_ref,
    summary_line,
)
from ehr_mip.api.schemas.patients import (
    AddressOut,
    BundleStatus,
    DataQuality,
    Identifier,
    PatientDetail,
    PatientResourceItem,
    PatientResourcesResponse,
    ResourceCounts,
    ResourceIssue,
)
from ehr_mip.api.schemas.resources import DetailIssue, ObservationRow, ResourceDetail, Section
from ehr_mip.db.read_models import (
    NON_PATIENT_TYPES,
    BundleInfo,
    IssueRow,
    PatientReader,
    PatientRow,
    ResourceReader,
    ResourceRow,
    StatusReader,
)
from ehr_mip.errors import PatientNotFoundError, ResourceNotFoundError
from ehr_mip.summarization.context import split_sections


def patient_and_bundle(conn: sqlite3.Connection, key: str) -> tuple[PatientRow, BundleInfo]:
    patient = PatientReader(conn).get(key)
    bundle = StatusReader(conn).bundle(key)
    if patient is None or bundle is None:
        msg = f"No patient with key {key}."
        raise PatientNotFoundError(msg)
    return patient, bundle


def patient_detail(
    conn: sqlite3.Connection, patient: PatientRow, bundle: BundleInfo, today: date
) -> PatientDetail:
    resources = ResourceReader(conn)
    fhir_patient = resources.get("Patient", patient.patient_key)
    identifiers = [
        Identifier(
            system=str(i.get("system", "")),
            value=str(i["value"]),
            use="old" if i.get("use") == "old" else "usual",
        )
        for i in (fhir_patient.resource.get("identifier", []) if fhir_patient else [])
        if i.get("value")
    ]
    address = patient.address
    first, last = resources.activity_range(patient.patient_key)
    audit = StatusReader(conn).audit_counts(patient.patient_key)
    return PatientDetail(
        **patient_ref(patient, today).model_dump(),
        family_name=patient.family_name,
        given_names=list(patient.given_names),
        identifiers=identifiers,
        phone=patient.phone,
        address=AddressOut(
            line=address.get("line"),
            city=address.get("city"),
            state=address.get("state"),
            postal_code=address.get("zip"),
        )
        if address
        else None,
        bundle=BundleStatus(
            is_valid=bundle.is_valid,
            error_count=bundle.error_count,
            warning_count=bundle.warning_count,
            bundle_hash=bundle.bundle_hash,
        ),
        counts=ResourceCounts(**resources.counts_by_type(patient.patient_key)),
        first_activity=iso(first),
        last_activity=iso(last),
        data_quality=DataQuality(
            audit_entries=sum(audit.values()), warnings=audit["warning"], errors=audit["error"]
        ),
    )


def listable_types(requested: Sequence[str]) -> list[str]:
    """The requested types, deduplicated; the Patient resource is never a list item."""
    if not requested:
        return list(NON_PATIENT_TYPES)
    return [t for t in dict.fromkeys(requested) if t != "Patient"]


def patient_resources(
    conn: sqlite3.Connection, key: str, types: Sequence[str], sort: str, order: str
) -> PatientResourcesResponse:
    reader = ResourceReader(conn)
    rows = reader.for_patient(key, types)
    issues = reader.issues(r.resource_id for r in rows)
    items = [_resource_item(row, issues.get(row.resource_id, [])) for row in rows]
    sort_resources(items, sort, order)
    return PatientResourcesResponse(patient_key=key, total=len(items), items=items)


def _resource_item(row: ResourceRow, row_issues: list[IssueRow]) -> PatientResourceItem:
    return PatientResourceItem(
        **resource_ref(row, row_issues).model_dump(),
        status=str(row.resource.get("status") or "unknown"),
        encounter_id=reference_id(row.resource.get("encounter")),
        summary_line=summary_line(row),
        interpretation=interpretation_of(row.resource)
        if row.resource_type == "Observation"
        else None,
        issues=[
            ResourceIssue(severity=i.severity, code=i.code, message=i.message)  # type: ignore[arg-type]
            for i in row_issues
        ],
    )


def sort_resources(items: list[PatientResourceItem], sort: str, order: str) -> None:
    """Date sort keeps undated records last in either order."""
    descending = order == "desc"
    if sort == "date":
        dated = sorted(
            (i for i in items if i.date), key=lambda i: (i.date or "", i.title), reverse=descending
        )
        undated = sorted((i for i in items if not i.date), key=lambda i: i.title)
        items[:] = [*dated, *undated]
    elif sort == "type":
        items.sort(key=lambda i: (i.resource_type, i.date or ""), reverse=descending)
    else:
        items.sort(key=lambda i: (i.title.lower(), i.date or ""), reverse=descending)


def resource_detail(
    conn: sqlite3.Connection, resource_type: str, resource_id: str, today: date
) -> ResourceDetail:
    reader = ResourceReader(conn)
    row = reader.get(resource_type, resource_id)
    patient = PatientReader(conn).get(row.patient_key) if row else None
    if row is None or patient is None:
        msg = f"No {resource_type} with id {resource_id}."
        raise ResourceNotFoundError(msg)
    issues = reader.issues([row.resource_id]).get(row.resource_id, [])
    text = row.text if row.resource_type != "Encounter" else None
    return ResourceDetail(
        resource=resource_ref(row, issues),
        patient=patient_ref(patient, today),
        text=text,
        sections=[Section(heading=h, body=b) for h, b in split_sections(text or "") if h],
        observations=lab_observations(reader, row),
        issues=[
            DetailIssue(severity=i.severity, code=i.code, message=i.message, path=i.path)  # type: ignore[arg-type]
            for i in issues
        ],
        fhir=row.resource,
    )


def lab_observations(reader: ResourceReader, row: ResourceRow) -> list[ObservationRow]:
    """Result rows of a lab DiagnosticReport, in report order."""
    if row.resource_type != "DiagnosticReport" or row.subtype != "LAB":
        return []
    ids = [i for i in (reference_id(r) for r in row.resource.get("result", [])) if i]
    found = reader.many(ids)
    rows = []
    for result_id in ids:
        obs = found.get(result_id)
        if obs is None:
            continue
        value, unit = observation_value(obs.resource)
        rows.append(
            ObservationRow(
                resource_id=obs.resource_id,
                name=str((obs.resource.get("code") or {}).get("text") or obs.title or ""),
                value=value,
                unit=unit,
                interpretation=interpretation_of(obs.resource),
                reference_range=reference_range(obs.resource),
            )
        )
    return rows
