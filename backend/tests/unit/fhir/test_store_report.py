"""BundleStore persistence (FR-2.6) and report files (FR-2.5)."""

from __future__ import annotations

import copy
import json
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from tests.support.clean_models import (
    PATIENT_KEY,
    make_document,
    make_encounter,
    make_lab,
    make_patient,
)

from ehr_mip.db.connection import connect
from ehr_mip.fhir.bundle import build_bundle
from ehr_mip.fhir.models import BuiltBundle, NormalizedBundle
from ehr_mip.fhir.report import _table, build_report, render_markdown, write_reports
from ehr_mip.fhir.store import BundleStore
from ehr_mip.fhir.validator import validate_bundle
from ehr_mip.ingestion.models import DocType

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 21)


def normalized(built: BuiltBundle) -> NormalizedBundle:
    validation = validate_bundle(built.bundle, patient_key=built.patient_key, today=TODAY)
    return NormalizedBundle(built=built, validation=validation)


def sample() -> NormalizedBundle:
    encounter = make_encounter()
    docs = [
        make_document(encounter=encounter),
        make_document(
            "IMPRESSION: Normal.", DocType.IMAGING_REPORT, encounter, title="CHEST X-RAY"
        ),
    ]
    built = build_bundle(
        make_patient(), [encounter], docs, [make_lab(encounter=encounter)], timestamp=NOW
    )
    return normalized(built)


def broken(result: NormalizedBundle) -> NormalizedBundle:
    bundle = copy.deepcopy(result.built.bundle)
    bundle["entry"][0]["resource"]["gender"] = "F"
    built = result.built.model_copy(update={"bundle": bundle})
    return normalized(built)


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "ehr.db"
    with closing(connect(db)) as conn, conn:
        # fhir tables reference patients, so the patient row must exist.
        conn.execute(
            "INSERT INTO patients (patient_key, mrn, gender, data_json) VALUES (?, ?, ?, ?)",
            (PATIENT_KEY, "00012345", "female", "{}"),
        )
    return db


def test_store_round_trip(tmp_path: Path) -> None:
    db = _db(tmp_path)
    result = sample()
    with closing(connect(db)) as conn:
        store = BundleStore(conn)
        store.save([result], created_at=NOW)
        assert store.load_bundle(PATIENT_KEY) == result.built.bundle
        assert store.bundle_hash(PATIENT_KEY) == result.built.bundle_hash
        assert store.patient_keys() == [PATIENT_KEY]
        imaging = next(r for r in result.built.rows if r.subtype == "RAD")
        assert store.load_resource("DiagnosticReport", imaging.resource_id) == imaging.resource
        assert store.load_issues(PATIENT_KEY) == result.validation.issues
        row = conn.execute(
            "SELECT is_valid, error_count, warning_count FROM fhir_bundles WHERE patient_key = ?",
            (PATIENT_KEY,),
        ).fetchone()
    assert tuple(row) == (1, 0, 0)


def test_store_save_replaces_previous_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with closing(connect(db)) as conn:
        store = BundleStore(conn)
        store.save([broken(sample())], created_at=NOW)
        assert [i.code for i in store.load_issues() if i.severity == "error"] == ["code.invalid"]
        store.save([sample()], created_at=NOW)
        assert not [i for i in store.load_issues() if i.severity == "error"]
    with closing(sqlite3.connect(db)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM fhir_resources").fetchone()[0]
    assert count == len(sample().built.rows)


def test_report_files_written(tmp_path: Path) -> None:
    results = [sample(), broken(sample())]
    report = build_report(results, generated_at=NOW)
    json_path, md_path = write_reports(report, tmp_path / "reports")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["bundles"] == 2
    assert data["valid_bundles"] == 1
    assert data["issues_by_code"]["code.invalid"] == {"severity": "error", "count": 1}
    assert data["resources_by_type"]["Observation"] == 2
    markdown = md_path.read_text(encoding="utf-8")
    assert markdown.startswith("# FHIR validation report")
    assert "| Valid bundles (no errors) | 1 |" in markdown
    assert "`code.invalid`" in markdown
    assert "Patient.gender 'F' is not an AdministrativeGender code" in markdown
    assert f"`{PATIENT_KEY}`" in markdown  # invalid bundles are listed by key


def test_report_contains_no_names_or_mrns() -> None:
    markdown = render_markdown(build_report([broken(sample())], generated_at=NOW))
    for phi in ("Doe", "Jane", "00012345", "1968-03-14"):
        assert phi not in markdown


def test_clean_report_says_so() -> None:
    markdown = render_markdown(build_report([sample()], generated_at=NOW))
    assert "None. Every bundle passed schema and reference checks." in markdown


# ---------------------------------------------------------------- review regressions


def test_partial_save_leaves_other_patients_alone(tmp_path: Path) -> None:
    db = _db(tmp_path)
    other_key = "00000000-0000-5000-8000-000000000001"
    with closing(connect(db)) as conn, conn:
        conn.execute(
            "INSERT INTO patients (patient_key, mrn, gender, data_json) VALUES (?, ?, ?, ?)",
            (other_key, "00055555", "male", "{}"),
        )
    other = sample().built.model_copy(update={"patient_key": other_key})
    other = other.model_copy(
        update={
            "rows": [
                r.model_copy(update={"patient_key": other_key, "resource_id": "o-" + r.resource_id})
                for r in other.rows
            ]
        }
    )
    with closing(connect(db)) as conn:
        store = BundleStore(conn)
        store.save([sample(), normalized(other)], created_at=NOW, full_refresh=True)
        store.save([sample()], created_at=NOW)  # one patient only
        assert sorted(store.patient_keys()) == sorted([PATIENT_KEY, other_key])
        rows = conn.execute(
            "SELECT COUNT(*) FROM fhir_resources WHERE patient_key = ?", (other_key,)
        ).fetchone()[0]
    assert rows == len(other.rows)


def test_full_refresh_with_nothing_is_refused(tmp_path: Path) -> None:
    with closing(connect(_db(tmp_path))) as conn, pytest.raises(ValueError, match="Refusing"):
        BundleStore(conn).save([], created_at=NOW, full_refresh=True)


def test_markdown_cells_survive_newlines() -> None:
    lines = _table(["A"], [["line one\nline two | more"]])
    assert lines[-1] == "| line one line two / more |"
