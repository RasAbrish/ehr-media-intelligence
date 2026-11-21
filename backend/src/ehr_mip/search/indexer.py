"""``ehr-mip index``: rebuild the vector index from SQLite (FR-4.1, FR-4.2).

Indexes DocumentReference and DiagnosticReport text (Observations when
``INDEX_OBSERVATIONS`` is on) and each patient's newest summary for the current
bundle. A full rebuild every run keeps it idempotent; the finished ``index`` run
bumps ``index_version``, which invalidates search caches.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import structlog

from ehr_mip.db.read_models import ResourceReader
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.fhir.store import BundleStore
from ehr_mip.search.chunker import Chunk, ResourceText, Rules, chunk_resource, chunk_summary
from ehr_mip.search.embedder import Embedder
from ehr_mip.search.vector_store import VectorStore
from ehr_mip.summarization.cache import SummaryCache
from ehr_mip.summarization.context import identifier_scrubber
from ehr_mip.summarization.records import read_bundle

log = structlog.get_logger(__name__)
EMBED_BATCH = 256


@dataclass(frozen=True)
class IndexStats:
    chunks: int
    resources: int
    summaries: int
    by_type: dict[str, int]


def searchable_types(*, index_observations: bool) -> tuple[str, ...]:
    base = ("DocumentReference", "DiagnosticReport")
    return (*base, "Observation") if index_observations else base


def build_chunks(conn: sqlite3.Connection, *, index_observations: bool) -> list[Chunk]:
    store = BundleStore(conn)
    cache = SummaryCache(conn)
    rules: dict[str, Rules] = {}
    chunks: list[Chunk] = []
    for patient_key in store.patient_keys():
        loaded = store.load_with_meta(patient_key)
        if loaded is None:
            continue
        bundle, bundle_hash, _ = loaded
        view = read_bundle(bundle)
        rules[patient_key] = identifier_scrubber(view.patient)
        summary = cache.latest(patient_key, bundle_hash)
        if summary is not None:
            chunks += chunk_summary(summary, rules[patient_key], view.latest_date())
    for row in ResourceReader(conn).searchable(
        searchable_types(index_observations=index_observations)
    ):
        text = ResourceText(
            patient_key=row.patient_key,
            resource_id=row.resource_id,
            resource_type=row.resource_type,
            subtype=row.subtype,
            title=row.title,
            date=row.date,
            text=row.text,
        )
        chunks += chunk_resource(text, rules.get(row.patient_key, []))
    return chunks


def run_index(
    conn: sqlite3.Connection,
    vector_store: VectorStore,
    embedder: Embedder,
    *,
    index_observations: bool,
) -> IndexStats:
    runs = PipelineRunRepository(conn)
    run_id = runs.start("index")
    chunks = build_chunks(conn, index_observations=index_observations)
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        vectors += embedder.embed([c.text for c in chunks[start : start + EMBED_BATCH]])
    vector_store.rebuild(chunks, vectors)
    by_type: dict[str, int] = {}
    for chunk in chunks:
        if chunk.chunk_index == 0:
            by_type[chunk.resource_type] = by_type.get(chunk.resource_type, 0) + 1
    stats = IndexStats(
        chunks=len(chunks),
        resources=sum(n for t, n in by_type.items() if t != "ClinicalSummary"),
        summaries=by_type.get("ClinicalSummary", 0),
        by_type=by_type,
    )
    runs.finish(
        run_id,
        {
            "chunks": stats.chunks,
            "resources": stats.resources,
            "summaries": stats.summaries,
            "model": embedder.model_name,
        },
    )
    log.info("index_built", chunks=stats.chunks, resources=stats.resources)
    return stats
