from __future__ import annotations

import json

import pytest
import structlog
from typer.testing import CliRunner

from ehr_mip.cli import EXIT_NOT_IMPLEMENTED, app
from ehr_mip.logging import configure_logging

runner = CliRunner()


def test_help_lists_every_stage() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in ("ingest", "normalize", "summarize", "index", "run-all", "serve", "eval"):
        assert stage in result.output


@pytest.mark.parametrize(
    ("stage", "phase"),
    [("ingest", 1), ("normalize", 2), ("summarize", 3), ("index", 4), ("run-all", 4)],
)
def test_pending_stage_names_its_phase(stage: str, phase: int) -> None:
    result = runner.invoke(app, [stage])
    assert result.exit_code == EXIT_NOT_IMPLEMENTED
    assert f"Phase {phase}" in result.output


def test_info_shows_config_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-value")
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "anthropic" in result.output
    assert "sk-secret-value" not in result.output


def test_logging_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    structlog.reset_defaults()
    configure_logging("INFO")
    structlog.get_logger("t").info("pipeline_started", run_id="r1")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "pipeline_started"
    assert payload["run_id"] == "r1"
    assert payload["level"] == "info"
    assert "ts" in payload
