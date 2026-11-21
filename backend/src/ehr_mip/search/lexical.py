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

    def for_patient(self, patient_keys: set[str], filters: SearchFilters) -> list[IndexedChunk]:
        return [
            c
            for c in self.chunks
            if c.metadata["patient_key"] in patient_keys and filters.matches(c.metadata)
        ]
