"""Bundle building, hashing and validation (FR-2.3, FR-2.4, FR-2.5, FR-2.7)."""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fhir.resources.R4B.bundle import Bundle
from tests.support.clean_models import (
    PATIENT_KEY,
    make_document,
    make_encounter,
    make_lab,
    make_patient,
)

from ehr_mip.fhir.bundle import build_bundle, bundle_hash, lab_line
from ehr_mip.fhir.models import BuiltBundle, BundleValidation
from ehr_mip.fhir.validator import validate_bundle
from ehr_mip.ingestion.models import DocType

TODAY = date(2026, 11, 21)
T1 = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 22, 18, 30, tzinfo=UTC)
IMAGING = "FINDINGS: Consolidation.\nIMPRESSION: Right lower lobe pneumonia."


def sample(timestamp: datetime = T1, **patient: Any) -> BuiltBundle:
    encounter = make_encounter()
    docs = [
        make_document(encounter=encounter),
        make_document(IMAGING, DocType.IMAGING_REPORT, encounter, title="CHEST X-RAY"),
        make_document("SUBJECTIVE: Doing well.", DocType.PROGRESS_NOTE, None, title="Visit"),
    ]
    labs = [
        make_lab(encounter=encounter),
        make_lab("Sodium", "2951-2", 140, ref_low=136, ref_high=145, flag="N", encounter=encounter),
    ]
    return build_bundle(make_patient(**patient), [encounter], docs, labs, timestamp=timestamp)


def check(bundle: dict[str, Any]) -> BundleValidation:
    return validate_bundle(bundle, patient_key=PATIENT_KEY, today=TODAY)


def entries_of(bundle: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == kind]


def test_bundle_validates() -> None:
    built = sample()
    Bundle.model_validate(built.bundle)
    result = check(built.bundle)
    assert result.is_valid
    assert result.error_count == 0
    assert result.warning_count == 0
    # The progress note has no encounter: info only.
    assert [i.code for i in result.issues] == ["encounter.missing"]
    kinds = [e["resource"]["resourceType"] for e in built.bundle["entry"]]
    assert kinds == [
        "Patient",
        "Encounter",
        "DocumentReference",
        "DiagnosticReport",
        "DocumentReference",
        "DiagnosticReport",
        "Observation",
        "Observation",
    ]
    assert built.bundle["type"] == "collection"
    assert built.bundle["identifier"] == {"system": "urn:ehr-mip:bundle", "value": PATIENT_KEY}


def test_reference_integrity() -> None:
    bundle = sample().bundle
    full_urls = {e["fullUrl"] for e in bundle["entry"]}
    assert all(e["fullUrl"] == f"urn:uuid:{e['resource']['id']}" for e in bundle["entry"])
    patient_url = f"urn:uuid:{PATIENT_KEY}"
    for resource in (e["resource"] for e in bundle["entry"]):
        if resource["resourceType"] != "Patient":
            assert resource["subject"]["reference"] == patient_url
    by_url = {e["fullUrl"]: e["resource"] for e in bundle["entry"]}
    lab_report = next(
        r
        for r in entries_of(bundle, "DiagnosticReport")
        if r["category"][0]["coding"][0]["code"] == "LAB"
    )
    assert [by_url[r["reference"]]["resourceType"] for r in lab_report["result"]] == [
        "Observation",
        "Observation",
    ]
    references = [ref for _, ref in _all_refs(bundle)]
    assert references
    assert set(references) <= full_urls


def _all_refs(node: Any, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        if isinstance(node.get("reference"), str):
            found.append((path, node["reference"]))
        for k, v in node.items():
            found += _all_refs(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += _all_refs(v, f"{path}[{i}]")
    return found


def test_deterministic_ids_and_hash() -> None:
    first, second = sample(T1), sample(T2)
    assert first.bundle["timestamp"] != second.bundle["timestamp"]
    assert first.bundle_hash == second.bundle_hash  # the timestamp is excluded
    assert [e["fullUrl"] for e in first.bundle["entry"]] == [
        e["fullUrl"] for e in second.bundle["entry"]
    ]
    changed = sample(T1, birth_date=date(1968, 3, 15))
    assert changed.bundle_hash != first.bundle_hash
    meta = copy.deepcopy(first.bundle)
    meta["entry"][0]["resource"]["meta"] = {"lastUpdated": "2026-01-01T00:00:00Z"}
    assert bundle_hash(meta) == first.bundle_hash


def test_resource_rows_for_index() -> None:
    rows = {r.resource_type + ":" + (r.subtype or ""): r for r in sample().rows}
    assert rows["DocumentReference:discharge_summary"].text_content.startswith("HOSPITAL COURSE")
    imaging = rows["DiagnosticReport:RAD"]
    assert imaging.title == "CHEST X-RAY"
    assert imaging.resource_date == "2025-02-04"
    lab = rows["DiagnosticReport:LAB"]
    assert lab.title == "Potassium and Sodium"
    assert lab.text_content == (
        "1 abnormal: Potassium H.\n"
        "Potassium 5.9 mmol/L (H, ref 3.5 to 5.1)\n"
        "Sodium 140 mmol/L (ref 136 to 145)"
    )
    assert lab.resource_date == "2025-02-02"
    assert rows["Patient:"].text_content is None
    assert all(r.patient_key == PATIENT_KEY for r in rows.values())


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"value_raw": "<0.01", "value": 0.01, "unit": "ng/mL", "ref_low": None, "ref_high": 0.04,
          "flag": "N", "test_name": "Troponin I"}, "Troponin I <0.01 ng/mL (ref up to 0.04)"),
        ({"ref_low": 40, "ref_high": None, "flag": "L", "test_name": "HDL", "value": 35,
          "value_raw": "35", "unit": "mg/dL"}, "HDL 35 mg/dL (L, ref at least 40)"),
    ],
)  # fmt: skip
def test_lab_line(overrides: dict[str, Any], expected: str) -> None:
    assert lab_line(make_lab(**overrides)) == expected


