"""Search filters and the Chroma where clause (docs/05-ALGORITHMS.md section 4.3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

SearchableType = Literal["DocumentReference", "DiagnosticReport", "Observation", "ClinicalSummary"]
SearchMode = Literal["semantic", "hybrid"]


@dataclass(frozen=True)
class SearchFilters:
    resource_types: tuple[SearchableType, ...] = ()
    date_from: date | None = None
    date_to: date | None = None
    patient_key: str | None = None

    @property
    def has_date(self) -> bool:
        return self.date_from is not None or self.date_to is not None

    def matches(self, metadata: Mapping[str, Any]) -> bool:
        """The same rules as :func:`build_where`, for filtering in Python (lexical, MRN)."""
        if self.resource_types and metadata["resource_type"] not in self.resource_types:
            return False
        if self.patient_key and metadata["patient_key"] != self.patient_key:
            return False
        ordinal = int(metadata.get("date_ord") or 0)
        if self.has_date and ordinal <= 0:
            return False
        if self.date_from and ordinal < self.date_from.toordinal():
            return False
        return not (self.date_to and ordinal > self.date_to.toordinal())


def build_where(filters: SearchFilters) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if filters.resource_types:
        clauses.append({"resource_type": {"$in": list(filters.resource_types)}})
    if filters.patient_key:
        clauses.append({"patient_key": filters.patient_key})
    if filters.date_from:
        clauses.append({"date_ord": {"$gte": filters.date_from.toordinal()}})
    if filters.date_to:
        clauses.append({"date_ord": {"$lte": filters.date_to.toordinal()}})
    if filters.has_date:
        clauses.append({"date_ord": {"$gt": 0}})
    if not clauses:
        return None
    # Chroma rejects $and with fewer than two items.
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}
