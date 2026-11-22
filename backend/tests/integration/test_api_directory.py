"""GET /patients and GET /stats (docs/04 sections 4.3 and 6.1)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for

from ehr_mip.db.connection import connect
from ehr_mip.db.read_models import PatientReader, PatientRow

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client(api_store: Path) -> Iterator[TestClient]:
    with client_for(api_store) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def patients(api_store: Path) -> list[PatientRow]:
    with closing(connect(api_store / "ehr.db")) as conn:
        keys = [r[0] for r in conn.execute("SELECT patient_key FROM patients")]
        return list(PatientReader(conn).many(keys).values())


def listing(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/patients", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_pages_cover_every_patient_once(client: TestClient, patients: list[PatientRow]) -> None:
    first = listing(client)
    assert (first["page"], first["page_size"], first["total"], first["total_pages"]) == (
        1,
        25,
        60,
        3,
    )
    seen = [i["patient_key"] for n in (1, 2, 3) for i in listing(client, page=n)["items"]]
    assert len(seen) == 60
    assert set(seen) == {p.patient_key for p in patients}
    assert listing(client, page=4)["items"] == []


@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("field", ["mrn", "resource_count", "birth_date", "last_activity"])
def test_sorting_keeps_nulls_last(client: TestClient, field: str, order: str) -> None:
    values = [i[field] for i in listing(client, sort=field, order=order, page_size=100)["items"]]
    present = [v for v in values if v is not None]
    assert present == sorted(present, reverse=order == "desc")
    assert values[len(present) :] == [None] * (len(values) - len(present))


def test_search_by_displayed_name(client: TestClient, patients: list[PatientRow]) -> None:
    for patient in patients:
        if not patient.family_name:
            continue
        found = listing(client, q=patient.display_name, page_size=100)["items"]
        assert patient.patient_key in {i["patient_key"] for i in found}, patient.patient_key


def test_search_by_current_and_merged_mrn(client: TestClient, patients: list[PatientRow]) -> None:
    for patient in patients:
        for mrn in (patient.mrn, *patient.secondary_mrns):
            for query in (mrn, mrn.lstrip("0"), f"MRN {mrn}"):
                found = listing(client, q=query, page_size=100)["items"]
                assert patient.patient_key in {i["patient_key"] for i in found}, query


@pytest.mark.parametrize("query", ["%", "_", "\\", "' OR 1=1 --"])
def test_search_treats_wildcards_and_sql_as_text(client: TestClient, query: str) -> None:
    assert listing(client, q=query)["total"] == 0


def test_conflict_only(client: TestClient, patients: list[PatientRow]) -> None:
    items = listing(client, conflict_only=True, page_size=100)["items"]
    expected = {p.patient_key for p in patients if p.identity_conflict}
    assert {i["patient_key"] for i in items} == expected


def test_summary_columns_match_the_summary_endpoint(client: TestClient) -> None:
    for item in listing(client, page_size=5)["items"]:
        summary = client.get(f"/patients/{item['patient_key']}/summary").json()
        assert item["has_summary"] is True
        assert item["chief_concern"] == summary["chief_concern"]
        for severity, count in item["anomaly_counts"].items():
            flagged = summary["flagged_anomalies"]
            assert count == sum(a["severity"] == severity for a in flagged)


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 101}, {"sort": "phone"}, {"order": "up"}]
)
def test_bad_params_are_422(client: TestClient, params: dict[str, Any]) -> None:
    assert client.get("/patients", params=params).status_code == 422


def test_stats(client: TestClient) -> None:
    response = client.get("/stats")
    assert response.headers["cache-control"] == "max-age=5"
    body = response.json()
    ready = client.get("/ready").json()["counts"]
    assert body["patients"] == ready["patients"] == 60
    assert body["summaries"] == ready["summaries"] == 60
    assert sum(body["resources_by_type"].values()) == ready["resources"]
    by_type = body["resources_by_type"]
    assert body["searchable_records"] == (
        by_type["DocumentReference"] + by_type["DiagnosticReport"] + body["summaries"]
    )
