"""``GET /patients/{key}/summary`` (docs/04 section 6.4), built from the stored summary."""

from __future__ import annotations

from typing import Literal

from ehr_mip.api.schemas.common import (
    AnomalySeverity,
    ApiModel,
    ConfidenceLevel,
    EvidenceRef,
    SummaryProvider,
)


class DiagnosisOut(ApiModel):
    name: str
    status: Literal["active", "historical", "suspected"]
    evidence: list[EvidenceRef]


class MediaOut(ApiModel):
    resource: EvidenceRef
    kind: Literal["imaging", "lab", "pathology", "note"]
    date: str | None
    finding: str


class AnomalyOut(ApiModel):
    description: str
    severity: AnomalySeverity
    source: Literal["rule", "model"]
    evidence: list[EvidenceRef]


class ConfidenceOut(ApiModel):
    level: ConfidenceLevel
    score: float
    rationale: str


class ClinicalSummaryResponse(ApiModel):
    patient_key: str
    chief_concern: str
    key_diagnoses: list[DiagnosisOut]
    recent_media: list[MediaOut]
    flagged_anomalies: list[AnomalyOut]
    overview: str
    word_count: int
    confidence: ConfidenceOut
    disclaimer: str
    provider: SummaryProvider
    model: str | None
    prompt_version: str
    bundle_hash: str
    generated_at: str
    cached: bool
    cache_key: str
    guardrail_notes: list[str]
