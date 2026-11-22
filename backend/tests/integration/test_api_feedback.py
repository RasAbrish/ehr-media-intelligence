"""POST /patients/{key}/summary/feedback (docs/04 section 9a.1, FR-7.5)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for, copy_store

from ehr_mip.db.connection import connect

pytestmark = pytest.mark.integration


@pytest.fixture
def store(tmp_path: Path, api_store: Path) -> Path:
    return copy_store(api_store, tmp_path / "store")


@pytest.fixture
def client(store: Path) -> Iterator[TestClient]:
    with client_for(store) as test_client:
        yield test_client


@pytest.fixture
def target(client: TestClient) -> tuple[str, str]:
    key = client.get("/patients").json()["items"][0]["patient_key"]
    return key, client.get(f"/patients/{key}/summary").json()["cache_key"]


def vote(client: TestClient, key: str, client_id: str | None = None, **body: Any) -> Any:
    payload = {"rating": "helpful", "reason": None, "comment": None, **body}
    headers = {"X-Client-Id": client_id} if client_id else {}
    return client.post(f"/patients/{key}/summary/feedback", json=payload, headers=headers)


def test_created_with_totals_and_overview(client: TestClient, target: tuple[str, str]) -> None:
    key, cache_key = target
    assert vote(client, key, str(uuid.uuid4()), cache_key=cache_key).status_code == 201
    second = vote(client, key, str(uuid.uuid4()), cache_key=cache_key, rating="not_helpful",
                  reason="too_long")  # fmt: skip
    assert second.status_code == 201
    assert second.json()["totals"] == {"helpful": 1, "not_helpful": 1}
    feedback = client.get("/quality/overview").json()["summaries"]["feedback"]
    assert feedback["helpful_rate"] == 0.5
    assert feedback["by_prompt_version"] == [
        {"prompt_version": "v1", "helpful_rate": 0.5, "votes": 2}
    ]


def test_duplicate_is_409_and_client_id_is_hashed(
    client: TestClient, store: Path, target: tuple[str, str]
) -> None:
    key, cache_key = target
    browser = str(uuid.uuid4())
    assert vote(client, key, browser, cache_key=cache_key).status_code == 201
    again = vote(client, key, browser, cache_key=cache_key)
    assert again.status_code == 409
    assert again.json()["code"] == "feedback_duplicate"
    with closing(connect(store / "ehr.db")) as conn:
        rows = [tuple(r) for r in conn.execute("SELECT * FROM summary_feedback")]
    assert len(rows) == 1
    assert browser not in str(rows)


@pytest.mark.parametrize(
    ("change", "loc"),
    [
        ({"rating": "not_helpful"}, "body.reason"),
        ({"cache_key": "unknown"}, "body.cache_key"),
        ({"comment": "x" * 281}, "body.comment"),
    ],
)
def test_rules_are_422(
    client: TestClient, target: tuple[str, str], change: dict[str, Any], loc: str
) -> None:
    key, cache_key = target
    response = vote(client, key, **{"cache_key": cache_key, **change})
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == loc


def test_cache_key_of_another_patient_is_422(client: TestClient, target: tuple[str, str]) -> None:
    other = client.get("/patients").json()["items"][1]["patient_key"]
    assert vote(client, other, cache_key=target[1]).status_code == 422


def test_unknown_patient_is_404(client: TestClient) -> None:
    response = vote(client, str(uuid.uuid4()), cache_key="any")
    assert response.json()["code"] == "patient_not_found"


def test_disabled_flag_is_enforced(store: Path) -> None:
    with client_for(store, feedback_enabled=False) as off:
        key = off.get("/patients").json()["items"][0]["patient_key"]
        cache_key = off.get(f"/patients/{key}/summary").json()["cache_key"]
        response = vote(off, key, cache_key=cache_key)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_rate_limited_at_20_per_minute(store: Path) -> None:
    with client_for(store, rate_limit_enabled=True) as limited:
        key = str(uuid.uuid4())
        statuses = [vote(limited, key, cache_key="any").status_code for _ in range(21)]
    assert statuses == [404] * 20 + [429]
