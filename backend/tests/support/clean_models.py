"""Factories for clean ingestion models used by FHIR tests."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ehr_mip import ids
from ehr_mip.ingestion.cleaners.text import content_hash
from ehr_mip.ingestion.models import (
    AdministrativeGender,
    CleanDocument,
    CleanEncounter,
    CleanLabResult,
    CleanPatient,
    DocType,
    EncounterClass,
)

NY = ZoneInfo("America/New_York")
PATIENT_KEY = ids.patient_key("00012345")


def make_patient(**overrides: Any) -> CleanPatient:
    values: dict[str, Any] = {
        "patient_key": PATIENT_KEY,
        "mrn": "00012345",
        "secondary_mrns": [],
        "family_name": "Doe",
        "given_names": ["Jane", "A"],
        "birth_date": date(1968, 3, 14),
        "gender": AdministrativeGender.FEMALE,
        "source_record_ids": ["ehr_export.json:patients[0]"],
    }
    values.update(overrides)
    return CleanPatient(**values)


def make_encounter(source_id: str = "ENC-1", **overrides: Any) -> CleanEncounter:
    values: dict[str, Any] = {
        "encounter_key": ids.encounter_key(PATIENT_KEY, source_id),
        "patient_key": PATIENT_KEY,
        "source_encounter_id": source_id,
        "encounter_class": EncounterClass.INPATIENT,
        "period_start": datetime(2025, 2, 1, 8, 30, tzinfo=NY),
        "period_end": date(2025, 2, 4),
    }
    values.update(overrides)
    return CleanEncounter(**values)


def make_document(
    text: str = "HOSPITAL COURSE: Treated for pneumonia.\nPLAN: Amoxicillin.",
    doc_type: DocType = DocType.DISCHARGE_SUMMARY,
    encounter: CleanEncounter | None = None,
    **overrides: Any,
) -> CleanDocument:
    digest = content_hash(text)
    values: dict[str, Any] = {
        "document_key": ids.document_key(PATIENT_KEY, digest),
        "patient_key": PATIENT_KEY,
        "encounter_key": encounter.encounter_key if encounter else None,
        "doc_type": doc_type,
        "title": "Discharge Summary",
        "author": "Dr. A. Rivera",
        "document_date": date(2025, 2, 4),
        "text": text,
        "content_hash": digest,
        "source_record_id": "ehr_export.json:patients[0].encounters[0].documents[0]",
    }
    values.update(overrides)
    return CleanDocument(**values)


def make_lab(
    test_name: str = "Potassium",
    loinc: str | None = "2823-3",
    value: float | None = 5.9,
    *,
    report_id: str = "LAB-1",
    encounter: CleanEncounter | None = None,
    **overrides: Any,
) -> CleanLabResult:
    report = ids.report_key(PATIENT_KEY, report_id)
    values: dict[str, Any] = {
        "result_key": ids.result_key(report, loinc or test_name),
        "patient_key": PATIENT_KEY,
        "encounter_key": encounter.encounter_key if encounter else None,
        "report_key": report,
        "test_name": test_name,
        "loinc": loinc,
        "value": value,
        "value_raw": "" if value is None else f"{value:g}",
        "unit": "mmol/L",
        "ref_low": 3.5,
        "ref_high": 5.1,
        "flag": "H",
        "collected_at": datetime(2025, 2, 2, 6, 10, tzinfo=NY),
        "source_record_id": "lab_results.csv:row 1",
    }
    values.update(overrides)
    return CleanLabResult(**values)
