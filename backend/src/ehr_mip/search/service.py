"""SearchService: MRN lookup, semantic or hybrid ranking, then hydration (docs/05 section 4.2).

``rank`` is CPU work (embedding, Chroma, BM25) and touches no database, so the API
runs it in a worker thread. Its output holds ids, scores and scrubbed snippets only;
``hydrate`` adds patient details from SQLite. That split keeps identifiers out of
the search cache.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import orjson

from ehr_mip.db.read_models import PatientReader, PatientRow, ResourceReader, StatusReader
from ehr_mip.errors import SearchIndexEmptyError
from ehr_mip.search.embedder import Embedder
from ehr_mip.search.filters import SearchFilters, SearchMode, SearchSort, build_where
from ehr_mip.search.highlights import highlight_ranges, query_terms, snippet
from ehr_mip.search.lexical import SUMMARY_TYPE, IndexedChunk, LexicalIndex
from ehr_mip.search.ranking import (
    Candidate,
    MatchType,
    distance_to_score,
    rank,
    reciprocal_rank_fusion,
)
from ehr_mip.search.vector_store import VectorStore

CANDIDATE_FACTOR = 6
SUMMARY_SNIPPET_CHARS = 160


@dataclass(frozen=True)
class RankedResult:
    """One ranked resource, free of patient identifiers (safe to cache)."""

    rank: int
    score: float
    semantic_score: float
    match_type: MatchType
    patient_key: str
    resource_id: str
    resource_type: str
    subtype: str
    title: str
    date: str  # YYYY-MM-DD or ""
    snippet: str
    highlights: list[tuple[int, int]]


@dataclass(frozen=True)
class SearchOutcome:
    results: list[RankedResult]
    timings: dict[str, float] = field(default_factory=dict)  # stage → milliseconds

    def to_bytes(self) -> bytes:
        return orjson.dumps([r.__dict__ for r in self.results])

    @classmethod
    def from_bytes(cls, payload: bytes) -> SearchOutcome:
        rows: list[dict[str, Any]] = orjson.loads(payload)
        return cls(
            results=[
                RankedResult(**{**r, "highlights": [tuple(h) for h in r["highlights"]]})
                for r in rows
            ]
        )


@dataclass(frozen=True)
class HydratedResult:
    ranked: RankedResult
    patient: PatientRow
    is_valid: bool
    summary_snippet: str | None


def _cut(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def normalize_query(query: str) -> str:
    return " ".join(query.split())


def cache_key(
    index_version: int,
    query: str,
    filters: SearchFilters,
    top_k: int,
    mode: SearchMode,
    mrn_patients: Sequence[str],
    sort: SearchSort,
) -> str:
    """``ehr-mip:search:{index_version}:{sha256}`` over the normalized request."""
    payload = orjson.dumps(
        {
            "q": normalize_query(query).lower(),
            "types": sorted(filters.resource_types),
            "from": filters.date_from.isoformat() if filters.date_from else None,
            "to": filters.date_to.isoformat() if filters.date_to else None,
            "patient": filters.patient_key,
            "top_k": top_k,
            "mode": mode,
            "mrn": sorted(mrn_patients),
            "sort": sort,
        }
    )
    return f"ehr-mip:search:{index_version}:{hashlib.sha256(payload).hexdigest()}"


class SearchService:
    def __init__(self, store: VectorStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder
        self._lexical = LexicalIndex([])
        self._version: int | None = None
        self._lock = threading.Lock()

    @property
    def index_version(self) -> int | None:
        return self._version

    def refresh(self, conn: sqlite3.Connection) -> int:
        """Reload Chroma and BM25 when another process rebuilt the index."""
        version = StatusReader(conn).index_version()
        if version != self._version:
            names = PatientReader(conn).name_index()
            with self._lock:
                self.store.reopen()
                self._lexical = LexicalIndex(self.store.all_chunks(), names)
                self._version = version
        return version

    def chunk_count(self) -> int:
        return self.store.count()

    def rank(
        self,
        query: str,
        filters: SearchFilters,
        *,
        top_k: int,
        mode: SearchMode,
        mrn_patients: Sequence[str] = (),
        sort: SearchSort = "relevance",
    ) -> SearchOutcome:
        if self.store.count() == 0:
            msg = "Nothing is indexed yet. Run `make pipeline`."
            raise SearchIndexEmptyError(msg)
        terms = query_terms(query)
        if mrn_patients:
            return SearchOutcome(self._by_mrn(set(mrn_patients), filters, top_k, sort))
        timings: dict[str, float] = {}
        started = time.perf_counter()
        if sort == "newest":
            with self._lock:
                found = self._lexical.newest(query, filters, top_k)
            timings["lexical"] = _ms(started)
            return SearchOutcome(
                [
                    self._result(position, 1.0, 0.0, "lexical", chunk, terms)
                    for position, chunk in enumerate(found, start=1)
                ],
                timings,
            )
        vector = self.embedder.embed([query])[0]
        timings["embed"] = _ms(started)

        started = time.perf_counter()
        hits = self.store.query(vector, top_k * CANDIDATE_FACTOR, build_where(filters))
        timings["vector"] = _ms(started)
        texts: dict[str, IndexedChunk] = {
            h.chunk_id: IndexedChunk(h.chunk_id, h.text, h.metadata) for h in hits
        }
        similarity = {h.chunk_id: distance_to_score(h.distance) for h in hits}

        if mode == "hybrid":
            started = time.perf_counter()
            with self._lock:
                lexical = self._lexical.search(query, filters, top_k * CANDIDATE_FACTOR)
                texts.update({i: self._lexical.by_id[i] for i in lexical if i not in texts})
            timings["lexical"] = _ms(started)
            fused = reciprocal_rank_fusion(list(similarity.items()), lexical)
            scored = {i: (score, kind) for i, (score, kind) in fused.items()}
        else:
            scored = {i: (round(s, 4), "semantic") for i, s in similarity.items()}

        candidates = [
            Candidate(
                chunk_id=chunk_id,
                resource_id=str(texts[chunk_id].metadata["resource_id"]),
                date_ord=int(texts[chunk_id].metadata.get("date_ord") or 0),
                score=score,
                semantic_score=round(similarity.get(chunk_id, 0.0), 4),
                match_type=kind,
            )
            for chunk_id, (score, kind) in scored.items()
        ]
        results = [
            self._result(
                position, c.score, c.semantic_score, c.match_type, texts[c.chunk_id], terms
            )
            for position, c in enumerate(rank(candidates, top_k), start=1)
        ]
        return SearchOutcome(results, timings)

    def _by_mrn(
        self, patients: set[str], filters: SearchFilters, top_k: int, sort: SearchSort
    ) -> list[RankedResult]:
        """Newest records of the patients the MRN names, score 1.0 (docs/05 section 4.2)."""
        with self._lock:
            chunks = self._lexical.for_patient(patients, filters)
        if sort == "newest":
            chunks = [c for c in chunks if c.metadata["resource_type"] != SUMMARY_TYPE]
        first: dict[str, IndexedChunk] = {}
        for chunk in sorted(chunks, key=lambda c: int(c.metadata["chunk_index"])):
            first.setdefault(str(chunk.metadata["resource_id"]), chunk)
        newest = sorted(
            first.values(),
            key=lambda c: (-int(c.metadata.get("date_ord") or 0), c.chunk_id),
        )[:top_k]
        return [
            self._result(position, 1.0, 0.0, "mrn", chunk, [])
            for position, chunk in enumerate(newest, start=1)
        ]

    @staticmethod
    def _result(
        position: int,
        score: float,
        semantic: float,
        match_type: MatchType,
        chunk: IndexedChunk,
        terms: list[str],
    ) -> RankedResult:
        meta = chunk.metadata
        text = snippet(chunk.text, terms)
        return RankedResult(
            rank=position,
            score=round(score, 4),
            semantic_score=round(semantic, 4),
            match_type=match_type,
            patient_key=str(meta["patient_key"]),
            resource_id=str(meta["resource_id"]),
            resource_type=str(meta["resource_type"]),
            subtype=str(meta.get("subtype") or ""),
            title=str(meta.get("title") or ""),
            date=str(meta.get("date") or ""),
            snippet=text,
            highlights=highlight_ranges(text, terms),
        )


def hydrate(conn: sqlite3.Connection, results: Sequence[RankedResult]) -> list[HydratedResult]:
    """Join patients, validity and summary snippets in a few IN queries."""
    keys = {r.patient_key for r in results}
    patients = PatientReader(conn).many(keys)
    issues = ResourceReader(conn).issues(r.resource_id for r in results)
    concerns = StatusReader(conn).chief_concerns(keys)
    hydrated = []
    for result in results:
        patient = patients.get(result.patient_key)
        if patient is None:  # deleted since indexing: skip rather than fail
            continue
        errors = [i for i in issues.get(result.resource_id, []) if i.severity == "error"]
        concern = concerns.get(result.patient_key)
        hydrated.append(
            HydratedResult(
                ranked=result,
                patient=patient,
                is_valid=not errors,
                summary_snippet=_cut(concern, SUMMARY_SNIPPET_CHARS) if concern else None,
            )
        )
    return hydrated


def parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)
