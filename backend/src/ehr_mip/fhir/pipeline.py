"""Task 2 pipeline: clean records from SQLite → one validated Bundle per patient."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

import structlog

from ehr_mip.fhir.bundle import build_bundle
from ehr_mip.fhir.models import NormalizedBundle
from ehr_mip.fhir.validator import validate_bundle
from ehr_mip.ingestion.models import CleanDocument, CleanEncounter, CleanLabResult
from ehr_mip.ingestion.repository import IngestionRepository

log = structlog.get_logger(__name__)


def run_normalization(
    conn: sqlite3.Connection, *, today: date, timestamp: datetime
) -> list[NormalizedBundle]:
    """Build and validate a bundle for every ingested patient (ordered by MRN)."""
    repo = IngestionRepository(conn)
    encounters: dict[str, list[CleanEncounter]] = {}
    documents: dict[str, list[CleanDocument]] = {}
    labs: dict[str, list[CleanLabResult]] = {}
    for enc in repo.load_encounters():
        encounters.setdefault(enc.patient_key, []).append(enc)
    for doc in repo.load_documents():
        documents.setdefault(doc.patient_key, []).append(doc)
    for lab in repo.load_lab_results():
        labs.setdefault(lab.patient_key, []).append(lab)

    results: list[NormalizedBundle] = []
    for patient in repo.load_patients():
        key = patient.patient_key
        built = build_bundle(
            patient,
            encounters.get(key, []),
            documents.get(key, []),
            labs.get(key, []),
            timestamp=timestamp,
        )
        validation = validate_bundle(built.bundle, patient_key=key, today=today)
        results.append(NormalizedBundle(built=built, validation=validation))
    log.info(
        "normalize_completed",
        bundles=len(results),
        valid=sum(r.validation.is_valid for r in results),
        errors=sum(r.validation.error_count for r in results),
        warnings=sum(r.validation.warning_count for r in results),
    )
    return results
