"""``POST /search`` (docs/04 section 5.1)."""

from __future__ import annotations

from pydantic import Field, field_validator

from ehr_mip.api.schemas.common import (
    ApiModel,
    MatchType,
    PatientRef,
    ResourceRef,
    SearchableType,
    SearchMode,
)

QUERY_MIN, QUERY_MAX = 2, 500


class SearchRequest(ApiModel):
    query: str = Field(description="Free text, trimmed; 2 to 500 characters after trimming.")

    @field_validator("query")
    @classmethod
    def _trimmed_length(cls, value: str) -> str:
        value = value.strip()
        if not QUERY_MIN <= len(value) <= QUERY_MAX:
            msg = f"query must be {QUERY_MIN} to {QUERY_MAX} characters after trimming"
            raise ValueError(msg)
        return value


class AppliedFilters(ApiModel):
    resource_type: list[SearchableType]
    date_from: str | None
    date_to: str | None
    patient_key: str | None


class SearchResult(ApiModel):
    rank: int
    score: float
    semantic_score: float
    match_type: MatchType
    patient: PatientRef
    resource: ResourceRef
    snippet: str
    highlights: list[tuple[int, int]]
    summary_snippet: str | None


class SearchResponse(ApiModel):
    query: str
    took_ms: int
    total: int
    mode: SearchMode
    filters: AppliedFilters
    results: list[SearchResult]
