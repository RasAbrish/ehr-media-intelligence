"""Guardrails (docs/05-ALGORITHMS.md section 3.5, docs/10 section 1).

Pure functions: given a provider output and the patient's bundle view, return a
grounded, bounded output plus notes describing every intervention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ehr_mip.summarization.context import INSTRUCTION_RE
from ehr_mip.summarization.records import BundleView
from ehr_mip.summarization.schemas import (
    MAX_ANOMALY,
    MAX_CHIEF_CONCERN,
    MAX_DIAGNOSIS_NAME,
    MAX_FINDING,
    MAX_ITEMS,
    MAX_OVERVIEW,
    MAX_RATIONALE,
    MAX_WORDS,
    NOT_DOCUMENTED,
    Anomaly,
    ClinicalSummaryLLM,
    Confidence,
    ConfidenceLevel,
    Diagnosis,
    MediaRecord,
    count_words,
)

SUPPORT_THRESHOLD = 85
TRIM_MEDIA = 3
_SEVERITY_RANK = {"high": 0, "moderate": 1, "low": 2}
_KIND_BY_TYPE = {"imaging": "imaging", "pathology": "pathology", "lab": "lab", "note": "note"}


# Notes that correct content; each one lowers confidence. Length handling does not.
CONTENT_NOTES = ("ungrounded_removed", "unsupported_diagnosis", "high_anomaly_restored",
                 "instruction_echo_removed")  # fmt: skip


def content_interventions(notes: list[str]) -> int:
    return sum(1 for note in notes if note.startswith(CONTENT_NOTES))


@dataclass
class GuardResult:
    output: ClinicalSummaryLLM
    notes: list[str] = field(default_factory=list)
    cited: int = 0
    grounded: int = 0

    @property
    def word_count(self) -> int:
        return count_words(self.output)


def _cut(text: str, limit: int) -> str:
    """Shorten to ``limit`` characters at a word boundary, ending with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{cut}…"


def _strip_instructions(text: str) -> tuple[str, bool]:
    """Drop sentences that carry instruction-like text (prompt injection echoes)."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [s for s in sentences if not INSTRUCTION_RE.search(s)]
    return " ".join(kept).strip(), len(kept) != len(sentences)


@dataclass
class _Grounded:
    diagnoses: list[Diagnosis]
    media: list[MediaRecord]
    anomalies: list[Anomaly]
    cited: int
    grounded: int
    dropped: int


def _ground(output: ClinicalSummaryLLM, view: BundleView, rules: list[Anomaly]) -> _Grounded:
    """Keep only evidence that exists in this patient's bundle; drop items left without any."""
    valid = view.ref_keys
    records = {r.ref.key: r for r in view.records}
    rule_descriptions = {a.description for a in rules}
    result = _Grounded([], [], [], 0, 0, 0)
    for diagnosis in output.key_diagnoses:
        evidence = [e for e in diagnosis.evidence if e.key in valid]
        result.cited += len(diagnosis.evidence)
        result.grounded += len(evidence)
        if evidence:
            result.diagnoses.append(diagnosis.model_copy(update={"evidence": evidence}))
        else:
            result.dropped += 1
    for item in output.recent_media:
        record = records.get(item.resource.key)
        result.cited += 1
        if record is None:
            result.dropped += 1
            continue
        result.grounded += 1
        # Date and kind come from the record itself, never from the model.
        update = {"date": record.when, "kind": _KIND_BY_TYPE[record.kind]}
        result.media.append(item.model_copy(update=update))
    for anomaly in output.flagged_anomalies:
        evidence = [e for e in anomaly.evidence if e.key in valid]
        result.cited += len(anomaly.evidence)
        result.grounded += len(evidence)
        # Rule anomalies about the record itself (identity) legitimately cite nothing.
        if evidence or (not anomaly.evidence and anomaly.description in rule_descriptions):
            result.anomalies.append(anomaly.model_copy(update={"evidence": evidence}))
        else:
            result.dropped += 1
    return result


