from __future__ import annotations

import json
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from ehr_mip.cli import app
from ehr_mip.logging import configure_logging

runner = CliRunner()


def test_help_lists_every_stage() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in ("ingest", "normalize", "summarize", "index", "run-all", "serve", "eval"):
        assert stage in result.output


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


def test_users_add_asks_for_the_password_and_never_shows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner  # noqa: PLC0415

    from ehr_mip.cli import app  # noqa: PLC0415

    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "users.db"))
    secret = "a very secret password"  # noqa: S105 (test value)
    runner = CliRunner()
    args = ["users", "add", "--email", "Ana@Example.org", "--name", "Ana"]
    result = runner.invoke(app, args, input=f"{secret}\n{secret}\n")
    assert result.exit_code == 0, result.output
    assert secret not in result.output
    again = runner.invoke(app, args, input=f"{secret}\n{secret}\n")
    assert again.exit_code == 1
    short = runner.invoke(
        app, ["users", "add", "--email", "b@example.org", "--name", "B"], input="short\nshort\n"
    )
    assert short.exit_code == 1
    assert runner.invoke(app, ["users", "disable", "--email", "ana@example.org"]).exit_code == 0
