"""DiagnosticReport mappers: imaging and pathology documents, and lab reports."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from ehr_mip.fhir import codes
from ehr_mip.fhir.mappers.common import (
    coding,
    concept,
    fhir_datetime,
    fhir_instant,
    ref,
    text_attachment,
)
from ehr_mip.ingestion.models import CleanDocument, CleanEncounter, CleanLabResult

# Header matched case-insensitively; the section ends at the next UPPER-CASE header line.
_CONCLUSION = re.compile(
    r"^(?i:IMPRESSION|DIAGNOSIS)[ \t]*:[ \t]*(?P<body>.+?)(?=^[A-Z][A-Z /&-]*:|\Z)",
    re.MULTILINE | re.DOTALL,
)
_ABNORMAL = {"L", "LL", "H", "HH"}


def extract_conclusion(text: str) -> str | None:
    """The IMPRESSION (imaging) or DIAGNOSIS (pathology) section, as one line."""
    match = _CONCLUSION.search(text)
    if match is None:
        return None
    return " ".join(match["body"].split()) or None


def map_imaging_report(doc: CleanDocument, encounter: CleanEncounter | None) -> dict[str, Any]:
    """Imaging (RAD) or pathology (PAT) document → DiagnosticReport with the text attached."""
    category, category_display = codes.REPORT_CATEGORY[doc.doc_type]
    loinc, display = codes.DOC_TYPE_LOINC[doc.doc_type]
    resource: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": doc.document_key,
        "status": "final",
        "category": [concept(codes.V2_0074, category, category_display)],
        "code": concept(codes.LOINC, loinc, display, text=doc.title),
        "subject": ref(doc.patient_key),
    }
    if encounter is not None:
        resource["encounter"] = ref(encounter.encounter_key)
    effective = fhir_datetime(doc.document_date)
    if effective:
        resource["effectiveDateTime"] = effective
    issued = fhir_instant(doc.document_date)
    if issued:
        resource["issued"] = issued
    if doc.author:
        resource["resultsInterpreter"] = [{"display": doc.author}]
    conclusion = extract_conclusion(doc.text)
    if conclusion:
        resource["conclusion"] = conclusion
    resource["presentedForm"] = [text_attachment(doc.text, doc.title, doc.document_date)]
    return resource


def lab_report_code(labs: Sequence[CleanLabResult]) -> tuple[tuple[str, str, str], str]:
    """Infer the report code from the set of tests: ((system, code, display), title).

    A panel code is used only when the report holds exactly that panel's tests.
    """
    members = {lab.loinc for lab in labs if lab.loinc}
    if len(labs) > 1 and len(members) == len(labs):
        for panel, code, display, title in codes.PANELS:
            if members == panel:
                if code is None or display is None:
                    return (codes.LOINC, *codes.LAB_REPORT_CODE), title
                return (codes.LOINC, code, display), title
    if len(labs) == 1 and labs[0].loinc:
        return (codes.LOINC, labs[0].loinc, labs[0].test_name), labs[0].test_name
    names = [lab.test_name for lab in labs]
    title = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return (codes.LOINC, *codes.LAB_REPORT_CODE), title


def lab_conclusion(labs: Sequence[CleanLabResult]) -> str:
    abnormal = [f"{lab.test_name} {lab.flag}" for lab in labs if lab.flag in _ABNORMAL]
    if not abnormal:
        return "All results within the reference range."
    return f"{len(abnormal)} abnormal: {', '.join(abnormal)}."


def map_lab_report(labs: Sequence[CleanLabResult]) -> dict[str, Any]:
    """One lab report (same ``report_key``) → DiagnosticReport referencing its Observations."""
    first = labs[0]
    report_coding, title = lab_report_code(labs)
    category, category_display = codes.LAB_CATEGORY
    resource: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": first.report_key,
        "status": "final",
        "category": [concept(codes.V2_0074, category, category_display)],
        "code": {"coding": [coding(*report_coding)], "text": title},
        "subject": ref(first.patient_key),
    }
    encounter_key = next((lab.encounter_key for lab in labs if lab.encounter_key), None)
    if encounter_key:
        resource["encounter"] = ref(encounter_key)
    collected = next((lab.collected_at for lab in labs if lab.collected_at), None)
    effective = fhir_datetime(collected)
    if effective:
        resource["effectiveDateTime"] = effective
    resource["result"] = [ref(lab.result_key) for lab in labs]
    resource["conclusion"] = lab_conclusion(labs)
    return resource