def _check_support(diagnoses: list[Diagnosis], view: BundleView) -> tuple[list[Diagnosis], int]:
    """A diagnosis must be written in the records it cites; otherwise it becomes suspected."""
    checked: list[Diagnosis] = []
    unsupported = 0
    for diagnosis in diagnoses:
        cited_text = "\n".join(view.text_for(e.key) for e in diagnosis.evidence).lower()
        supported = fuzz.partial_ratio(diagnosis.name.lower(), cited_text) >= SUPPORT_THRESHOLD
        unsupported += not supported
        checked.append(
            diagnosis if supported else diagnosis.model_copy(update={"status": "suspected"})
        )
    return checked, unsupported


def _restore_high(anomalies: list[Anomaly], rules: list[Anomaly]) -> tuple[list[Anomaly], int]:
    """Every high rule anomaly must be present, matched by its evidence."""
    present = {e.key for a in anomalies for e in a.evidence}
    restored: list[Anomaly] = []
    for rule in rules:
        if rule.severity == "high" and not any(e.key in present for e in rule.evidence):
            restored.append(rule)
            present |= {e.key for e in rule.evidence}
    merged = sorted([*anomalies, *restored], key=lambda a: _SEVERITY_RANK[a.severity])
    return merged, len(restored)


def _apply_limits(
    output: ClinicalSummaryLLM,
    chief: str,
    overview: str,
    grounded: _Grounded,
) -> tuple[ClinicalSummaryLLM, bool]:
    lists = (grounded.diagnoses, grounded.media, grounded.anomalies)
    truncated = any(len(items) > MAX_ITEMS for items in lists)

    def fit(text: str, limit: int) -> str:
        nonlocal truncated
        result = _cut(text, limit)
        truncated = truncated or result != " ".join(text.split())
        return result

    limited = ClinicalSummaryLLM(
        chief_concern=fit(chief or NOT_DOCUMENTED, MAX_CHIEF_CONCERN),
        key_diagnoses=[
            d.model_copy(update={"name": fit(d.name, MAX_DIAGNOSIS_NAME)})
            for d in grounded.diagnoses[:MAX_ITEMS]
        ],
        recent_media=[
            m.model_copy(update={"finding": fit(m.finding, MAX_FINDING)})
            for m in grounded.media[:MAX_ITEMS]
        ],
        flagged_anomalies=[
            a.model_copy(update={"description": fit(a.description, MAX_ANOMALY)})
            for a in grounded.anomalies[:MAX_ITEMS]
        ],
        overview=fit(overview or NOT_DOCUMENTED, MAX_OVERVIEW),
        self_reported_confidence=output.self_reported_confidence,
    )
    return limited, truncated


def apply_guardrails(
    output: ClinicalSummaryLLM, view: BundleView, rule_anomalies: list[Anomaly]
) -> GuardResult:
    """Ground, check support, restore high anomalies, remove injection echoes, enforce limits."""
    notes: list[str] = []
    grounded = _ground(output, view, rule_anomalies)
    if grounded.dropped:
        notes.append(f"ungrounded_removed ({grounded.dropped})")
    grounded.diagnoses, unsupported = _check_support(grounded.diagnoses, view)
    if unsupported:
        notes.append(f"unsupported_diagnosis ({unsupported})")
    grounded.anomalies, restored = _restore_high(grounded.anomalies, rule_anomalies)
    if restored:
        notes.append(f"high_anomaly_restored ({restored})")
    chief, chief_cut = _strip_instructions(output.chief_concern)
    overview, overview_cut = _strip_instructions(output.overview)
    if chief_cut or overview_cut:
        notes.append("instruction_echo_removed")
    limited, truncated = _apply_limits(output, chief, overview, grounded)
    if truncated:
        notes.append("field_limits_applied")
    return GuardResult(
        output=limited, notes=notes, cited=grounded.cited, grounded=grounded.grounded
    )


