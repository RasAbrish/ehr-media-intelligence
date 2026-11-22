"""Data quality endpoints and their PHI masking (docs/04 sections 6.8 and 8, FR-6.4)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for

from ehr_mip.db.connection import connect
from ehr_mip.db.read_models import PatientReader

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client(api_store: Path) -> Iterator[TestClient]:
    with client_for(api_store) as test_client:
        yield test_client


def every_item(client: TestClient, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.get(path, params={"page": page, "page_size": 100})
        assert response.status_code == 200, response.text
        body = response.json()
        items += body["items"]
        if page >= body["total_pages"]:
            assert len(items) == body["total"]
            return items
        page += 1


def test_audit_and_quarantine_leak_no_identifiers(client: TestClient, api_store: Path) -> None:
    with closing(connect(api_store / "ehr.db")) as conn:
        keys = [r[0] for r in conn.execute("SELECT patient_key FROM patients")]
        patients = list(PatientReader(conn).many(keys).values())
    names = {
        part.lower()
        for p in patients
        for part in (p.family_name, *p.given_names)
        if part and len(part) > 2
    }
    births = {p.birth_date.isoformat() for p in patients if p.birth_date}
    phones = {re.sub(r"\D", "", p.phone)[-10:] for p in patients if p.phone}

    leaks: dict[tuple[str, str, str], int] = {}
    for item in every_item(client, "/quality/audit"):
        for column in ("before", "after", "message", "record_id"):
            value = str(item[column] or "")
            if column in {"record_id", "before", "after"}:
                value = value.replace("chest_x_ray", "")  # file name term; "Ray" is also a name
            words = set(re.findall(r"[a-z]+", value.lower()))
            dob = value in births and item["field"] not in {"date", "start", "end", "collected_at"}
            phone = re.sub(r"\D", "", value)[-10:] in phones
            if words & names or dob or phone:
                key = (item["rule"], str(item["field"]), column)
                leaks[key] = leaks.get(key, 0) + 1
    assert leaks == {}

    previews = " ".join(i["payload_preview"] for i in every_item(client, "/quality/quarantine"))
    assert not set(re.findall(r"[a-z]+", previews.lower())) & names
    assert not [b for b in births if b in previews]


def test_name_and_dob_values_are_masked(client: TestClient) -> None:
    items = every_item(client, "/quality/audit")
    for item in items:
        for value in (item["before"], item["after"]):
            if not value:
                continue
            if item["field"] == "name":
                assert all(set(w[1:]) <= {"*"} for w in re.findall(r"[^\W\d_][\w*]*", value))
            if item["field"] == "dob":
                # Century and day of an ISO date, or nothing but separators.
                assert re.fullmatch(r"\d\d\*\*-\*\*-\d\d|[^\dA-Za-z]+", value), item["id"]


def test_quarantine_preview_is_bounded(client: TestClient) -> None:
    items = every_item(client, "/quality/quarantine")
    assert items
    assert all(len(i["payload_preview"]) <= 200 for i in items)
    assert "1971-05-20" not in str(items)


def test_audit_filters(client: TestClient) -> None:
    rules = client.get("/quality/audit", params={"rule": "date.", "page_size": 100}).json()
    assert rules["items"]
    assert all(i["rule"].startswith("date.") for i in rules["items"])
    for name, value in (("stage", "identity"), ("severity", "error")):
        items = client.get("/quality/audit", params={name: value}).json()["items"]
        assert items
        assert {i[name] for i in items} == {value}
    assert client.get("/quality/audit", params={"rule": "%"}).json()["total"] == 0


def test_patient_audit(client: TestClient) -> None:
    entry = next(i for i in every_item(client, "/quality/audit") if i["patient"])
    key = entry["patient"]["patient_key"]
    scoped = client.get("/quality/audit", params={"patient_key": key, "page_size": 100}).json()
    own = client.get(f"/patients/{key}/audit", params={"page_size": 100}).json()
    assert own["total"] == scoped["total"] > 0
    assert "patient" not in own["items"][0]
    info = client.get(f"/patients/{key}/audit", params={"severity": "info"}).json()
    assert {i["severity"] for i in info["items"]} == {"info"}
    assert client.get(f"/patients/{uuid.uuid4()}/audit").status_code == 404
    assert client.get("/patients/nope/audit").status_code == 422


def test_validation_issues(client: TestClient) -> None:
    items = every_item(client, "/quality/validation")
    assert items
    for name in ("severity", "code"):
        value = items[0][name]
        found = client.get("/quality/validation", params={name: value, "page_size": 100}).json()
        assert found["total"] == sum(i[name] == value for i in items)
    # The contract types this filter as ResourceType, which has no "Bundle".
    assert client.get("/quality/validation", params={"resource_type": "Bundle"}).status_code == 422


def test_overview_counts_equal_repository_counts(client: TestClient, api_store: Path) -> None:
    body = client.get("/quality/overview").json()
    with closing(connect(api_store / "ehr.db")) as conn:

        def count(table: str) -> int:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: S608

        ingestion, validation = body["ingestion"], body["validation"]
        assert ingestion["patients"] == count("patients")
        assert ingestion["documents"] == count("documents")
        assert ingestion["lab_results"] == count("lab_results")
        assert ingestion["quarantined"] == count("quarantine")
        assert sum(ingestion["audit_by_severity"].values()) == count("audit_log")
        assert validation["bundles"] == count("fhir_bundles")
        assert sum(validation["issues_by_severity"].values()) == count("validation_issues")
    assert ingestion["records_read"] == sum(ingestion["by_format"].values()) > 0
    assert len(ingestion["top_rules"]) == 8
    assert body["summaries"]["by_provider"] == {"anthropic": 0, "extractive": 60}
    assert body["summaries"]["max_word_count"] <= 200
    assert body["summaries"]["llm"]["calls"] == 0
    assert body["summaries"]["feedback"]["helpful_rate"] is None
