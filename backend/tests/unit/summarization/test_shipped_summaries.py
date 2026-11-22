"""Model summaries win over offline ones, and travel as a file (ADR-014)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.support.bundles import heart_failure_bundle
from tests.support.summaries import good_output
from tests.unit.summarization.test_service import TODAY, _store

from ehr_mip.db.listings import Listings
from ehr_mip.db.read_models import StatusReader
from ehr_mip.summarization.cache import SummaryCache, export_summaries, import_summaries
from ehr_mip.summarization.providers.extractive import ExtractiveProvider
from ehr_mip.summarization.providers.fake import FakeProvider
from ehr_mip.summarization.service import SummaryService

T0 = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def run(conn: sqlite3.Connection, provider: object, at: datetime) -> str:
    service = SummaryService(
        conn,
        provider=provider,
        prompt_version="v1",
        today=TODAY,
        clock=lambda: at,  # type: ignore[arg-type]
    )
    return asyncio.run(service.summarize_all()).outcomes[0].summary.patient_key


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(connect_db(tmp_path / "a.db")) as connection:
        yield connection


def connect_db(path: Path) -> sqlite3.Connection:
    from ehr_mip.db.connection import connect  # noqa: PLC0415

    connection = connect(path)
    _store(connection, heart_failure_bundle())
    return connection


def groq() -> FakeProvider:
    return FakeProvider(script=good_output, name="groq", kind="groq", model="openai/gpt-oss-120b")


def test_a_model_summary_beats_a_newer_offline_one(conn: sqlite3.Connection) -> None:
    key = run(conn, groq(), T0)
    run(conn, ExtractiveProvider(), T0 + timedelta(hours=1))
    bundle_hash = conn.execute("SELECT bundle_hash FROM fhir_bundles").fetchone()[0]
    served = SummaryCache(conn).latest(key, bundle_hash)
    assert served is not None
    assert (served.provider, served.model) == ("groq", "openai/gpt-oss-120b")
    concern = StatusReader(conn).chief_concerns([key])[key]
    assert concern == served.chief_concern
    assert Listings(conn).current_summaries([key])[key]["provider"] == "groq"


def test_export_then_import_into_a_fresh_build(conn: sqlite3.Connection, tmp_path: Path) -> None:
    key = run(conn, groq(), T0)
    run(conn, ExtractiveProvider(), T0)
    exported = export_summaries(conn)
    assert [item["summary"]["provider"] for item in exported] == ["groq"]  # offline ones stay
    file = tmp_path / "summaries.json"
    file.write_text(json.dumps(exported))

    with closing(connect_db(tmp_path / "b.db")) as fresh:
        run(fresh, ExtractiveProvider(), T0 + timedelta(days=1))
        assert import_summaries(fresh, json.loads(file.read_text())) == (1, 0)
        bundle_hash = fresh.execute("SELECT bundle_hash FROM fhir_bundles").fetchone()[0]
        served = SummaryCache(fresh).latest(key, bundle_hash)
        assert served is not None
        assert served.provider == "groq"


def test_import_skips_summaries_of_changed_data(conn: sqlite3.Connection) -> None:
    run(conn, groq(), T0)
    exported = export_summaries(conn)
    exported[0]["summary"]["bundle_hash"] = "0" * 64
    assert import_summaries(conn, exported) == (0, 1)
