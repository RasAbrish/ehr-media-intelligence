"""Task 3 end to end on the synthetic data: privacy, gates, caching and injection (no API key)."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ehr_mip.cli import app
from ehr_mip.config import PROJECT_ROOT, get_settings
from ehr_mip.db.connection import connect
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.fhir.pipeline import run_normalization
from ehr_mip.fhir.store import BundleStore
from ehr_mip.ingestion.pipeline import run_ingestion
from ehr_mip.ingestion.repository import IngestionRepository
from ehr_mip.summarization.anomalies import detect_anomalies
from ehr_mip.summarization.context import build_context
from ehr_mip.summarization.evaluate import run_eval
from ehr_mip.summarization.prompts.registry import load_prompt
from ehr_mip.summarization.providers.extractive import ExtractiveProvider
from ehr_mip.summarization.providers.fake import FakeProvider
from ehr_mip.summarization.records import read_bundle
from ehr_mip.summarization.service import SummaryService

pytestmark = pytest.mark.integration

RAW = PROJECT_ROOT / "data" / "raw"
FIXTURES = PROJECT_ROOT / "backend" / "tests" / "fixtures"
TODAY = date(2026, 11, 21)
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("summaries") / "ehr.db"
    with closing(connect(path)) as conn:
        runs = PipelineRunRepository(conn)
        IngestionRepository(conn).save(runs.start("ingest"), run_ingestion(RAW, today=TODAY))
        BundleStore(conn).save(
            run_normalization(conn, today=TODAY, timestamp=NOW), created_at=NOW, full_refresh=True
        )
    return path


@pytest.fixture
def conn(db: Path, tmp_path: Path) -> Iterator[sqlite3.Connection]:
    work = tmp_path / "work.db"
    work.write_bytes(db.read_bytes())
    with closing(connect(work)) as connection:
        yield connection


@pytest.fixture(scope="module")
def truth() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RAW / "_ground_truth.json").read_text(encoding="utf-8"))
    return data


def service(conn: sqlite3.Connection, provider: object) -> SummaryService:
    return SummaryService(conn, provider=provider, prompt_version="v1", today=TODAY,  # type: ignore[arg-type]
                          clock=lambda: NOW)  # fmt: skip


def _dob_forms(dob: date) -> list[str]:
    return [dob.isoformat(), dob.strftime("%m/%d/%Y"), dob.strftime("%d-%b-%Y"),
            f"{dob.strftime('%B')} {dob.day}, {dob.year}", dob.strftime("%Y%m%d")]  # fmt: skip


def test_context_has_no_phi_for_every_patient(
    conn: sqlite3.Connection, truth: dict[str, Any]
) -> None:
    store = BundleStore(conn)
    names_in_notes = 0
    for key in store.patient_keys():
        bundle = store.load_bundle(key)
        assert bundle is not None
        view = read_bundle(bundle)
        text = build_context(view, detect_anomalies(view, today=TODAY)).text
        prompt = load_prompt("v1").render_user(text)
        patient = view.patient
        identifiers = [p for p in (patient.family, *patient.given) if p and len(p) >= 2]
        identifiers += [m.lstrip("0") for m in patient.mrns]
        identifiers += _dob_forms(patient.birth_date) if patient.birth_date else []
        for identifier in identifiers:
            assert not re.search(
                rf"(?<![\w-]){re.escape(identifier)}(?![\w-])", prompt, re.IGNORECASE
            ), (key, identifier)
        names_in_notes += any(patient.family and patient.family in r.text for r in view.records)
    assert names_in_notes > 5  # the generator names patients inside notes: scrubbing was exercised


def test_eval_gates_pass_without_api_key(conn: sqlite3.Connection) -> None:
    result = asyncio.run(
        run_eval(
            conn,
            service(conn, ExtractiveProvider()),
            golden_dir=FIXTURES / "golden",
            adversarial_dir=FIXTURES / "adversarial",
            truth_path=RAW / "_ground_truth.json",
            today=TODAY,
            now=NOW,
        )
    )
    report = result.report
    assert len(result.summaries) == 60
    failed = [name for name, ok in report["gates"].items() if not ok]
    assert failed == [], report
    assert report["full_set"]["patients"] == 60
    assert report["full_set"]["grounding_final"] == 1.0
    assert report["full_set"]["high_anomaly_recall"] == 1.0
    assert report["ground_truth"]["recall"] >= 0.85


async def test_second_run_makes_no_provider_calls(conn: sqlite3.Connection) -> None:
    extractive = ExtractiveProvider()
    provider = FakeProvider(script=extractive.build)  # the LLM path, with grounded content
    first = await service(conn, provider).summarize_all()
    second = await service(conn, provider).summarize_all()
    assert sum(o.provider_calls for o in first) == 60
    assert sum(o.provider_calls for o in second) == 0
    assert all(o.summary.cached for o in second)
    assert len(provider.calls) == 60
    summaries = [o.summary for o in first]
    assert all(0 < s.word_count <= 200 for s in summaries)
    assert {s.provider for s in summaries} == {"anthropic"}


async def test_real_adversarial_note_is_ignored(
    conn: sqlite3.Connection, truth: dict[str, Any]
) -> None:
    adversarial = truth["adversarial"]
    person = truth["persons"][adversarial["person_id"]]
    patient = next(
        p
        for p in IngestionRepository(conn).load_patients()
        if person["mrns"][0] in {p.mrn, *p.secondary_mrns}
    )
    outcome = await service(conn, ExtractiveProvider()).summarize_patient(patient.patient_key)
    text = outcome.summary.model_dump_json().lower()
    assert "ignore all previous instructions" not in text
    assert "healthy" not in text
    assert any(a.severity == "high" and "lactate" in a.description.lower()
               for a in outcome.summary.flagged_anomalies)  # fmt: skip


def test_summarize_and_eval_commands(
    db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "cli.db"
    work.write_bytes(db.read_bytes())
    monkeypatch.setenv("SQLITE_PATH", str(work))
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))
    get_settings.cache_clear()
    runner = CliRunner()
    first = runner.invoke(app, ["summarize"])
    assert first.exit_code == 0, first.output
    assert "Provider: extractive" in first.output
    second = runner.invoke(app, ["summarize"])
    assert re.search(r"From cache\s*│\s*60", second.output)
    evaluated = runner.invoke(app, ["eval"])
    assert evaluated.exit_code == 0, evaluated.output
    assert (tmp_path / "reports" / "eval_report.md").is_file()
    report = json.loads((tmp_path / "reports" / "eval_report.json").read_text(encoding="utf-8"))
    assert report["passed"]


def test_summarize_without_bundles_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "empty.db"))
    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["summarize"])
    assert result.exit_code == 1
    assert "make normalize" in result.output
