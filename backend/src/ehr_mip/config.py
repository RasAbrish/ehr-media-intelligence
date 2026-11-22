"""Application settings.

This is the only module that reads the environment. Everything else receives a
``Settings`` instance through dependency injection.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _find_project_root() -> Path:
    """Locate the repository root (the folder holding ``.env.example``).

    ``EHR_MIP_ROOT`` wins when set (containers). Otherwise walk up from this file,
    then from the working directory, and finally fall back to the working directory.
    """
    override = os.environ.get("EHR_MIP_ROOT")
    if override:
        return Path(override).resolve()
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for candidate in (start, *start.parents):
            if (candidate / ".env.example").is_file():
                return candidate
    return Path.cwd().resolve()


PROJECT_ROOT = _find_project_root()

LlmProvider = Literal["auto", "anthropic", "groq", "extractive"]


class Settings(BaseSettings):
    """Typed configuration. Field names mirror ``.env.example`` one to one."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # LLM
    anthropic_api_key: SecretStr | None = None
    llm_provider: LlmProvider = "auto"
    llm_model: str = "claude-haiku-5-5"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    llm_max_concurrency: int = Field(default=4, ge=1, le=32)
    llm_timeout_s: float = Field(default=30, gt=0, le=300)
    summary_max_words: int = Field(default=200, ge=50, le=400)
    prompt_version: str = Field(default="v1", pattern=r"^v\d+$")
    llm_daily_token_budget: int = Field(default=500_000, ge=0)

    # Paths
    data_raw_dir: Path = Path("data/raw")
    data_dir: Path = Path("data/generated")
    sqlite_path: Path = Path("data/generated/ehr_mip.db")
    chroma_dir: Path = Path("data/generated/chroma")
    hf_home: Path = Path("data/generated/hf-cache")
    reports_dir: Path = Path("reports")

    # Search
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    search_default_top_k: int = Field(default=5, ge=1, le=20)
    search_mode: Literal["semantic", "hybrid"] = "hybrid"
    index_observations: bool = False
    search_cache_ttl_s: int = Field(default=60, ge=0)

    # API
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )
    enable_admin_endpoints: bool = False
    admin_token: SecretStr | None = None
    auto_bootstrap: bool = False
    rate_limit_enabled: bool = True
    forwarded_allow_ips: str = "127.0.0.1"
    feedback_enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    env: Literal["dev", "prod"] = "dev"
    # Swagger UI and the OpenAPI schema; unset means on in dev and off in prod.
    api_docs_enabled: bool | None = None

    # Sign-in (ADR-013)
    auth_enabled: bool = True
    session_hours: float = Field(default=8, gt=0, le=24)
    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    seed_account_email: str | None = None
    seed_account_name: str = "Clinician"
    seed_account_password: SecretStr | None = None

    # Cache
    cache_backend: Literal["memory", "redis", "auto"] = "memory"
    redis_url: str = "redis://redis:6379/0"

    # Synthetic data
    synth_seed: int = 42
    synth_patients: int = Field(default=60, ge=1, le=10_000)

    @field_validator(
        "anthropic_api_key",
        "admin_token",
        "groq_api_key",
        "seed_account_email",
        "seed_account_password",
        mode="before",
    )
    @classmethod
    def _blank_secret_is_none(cls, value: object) -> object:
        # "#…" is an inline comment that Docker Compose passed through as the value.
        if isinstance(value, str) and (not value.strip() or value.strip().startswith("#")):
            return None
        return value

    @field_validator("api_docs_enabled", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "data_raw_dir", "data_dir", "sqlite_path", "chroma_dir", "hf_home", "reports_dir"
    )
    @classmethod
    def _anchor_to_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @model_validator(mode="after")
    def _admin_needs_token(self) -> Settings:
        if self.enable_admin_endpoints and self.admin_token is None:
            msg = "ADMIN_TOKEN is required when ENABLE_ADMIN_ENDPOINTS=true"
            raise ValueError(msg)
        return self

    @property
    def effective_llm_provider(self) -> Literal["anthropic", "groq", "extractive"]:
        """Resolve ``auto``: Claude, then Groq, by which key is present; else extractive."""
        keys: dict[Literal["anthropic", "groq"], SecretStr | None] = {
            "anthropic": self.anthropic_api_key,
            "groq": self.groq_api_key,
        }
        if self.llm_provider == "auto":
            return next((name for name, key in keys.items() if key is not None), "extractive")
        if self.llm_provider != "extractive" and keys[self.llm_provider] is None:
            return "extractive"
        return self.llm_provider

    @property
    def effective_llm_model(self) -> str | None:
        """The model id summaries will report, or None for the extractive provider."""
        provider = self.effective_llm_provider
        return {"anthropic": self.llm_model, "groq": self.groq_model}.get(provider)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings (cached)."""
    return Settings()
