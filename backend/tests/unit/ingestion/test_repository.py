"""SQLite persistence for Task 1 (FR-1.8, FR-1.9 storage side)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from tests.support.raw_folder import RawFolder, document, encounter, lab_row, note_text, patient

from ehr_mip.db.connection import connect
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.errors import EmptyIngestionError
from ehr_mip.ingestion.repository import IngestionRepository


def _save(db: Path, raw: RawFolder) -> str:
    result = raw.run()
    with closing(connect(db)) as conn:
        runs = PipelineRunRepository(conn)
        run_id = runs.start("ingest")
        IngestionRepository(conn).save(run_id, result)
        runs.finish(run_id, result.stats.model_dump())
    return run_id


def _counts(db: Path) -> dict[str, int]:
    with closing(sqlite3.connect(db)) as conn:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
            for t in ("patients", "encounters", "documents", "lab_results")
        }


def _sample(raw: RawFolder) -> RawFolder:
    raw.patients = [
        patient(
            mrn="MRN-12345",
            dob="03/14/1968",
            encounters=[encounter(documents=[document(doc_date="Feb 4 2025")])],
        )
    ]
    raw.lab_rows = [lab_row(value="5.9", flag="")]
    raw.notes = {"scan.txt": note_text("FINDINGS: Normal heart size.", title="CHEST X-RAY")}
    return raw


def test_store_round_trip(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    run_id = _save(db, _sample(raw))
    result = raw.run()
    with closing(connect(db)) as conn:
        repo = IngestionRepository(conn)
        assert repo.load_patients() == result.patients
        assert repo.load_encounters() == sorted(result.encounters, key=lambda e: e.encounter_key)
        assert repo.load_documents() == sorted(result.documents, key=lambda d: d.document_key)
        assert repo.load_lab_results() == sorted(result.lab_results, key=lambda r: r.result_key)
        assert repo.load_audit(run_id) == result.audit
        assert repo.load_quarantine(run_id) == result.quarantine
        latest = PipelineRunRepository(conn).latest("ingest")
        assert latest is not None
        assert latest["run_id"] == run_id


def test_rerun_is_idempotent(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    _save(db, _sample(raw))
    first = _counts(db)
    _save(db, raw)
    assert (
        _counts(db) == first == {"patients": 1, "encounters": 1, "documents": 2, "lab_results": 1}
    )


def test_rows_dropped_from_source_are_removed(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    _save(db, _sample(raw))
    raw.notes = {}
    (raw.root / "notes" / "scan.txt").unlink()
    _save(db, raw)
    assert _counts(db)["documents"] == 1


def test_dates_keep_their_precision(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    _save(db, _sample(raw))
    with closing(connect(db)) as conn:
        repo = IngestionRepository(conn)
        encounter_row = repo.load_encounters()[0]
        doc = next(d for d in repo.load_documents() if d.source_record_id.startswith("ehr"))
    assert type(encounter_row.period_end).__name__ == "date"
    assert type(encounter_row.period_start).__name__ == "datetime"
    assert type(doc.document_date).__name__ == "date"


def test_schema_has_foreign_keys_on(tmp_path: Path) -> None:
    with closing(connect(tmp_path / "x.db")) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"patients", "audit_log", "quarantine", "fhir_bundles", "summary_cache"} <= tables


# ---------------------------------------------------------------- review regressions


def test_empty_result_never_wipes_the_store(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    _save(db, _sample(raw))
    empty = RawFolder(tmp_path / "empty").run()
    with closing(connect(db)) as conn, pytest.raises(EmptyIngestionError):
        IngestionRepository(conn).save("run-x", empty)
    assert _counts(db)["patients"] == 1


def test_document_moving_to_a_new_encounter_saves(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    raw.patients = [patient(encounters=[encounter("ENC-1", [document()])])]
    _save(db, raw)
    # Same text (same document key), now filed under a different encounter id.
    raw.patients = [patient(encounters=[encounter("ENC-2", [document()])])]
    _save(db, raw)
    with closing(connect(db)) as conn:
        repo = IngestionRepository(conn)
        (enc,) = repo.load_encounters()
        (doc,) = repo.load_documents()
    assert enc.source_encounter_id == "ENC-2"
    assert doc.encounter_key == enc.encounter_key


def test_only_the_latest_run_keeps_audit_rows(tmp_path: Path, raw: RawFolder) -> None:
    db = tmp_path / "ehr.db"
    _save(db, _sample(raw))
    latest = _save(db, raw)
    with closing(sqlite3.connect(db)) as conn:
        runs = {r[0] for r in conn.execute("SELECT DISTINCT run_id FROM audit_log")}
    assert runs == {latest}
