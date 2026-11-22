"""BM25 lexical index over chunk text plus patient name tokens (docs/05 section 4.2).

Names are not in the chunk text (they are scrubbed before embedding); they are only
added to this in-memory index so a clinician can find a patient by name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Plus  # type: ignore[import-untyped]

from ehr_mip.search.filters import SearchFilters
from ehr_mip.search.highlights import STOP_WORDS

_TOKEN = re.compile(r"[a-z0-9]+")
SUMMARY_TYPE = "ClinicalSummary"


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    text: str
    metadata: Mapping[str, Any]


class LexicalIndex:
    def __init__(
        self, chunks: Sequence[IndexedChunk], names: Mapping[str, str] | None = None
    ) -> None:
        """``names`` maps patient_key to the patient's name text (never stored on disk)."""
        self.chunks = list(chunks)
        self.by_id = {c.chunk_id: c for c in self.chunks}
        names = names or {}
        corpus = [
            tokenize(f"{c.text} {names.get(str(c.metadata['patient_key']), '')}")
            for c in self.chunks
        ]
        self._tokens = [set(tokens) for tokens in corpus]
        # BM25+ keeps a positive weight for terms found in many chunks (small corpora).
        self._bm25 = BM25Plus(corpus) if corpus else None

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, filters: SearchFilters, limit: int) -> list[str]:
        """Chunk ids that contain a query term, best first, after the same filters as Chroma."""
        terms = [t for t in tokenize(query) if t not in STOP_WORDS]
        if self._bm25 is None or not terms:
            return []
        wanted = set(terms)
        scores = self._bm25.get_scores(terms)
        ranked = sorted(
            (
                (float(score), chunk.chunk_id)
                for score, chunk, tokens in zip(scores, self.chunks, self._tokens, strict=True)
                if tokens & wanted and filters.matches(chunk.metadata)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        return [chunk_id for _, chunk_id in ranked[:limit]]

    def newest(self, query: str, filters: SearchFilters, limit: int) -> list[IndexedChunk]:
        """The newest records holding every query word (docs/05 section 4.2, newest order).

        Scans the whole index: a candidate pool cut by score could miss the newest match.
        AI summaries never match, because their date is the patient's latest record.
        Returns, per record, the chunk with the most query words (then the earliest).
        """
        wanted = {term for term in tokenize(query) if term not in STOP_WORDS}
        if not wanted:
            return []
        records: dict[str, list[tuple[set[str], IndexedChunk]]] = {}
        for chunk, tokens in zip(self.chunks, self._tokens, strict=True):
            if chunk.metadata["resource_type"] == SUMMARY_TYPE or not filters.matches(
                chunk.metadata
            ):
                continue
            records.setdefault(str(chunk.metadata["resource_id"]), []).append(
                (tokens & wanted, chunk)
            )
        matched = {
            record: min(parts, key=lambda p: (-len(p[0]), int(p[1].metadata["chunk_index"])))[1]
            for record, parts in records.items()
            if set().union(*(found for found, _ in parts)) == wanted
        }
        ordered = sorted(
            matched.items(), key=lambda item: (-int(item[1].metadata.get("date_ord") or 0), item[0])
        )
        return [chunk for _, chunk in ordered[:limit]]

    def for_patient(self, patient_keys: set[str], filters: SearchFilters) -> list[IndexedChunk]:
        return [
            c
            for c in self.chunks
            if c.metadata["patient_key"] in patient_keys and filters.matches(c.metadata)
        ]
