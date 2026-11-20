"""Deterministic UUIDv5 keys (docs/03-DATA-MODEL.md section 3.2, ADR-004).

Lives in the shared bottom layer so ingestion and fhir can both use it.
The same source facts always give the same key, so re-runs are idempotent
and FHIR ids, cache entries and vector ids stay stable.
"""

from __future__ import annotations

import uuid
from datetime import date

# Fixed forever: changing it would change every key in every store.
NAMESPACE = uuid.UUID("5f0c2a8e-3b1d-5e7a-9c46-1d2e3f405162")


def make_key(name: str) -> str:
    """UUIDv5 of ``name`` in the project namespace, as a string."""
    return str(uuid.uuid5(NAMESPACE, name))


def patient_key(
    mrn: str,
    split_dob: date | None = None,
    *,
    split: bool = False,
    qualifier: str | None = None,
) -> str:
    """``patient:{mrn}``, or ``patient:{mrn}:{dob}`` for the minority side of an MRN conflict.

    ``qualifier`` (a normalized name) is appended only when two split patients on one MRN
    would otherwise share a DOB, so every person keeps a distinct key.
    """
    if not split:
        return make_key(f"patient:{mrn}")
    dob_part = split_dob.isoformat() if split_dob is not None else "unknown"
    suffix = f":{qualifier}" if qualifier else ""
    return make_key(f"patient:{mrn}:{dob_part}{suffix}")


def encounter_key(patient: str, source_encounter_id: str) -> str:
    return make_key(f"encounter:{patient}:{source_encounter_id}")


def document_key(patient: str, content_hash: str) -> str:
    return make_key(f"document:{patient}:{content_hash}")


def report_key(patient: str, source_report_id: str) -> str:
    """``source_report_id`` is the lab report id, or the collection time when it is missing."""
    return make_key(f"report:{patient}:{source_report_id}")


def result_key(report: str, code: str) -> str:
    """``code`` is the LOINC code, or the test name when LOINC is missing."""
    return make_key(f"result:{report}:{code}")
