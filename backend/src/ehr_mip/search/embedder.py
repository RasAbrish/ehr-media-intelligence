"""Text embedders. The app uses all-MiniLM-L6-v2; tests use a deterministic hash embedder."""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

DIMENSIONS = 384
_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """L2-normalized vectors, one per text."""
        ...


class SentenceTransformerEmbedder:
    """all-MiniLM-L6-v2 on CPU. Loading is slow, so it happens once and is then warmed."""

    def __init__(self, model_name: str, cache_dir: Path, *, batch_size: int = 64) -> None:
        os.environ.setdefault("HF_HOME", str(cache_dir))
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415 (slow import)

        self._name = model_name
        self._batch_size = batch_size
        try:  # cached model: no network call at all
            self._model: SentenceTransformer = SentenceTransformer(
                model_name, cache_folder=str(cache_dir), device="cpu", local_files_only=True
            )
        except OSError:  # first run: download into cache_dir
            self._model = SentenceTransformer(model_name, cache_folder=str(cache_dir), device="cpu")
        self.embed(["warm up"])

    @property
    def model_name(self) -> str:
        return self._name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in row] for row in vectors]


class HashEmbedder:
    """Bag of hashed tokens: texts sharing words get similar vectors. Tests only."""

    model_name = "hash-embedder"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * DIMENSIONS
            for token in _TOKEN.findall(text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=4).digest()
                vector[int.from_bytes(digest, "big") % DIMENSIONS] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors
