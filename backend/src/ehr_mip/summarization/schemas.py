"""Summary schemas (docs/03-DATA-MODEL.md section 6, docs/04-API-CONTRACT.md section 6.4).

``ClinicalSummaryLLM`` is the shape the model (or the extractive provider) fills in.
It carries no length limits, so an over-long answer still parses and the guardrails
can fix it deterministically. ``ClinicalSummary`` is the stored, guarded result and
validates every field limit.
"""

from __future__ import annotations

import datetime as dt
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DISCLAIMER: Final = (
    "AI-generated summary for information retrieval only. Not a clinical decision. "
    "Verify against source records before acting."
)
NOT_DOCUMENTED = "Not documented"

EvidenceType = Literal["DocumentReference", "DiagnosticReport", "Observation", "Encounter"]
DiagnosisStatus = Literal["active", "historical", "suspected"]
MediaKind = Literal["imaging", "lab", "pathology", "note"]
AnomalySeverity = Literal["low", "moderate", "high"]
AnomalySource = Literal["rule", "model"]
ConfidenceLevel = Literal["low", "medium", "high"]
SummaryProvider = Literal["anthropic", "extractive"]

# Field limits (docs/03 section 6).
MAX_CHIEF_CONCERN = 160
MAX_ITEMS = 5
MAX_DIAGNOSIS_NAME = 80
MAX_FINDING = 120
MAX_ANOMALY = 140
MAX_OVERVIEW = 600
MAX_WORDS = 200
MAX_RATIONALE = 160


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(_Model):
    resource_type: EvidenceType
    resource_id: str

    @property
    def key(self) -> str:
        return f"{self.resource_type}/{self.resource_id}"


class Diagnosis(_Model):
    name: str
    status: DiagnosisStatus
    evidence: list[EvidenceRef]


class MediaRecord(_Model):
    resource: EvidenceRef
    kind: MediaKind
    date: dt.date | None = None  # contract field name: the module-qualified type avoids shadowing
    finding: str


class Anomaly(_Model):
    description: str
    severity: AnomalySeverity
    source: AnomalySource
    evidence: list[EvidenceRef]


class ClinicalSummaryLLM(_Model):
    """What a provider returns. Every claim cites record ids from the context."""

    chief_concern: str
    key_diagnoses: list[Diagnosis]
    recent_media: list[MediaRecord]
    flagged_anomalies: list[Anomaly]
    overview: str
    self_reported_confidence: ConfidenceLevel


class Confidence(_Model):
    level: ConfidenceLevel
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=MAX_RATIONALE)


def count_words(summary: ClinicalSummaryLLM) -> int:
    """Whitespace tokens across the free-text fields (docs/05 section 3.5)."""
    parts = [
        summary.chief_concern,
        *(d.name for d in summary.key_diagnoses),
        *(m.finding for m in summary.recent_media),
        *(a.description for a in summary.flagged_anomalies),
        summary.overview,
    ]
    return sum(len(p.split()) for p in parts)


def limit_violations(summary: ClinicalSummaryLLM) -> list[str]:
    """Every field-limit breach in a summary, as readable strings (empty when valid)."""
    problems: list[str] = []
    if len(summary.chief_concern) > MAX_CHIEF_CONCERN:
        problems.append("chief_concern too long")
    if len(summary.overview) > MAX_OVERVIEW:
        problems.append("overview too long")
    for name, items in (
        ("key_diagnoses", summary.key_diagnoses),
        ("recent_media", summary.recent_media),
        ("flagged_anomalies", summary.flagged_anomalies),
    ):
        if len(items) > MAX_ITEMS:
            problems.append(f"{name} has more than {MAX_ITEMS} items")
    for diagnosis in summary.key_diagnoses:
        if len(diagnosis.name) > MAX_DIAGNOSIS_NAME:
            problems.append("diagnosis name too long")
        if not diagnosis.evidence:
            problems.append("diagnosis without evidence")
    if any(len(m.finding) > MAX_FINDING for m in summary.recent_media):
        problems.append("media finding too long")
    if any(len(a.description) > MAX_ANOMALY for a in summary.flagged_anomalies):
        problems.append("anomaly description too long")
    if count_words(summary) > MAX_WORDS:
        problems.append(f"more than {MAX_WORDS} words")
    return problems


class ClinicalSummary(ClinicalSummaryLLM):
    """A guarded summary as stored and served (contract: ClinicalSummaryResponse)."""

    patient_key: str
    word_count: int = Field(ge=0, le=MAX_WORDS)
    confidence: Confidence
    disclaimer: Literal[
        "AI-generated summary for information retrieval only. Not a clinical decision. "
        "Verify against source records before acting."
    ] = DISCLAIMER
    provider: SummaryProvider
    model: str | None
    prompt_version: str
    bundle_hash: str
    generated_at: dt.datetime
    cached: bool = False
    cache_key: str
    guardrail_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _within_limits(self) -> Self:
        problems = limit_violations(self)
        if problems:
            msg = "; ".join(problems)
            raise ValueError(msg)
        if self.word_count != count_words(self):
            msg = "word_count does not match the summary text"
            raise ValueError(msg)
        return self


class SummaryTrace(_Model):
    """Evaluation data kept next to a cached summary (never served to clients)."""

    cited_ids: int
    grounded_ids: int
    interventions: list[str]
    attempts: int
    shortened: bool
    fallback_reason: str | None = None
