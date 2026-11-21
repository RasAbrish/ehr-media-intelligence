"""Chunk text for the vector index (docs/05-ALGORITHMS.md section 4.1, docs/03 section 7).

Each searchable resource becomes one or more sentence-aware windows of about 180
words with 30 words of overlap. Patient names and MRNs are scrubbed before
anything is embedded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ehr_mip.search.filters import SearchableType
from ehr_mip.summarization.context import scrub
from ehr_mip.summarization.schemas import ClinicalSummary

WINDOW_WORDS = 180
OVERLAP_WORDS = 30
SUMMARY_TITLE = "AI clinical summary"

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_DOC_LABELS = {
    "discharge_summary": "Discharge summary",
    "progress_note": "Progress note",
    "consult_note": "Consult note",
    "imaging_report": "Imaging report",
    "lab_report": "Lab report",
    "pathology_report": "Pathology report",
    "scanned_document": "Scanned document",
}
_REPORT_LABELS = {"LAB": "Lab", "RAD": "Imaging", "PAT": "Pathology"}

Rules = list[tuple[re.Pattern[str], str]]


@dataclass(frozen=True)
class Chunk:
    """One window of text plus the metadata stored next to its vector."""

    patient_key: str
    resource_id: str  # summaries: "summary:{patient_key}"
    resource_type: SearchableType
    subtype: str
    title: str
    date: date | None
    chunk_index: int
    text: str

    @property
    def id(self) -> str:
        return f"{self.resource_id}:{self.chunk_index}"

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "patient_key": self.patient_key,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "subtype": self.subtype,
            "title": self.title,
            "date": self.date.isoformat() if self.date else "",
            "date_ord": self.date.toordinal() if self.date else 0,
            "chunk_index": self.chunk_index,
        }


@dataclass(frozen=True)
class ResourceText:
    """A row of ``fhir_resources`` with what the chunker needs."""

    patient_key: str
    resource_id: str
    resource_type: str
    subtype: str | None
    title: str | None
    date: date | None
    text: str | None


def windows(text: str, *, size: int = WINDOW_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Sentence-aware windows of about ``size`` words, each starting with ``overlap`` words
    of the previous one. A sentence longer than a window is split by words."""
    piece = max(size - overlap, 1)  # a split piece plus the overlap still fits a window
    sentences: list[list[str]] = []
    for sentence in _SENTENCE_END.split(text):
        words = sentence.split()
        if len(words) > piece:  # so overlap + sentence always fits in one window
            sentences += [words[i : i + piece] for i in range(0, len(words), piece)]
        elif words:
            sentences.append(words)
    result: list[str] = []
    current: list[str] = []
    for words in sentences:
        if current and len(current) + len(words) > size:
            result.append(" ".join(current))
            current = current[-overlap:] if overlap else []
        current = current + words
    if current:
        result.append(" ".join(current))
    return result


def _date_text(value: date | None) -> str:
    return value.isoformat() if value else "Undated"


def resource_template(row: ResourceText) -> str | None:
    """The text template of docs/05 section 4.1, or ``None`` for a type that is not indexed."""
    body = " ".join((row.text or "").split())
    title = row.title or row.resource_type
    when = _date_text(row.date)
    if row.resource_type == "DocumentReference":
        label = _DOC_LABELS.get(row.subtype or "", "Clinical note")
        return f"{label}: {title}. {when}. {body}"
    if row.resource_type == "DiagnosticReport":
        label = _REPORT_LABELS.get(row.subtype or "", "Diagnostic")
        return f"{label} report: {title}. {when}. {body}"
    if row.resource_type == "Observation":
        return f"{body} {when}"
    return None


def chunk_resource(row: ResourceText, rules: Rules) -> list[Chunk]:
    template = resource_template(row)
    if template is None:
        return []
    return [
        Chunk(
            patient_key=row.patient_key,
            resource_id=row.resource_id,
            resource_type=row.resource_type,  # type: ignore[arg-type]
            subtype=row.subtype or "",
            title=row.title or row.resource_type,
            date=row.date,
            chunk_index=index,
            text=window,
        )
        for index, window in enumerate(windows(scrub(template, rules)))
    ]


def summary_template(summary: ClinicalSummary) -> str:
    diagnoses = "; ".join(f"{d.name} ({d.status})" for d in summary.key_diagnoses) or "none"
    media = "; ".join(m.finding for m in summary.recent_media) or "none"
    anomalies = "; ".join(f"{a.description} ({a.severity})" for a in summary.flagged_anomalies)
    return (
        f"Clinical summary. Chief concern: {summary.chief_concern} Diagnoses: {diagnoses}. "
        f"Recent: {media}. Anomalies: {anomalies or 'none'}. Overview: {summary.overview}"
    )


def chunk_summary(summary: ClinicalSummary, rules: Rules, as_of: date | None) -> list[Chunk]:
    """Summary chunks are dated by the newest record they cover (``as_of``), not by when
    the summary was generated, so date filters and MRN lookups treat them like records."""
    resource_id = f"summary:{summary.patient_key}"
    return [
        Chunk(
            patient_key=summary.patient_key,
            resource_id=resource_id,
            resource_type="ClinicalSummary",
            subtype=summary.provider,
            title=SUMMARY_TITLE,
            date=as_of,
            chunk_index=index,
            text=window,
        )
        for index, window in enumerate(windows(scrub(summary_template(summary), rules)))
    ]
