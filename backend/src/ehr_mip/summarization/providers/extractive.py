"""Extractive provider: an offline summary built only from text in the records (ADR-006).

Works on the same de-identified text the model would see, so both providers obey
the same privacy rules. It never writes a diagnosis that is not in a record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ehr_mip.summarization.context import identifier_scrubber, scrub
from ehr_mip.summarization.dictionary import Mention, find_concepts
from ehr_mip.summarization.providers.base import ProviderResult, SummaryRequest
from ehr_mip.summarization.records import SourceRecord
from ehr_mip.summarization.schemas import (
    MAX_FINDING,
    MAX_ITEMS,
    NOT_DOCUMENTED,
    ClinicalSummaryLLM,
    Diagnosis,
    DiagnosisStatus,
    EvidenceRef,
    MediaRecord,
    SummaryProvider,
)

# Only the section name is case-insensitive; the next header must be upper case.
_SECTION = r"(?m)^(?i:{name})\s*:\s*(?P<body>.+?)(?=^[A-Z][A-Z /&-]*:|\Z)"
_CLASS_WORDS = {"IMP": "inpatient", "AMB": "outpatient", "EMER": "emergency", "VR": "virtual"}
MAX_EVIDENCE = 3
TOP_DIAGNOSES_IN_OVERVIEW = 3


def _section(text: str, *names: str) -> str | None:
    for name in names:
        match = re.search(_SECTION.format(name=name), text, re.DOTALL)
        if match:
            body = " ".join(match["body"].split())
            if body:
                return body
    return None


def _first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return (match.group(1) if match else text).strip()


def _when(record: SourceRecord) -> date:
    return record.when or date.min


@dataclass
class ExtractiveProvider:
    name: str = "extractive"
    kind: SummaryProvider = "extractive"
    model: str | None = None
    can_shorten: bool = False

    async def summarize(self, request: SummaryRequest) -> ProviderResult:
        return ProviderResult(self.build(request), attempts=1)

    async def shorten(
        self, request: SummaryRequest, previous: ClinicalSummaryLLM, words: int
    ) -> ProviderResult:
        return ProviderResult(previous)

    def build(self, request: SummaryRequest) -> ClinicalSummaryLLM:
        view = request.view
        rules = identifier_scrubber(view.patient)
        records = sorted(view.records, key=lambda r: (_when(r), r.ref.key), reverse=True)
        texts = {r.ref.key: scrub(f"{r.title}\n{r.text}", rules) for r in records}
        notes = [r for r in records if r.kind == "note"]
        reports = [r for r in records if r.kind in {"imaging", "pathology"}]

        chief = None
        for record in notes:
            assessment = _section(texts[record.ref.key], "ASSESSMENT")
            if assessment:
                chief = _first_sentence(assessment)
                break
        if chief is None:
            for record in reports:
                impression = _section(texts[record.ref.key], "IMPRESSION", "DIAGNOSIS")
                if impression:
                    chief = _first_sentence(impression)
                    break

        # Diagnoses: concepts written in notes and reports, newest mention first.
        mentions: dict[str, list[tuple[SourceRecord, Mention]]] = {}
        for record in [*notes, *reports]:
            for canonical, mention in find_concepts(texts[record.ref.key]).items():
                mentions.setdefault(canonical, []).append((record, mention))
        all_text = "\n".join(texts.values()).lower()
        newest_note = notes[0].ref.key if notes else None
        ranked = sorted(
            mentions.items(), key=lambda kv: (_when(kv[1][0][0]), len(kv[1])), reverse=True
        )
        diagnoses = []
        for canonical, hits in ranked[:MAX_ITEMS]:
            surface = hits[0][1].surface
            name = canonical if canonical.lower() in all_text else surface[:1].upper() + surface[1:]
            affirmed = [record for record, m in hits if m.certainty == "affirmed"]
            status: DiagnosisStatus = (
                "suspected"
                if not affirmed
                else "active"
                if any(r.ref.key == newest_note for r in affirmed)
                else "historical"
            )
            diagnoses.append(
                Diagnosis(
                    name=name,
                    status=status,
                    evidence=[_ref(record) for record, _ in hits[:MAX_EVIDENCE]],
                )
            )

        media = []
        for record in [r for r in records if r.kind != "note"][:MAX_ITEMS]:
            finding = (
                record.conclusion or _section(texts[record.ref.key], "IMPRESSION") or record.title
            )
            media.append(
                MediaRecord(
                    resource=_ref(record),
                    kind=record.kind,
                    date=record.when,
                    finding=scrub(f"{record.title}: {finding}", rules)[:MAX_FINDING],
                )
            )

        return ClinicalSummaryLLM(
            chief_concern=chief or NOT_DOCUMENTED,
            key_diagnoses=diagnoses,
            recent_media=media,
            flagged_anomalies=list(request.anomalies[:MAX_ITEMS]),
            overview=self._overview(request, diagnoses),
            self_reported_confidence="low",
        )

    @staticmethod
    def _overview(request: SummaryRequest, diagnoses: list[Diagnosis]) -> str:
        context = request.context
        sex = {"female": "female", "male": "male"}.get(context.sex, "patient")
        who = f"{context.age}-year-old {sex}" if context.age is not None else sex.capitalize()
        top = diagnoses[:TOP_DIAGNOSES_IN_OVERVIEW]
        conditions = ", ".join(_condition(d) for d in top) if top else "no documented diagnoses"
        encounters = [e for e in request.view.encounters if e.start]
        if encounters:
            latest = max(encounters, key=lambda e: e.start or date.min)
            visit = (
                f"latest encounter {latest.start.isoformat() if latest.start else 'undated'} "
                f"({_CLASS_WORDS.get(latest.encounter_class, 'unknown type')})"
            )
        else:
            visit = "no encounter on record"
        return f"{who} with {conditions}; {visit}."


def _condition(diagnosis: Diagnosis) -> str:
    """A diagnosis as the overview words it: a suspected one is never stated as fact."""
    name = diagnosis.name[:1].lower() + diagnosis.name[1:]
    return f"suspected {name}" if diagnosis.status == "suspected" else name


def _ref(record: SourceRecord) -> EvidenceRef:
    return EvidenceRef(resource_type=record.ref.resource_type, resource_id=record.ref.resource_id)
