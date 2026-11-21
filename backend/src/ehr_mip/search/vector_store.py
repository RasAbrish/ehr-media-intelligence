"""Chroma collection ``ehr_records`` (docs/03-DATA-MODEL.md section 7).

Chroma runs in-process through ``PersistentClient`` only: no Chroma server or HTTP
client exists, which is why the server-side advisories in docs/09 section 8.1 do
not apply. Vectors always come from our own Embedder.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.collection_configuration import CreateCollectionConfiguration
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError

from ehr_mip.search.chunker import Chunk
from ehr_mip.search.lexical import IndexedChunk

COLLECTION = "ehr_records"
_NEXT = f"{COLLECTION}_next"
_BATCH = 512
_RETRIES = 3
_SPACE: CreateCollectionConfiguration = {"hnsw": {"space": "cosine"}}


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float


def open_client(path: Path) -> ClientAPI:
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(path),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )


class VectorStore:
    def __init__(self, client: ClientAPI) -> None:
        self._client = client
        self._collection: Any = None
        self.reopen()

    def reopen(self) -> None:
        """Pick up a collection rebuilt by another process (``ehr-mip index``)."""
        self._collection = self._client.get_or_create_collection(
            COLLECTION, configuration=_SPACE, embedding_function=None
        )

    def rebuild(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        """Build the new index next to the live one, then swap it in by renaming.

        Readers keep the old collection until the swap, and a reader whose handle went
        stale reopens and retries (:meth:`_retry`), so a reindex never empties search.
        """
        existing = {c.name for c in self._client.list_collections()}
        if _NEXT in existing:
            self._client.delete_collection(_NEXT)
        staging = self._client.create_collection(
            _NEXT, configuration=_SPACE, embedding_function=None
        )
        for start in range(0, len(chunks), _BATCH):
            batch = chunks[start : start + _BATCH]
            staging.add(
                ids=[c.id for c in batch],
                embeddings=cast("Any", [list(v) for v in vectors[start : start + _BATCH]]),
                documents=[c.text for c in batch],
                metadatas=[c.metadata for c in batch],
            )
        if COLLECTION in existing:
            self._client.delete_collection(COLLECTION)
        staging.modify(name=COLLECTION)
        self._collection = self._client.get_collection(COLLECTION, embedding_function=None)

    def _retry(self, operation: Callable[[], Any]) -> Any:
        """Run ``operation``; if another process swapped the collection, reopen and retry."""
        for attempt in range(_RETRIES):
            try:
                return operation()
            except NotFoundError:
                if attempt == _RETRIES - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
                try:
                    self._collection = self._client.get_collection(
                        COLLECTION, embedding_function=None
                    )
                except NotFoundError:
                    continue
        return None  # unreachable: the last attempt returns or raises

    def count(self) -> int:
        # The lambda re-reads self._collection, which _retry may replace.
        return int(self._retry(lambda: self._collection.count()))  # noqa: PLW0108

    def query(
        self, vector: Sequence[float], n_results: int, where: dict[str, Any] | None
    ) -> list[VectorHit]:
        if n_results <= 0:
            return []
        result = self._retry(
            lambda: self._collection.query(
                query_embeddings=[list(vector)],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        )
        ids = result["ids"][0]
        documents = cast("list[str]", (result["documents"] or [[]])[0])
        metadatas = cast("list[dict[str, Any]]", (result["metadatas"] or [[]])[0])
        distances = cast("list[float]", (result["distances"] or [[]])[0])
        return [
            VectorHit(chunk_id=i, text=d, metadata=dict(m), distance=float(dist))
            for i, d, m, dist in zip(ids, documents, metadatas, distances, strict=True)
        ]

    def all_chunks(self) -> list[IndexedChunk]:
        """Every stored chunk (text and metadata) for the lexical index."""
        result = self._retry(lambda: self._collection.get(include=["documents", "metadatas"]))
        documents = cast("list[str]", result["documents"] or [])
        metadatas = cast("list[dict[str, Any]]", result["metadatas"] or [])
        return [
            IndexedChunk(chunk_id=i, text=d, metadata=dict(m))
            for i, d, m in zip(result["ids"], documents, metadatas, strict=True)
        ]
