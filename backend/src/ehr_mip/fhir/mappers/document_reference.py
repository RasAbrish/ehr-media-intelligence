"""CleanDocument (notes) → FHIR DocumentReference."""

from __future__ import annotations

from typing import Any

from ehr_mip.fhir import codes
from ehr_mip.fhir.mappers.common import concept, fhir_instant, period, ref, text_attachment
from ehr_mip.ingestion.models import CleanDocument, CleanEncounter


def map_document_reference(doc: CleanDocument, encounter: CleanEncounter | None) -> dict[str, Any]:
    loinc, display = codes.DOC_TYPE_LOINC[doc.doc_type]
    resource: dict[str, Any] = {
        "resourceType": "DocumentReference",
        "id": doc.document_key,
        "status": "current",
        "docStatus": "final",
        "type": concept(codes.LOINC, loinc, display),
        "category": [concept(codes.DOCREF_CATEGORY, "clinical-note", "Clinical Note")],
        "subject": ref(doc.patient_key),
    }
    instant = fhir_instant(doc.document_date)
    if instant:
        resource["date"] = instant
    if doc.author:
        resource["author"] = [{"display": doc.author}]
    resource["description"] = doc.title
    resource["content"] = [{"attachment": text_attachment(doc.text, doc.title, doc.document_date)}]
    if encounter is not None:
        context: dict[str, Any] = {"encounter": [ref(encounter.encounter_key)]}
        span = period(encounter.period_start, encounter.period_end)
        if span:
            context["period"] = span
        resource["context"] = context
    return resource
