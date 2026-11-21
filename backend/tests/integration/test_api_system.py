"""/health, /ready, /metrics, unknown routes and the search cache (FR-9.1, FR-9.3)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for, copy_store

from ehr_mip import __version__
from ehr_mip.api.schemas.system import ReadyResponse
from ehr_mip.db.connection import connect
from ehr_mip.search.embedder import HashEmbedder
from ehr_mip.search.indexer import run_index
from ehr_mip.search.vector_store import VectorStore, open_client

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client(api_store: Path) -> Iterator[TestClient]:
    with client_for(api_store) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "version": __version__}


def test_ready_without_api_key_is_degraded(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = ReadyResponse.model_validate(response.json())
    assert body.status == "degraded"  # extractive provider
    assert body.checks.sqlite.ok
    assert body.checks.sqlite.detail == "wal"
    assert body.checks.vector_store.chunks > 0
    assert body.checks.embedder.model == "hash-embedder"
    assert body.checks.llm.provider == "extractive"
    assert body.checks.llm.model is None
    assert body.counts.patients == 60
    assert body.counts.summaries == 60
    assert body.counts.chunks == body.checks.vector_store.chunks
    assert body.last_run is not None
    assert body.last_run.status == "succeeded"
    assert body.flags.cache_backend == "memory"
    assert body.cache.index_version == 1


def test_unknown_route_and_method(client: TestClient) -> None:
    missing = client.get("/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    wrong = client.get("/search")
    assert wrong.status_code == 405
    assert wrong.json()["code"] == "method_not_allowed"


def test_metrics_endpoint(client: TestClient) -> None:
    client.post("/search", json={"query": "metrics probe"})
    text = client.get("/metrics").text
    for series in (
        "http_requests_total",
        "http_request_duration_seconds",
        "search_latency_seconds",
        "cache_requests_total",
        "rate_limited_total",
    ):
        assert series in text


def test_search_cache_hit_and_index_version(tmp_path: Path, api_store: Path) -> None:
    store = copy_store(api_store, tmp_path / "store")
    with client_for(store) as fresh:
        query = {"query": "Shortness of breath"}
        first = fresh.post("/search", json=query)
        assert first.headers["x-cache"] == "MISS"
        again = fresh.post("/search", json={"query": "  shortness   of BREATH "})  # normalized
        assert again.headers["x-cache"] == "HIT"
        assert again.json()["results"] == first.json()["results"]
        other = fresh.post("/search", params={"top_k": 3}, json=query)
        assert other.headers["x-cache"] == "MISS"  # different parameters, different key

        with closing(connect(store / "ehr.db")) as conn:
            run_index(
                conn,
                VectorStore(open_client(store / "chroma")),
                HashEmbedder(),
                index_observations=False,
            )
        after = fresh.post("/search", json=query)
        assert after.headers["x-cache"] == "MISS"  # reindex bumped index_version
        assert fresh.get("/ready").json()["cache"]["index_version"] == 2
