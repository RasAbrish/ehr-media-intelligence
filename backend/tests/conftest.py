"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

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
