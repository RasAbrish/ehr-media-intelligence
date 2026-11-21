"""Scores, fusion and per-resource dedupe (docs/05-ALGORITHMS.md section 4.2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

RRF_K = 60
MatchType = Literal["semantic", "lexical", "hybrid", "mrn"]


@dataclass(frozen=True)
class Candidate:
    """A scored chunk before grouping by resource."""

    chunk_id: str
    resource_id: str
    date_ord: int
    score: float  # display score, 0..1
    semantic_score: float  # cosine similarity of this chunk, 0..1 (0 when lexical only)
    match_type: MatchType


def distance_to_score(distance: float) -> float:
    """Cosine distance (0..2) to a similarity clamped to 0..1."""
    return min(max(1.0 - distance, 0.0), 1.0)


def reciprocal_rank_fusion(
    semantic: Sequence[tuple[str, float]], lexical: Sequence[str], *, k: int = RRF_K
) -> dict[str, tuple[float, MatchType]]:
    """Fuse two ranked id lists: Σ 1 / (k + rank), rescaled so rank 1 in both lists is 1.0.

    ``semantic`` holds (chunk id, similarity) best first; ``lexical`` holds chunk ids
    best first.
    """
    fused: dict[str, float] = {}
    seen_in: dict[str, set[str]] = {}
    for source, ids in (("semantic", [i for i, _ in semantic]), ("lexical", list(lexical))):
        for rank, chunk_id in enumerate(ids, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
            seen_in.setdefault(chunk_id, set()).add(source)
    best = 2.0 / (k + 1)
    return {
        chunk_id: (
            round(min(value / best, 1.0), 4),
            _match_type(seen_in[chunk_id]),
        )
        for chunk_id, value in fused.items()
    }


def _match_type(sources: set[str]) -> MatchType:
    if len(sources) == 2:  # noqa: PLR2004
        return "hybrid"
    return "semantic" if "semantic" in sources else "lexical"


def best_per_resource(candidates: Sequence[Candidate]) -> list[Candidate]:
    """One candidate per resource (its best chunk), keeping the best semantic score seen."""
    best: dict[str, Candidate] = {}
    semantic: dict[str, float] = {}
    for candidate in candidates:
        semantic[candidate.resource_id] = max(
            semantic.get(candidate.resource_id, 0.0), candidate.semantic_score
        )
        current = best.get(candidate.resource_id)
        if current is None or candidate.score > current.score:
            best[candidate.resource_id] = candidate
    return [replace(c, semantic_score=semantic[c.resource_id]) for c in best.values()]


def rank(candidates: Sequence[Candidate], top_k: int) -> list[Candidate]:
    """Best chunk per resource, score descending, ties broken by the newer date."""
    grouped = best_per_resource(candidates)
    grouped.sort(key=lambda c: (-c.score, -c.date_ord, c.resource_id))
    return grouped[:top_k]
