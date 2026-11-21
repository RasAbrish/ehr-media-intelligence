"""Chroma collection swap: a reindex never breaks a reader holding the old handle."""

from __future__ import annotations

from pathlib import Path

from ehr_mip.search.chunker import Chunk
from ehr_mip.search.embedder import HashEmbedder
from ehr_mip.search.vector_store import COLLECTION, VectorStore, open_client


def _chunks(word: str, count: int) -> list[Chunk]:
    return [
        Chunk(patient_key="p", resource_id=f"{word}-{i}", resource_type="DocumentReference",
              subtype="progress_note", title="Note", date=None, chunk_index=0, text=f"{word} {i}")
        for i in range(count)
    ]  # fmt: skip


def _rebuild(store: VectorStore, chunks: list[Chunk]) -> None:
    store.rebuild(chunks, HashEmbedder().embed([c.text for c in chunks]))


def test_reader_survives_rebuild_by_another_store(tmp_path: Path) -> None:
    indexer = VectorStore(open_client(tmp_path))
    _rebuild(indexer, _chunks("first", 3))
    reader = VectorStore(open_client(tmp_path))  # the API's handle
    assert reader.count() == 3

    _rebuild(indexer, _chunks("second", 5))  # swaps the collection under the reader
    assert reader.count() == 5
    hits = reader.query(HashEmbedder().embed(["second 1"])[0], 2, None)
    assert hits[0].chunk_id == "second-1:0"
    assert {c.chunk_id.split("-")[0] for c in reader.all_chunks()} == {"second"}
    names = [c.name for c in open_client(tmp_path).list_collections()]
    assert names == [COLLECTION]  # the staging collection was renamed, not left behind


def test_rebuild_with_no_chunks_leaves_an_empty_collection(tmp_path: Path) -> None:
    store = VectorStore(open_client(tmp_path))
    _rebuild(store, _chunks("x", 2))
    _rebuild(store, [])
    assert store.count() == 0
