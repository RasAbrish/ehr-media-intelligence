"""Small FHIR bundles for summarization tests, built with the real Phase 2 builder."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

from tests.support.clean_models import (
    NY,
    make_document,
    make_encounter,
    make_lab,
    make_patient,
)

from ehr_mip import ids
from ehr_mip.fhir.bundle import build_bundle, bundle_hash
from ehr_mip.fhir.models import BuiltBundle
from ehr_mip.ingestion.models import CleanDocument, CleanLabResult, DocType

T0 = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)

DISCHARGE = (
    "HOSPITAL COURSE: Ms. Doe, a 56-year-old woman, was admitted with dyspnea. "
    "MRN 00012345, DOB 03/14/1968. BNP was 1250 pg/mL.\n"
    "ASSESSMENT: Acute on chronic systolic heart failure.\n"
    "PLAN: Furosemide 40 mg daily. Cardiology follow-up in 1 week."
)
ECHO = (
    "FINDINGS: Dilated left ventricle with global hypokinesis.\n"
    "IMPRESSION: Reduced ejection fraction of 30% consistent with systolic heart failure."
)


def labs(encounter: Any = None, **flags: Any) -> list[CleanLabResult]:
    return [
        make_lab("Potassium", "2823-3", 6.3, flag="HH", encounter=encounter),
        make_lab("Sodium", "2951-2", 131, ref_low=136, ref_high=145, flag="L", encounter=encounter),
        make_lab("Creatinine", "2160-0", 0.9, unit="mg/dL", ref_low=0.6, ref_high=1.2, flag="N",
                 encounter=encounter),
    ]  # fmt: skip


def heart_failure_bundle(
    documents: Sequence[CleanDocument] | None = None,
    lab_results: Sequence[CleanLabResult] | None = None,
    **patient: Any,
) -> BuiltBundle:
    encounter = make_encounter()
    docs = (
        list(documents)
        if documents is not None
        else [
            make_document(DISCHARGE, encounter=encounter),
            make_document(ECHO, DocType.IMAGING_REPORT, encounter, title="ECHOCARDIOGRAM",
                          document_date=date(2025, 2, 2)),
        ]
    )  # fmt: skip
    results = list(lab_results) if lab_results is not None else labs(encounter)
    return build_bundle(make_patient(**patient), [encounter], docs, results, timestamp=T0)


def trend_labs() -> list[CleanLabResult]:
    """Three rising potassium values on separate reports, the last one high."""
    values = [(4.9, "N", datetime(2025, 1, 5, 8, 0, tzinfo=NY)),
              (5.3, "H", datetime(2025, 1, 20, 8, 0, tzinfo=NY)),
              (5.7, "H", datetime(2025, 2, 2, 8, 0, tzinfo=NY))]  # fmt: skip
    return [
        make_lab("Potassium", "2823-3", v, flag=f, collected_at=when, report_id=f"LAB-{i}")
        for i, (v, f, when) in enumerate(values)
    ]


def as_other_patient(built: BuiltBundle, mrn: str) -> BuiltBundle:
    """The same clinical content filed under another patient, with every id re-derived."""
    new_key = ids.patient_key(mrn)
    text = built.model_dump_json()
    for row in built.rows:
        old = row.resource_id
        text = text.replace(
            old, new_key if old == built.patient_key else ids.make_key(f"{new_key}:{old}")
        )
    text = text.replace('"value":"00012345"', f'"value":"{mrn}"')
    moved = BuiltBundle.model_validate_json(text)
    return moved.model_copy(update={"bundle_hash": bundle_hash(moved.bundle)})
