"""Deduplication (docs/05-ALGORITHMS.md section 1.5). Never across patients."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from itertools import combinations

from rapidfuzz import fuzz

from ehr_mip.ingestion.audit import Note
from ehr_mip.ingestion.cleaners.dates import NY
from ehr_mip.ingestion.cleaners.text import comparison_text
from ehr_mip.ingestion.models import CleanDocument, CleanLabResult, DocType

NEAR_DUPLICATE_RATIO = 97.0
MAX_DAYS_APART = 1


@dataclass(frozen=True, slots=True)
class Ordered:
    """A document or lab result with its read order (earlier source wins ties)."""

    order: int
    record_id: str


def _richness(doc: CleanDocument) -> int:
    return sum(
        (
            doc.encounter_key is not None,
            doc.document_date is not None,
            doc.author is not None,
            doc.doc_type is not DocType.SCANNED_DOCUMENT,
            bool(doc.title),
        )
    )


def _day(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(NY).date()
    return value


def _compatible(a: CleanDocument, b: CleanDocument) -> bool:
    types_ok = a.doc_type == b.doc_type or DocType.SCANNED_DOCUMENT in (a.doc_type, b.doc_type)
    day_a, day_b = _day(a.document_date), _day(b.document_date)
    if not types_ok or day_a is None or day_b is None:
        return False
    return abs((day_a - day_b).days) <= MAX_DAYS_APART


_Item = tuple[CleanDocument, Ordered]


def _best(group: list[_Item]) -> _Item:
    return max(group, key=lambda item: (_richness(item[0]), -item[1].order))


def _dropped(rule: str, message: str, item: _Item, best: _Item) -> tuple[str, str, Note]:
    note = Note(rule, "info", message, item[1].record_id, best[1].record_id)
    return item[1].record_id, item[0].patient_key, note


def _exact_pass(docs: list[_Item], notes: list[tuple[str, str, Note]]) -> list[_Item]:
    """Keep one document per content hash."""
    by_hash: dict[str, list[_Item]] = {}
    for item in docs:
        by_hash.setdefault(item[0].content_hash, []).append(item)
    survivors: list[_Item] = []
    for group in by_hash.values():
        best = _best(group)
        survivors.append(best)
        notes.extend(
            _dropped("dedupe.exact", "Exact duplicate removed; the richest copy was kept.", i, best)
            for i in group
            if i is not best
        )
    return sorted(survivors, key=lambda i: i[1].order)


def _near_pass(docs: list[_Item], notes: list[tuple[str, str, Note]]) -> list[_Item]:
    """Union documents that differ only in case and spacing (compatible type, close dates)."""
    parent = list(range(len(docs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    texts = [comparison_text(doc.text) for doc, _ in docs]
    for i, j in combinations(range(len(docs)), 2):
        if _compatible(docs[i][0], docs[j][0]) and (
            fuzz.ratio(texts[i], texts[j]) >= NEAR_DUPLICATE_RATIO
        ):
            parent[find(j)] = find(i)
    clusters: dict[int, list[_Item]] = {}
    for index, item in enumerate(docs):
        clusters.setdefault(find(index), []).append(item)
    kept: list[_Item] = []
    message = "Near duplicate (case or spacing only) removed; the richest copy was kept."
    for group in clusters.values():
        best = _best(group)
        kept.append(best)
        notes.extend(_dropped("dedupe.near", message, i, best) for i in group if i is not best)
    return kept


def dedupe_documents(
    items: list[_Item],
) -> tuple[list[_Item], list[tuple[str, str, Note]], int, int]:
    """Remove exact then near duplicates within each patient. Returns kept, notes, counts."""
    by_patient: dict[str, list[_Item]] = {}
    for item in sorted(items, key=lambda i: i[1].order):
        by_patient.setdefault(item[0].patient_key, []).append(item)
    exact_notes: list[tuple[str, str, Note]] = []
    near_notes: list[tuple[str, str, Note]] = []
    kept: list[_Item] = []
    for docs in by_patient.values():
        kept.extend(_near_pass(_exact_pass(docs, exact_notes), near_notes))
    kept.sort(key=lambda i: i[1].order)
    return kept, [*exact_notes, *near_notes], len(exact_notes), len(near_notes)


def dedupe_labs(
    items: list[tuple[CleanLabResult, Ordered]],
) -> tuple[list[tuple[CleanLabResult, Ordered]], list[tuple[str, str, Note]], int]:
    """Same patient, test, collection time and value (or the same result key): keep the first."""
    seen: dict[tuple[object, ...], Ordered] = {}
    by_result_key: dict[str, Ordered] = {}
    kept: list[tuple[CleanLabResult, Ordered]] = []
    notes: list[tuple[str, str, Note]] = []
    for lab, order in sorted(items, key=lambda i: i[1].order):
        # Without a collection time two equal values may be different draws: never merge those.
        key = (lab.patient_key, lab.loinc or lab.test_name, lab.collected_at, lab.value)
        first = (seen.get(key) if lab.collected_at is not None else None) or by_result_key.get(
            lab.result_key
        )
        if first is not None:
            notes.append(
                (
                    order.record_id,
                    lab.patient_key,
                    Note(
                        "dedupe.lab",
                        "info",
                        "Duplicate lab result removed; the first copy was kept.",
                        order.record_id,
                        first.record_id,
                    ),
                )
            )
            continue
        seen[key] = order
        by_result_key[lab.result_key] = order
        kept.append((lab, order))
    return kept, notes, len(notes)
