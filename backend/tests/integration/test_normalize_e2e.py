"""Task 2 end to end on the committed synthetic data (FR-2.1 to FR-2.7 acceptance)."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fhir.resources.R4B.bundle import Bundle
from typer.testing import CliRunner

from ehr_mip.cli import app
from ehr_mip.config import PROJECT_ROOT, get_settings
from ehr_mip.db.connection import connect
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.fhir.models import NormalizedBundle
from ehr_mip.fhir.pipeline import run_normalization
from ehr_mip.ingestion.pipeline import run_ingestion
from ehr_mip.ingestion.repository import IngestionRepository

pytestmark = pytest.mark.integration

RAW = PROJECT_ROOT / "data" / "raw"
TODAY = date(2026, 11, 21)
T1 = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 21, 17, 45, tzinfo=UTC)


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("normalize") / "ehr.db"
    result = run_ingestion(RAW, today=TODAY)
    with closing(connect(path)) as conn:
        run_id = PipelineRunRepository(conn).start("ingest")
        IngestionRepository(conn).save(run_id, result)
    return path


@pytest.fixture(scope="module")
def results(db: Path) -> list[NormalizedBundle]:
    with closing(connect(db)) as conn:
        return run_normalization(conn, today=TODAY, timestamp=T1)


@pytest.fixture(scope="module")
def truth() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RAW / "_ground_truth.json").read_text(encoding="utf-8"))
    return data


def test_every_bundle_is_valid(results: list[NormalizedBundle]) -> None:
    assert len(results) == 60
    errors = [i for r in results for i in r.validation.issues if i.severity == "error"]
    assert errors == []
    assert all(r.validation.is_valid for r in results)
    for result in results:
        Bundle.model_validate(result.built.bundle)


def test_reference_integrity(results: list[NormalizedBundle]) -> None:
    checked = 0
    clinical = 0
    for result in results:
        bundle = result.built.bundle
        by_url = {e["fullUrl"]: e["resource"] for e in bundle["entry"]}
        patient_url = next(u for u, r in by_url.items() if r["resourceType"] == "Patient")
        for resource in by_url.values():
            for ref in _refs(resource):
                assert ref in by_url, (resource["resourceType"], ref)
                checked += 1
            if resource["resourceType"] != "Patient":
                clinical += 1
                assert resource["subject"]["reference"] == patient_url
            if resource["resourceType"] == "DiagnosticReport":
                for item in resource.get("result", []):
                    assert by_url[item["reference"]]["resourceType"] == "Observation"
    assert checked >= clinical > 0  # every clinical resource at least references its subject


def _refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        own = [node["reference"]] if isinstance(node.get("reference"), str) else []
        return own + [r for k, v in node.items() if k != "reference" for r in _refs(v)]
    if isinstance(node, list):
        return [r for v in node for r in _refs(v)]
    return []


def test_resource_counts_match_ingestion(
    results: list[NormalizedBundle], truth: dict[str, Any]
) -> None:
    counts = Counter(row.resource_type for r in results for row in r.built.rows)
    documents = truth["counts"]["unique_documents"]
    lab_reports = truth["counts"]["lab_reports"]
    assert counts["Patient"] == 60
    assert counts["Encounter"] == truth["counts"]["encounters"]
    assert counts["Observation"] == truth["counts"]["csv_rows"] - 1
    assert counts["DocumentReference"] + counts["DiagnosticReport"] == documents + lab_reports
    subtypes = Counter(
        row.subtype
        for r in results
        for row in r.built.rows
        if row.resource_type == "DiagnosticReport"
    )
    assert subtypes["LAB"] == lab_reports
    assert subtypes["RAD"] > 0
    assert subtypes["PAT"] > 0


def test_identity_flags_carried_into_fhir(
    results: list[NormalizedBundle], truth: dict[str, Any]
) -> None:
    warnings = [i for r in results for i in r.validation.issues if i.severity == "warning"]
    assert [i.code for i in warnings] == ["patient.identity_conflict"] * 4
    patients = [r.built.bundle["entry"][0]["resource"] for r in results]
    old_ids = {i["value"] for p in patients for i in p["identifier"] if i["use"] == "old"}
    secondary = {m["mrns"][1] for m in truth["mrn_merges"]}
    assert old_ids == secondary


def test_identical_bundle_hash_on_rerun(db: Path, results: list[NormalizedBundle]) -> None:
    with closing(connect(db)) as conn:
        again = run_normalization(conn, today=TODAY, timestamp=T2)
    assert [r.built.bundle_hash for r in again] == [r.built.bundle_hash for r in results]
    assert [r.built.bundle["timestamp"] for r in again] != [
        r.built.bundle["timestamp"] for r in results
    ]


def test_adversarial_note_survives_unchanged(
    results: list[NormalizedBundle], truth: dict[str, Any]
) -> None:
    phrase = truth["adversarial"]["phrase"]
    texts = [row.text_content or "" for r in results for row in r.built.rows]
    assert sum(phrase in t for t in texts) == 1


def test_normalize_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, db: Path) -> None:
    work = tmp_path / "ehr.db"
    work.write_bytes(db.read_bytes())
    monkeypatch.setenv("SQLITE_PATH", str(work))
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))
    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["normalize"])
    assert result.exit_code == 0, result.output
    assert "Valid bundles" in result.output
    assert (tmp_path / "reports" / "validation_report.md").is_file()
    with closing(sqlite3.connect(work)) as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM fhir_bundles WHERE is_valid = 1").fetchone()[0] == 60
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM validation_issues WHERE severity='error'"
            ).fetchone()[0]
            == 0
        )


def test_normalize_without_ingest_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "empty.db"))
    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["normalize"])
    assert result.exit_code == 1
    assert "make ingest" in result.output
