"""``ehr-mip ingest`` end to end, plus the PHI-free logging rule (docs/09 section 11)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from ehr_mip.cli import app
from ehr_mip.config import PROJECT_ROOT, get_settings
from ehr_mip.ingestion.pipeline import run_ingestion
from ehr_mip.logging import configure_logging

pytestmark = pytest.mark.integration
RAW = PROJECT_ROOT / "data" / "raw"


def test_ingest_command_writes_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "ehr_mip.db"
    monkeypatch.setenv("DATA_RAW_DIR", str(RAW))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    result = CliRunner().invoke(app, ["ingest"])
    assert result.exit_code == 0, result.output
    assert "Patients" in result.output
    assert "Records quarantined" in result.output
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 60
        assert conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0] == 3
        stats = json.loads(
            conn.execute("SELECT stats_json FROM pipeline_runs WHERE stage='ingest'").fetchone()[0]
        )
    assert stats["identities_merged"] == 3


def test_logs_contain_no_phi(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATA_RAW_DIR", str(RAW))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "ehr_mip.db"))
    structlog.reset_defaults()
    configure_logging("DEBUG")
    run_ingestion(RAW)
    logs = capsys.readouterr().err
    assert "ingest_completed" in logs
    truth = json.loads((RAW / "_ground_truth.json").read_text(encoding="utf-8"))
    for person in truth["persons"].values():
        assert person["family"] not in logs
        for mrn in person["mrns"]:
            assert mrn not in logs
            assert mrn.lstrip("0") not in logs


def test_ingest_refuses_empty_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "ehr_mip.db"
    monkeypatch.setenv("DATA_RAW_DIR", str(RAW))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    assert CliRunner().invoke(app, ["ingest"]).exit_code == 0
    monkeypatch.setenv("DATA_RAW_DIR", str(tmp_path / "missing"))
    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["ingest"])
    assert result.exit_code == 1
    assert "database was not changed" in result.output
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 60
