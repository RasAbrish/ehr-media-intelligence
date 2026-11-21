"""Bundle validation: schema plus business rules (docs/05-ALGORITHMS.md section 2.2).

Schema validation uses ``fhir.resources.R4B``. Version 8 of that package checks
structure and code format but not required value sets, so ``code.invalid``
checks the bindings this project relies on.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from fhir.resources.R4B.bundle import Bundle
from pydantic import ValidationError

from ehr_mip.fhir import codes
from ehr_mip.fhir.models import BundleValidation, Severity, ValidationIssue

_CLINICAL = ("Encounter", "DocumentReference", "DiagnosticReport", "Observation")


class _Issues:
    def __init__(self, patient_key: str) -> None:
        self.patient_key = patient_key
        self.items: list[ValidationIssue] = []

    def add(
        self,
        resource: dict[str, Any] | None,
        path: str | None,
        severity: Severity,
        code: str,
        message: str,
    ) -> None:
        self.items.append(
            ValidationIssue(
                patient_key=self.patient_key,
                resource_type=str(resource.get("resourceType", "Unknown"))
                if resource
                else "Bundle",
                resource_id=resource.get("id") if resource else None,
                path=path,
                severity=severity,
                code=code,
                message=message,
            )
        )


def _fhir_path(resource_type: str, loc: tuple[int | str, ...]) -> str:
    """Pydantic ``loc`` → ``Resource.field[0].sub``."""
    path = resource_type
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part.removesuffix('__ext').replace('class_fhir', 'class')}"
    return path


def _entries(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    entries = bundle.get("entry")
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _schema(bundle: dict[str, Any], issues: _Issues) -> None:
    try:
        Bundle.model_validate(bundle)
    except ValidationError as error:
        raw_entries = bundle.get("entry")
        entries: list[Any] = raw_entries if isinstance(raw_entries, list) else []
        for detail in error.errors():
            loc = tuple(detail["loc"])
            resource: dict[str, Any] | None = None
            path = _fhir_path("Bundle", loc)
            if (
                len(loc) >= 3  # noqa: PLR2004
                and loc[0] == "entry"
                and isinstance(loc[1], int)
                and loc[2] == "resource"
                and loc[1] < len(entries)
            ):
                entry = entries[loc[1]]
                candidate = entry.get("resource") if isinstance(entry, dict) else None
                if isinstance(candidate, dict):
                    resource = candidate
                    path = _fhir_path(str(candidate.get("resourceType", "Resource")), loc[3:])
            issues.add(resource, path, "error", "schema.invalid", f"{path}: {detail['msg']}")


def _references(node: Any, path: str) -> Iterator[tuple[str, str]]:
    """Every ``reference`` string inside a resource, with its FHIR path."""
    if isinstance(node, dict):
        ref = node.get("reference")
        if isinstance(ref, str):
            yield path, ref
        for key, value in node.items():
            if key != "reference":
                yield from _references(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _references(value, f"{path}[{index}]")


def _date_of(resource: dict[str, Any]) -> tuple[str, str] | None:
    """The clinical date of a resource and its path, if any."""
    kind = resource.get("resourceType")
    candidates: list[tuple[str, Any]] = []
    if kind == "Encounter":
        candidates = [("period.start", (resource.get("period") or {}).get("start"))]
    elif kind == "DocumentReference":
        content = resource.get("content") or [{}]
        attachment = (content[0] or {}).get("attachment") or {}
        candidates = [("date", resource.get("date")), ("content[0].attachment.creation",
                                                       attachment.get("creation"))]  # fmt: skip
    elif kind in {"DiagnosticReport", "Observation"}:
        candidates = [("effectiveDateTime", resource.get("effectiveDateTime"))]
    for path, value in candidates:
        if isinstance(value, str) and len(value) >= 10:  # noqa: PLR2004
            return path, value[:10]
    return None


def _codes(resource: dict[str, Any], issues: _Issues) -> None:
    kind = str(resource.get("resourceType"))
    gender = resource.get("gender")
    if kind == "Patient" and gender is not None and gender not in codes.ADMINISTRATIVE_GENDER:
        issues.add(
            resource,
            "Patient.gender",
            "error",
            "code.invalid",
            f"Patient.gender '{gender}' is not an AdministrativeGender code "
            "(male, female, other, unknown).",
        )
    allowed = codes.STATUS_VALUES.get(kind)
    status = resource.get("status")
    if allowed is not None and status is not None and status not in allowed:
        issues.add(
            resource, f"{kind}.status", "error", "code.invalid",
            f"{kind}.status '{status}' is not a valid status code.",
        )  # fmt: skip
    doc_status = resource.get("docStatus")
    if (
        kind == "DocumentReference"
        and doc_status is not None
        and (doc_status not in codes.DOC_STATUS_VALUES)
    ):
        issues.add(
            resource, "DocumentReference.docStatus", "error", "code.invalid",
            f"DocumentReference.docStatus '{doc_status}' is not a valid code.",
        )  # fmt: skip


def _patient_rules(patient: dict[str, Any], issues: _Issues) -> None:
    if not patient.get("identifier"):
        issues.add(
            patient, "Patient.identifier", "error", "patient.identifier_missing",
            "Patient has no identifier (MRN).",
        )  # fmt: skip
    if not patient.get("birthDate"):
        issues.add(
            patient, "Patient.birthDate", "info", "patient.birthdate_missing",
            "Patient has no birth date.",
        )  # fmt: skip
    tags = (patient.get("meta") or {}).get("tag") or []
    if any(t.get("code") == "identity-conflict" for t in tags if isinstance(t, dict)):
        issues.add(
            patient, "Patient.meta.tag", "warning", "patient.identity_conflict",
            "Records under this MRN belong to more than one person; review the identity.",
        )  # fmt: skip


@dataclass(frozen=True)
class _Context:
    by_url: dict[str, dict[str, Any]]
    patient_url: str | None
    birth: date | None
    today: date


def _reference_rules(resource: dict[str, Any], ctx: _Context, issues: _Issues) -> None:
    kind = str(resource.get("resourceType"))
    for path, ref in _references(resource, kind):
        if ref not in ctx.by_url:
            issues.add(
                resource, path, "error", "ref.unresolved",
                f"{path} points to {ref}, which is not in this bundle.",
            )  # fmt: skip
    if kind in _CLINICAL:
        subject = (resource.get("subject") or {}).get("reference")
        if ctx.patient_url is None or subject != ctx.patient_url:
            issues.add(
                resource, f"{kind}.subject", "error", "ref.subject_missing",
                f"{kind} does not reference the bundle's Patient as its subject.",
            )  # fmt: skip
    if kind == "DiagnosticReport":
        for index, result in enumerate(resource.get("result") or []):
            target = ctx.by_url.get((result or {}).get("reference", ""))
            if target is not None and target.get("resourceType") != "Observation":
                issues.add(
                    resource, f"DiagnosticReport.result[{index}]", "error",
                    "ref.result_not_observation",
                    f"DiagnosticReport.result[{index}] points to a "
                    f"{target.get('resourceType')}, not an Observation.",
                )  # fmt: skip


def _is_document_report(resource: dict[str, Any]) -> bool:
    """Imaging or pathology DiagnosticReport: a document, unlike a lab report."""
    categories = resource.get("category") or []
    return any(
        (c or {}).get("code") in {"RAD", "PAT"}
        for cat in categories
        for c in ((cat or {}).get("coding") or [])
    )


def _document_rules(resource: dict[str, Any], issues: _Issues) -> None:
    kind = resource.get("resourceType")
    if kind == "DiagnosticReport" and _is_document_report(resource):
        if not resource.get("encounter"):
            issues.add(
                resource, "DiagnosticReport.encounter", "info", "encounter.missing",
                "Document has no encounter context.",
            )  # fmt: skip
        return
    if kind != "DocumentReference":
        return
    attachments = [(c or {}).get("attachment") or {} for c in resource.get("content") or []]
    if not any(a.get("data") or a.get("url") for a in attachments):
        issues.add(
            resource, "DocumentReference.content", "error", "docref.content_empty",
            "DocumentReference has no attachment data.",
        )  # fmt: skip
    if not (resource.get("context") or {}).get("encounter"):
        issues.add(
            resource, "DocumentReference.context.encounter", "info", "encounter.missing",
            "Document has no encounter context.",
        )  # fmt: skip


def _date_rules(resource: dict[str, Any], ctx: _Context, issues: _Issues) -> None:
    dated = _date_of(resource)
    if dated is None:
        return
    kind = str(resource.get("resourceType"))
    path, text = dated
    try:
        when = date.fromisoformat(text)
    except ValueError:
        return
    if ctx.birth is not None and when < ctx.birth:
        issues.add(
            resource, f"{kind}.{path}", "warning", "date.before_birth",
            f"{kind}.{path} is before the patient's birth date.",
        )  # fmt: skip
    if when > ctx.today + timedelta(days=1):
        issues.add(
            resource, f"{kind}.{path}", "warning", "date.future",
            f"{kind}.{path} is more than a day in the future.",
        )  # fmt: skip


def validate_bundle(bundle: dict[str, Any], *, patient_key: str, today: date) -> BundleValidation:
    """Validate one bundle. ``is_valid`` is true when there are no errors."""
    issues = _Issues(patient_key)
    _schema(bundle, issues)
    if bundle.get("type") not in codes.BUNDLE_TYPES:
        issues.add(
            None, "Bundle.type", "error", "code.invalid",
            f"Bundle.type '{bundle.get('type')}' is not a valid bundle type.",
        )  # fmt: skip

    entries = _entries(bundle)
    by_url: dict[str, dict[str, Any]] = {}
    for entry in entries:
        resource = entry.get("resource")
        if isinstance(entry.get("fullUrl"), str) and isinstance(resource, dict):
            by_url[entry["fullUrl"]] = resource
    patients = [r for r in by_url.values() if r.get("resourceType") == "Patient"]
    patient_url = next((u for u, r in by_url.items() if r.get("resourceType") == "Patient"), None)
    birth: date | None = None
    if not patients:
        issues.add(None, "Bundle.entry", "error", "patient.missing", "Bundle has no Patient.")
    else:
        _patient_rules(patients[0], issues)
        for extra in patients[1:]:
            issues.add(
                extra, "Bundle.entry", "error", "patient.multiple",
                "Bundle holds more than one Patient; a bundle must describe one person.",
            )  # fmt: skip
        try:
            birth = date.fromisoformat(str(patients[0].get("birthDate")))
        except ValueError:
            birth = None

    ctx = _Context(by_url, patient_url, birth, today)
    for resource in by_url.values():
        _codes(resource, issues)
        _reference_rules(resource, ctx, issues)
        _document_rules(resource, issues)
        _date_rules(resource, ctx, issues)

    counts = {
        s: sum(1 for i in issues.items if i.severity == s) for s in ("error", "warning", "info")
    }
    return BundleValidation(
        patient_key=patient_key,
        is_valid=counts["error"] == 0,
        error_count=counts["error"],
        warning_count=counts["warning"],
        info_count=counts["info"],
        issues=issues.items,
    )
