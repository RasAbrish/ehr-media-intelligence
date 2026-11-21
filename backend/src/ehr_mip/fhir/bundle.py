"""One FHIR ``collection`` Bundle per patient, plus its index rows (docs/03 section 5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

import orjson

from ehr_mip.fhir import codes
from ehr_mip.fhir.ids import reference
from ehr_mip.fhir.mappers import (
    lab_report_code,
    map_document_reference,
    map_encounter,
    map_imaging_report,
    map_lab_report,
    map_observation,
    map_patient,
)
from ehr_mip.fhir.models import BuiltBundle, ResourceRow
from ehr_mip.ingestion.cleaners.dates import NY
from ehr_mip.ingestion.models import (
    CleanDocument,
    CleanEncounter,
    CleanLabResult,
    CleanPatient,
)


def bundle_hash(bundle: dict[str, Any]) -> str:
    """SHA-256 over the bundle without volatile fields (docs/05 section 2.1).

    Copies only the dicts it changes, so large attachment payloads are never duplicated.
    """
    stable = {k: v for k, v in bundle.items() if k != "timestamp"}
    entries = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        meta = resource.get("meta")
        if isinstance(meta, dict) and "lastUpdated" in meta:
            kept = {k: v for k, v in meta.items() if k != "lastUpdated"}
            resource = {k: v for k, v in resource.items() if k != "meta"}
            if kept:
                resource["meta"] = kept
            entries.append({**entry, "resource": resource})
        else:
            entries.append(entry)
    if "entry" in bundle:
        stable["entry"] = entries
    return hashlib.sha256(orjson.dumps(stable, option=orjson.OPT_SORT_KEYS)).hexdigest()


def _day(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(NY).date().isoformat()
    return value.isoformat()


def _sort_key(value: datetime | date | None) -> str:
    """Chronological sort key across dates and datetimes; missing dates sort last."""
    if value is None:
        return "9999"
    if isinstance(value, datetime):
        return value.astimezone(NY).isoformat()
    return value.isoformat()


def _format_number(value: float | None) -> str:
    return "" if value is None else f"{value:g}"


def lab_line(lab: CleanLabResult) -> str:
    """Readable result line, e.g. ``Potassium 5.9 mmol/L (H, ref 3.5 to 5.1)``.

    Uses the parsed value (keeping a ``<``/``>`` comparator), not the raw source text,
    so OCR slips and trailing flags never reach clinicians or search.
    """
    if lab.value is not None:
        comparator = next((c for c in ("<=", ">=", "<", ">") if lab.value_raw.startswith(c)), "")
        value = f"{comparator}{_format_number(lab.value)}"
    else:
        value = lab.value_raw
    parts = [lab.test_name, value]
    if lab.unit:
        parts.append(lab.unit)
    detail: list[str] = []
    if lab.flag and lab.flag != "N":
        detail.append(lab.flag)
    if lab.ref_low is not None and lab.ref_high is not None:
        detail.append(f"ref {_format_number(lab.ref_low)} to {_format_number(lab.ref_high)}")
    elif lab.ref_high is not None:
        detail.append(f"ref up to {_format_number(lab.ref_high)}")
    elif lab.ref_low is not None:
        detail.append(f"ref at least {_format_number(lab.ref_low)}")
    line = " ".join(p for p in parts if p)
    return f"{line} ({', '.join(detail)})" if detail else line


def build_bundle(
    patient: CleanPatient,
    encounters: Sequence[CleanEncounter],
    documents: Sequence[CleanDocument],
    labs: Sequence[CleanLabResult],
    *,
    timestamp: datetime,
) -> BuiltBundle:
    """Map one patient's clean records into a Bundle with deterministic ids and order."""
    key = patient.patient_key
    resources: list[dict[str, Any]] = []
    rows: list[ResourceRow] = []

    def add(resource: dict[str, Any], **row: Any) -> None:
        resources.append(resource)
        rows.append(
            ResourceRow(
                resource_id=resource["id"],
                patient_key=key,
                resource_type=resource["resourceType"],
                resource=resource,
                **row,
            )
        )

    add(map_patient(patient), resource_date=None, title=None, subtype=None, text_content=None)

    by_encounter = {e.encounter_key: e for e in encounters}
    for enc in sorted(encounters, key=lambda e: (_sort_key(e.period_start), e.encounter_key)):
        add(
            map_encounter(enc),
            resource_date=_day(enc.period_start),
            title=f"{enc.encounter_class.value.capitalize()} encounter",
            subtype=enc.encounter_class.value,
            text_content=None,
        )

    for doc in sorted(documents, key=lambda d: (_sort_key(d.document_date), d.document_key)):
        encounter = by_encounter.get(doc.encounter_key or "")
        category = codes.REPORT_CATEGORY.get(doc.doc_type)
        resource = (
            map_imaging_report(doc, encounter)
            if category
            else map_document_reference(doc, encounter)
        )
        add(
            resource,
            resource_date=_day(doc.document_date),
            title=doc.title,
            subtype=category[0] if category else doc.doc_type.value,
            text_content=doc.text,
        )

    reports: dict[str, list[CleanLabResult]] = {}
    for lab in labs:
        reports.setdefault(lab.report_key, []).append(lab)
    ordered = sorted(
        reports.values(), key=lambda group: (_sort_key(group[0].collected_at), group[0].report_key)
    )
    for group in ordered:
        report = map_lab_report(group)
        _, title = lab_report_code(group)
        add(
            report,
            resource_date=_day(group[0].collected_at),
            title=title,
            subtype="LAB",
            text_content="\n".join([report["conclusion"], *(lab_line(lab) for lab in group)]),
        )
        for lab in group:
            add(
                map_observation(lab),
                resource_date=_day(lab.collected_at),
                title=lab.test_name,
                subtype=None,
                text_content=lab_line(lab),
            )

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "id": key,
        "identifier": {"system": codes.BUNDLE_IDENTIFIER_SYSTEM, "value": key},
        "type": "collection",
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "entry": [{"fullUrl": reference(r["id"]), "resource": r} for r in resources],
    }
    return BuiltBundle(patient_key=key, bundle=bundle, bundle_hash=bundle_hash(bundle), rows=rows)
