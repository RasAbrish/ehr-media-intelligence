"""`ehr-mip index`, `run-all` and `serve` (FR-4.1, FR-4.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ehr_mip.cli import app
from ehr_mip.config import get_settings
from ehr_mip.search.embedder import HashEmbedder

pytestmark = pytest.mark.integration
runner = CliRunner()


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ehr_mip.search.embedder.SentenceTransformerEmbedder", lambda *_, **__: HashEmbedder()
    )


def _env(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(root / "ehr.db"))
    monkeypatch.setenv("CHROMA_DIR", str(root / "chroma"))
    monkeypatch.setenv("REPORTS_DIR", str(root / "reports"))
    get_settings.cache_clear()


@pytest.mark.usefixtures("fake_model")
def test_run_all_then_index_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, tmp_path)
    first = runner.invoke(app, ["run-all"])
    assert first.exit_code == 0, first.output
    for title in ("Ingestion", "FHIR normalization", "Summaries", "Index"):
        assert title in first.output
    again = runner.invoke(app, ["index"])
    assert again.exit_code == 0, again.output

    def chunks(output: str) -> str:
        return next(line for line in output.splitlines() if "Chunks" in line)

    assert chunks(first.output) == chunks(again.output)
    assert "Type: ClinicalSummary" in again.output


def test_index_without_bundles_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["index"])
    assert result.exit_code == 1
    assert "make normalize" in result.output


def test_serve_starts_uvicorn_with_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: calls.update(kwargs, app=app))
    result = runner.invoke(app, ["serve", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert calls["port"] == 8123
    assert calls["host"] == "127.0.0.1"
    assert calls["limit_concurrency"] == 64
    assert calls["timeout_graceful_shutdown"] == 10
