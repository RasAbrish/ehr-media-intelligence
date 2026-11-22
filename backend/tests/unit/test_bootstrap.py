"""AUTO_BOOTSTRAP: ``serve`` fills an empty store before it listens (docs/02 section 7)."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pytest
import uvicorn
from typer.testing import CliRunner

from ehr_mip import cli
from ehr_mip.config import Settings
from ehr_mip.db.connection import connect
from ehr_mip.db.repositories import PipelineRunRepository


@pytest.mark.parametrize(
    ("enabled", "indexed", "expected"),
    [
        (True, False, ["pipeline", "listen"]),
        (True, True, ["listen"]),
        (False, False, ["listen"]),
    ],
)
def test_serve_bootstraps_only_an_empty_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool, indexed: bool, expected: list
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        auto_bootstrap=enabled,
        sqlite_path=tmp_path / "ehr.db",
        chroma_dir=tmp_path / "chroma",
    )
    if indexed:
        with closing(connect(settings.sqlite_path)) as conn:
            runs = PipelineRunRepository(conn)
            runs.finish(runs.start("index"), {})
    calls: list[str] = []
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "run_all", lambda: calls.append("pipeline"))
    monkeypatch.setattr("ehr_mip.api.main.create_app", object)
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: calls.append("listen"))
    result = CliRunner().invoke(cli.app, ["serve"])
    assert result.exit_code == 0, result.output
    assert calls == expected


def test_serve_does_not_listen_when_bootstrap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(_env_file=None, auto_bootstrap=True, sqlite_path=tmp_path / "ehr.db")  # type: ignore[call-arg]
    calls: list[str] = []

    def failing() -> None:
        raise cli.typer.Exit(code=1)

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "run_all", failing)
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: calls.append("listen"))
    assert CliRunner().invoke(cli.app, ["serve"]).exit_code == 1
    assert calls == []


def test_serve_never_logs_query_strings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """uvicorn's access log prints `?q=<patient name>`; ours logs the route only (FR-6.4)."""
    settings = Settings(_env_file=None, sqlite_path=tmp_path / "ehr.db")  # type: ignore[call-arg]
    seen: dict[str, object] = {}
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr("ehr_mip.api.main.create_app", object)
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **kwargs: seen.update(kwargs))
    assert CliRunner().invoke(cli.app, ["serve"]).exit_code == 0
    assert seen["access_log"] is False
