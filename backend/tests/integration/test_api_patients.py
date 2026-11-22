"""Patient detail, resources and summary (docs/04 sections 6.2 to 6.4)."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for, copy_store

from ehr_mip.api.schemas.patients import PatientDetail, PatientResourcesResponse
from ehr_mip.api.schemas.summary import ClinicalSummaryResponse
from ehr_mip.db.connection import connect

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client(api_store: Path) -> Iterator[TestClient]:
    with client_for(api_store) as test_client:
        yield test_client


def _row(store: Path, sql: str) -> sqlite3.Row:
    with closing(connect(store / "ehr.db")) as conn:
        row: sqlite3.Row = conn.execute(sql).fetchone()
        return row


@pytest.fixture(scope="module")
def merged(api_store: Path) -> sqlite3.Row:
    return _row(
        api_store,
        "SELECT * FROM patients WHERE json_array_length(data_json, '$.secondary_mrns') > 0 LIMIT 1",
    )


def test_patient_detail(client: TestClient, merged: sqlite3.Row) -> None:
    first = client.get(f"/patients/{merged['patient_key']}")
    assert first.status_code == 200
    detail = PatientDetail.model_validate(first.json())
    assert detail.mrn == merged["mrn"]
    assert detail.display_name.endswith(merged["family_name"])
    uses = {i.use for i in detail.identifiers}
    assert uses == {"usual", "old"}
    assert all(i.system == "urn:oid:2.999.1.1" for i in detail.identifiers)
    assert len(detail.bundle.bundle_hash) > 0
    assert detail.counts.DocumentReference + detail.counts.DiagnosticReport > 0
    assert detail.first_activity is not None
    assert detail.last_activity is not None
    assert detail.first_activity <= detail.last_activity
    assert detail.data_quality.audit_entries > 0
    assert first.headers["cache-control"] == "no-store"
    second = client.get(f"/patients/{merged['patient_key']}")
    assert second.headers["x-cache"] == "HIT"
    assert second.json() == first.json()


def test_unknown_and_malformed_patient_keys(client: TestClient) -> None:
    missing = client.get(f"/patients/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "patient_not_found"
    for path in (
        "/patients/not-a-uuid",
        "/patients/not-a-uuid/resources",
        "/patients/not-a-uuid/summary",
    ):
        bad = client.get(path)
        assert bad.status_code == 422
        assert bad.json()["errors"][0]["loc"] == "path.patient_key"
    assert client.get(f"/patients/{uuid.uuid4()}/summary").json()["code"] == "patient_not_found"


def test_patient_resources(client: TestClient, merged: sqlite3.Row) -> None:
    response = client.get(f"/patients/{merged['patient_key']}/resources")
    assert response.status_code == 200
    body = PatientResourcesResponse.model_validate(response.json())
    assert body.total == len(body.items) > 0
    assert "Patient" not in {i.resource_type for i in body.items}
    dated = [i.date for i in body.items if i.date]
    assert dated == sorted(dated, reverse=True)
    first_undated = next((n for n, i in enumerate(body.items) if not i.date), len(body.items))
    assert all(not i.date for i in body.items[first_undated:])  # undated last
    observations = client.get(
        f"/patients/{merged['patient_key']}/resources",
        params={"resource_type": "Observation", "sort": "title", "order": "asc"},
    ).json()["items"]
    assert observations
    assert all(o["resource_type"] == "Observation" and o["subtype"] is None for o in observations)
    assert all(o["interpretation"] in {"LL", "L", "N", "H", "HH", None} for o in observations)
    titles = [o["title"].lower() for o in observations]
    assert titles == sorted(titles)
    encounter = next(i for i in body.items if i.resource_type == "Encounter")
    assert encounter.subtype is None
    assert encounter.title.endswith("encounter")


def test_bad_resource_filter_and_sort(client: TestClient, merged: sqlite3.Row) -> None:
    for params in ({"resource_type": "Medication"}, {"sort": "size"}, {"order": "up"}):
        response = client.get(f"/patients/{merged['patient_key']}/resources", params=params)
        assert response.status_code == 422


def test_summary_with_etag(client: TestClient, merged: sqlite3.Row) -> None:
    response = client.get(f"/patients/{merged['patient_key']}/summary")
    assert response.status_code == 200
    summary = ClinicalSummaryResponse.model_validate(response.json())
    assert summary.cached is True
    assert summary.word_count <= 200
    assert summary.disclaimer.startswith("AI-generated summary")
    assert "self_reported_confidence" not in response.json()
    etag = response.headers["etag"]
    assert etag == f'"{summary.bundle_hash}:{summary.prompt_version}"'
    not_modified = client.get(
        f"/patients/{merged['patient_key']}/summary", headers={"If-None-Match": etag}
    )
    assert not_modified.status_code == 304
    assert not_modified.content == b""
    changed = client.get(
        f"/patients/{merged['patient_key']}/summary", headers={"If-None-Match": '"other:v0"'}
    )
    assert changed.status_code == 200


def test_summary_not_found(tmp_path: Path, api_store: Path, merged: sqlite3.Row) -> None:
    store = copy_store(api_store, tmp_path / "store")
    with closing(connect(store / "ehr.db")) as conn, conn:
        conn.execute("DELETE FROM summary_cache WHERE patient_key = ?", (merged["patient_key"],))
    with client_for(store) as fresh:
        response = fresh.get(f"/patients/{merged['patient_key']}/summary")
    assert response.status_code == 404
    assert response.json()["code"] == "summary_not_found"


def _resource(store: Path, sql: str) -> dict[str, Any]:
    row = _row(store, sql)
    return dict(row)


def test_lab_report_detail(client: TestClient, api_store: Path) -> None:
    report = _resource(
        api_store,
        "SELECT resource_id FROM fhir_resources "
        "WHERE resource_type = 'DiagnosticReport' AND subtype = 'LAB' LIMIT 1",
    )
    body = client.get(f"/resources/DiagnosticReport/{report['resource_id']}").json()
    assert body["resource"]["subtype"] == "LAB"
    assert body["observations"]
    first = body["observations"][0]
    assert set(first) == {
        "resource_id",
        "name",
        "value",
        "unit",
        "interpretation",
        "reference_range",
    }
    assert body["fhir"]["resourceType"] == "DiagnosticReport"
    assert body["patient"]["patient_key"]


def test_note_detail_has_sections(client: TestClient, api_store: Path) -> None:
    note = _resource(
        api_store,
        "SELECT resource_id FROM fhir_resources WHERE resource_type = "
        "'DocumentReference' AND text_content LIKE '%PLAN:%' LIMIT 1",
    )
    body = client.get(f"/resources/DocumentReference/{note['resource_id']}").json()
    assert body["text"]
    assert "PLAN" in [s["heading"] for s in body["sections"]]
    assert body["observations"] == []


def test_encounter_detail_and_errors(client: TestClient, api_store: Path) -> None:
    encounter = _resource(
        api_store,
        "SELECT resource_id FROM fhir_resources WHERE resource_type = 'Encounter' LIMIT 1",
    )
    body = client.get(f"/resources/Encounter/{encounter['resource_id']}").json()
    assert body["text"] is None
    assert body["sections"] == []
    missing = client.get(f"/resources/Observation/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "resource_not_found"
    assert client.get(f"/resources/Patient/{uuid.uuid4()}").status_code == 422
    # Right id, wrong type: still not found.
    assert client.get(f"/resources/Observation/{encounter['resource_id']}").status_code == 404


def test_patient_type_filter_is_ignored_not_a_crash(
    client: TestClient, merged: sqlite3.Row
) -> None:
    url = f"/patients/{merged['patient_key']}/resources"
    only_patient = client.get(url, params={"resource_type": "Patient"})
    assert only_patient.status_code == 200
    assert only_patient.json()["items"] == []
    mixed = client.get(url, params={"resource_type": ["Patient", "Encounter"]}).json()
    assert mixed["items"]
    assert {i["resource_type"] for i in mixed["items"]} == {"Encounter"}


def test_patient_responses_never_reach_the_shared_cache(
    api_store: Path, merged: sqlite3.Row
) -> None:
    from ehr_mip.cache.backend import MemoryBackend  # noqa: PLC0415

    class Spy(MemoryBackend):
        def __init__(self) -> None:
            super().__init__()
            self.keys: list[str] = []

        async def set(self, key: str, value: bytes, ttl_s: int) -> None:
            self.keys.append(key)
            await super().set(key, value, ttl_s)

    spy = Spy()
    from tests.support.api import CSRF, settings_for  # noqa: PLC0415

    from ehr_mip.api.main import create_app  # noqa: PLC0415
    from ehr_mip.search.embedder import HashEmbedder  # noqa: PLC0415

    app = create_app(settings_for(api_store), embedder_factory=lambda _: HashEmbedder(),
                     cache=spy, configure_logs=False)  # fmt: skip
    with TestClient(app, headers=dict([CSRF])) as test_client:
        key = merged["patient_key"]
        assert test_client.get(f"/patients/{key}").status_code == 200
        assert test_client.get(f"/patients/{key}").headers["x-cache"] == "HIT"
        test_client.get(f"/patients/{key}/resources")
        test_client.post("/search", json={"query": "chest pain"})
    assert spy.keys
    assert all(k.startswith("ehr-mip:search:") for k in spy.keys)
