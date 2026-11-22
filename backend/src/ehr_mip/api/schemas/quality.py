"""Data quality and audit contracts (docs/04 sections 6.8 and 8)."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from ehr_mip.api.schemas.common import ApiModel, PatientRef, ResourceType, Severity

T = TypeVar("T")
AuditStage = Literal["read", "clean", "identity", "dedupe"]


class Page(ApiModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class AuditEntryItem(ApiModel):
    id: int
    run_id: str
    record_id: str
    stage: AuditStage
    field: str | None
    rule: str
    before: str | None
    after: str | None
    severity: Severity
    message: str


class AuditEntryWithPatient(AuditEntryItem):
    patient: PatientRef | None


class ValidationIssueItem(ApiModel):
    id: int
    patient: PatientRef
    resource_type: ResourceType | Literal["Bundle"]
    resource_id: str | None
    path: str
    severity: Severity
    code: str
    message: str


class QuarantineItem(ApiModel):
    id: int
    run_id: str
    source_locator: str
    reason: str
    payload_preview: str


class BySeverity(ApiModel):
    info: int
    warning: int
    error: int


class RuleCount(ApiModel):
    rule: str
    count: int


class CodeCount(ApiModel):
    code: str
    count: int


class IngestionOverview(ApiModel):
    records_read: int
    by_format: dict[Literal["json", "csv", "txt"], int]
    patients: int
    documents: int
    lab_results: int
    exact_duplicates_removed: int
    near_duplicates_removed: int
    identities_merged: int
    identity_conflicts: int
    quarantined: int
    audit_by_severity: BySeverity
    top_rules: list[RuleCount]


class ValidationOverview(ApiModel):
    bundles: int
    valid_bundles: int
    issues_by_severity: BySeverity
    top_codes: list[CodeCount]


class LlmOverview(ApiModel):
    calls: int
    fallback_calls: int
    failed_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd_estimate: float
    p95_latency_ms: int


class PromptFeedback(ApiModel):
    prompt_version: str
    helpful_rate: float | None
    votes: int


class FeedbackOverview(ApiModel):
    helpful: int
    not_helpful: int
    helpful_rate: float | None
    by_prompt_version: list[PromptFeedback]


class SummaryOverview(ApiModel):
    total: int
    by_provider: dict[Literal["anthropic", "extractive"], int]
    avg_word_count: float
    max_word_count: int
    confidence: dict[Literal["low", "medium", "high"], int]
    guardrail_interventions: int
    llm: LlmOverview
    feedback: FeedbackOverview


class LastRunOut(ApiModel):
    run_id: str
    finished_at: str | None
    status: Literal["queued", "running", "succeeded", "failed"]


class QualityOverview(ApiModel):
    ingestion: IngestionOverview
    validation: ValidationOverview
    summaries: SummaryOverview
    last_run: LastRunOut | None
