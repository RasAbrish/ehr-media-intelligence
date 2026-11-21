"""``/health`` and ``/ready`` (docs/04 section 4)."""

from __future__ import annotations

from typing import Literal

from ehr_mip.api.schemas.common import ApiModel, RunStatus, SearchMode, SummaryProvider


class HealthResponse(ApiModel):
    status: Literal["ok"]
    version: str


class Check(ApiModel):
    ok: bool
    detail: str


class VectorStoreCheck(Check):
    chunks: int


class EmbedderCheck(Check):
    model: str


class LlmCheck(Check):
    provider: SummaryProvider
    model: str | None


class ReadyChecks(ApiModel):
    sqlite: Check
    vector_store: VectorStoreCheck
    embedder: EmbedderCheck
    llm: LlmCheck


class ReadyCounts(ApiModel):
    patients: int
    resources: int
    summaries: int
    chunks: int


class LastRun(ApiModel):
    run_id: str
    finished_at: str | None
    status: RunStatus


class ReadyFlags(ApiModel):
    search_mode: SearchMode
    index_observations: bool
    admin_enabled: bool
    cache_backend: Literal["memory", "redis"]
    feedback_enabled: bool


class CacheStatus(ApiModel):
    backend: Literal["memory", "redis"]
    ok: bool
    index_version: int


class ReadyResponse(ApiModel):
    status: Literal["ready", "degraded", "not_ready"]
    checks: ReadyChecks
    counts: ReadyCounts
    last_run: LastRun | None
    flags: ReadyFlags
    cache: CacheStatus
