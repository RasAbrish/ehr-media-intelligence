"""Task 1 end to end on the committed synthetic data (FR-1.1 to FR-1.10 acceptance)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from ehr_mip.config import PROJECT_ROOT
from ehr_mip.ingestion.models import CleanPatient, IngestionResult
from ehr_mip.ingestion.pipeline import run_ingestion

pytestmark = pytest.mark.integration

RAW = PROJECT_ROOT / "data" / "raw"
TODAY = date(2026, 11, 20)


@pytest.fixture(scope="module")
def truth() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RAW / "_ground_truth.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def result() -> IngestionResult:
    return run_ingestion(RAW, today=TODAY)


def _audit_locations(result: IngestionResult, rule: str) -> set[tuple[str, str | None]]:
    return {(a.record_id, a.field) for a in result.audit if a.rule == rule}


def _patient_for(result: IngestionResult, person: dict[str, Any]) -> CleanPatient:
    dob = date.fromisoformat(person["dob"])
    matches = [
        p
        for p in result.patients
        if person["mrns"][0] in {p.mrn, *p.secondary_mrns} and p.birth_date == dob
    ]
    assert len(matches) == 1, person
    return matches[0]


def test_ingestion_matches_ground_truth(result: IngestionResult, truth: dict[str, Any]) -> None:
    counts, stats = truth["counts"], result.stats
    assert stats.records_read == {
        "csv": counts["csv_rows"],
        "json": counts["json_patient_entries"] + counts["encounters"] + counts["json_documents"],
        "txt": counts["txt_notes"] - 1,  # the empty scan is quarantined while reading
    }
    assert stats.patients == counts["expected_patients_after_identity"] == 60
    assert stats.identities_merged == len(truth["mrn_merges"]) == 3
    assert stats.identity_conflicts == len(truth["mrn_conflicts"]) == 2
    assert stats.duplicates_exact == len(truth["exact_duplicates"]) == 12
    assert stats.duplicates_near == len(truth["near_duplicates"]) == 7
    assert stats.duplicates_lab == 0
    assert stats.quarantined == counts["quarantined"] == 3
    assert stats.encounters == counts["encounters"]
    assert stats.documents == counts["unique_documents"]
    assert stats.lab_results == counts["csv_rows"] - 1  # one unusable row quarantined
    assert stats.lab_reports == counts["lab_reports"]


def test_every_person_resolves_with_true_demographics(
    result: IngestionResult, truth: dict[str, Any]
) -> None:
    blanked = {m["locator"] for m in truth["missing_fields"] if m["field"] == "gender"}
    for person in truth["persons"].values():
        patient = _patient_for(result, person)
        # Case-insensitive: smart title-case intentionally writes "McLaughlin" for "Mclaughlin".
        assert (patient.family_name or "").lower() == person["family"].lower()
        assert patient.given_names[0].lower() == person["given"].lower()
        if patient.gender.value != person["gender"]:
            # Only acceptable when the source gender was blanked on every registration.
            assert patient.gender.value == "unknown"
            assert set(patient.source_record_ids) & blanked, person


def test_merged_identities(result: IngestionResult, truth: dict[str, Any]) -> None:
    for merge in truth["mrn_merges"]:
        patient = _patient_for(result, truth["persons"][merge["person_id"]])
        assert {patient.mrn, *patient.secondary_mrns} == set(merge["mrns"])
        assert not patient.identity_conflict


def test_conflicting_mrns_split_and_flagged(result: IngestionResult, truth: dict[str, Any]) -> None:
    for conflict in truth["mrn_conflicts"]:
        sharing = [p for p in result.patients if p.mrn == conflict["mrn"]]
        assert len(sharing) == 2
        assert all(p.identity_conflict for p in sharing)
        assert {p.birth_date.isoformat() for p in sharing if p.birth_date} == set(conflict["dobs"])
    flagged = [p for p in result.patients if p.identity_conflict]
    assert len(flagged) == 4


def test_duplicates_removed_keep_the_json_original(
    result: IngestionResult, truth: dict[str, Any]
) -> None:
    for kind in ("exact", "near"):
        dropped = {a.record_id for a in result.audit if a.rule == f"dedupe.{kind}"}
        expected = {pair.split("::")[1] for pair in truth[f"{kind}_duplicates"]}
        assert dropped == expected, kind
    kept_sources = {d.source_record_id for d in result.documents}
    assert not kept_sources & {p.split("::")[1] for p in truth["exact_duplicates"]}


def test_quarantine_matches(result: IngestionResult, truth: dict[str, Any]) -> None:
    got = sorted((q.source_locator, q.reason) for q in result.quarantine)
    assert got == sorted((q["locator"], q["reason"]) for q in truth["quarantine"])


def test_date_issues_are_audited_where_injected(
    result: IngestionResult, truth: dict[str, Any]
) -> None:
    invalid = {(i["locator"], i["field"]) for i in truth["invalid_dates"]}
    assert _audit_locations(result, "date.parse.invalid") == invalid
    ambiguous = {(i["locator"], i["field"]) for i in truth["ambiguous_dates"]}
    assert _audit_locations(result, "date.parse.us_ambiguous") == ambiguous


def test_two_digit_year_dobs_resolve_to_true_dates(
    result: IngestionResult, truth: dict[str, Any]
) -> None:
    changed = {
        (a.before, a.after) for a in result.audit if a.field == "dob" and a.after is not None
    }
    for item in truth["two_digit_year_dobs"]:
        assert (item["value"], item["true"]) in changed


def test_lab_flag_issues_recomputed(result: IngestionResult, truth: dict[str, Any]) -> None:
    expected = {(i["locator"], "flag") for i in truth["lab_flag_issues"]}
    assert _audit_locations(result, "lab.flag_recomputed") == expected


def test_missing_fields_are_audited(result: IngestionResult, truth: dict[str, Any]) -> None:
    audited = {(a.record_id, a.field) for a in result.audit}
    for item in truth["missing_fields"]:
        assert (item["locator"], item["field"]) in audited, item


def test_adversarial_note_is_kept_verbatim(result: IngestionResult, truth: dict[str, Any]) -> None:
    adversarial = truth["adversarial"]
    doc = next(d for d in result.documents if d.source_record_id == adversarial["locator"])
    assert adversarial["phrase"] in doc.text


def test_every_record_is_accounted_for(result: IngestionResult) -> None:
    patient_keys = {p.patient_key for p in result.patients}
    assert {e.patient_key for e in result.encounters} <= patient_keys
    assert {d.patient_key for d in result.documents} <= patient_keys
    assert {lab.patient_key for lab in result.lab_results} <= patient_keys
    assert {a.patient_key for a in result.audit if a.patient_key} <= patient_keys
    encounter_keys = {e.encounter_key for e in result.encounters}
    assert {d.encounter_key for d in result.documents if d.encounter_key} <= encounter_keys


def test_rerun_is_identical(result: IngestionResult) -> None:
    assert run_ingestion(RAW, today=TODAY) == result