# ---------------------------------------------------------------- validation rules


def _resource(bundle: dict[str, Any], kind: str, index: int = 0) -> dict[str, Any]:
    return entries_of(bundle, kind)[index]


def test_validation_report_captures_errors() -> None:
    bundle = copy.deepcopy(sample().bundle)
    _resource(bundle, "Patient")["gender"] = "F"
    del _resource(bundle, "Observation")["status"]
    result = check(bundle)
    assert not result.is_valid
    found = {(i.code, i.resource_type, i.path) for i in result.issues if i.severity == "error"}
    assert ("code.invalid", "Patient", "Patient.gender") in found
    assert ("schema.invalid", "Observation", "Observation.status") in found
    messages = " ".join(i.message for i in result.issues)
    assert "Patient.gender 'F' is not an AdministrativeGender code" in messages
    assert "Observation.status" in messages
    observation_issue = next(i for i in result.issues if i.path == "Observation.status")
    assert observation_issue.resource_id == _resource(bundle, "Observation")["id"]
    assert result.error_count == 2


def test_unresolved_reference_and_wrong_result_target() -> None:
    bundle = copy.deepcopy(sample().bundle)
    lab_report = next(
        r
        for r in entries_of(bundle, "DiagnosticReport")
        if r["category"][0]["coding"][0]["code"] == "LAB"
    )
    lab_report["result"][0] = {"reference": "urn:uuid:not-here"}
    lab_report["result"][1] = {"reference": f"urn:uuid:{_resource(bundle, 'Encounter')['id']}"}
    codes_found = {i.code for i in check(bundle).issues}
    assert {"ref.unresolved", "ref.result_not_observation"} <= codes_found


def test_subject_missing_and_empty_content() -> None:
    bundle = copy.deepcopy(sample().bundle)
    del _resource(bundle, "Encounter")["subject"]
    _resource(bundle, "DocumentReference")["content"][0]["attachment"].pop("data")
    codes_found = {i.code for i in check(bundle).issues if i.severity == "error"}
    assert {"ref.subject_missing", "docref.content_empty"} <= codes_found


def test_patient_rules() -> None:
    built = sample(identity_conflict=True, birth_date=None)
    bundle = copy.deepcopy(built.bundle)
    del _resource(bundle, "Patient")["identifier"]
    found = {(i.code, i.severity) for i in check(bundle).issues}
    assert ("patient.identifier_missing", "error") in found
    assert ("patient.birthdate_missing", "info") in found
    assert ("patient.identity_conflict", "warning") in found


def test_date_rules() -> None:
    bundle = copy.deepcopy(sample(birth_date=date(2025, 3, 1)).bundle)
    _resource(bundle, "Observation")["effectiveDateTime"] = "2027-01-01T00:00:00-05:00"
    found = {(i.code, i.path) for i in check(bundle).issues if i.severity == "warning"}
    assert ("date.before_birth", "Encounter.period.start") in found
    assert ("date.future", "Observation.effectiveDateTime") in found


def test_missing_patient_and_bad_bundle_type() -> None:
    bundle = copy.deepcopy(sample().bundle)
    bundle["entry"] = [e for e in bundle["entry"] if e["resource"]["resourceType"] != "Patient"]
    bundle["type"] = "pile"
    codes_found = {i.code for i in check(bundle).issues}
    assert {"patient.missing", "code.invalid", "ref.subject_missing"} <= codes_found


# ---------------------------------------------------------------- review regressions


@pytest.mark.parametrize(
    ("raw", "value", "expected"),
    [
        ("5.9 H", 5.9, "Potassium 5.9 mmol/L (H, ref 3.5 to 5.1)"),
        ("5.l", 5.1, "Potassium 5.1 mmol/L (H, ref 3.5 to 5.1)"),
        ("<0.01", 0.01, "Potassium <0.01 mmol/L (H, ref 3.5 to 5.1)"),
    ],
)
def test_lab_line_uses_parsed_value(raw: str, value: float, expected: str) -> None:
    assert lab_line(make_lab(value=value, value_raw=raw)) == expected


def test_imaging_report_without_encounter_is_reported() -> None:
    doc = make_document(IMAGING, DocType.IMAGING_REPORT, None, title="CHEST X-RAY")
    built = build_bundle(make_patient(), [], [doc], [], timestamp=T1)
    issues = [(i.code, i.resource_type, i.path) for i in check(built.bundle).issues]
    assert issues == [("encounter.missing", "DiagnosticReport", "DiagnosticReport.encounter")]


def test_second_patient_in_bundle_is_an_error() -> None:
    bundle = copy.deepcopy(sample().bundle)
    other = copy.deepcopy(bundle["entry"][0])
    other["resource"]["id"] = "other-patient"
    other["fullUrl"] = "urn:uuid:other-patient"
    bundle["entry"].append(other)
    result = check(bundle)
    assert [i.code for i in result.issues if i.severity == "error"] == ["patient.multiple"]
    assert not result.is_valid


def test_hash_does_not_copy_or_mutate_input() -> None:
    built = sample()
    before = copy.deepcopy(built.bundle)
    bundle_hash(built.bundle)
    assert built.bundle == before
