"""POST /search against the synthetic store (docs/04 section 5.1, FR-4.3, FR-4.4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for

from ehr_mip.api.schemas.search import SearchResponse
from ehr_mip.db.connection import connect

pytestmark = pytest.mark.integration
EXAMPLE = "worsening kidney function with high potassium"


@pytest.fixture(scope="module")
def client(api_store: Path) -> Iterator[TestClient]:
    with client_for(api_store) as test_client:
        yield test_client


def search(client: TestClient, query: str, **params: Any) -> Any:
    return client.post("/search", params=params, json={"query": query})


def _problem(response: Any, status: int, code: str, loc: str | None = None) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == code
    assert body["status"] == status
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["type"] == f"https://ehr-mip.local/problems/{code}"
    if loc:
        assert loc in [e["loc"] for e in body["errors"]]


def test_contract_example_request(client: TestClient) -> None:
    response = search(client, EXAMPLE, resource_type="DiagnosticReport", date_from="2024-06-01")
    assert response.status_code == 200
    body = SearchResponse.model_validate(response.json()).model_dump()
    assert set(response.json()) == {"query", "took_ms", "total", "mode", "filters", "results"}
    assert body["filters"] == {
        "resource_type": ["DiagnosticReport"],
        "date_from": "2024-06-01",
        "date_to": None,
        "patient_key": None,
    }
    results = body["results"]
    assert 0 < len(results) <= 5
    assert body["total"] == len(results)
    assert [r["rank"] for r in results] == list(range(1, len(results) + 1))
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert len({r["resource"]["resource_id"] for r in results}) == len(results)
    for result in results:
        assert result["resource"]["resource_type"] == "DiagnosticReport"
        assert result["resource"]["date"] >= "2024-06-01"
        assert result["resource"]["subtype"] in {"LAB", "RAD", "PAT"}
        assert 0 <= result["score"] <= 1
        assert len(result["snippet"]) <= 320
        for start, end in result["highlights"]:
            assert 0 <= start < end <= len(result["snippet"])
        assert result["patient"]["display_name"]
        assert len(result["patient"]["mrn"]) == 8
    assert "embed;dur=" in response.headers["server-timing"]
    assert "hydrate;dur=" in response.headers["server-timing"]
    assert response.headers["x-cache"] in {"HIT", "MISS"}


def test_semantic_search_finds_relevant_records(client: TestClient) -> None:
    results = search(client, "pulmonary embolism CT angiography").json()["results"]
    assert any("embol" in r["snippet"].lower() for r in results)
    assert all(r["match_type"] == "semantic" for r in results)


def test_hybrid_mode(client: TestClient) -> None:
    body = search(client, "potassium", mode="hybrid", top_k=10).json()
    assert body["mode"] == "hybrid"
    assert 0 < body["total"] <= 10
    assert {r["match_type"] for r in body["results"]} <= {"semantic", "lexical", "hybrid"}
    assert any(r["highlights"] for r in body["results"])


def test_resource_type_filter(client: TestClient) -> None:
    results = search(
        client, "chest", resource_type=["DocumentReference", "ClinicalSummary"], top_k=20
    ).json()["results"]
    assert results
    assert {r["resource"]["resource_type"] for r in results} <= {
        "DocumentReference",
        "ClinicalSummary",
    }
    summary = next(
        (r for r in results if r["resource"]["resource_type"] == "ClinicalSummary"), None
    )
    if summary:
        assert summary["resource"]["resource_id"] == f"summary:{summary['patient']['patient_key']}"
    # Observations are not indexed by default: a valid filter that matches nothing.
    assert search(client, "potassium", resource_type="Observation").json()["results"] == []


def test_date_range_inclusive_and_undated_excluded(api_store: Path, client: TestClient) -> None:
    with closing(connect(api_store / "ehr.db")) as conn:
        day = conn.execute(
            "SELECT resource_date FROM fhir_resources WHERE resource_type = 'DocumentReference' "
            "AND resource_date IS NOT NULL ORDER BY resource_date LIMIT 1"
        ).fetchone()[0]
    results = search(client, "note", date_from=day, date_to=day, top_k=20).json()["results"]
    assert results
    assert {r["resource"]["date"] for r in results} == {day}
    any_date = search(client, "note", date_from="1900-01-01", top_k=20).json()["results"]
    assert all(r["resource"]["date"] for r in any_date)  # undated records are excluded
    empty = search(client, "note", date_from="1900-01-01", date_to="1900-01-02")
    assert empty.status_code == 200
    assert (empty.json()["results"], empty.json()["total"]) == ([], 0)


def _mrns(store: Path) -> tuple[str, str, str]:
    with closing(connect(store / "ehr.db")) as conn:
        conn.row_factory = sqlite3.Row
        merged = conn.execute(
            "SELECT patient_key, mrn, json_extract(data_json, '$.secondary_mrns[0]') AS old "
            "FROM patients WHERE json_array_length(data_json, '$.secondary_mrns') > 0 LIMIT 1"
        ).fetchone()
    return merged["patient_key"], merged["mrn"], merged["old"]


def test_mrn_lookup(api_store: Path, client: TestClient) -> None:
    key, mrn, old = _mrns(api_store)
    for query in (f"MRN {mrn}", mrn.lstrip("0"), f"mrn:{old}"):
        results = search(client, query).json()["results"]
        assert results, query
        assert {r["patient"]["patient_key"] for r in results} == {key}
        assert all(r["match_type"] == "mrn" and r["score"] == 1.0 for r in results)
        dates = [r["resource"]["date"] or "" for r in results]
        assert dates == sorted(dates, reverse=True)  # newest first
    # Digits that match no patient fall back to a normal search.
    assert all(r["match_type"] != "mrn" for r in search(client, "99999999").json()["results"])


@pytest.mark.parametrize(
    ("query", "params", "loc"),
    [
        ("a", {}, "body.query"),
        ("   x   ", {}, "body.query"),
        ("x" * 501, {}, "body.query"),
        ("chest", {"date_from": "2024-06-02", "date_to": "2024-06-01"}, "query.date_to"),
        ("chest", {"date_from": "06/01/2024"}, "query.date_from"),
        ("chest", {"date_from": "2024-13-01"}, "query.date_from"),
        ("chest", {"resource_type": "Patient"}, "query.resource_type.0"),
        ("chest", {"top_k": 0}, "query.top_k"),
        ("chest", {"top_k": 21}, "query.top_k"),
        ("chest", {"mode": "fuzzy"}, "query.mode"),
        ("chest", {"patient_key": "not-a-uuid"}, "query.patient_key"),
    ],
)
def test_validation_errors(
    client: TestClient, query: str, params: dict[str, Any], loc: str
) -> None:
    _problem(search(client, query, **params), 422, "validation_error", loc)


def test_invalid_range_422_detail(client: TestClient) -> None:
    body = search(client, "chest", date_from="2024-06-02", date_to="2024-06-01").json()
    assert body["detail"] == "date_to must be on or after date_from"
    assert body["errors"] == [
        {
            "loc": "query.date_to",
            "type": "value_error",
            "message": "date_to must be on or after date_from",
        }
    ]


def test_body_shape_errors(client: TestClient) -> None:
    _problem(client.post("/search", json={"query": "chest", "extra": 1}), 422, "validation_error")
    _problem(
        client.post("/search", content=b"{not json", headers={"Content-Type": "application/json"}),
        422,
        "validation_error",
    )
    _problem(client.post("/search", json={}), 422, "validation_error", "body.query")


def test_patient_filter(api_store: Path, client: TestClient) -> None:
    key, _, _ = _mrns(api_store)
    results = search(client, "lab", patient_key=key, top_k=20).json()["results"]
    assert results
    assert {r["patient"]["patient_key"] for r in results} == {key}


def test_empty_index_is_503(tmp_path: Path, api_store: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    (root / "ehr.db").write_bytes((api_store / "ehr.db").read_bytes())
    with client_for(root) as empty:
        _problem(search(empty, "chest"), 503, "search_index_empty")


def test_embedder_failure_is_not_ready(api_store: Path) -> None:
    def broken(_: object) -> Any:
        raise OSError("model files missing")

    with client_for(api_store, embedder_factory=broken) as down:
        _problem(search(down, "chest"), 503, "not_ready")
        ready = down.get("/ready")
        assert ready.status_code == 503
        assert ready.json()["status"] == "not_ready"
        assert ready.json()["checks"]["embedder"] == {
            "ok": False,
            "detail": "OSError",
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        }