def trim_to_word_limit(output: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
    """Deterministic trim, in the order of docs/05 section 3.5, until ≤ 200 words.

    After the documented steps it drops media, then non-high anomalies, then
    non-active diagnoses, then shortens the longest text, so the limit always holds.
    """
    current = output.model_copy(update={"recent_media": output.recent_media[:TRIM_MEDIA]})

    def shorter_overview(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        sentences = re.split(r"(?<=[.!?])\s+", s.overview)
        return s.model_copy(update={"overview": " ".join(sentences[:2])})

    def without_low_anomalies(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        kept = [a for a in s.flagged_anomalies if a.severity != "low"]
        return s.model_copy(update={"flagged_anomalies": kept})

    def without_historical(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        kept = [d for d in s.key_diagnoses if d.status != "historical"]
        return s.model_copy(update={"key_diagnoses": kept})

    def cut_overview(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        words = s.overview.split()
        keep = max(len(words) - (count_words(s) - MAX_WORDS) - 1, 0)
        return s.model_copy(
            update={"overview": " ".join(words[:keep]) + "…" if keep else NOT_DOCUMENTED}
        )

    def without_media(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        return s.model_copy(update={"recent_media": []})

    def only_high_anomalies(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        kept = [a for a in s.flagged_anomalies if a.severity == "high"]
        return s.model_copy(update={"flagged_anomalies": kept})

    def only_active_diagnoses(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
        kept = [d for d in s.key_diagnoses if d.status == "active"]
        return s.model_copy(update={"key_diagnoses": kept})

    steps = (shorter_overview, without_low_anomalies, without_historical, cut_overview,
             without_media, only_high_anomalies, only_active_diagnoses)  # fmt: skip
    for step in steps:
        if count_words(current) <= MAX_WORDS:
            return current
        current = step(current)
    # Last resort: halve the longest remaining text until the limit holds. It always
    # terminates because every field shrinks to a single word.
    while count_words(current) > MAX_WORDS:
        current = _halve_longest(current)
    return current


def _halve(text: str) -> str:
    words = text.split()
    return " ".join(words[: max(len(words) // 2, 1)]).rstrip(" ,;:.…") + "…"


def _halve_longest(s: ClinicalSummaryLLM) -> ClinicalSummaryLLM:
    fields: list[tuple[int, str, int]] = [(len(s.chief_concern.split()), "chief", 0)]
    fields += [(len(d.name.split()), "diagnosis", i) for i, d in enumerate(s.key_diagnoses)]
    fields += [
        (len(a.description.split()), "anomaly", i) for i, a in enumerate(s.flagged_anomalies)
    ]
    _, kind, index = max(fields)
    if kind == "chief":
        return s.model_copy(update={"chief_concern": _halve(s.chief_concern)})
    if kind == "diagnosis":
        items = list(s.key_diagnoses)
        items[index] = items[index].model_copy(update={"name": _halve(items[index].name)})
        return s.model_copy(update={"key_diagnoses": items})
    anomalies = list(s.flagged_anomalies)
    anomalies[index] = anomalies[index].model_copy(
        update={"description": _halve(anomalies[index].description)}
    )
    return s.model_copy(update={"flagged_anomalies": anomalies})


_BASE = {"high": 0.85, "medium": 0.65, "low": 0.40}


def score_confidence(
    self_reported: ConfidenceLevel,
    interventions: int,
    *,
    records: int,
    identity_conflict: bool,
    extractive: bool,
    bundle_has_errors: bool,
) -> Confidence:
    """Confidence math from docs/05 section 3.5 and docs/10 section 5."""
    reasons: list[str] = []
    score = _BASE[self_reported] - 0.10 * interventions
    if self_reported != "high":
        reasons.append(f"model reported {self_reported} confidence")
    if interventions:
        reasons.append(f"{interventions} guardrail intervention{'s' if interventions > 1 else ''}")
    if records < 2:  # noqa: PLR2004
        score = min(score, 0.40)
        reasons.append("fewer than 2 records")
    if identity_conflict:
        score = min(score, 0.40)
        reasons.append("identity conflict")
    if extractive:
        score = min(score, 0.50)
        reasons.append("offline extractive summary")
    if bundle_has_errors:
        score = min(score, 0.50)
        reasons.append("bundle has validation errors")
    score = round(min(max(score, 0.10), 0.95), 2)
    level: ConfidenceLevel = "high" if score >= 0.75 else "medium" if score >= 0.50 else "low"  # noqa: PLR2004
    rationale = "; ".join(reasons) or "records consistent; no guardrail interventions"
    return Confidence(
        level=level,
        score=score,
        rationale=_cut(rationale[:1].upper() + rationale[1:] + ".", MAX_RATIONALE),
    )
