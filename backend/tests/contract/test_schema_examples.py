"""The Pydantic schemas accept the docs/04 examples (the Zod side has the same test)."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from ehr_mip.api.schemas.patients import (
    PatientListItem,
    SummaryFeedbackRequest,
    SummaryFeedbackResponse,
)
from ehr_mip.api.schemas.quality import AuditEntryItem, Page, QualityOverview
from ehr_mip.api.schemas.system import StatsResponse
from ehr_mip.config import PROJECT_ROOT

FIXTURES = PROJECT_ROOT / "frontend" / "src" / "test" / "fixtures" / "contract"


@pytest.mark.parametrize(
    ("example", "schema"),
    [
        ("4.3-1", StatsResponse),
        ("6.1-1", Page[PatientListItem]),
        ("6.8-1", AuditEntryItem),
        ("8.1-1", QualityOverview),
        ("9a.1-1", SummaryFeedbackRequest),
        ("9a.1-2", SummaryFeedbackResponse),
    ],
)
def test_example_round_trips(example: str, schema: type[BaseModel]) -> None:
    data = json.loads((FIXTURES / f"{example}.json").read_text(encoding="utf-8"))
    assert schema.model_validate(data).model_dump(mode="json") == data
