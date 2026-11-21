"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from ehr_mip.config import Settings, get_settings

_ENV_KEYS = [name.upper() for name in Settings.model_fields]


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep the developer's shell and .env from leaking into tests."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    """Settings built from defaults only (no .env file)."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """Each test starts with default logging so streams from other tests never leak in."""
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()


@pytest.fixture(scope="session")
def api_store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The synthetic store, built and indexed once per session. Treat it as read-only."""
    from tests.support.api import build_store  # noqa: PLC0415 (only API tests pay for it)

    return build_store(tmp_path_factory.mktemp("api") / "store")
