from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from ehr_mip.config import PROJECT_ROOT, Settings


def _settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[arg-type]


def test_project_root_holds_env_example() -> None:
    assert (PROJECT_ROOT / ".env.example").is_file()


def test_defaults_run_without_api_key(settings: Settings) -> None:
    assert settings.anthropic_api_key is None
    assert settings.effective_llm_provider == "extractive"
    assert settings.search_mode == "hybrid"
    assert settings.cache_backend == "memory"


def test_relative_paths_anchor_to_project_root(settings: Settings) -> None:
    assert settings.sqlite_path == PROJECT_ROOT / "data/generated/ehr_mip.db"
    assert settings.data_raw_dir.is_absolute()


def test_absolute_path_is_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "x.db"))
    assert _settings().sqlite_path == tmp_path / "x.db"


def test_blank_api_key_means_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    assert _settings().anthropic_api_key is None


@pytest.mark.parametrize(
    ("provider", "key", "expected"),
    [
        ("auto", "sk-test", "anthropic"),
        ("auto", "", "extractive"),
        ("anthropic", "", "extractive"),
        ("anthropic", "sk-test", "anthropic"),
        ("extractive", "sk-test", "extractive"),
    ],
)
def test_effective_provider(
    monkeypatch: pytest.MonkeyPatch, provider: str, key: str, expected: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    assert _settings().effective_llm_provider == expected


def test_api_key_is_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-value")
    assert "sk-secret-value" not in repr(_settings())


def test_cors_origins_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test,")
    assert _settings().cors_origins == ["http://a.test", "http://b.test"]


def test_admin_endpoints_require_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_ADMIN_ENDPOINTS", "true")
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        _settings()


def test_invalid_prompt_version_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPT_VERSION", "latest")
    with pytest.raises(ValidationError):
        _settings()


def test_env_example_parses_with_inline_comments() -> None:
    """Every key in .env.example loads, and inline comments are stripped."""
    parsed = Settings(_env_file=PROJECT_ROOT / ".env.example")  # type: ignore[call-arg]
    assert parsed.anthropic_api_key is None
    assert parsed.llm_provider == "auto"
    assert parsed.llm_model == "claude-haiku-5-5"
    assert parsed.search_mode == "hybrid"
    assert parsed.cors_origins == ["http://localhost:5173", "http://localhost:8080"]


def test_env_example_lists_every_setting() -> None:
    text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    keys = {
        line.split("=", 1)[0].strip()
        for line in text.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert keys == {name.upper() for name in Settings.model_fields}


def test_env_example_blank_values_have_no_inline_comment() -> None:
    """Compose reads `KEY=   # note` as the value "# note", unlike python-dotenv."""
    lines = (PROJECT_ROOT / ".env.example").read_text().splitlines()
    assert [line for line in lines if re.match(r"^[A-Z_]+=\s+#", line)] == []


def test_comment_as_secret_means_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A .env copied from an older example must not become an API key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "# empty → extractive fallback")
    settings = _settings()
    assert settings.anthropic_api_key is None
    assert settings.effective_llm_provider == "extractive"
