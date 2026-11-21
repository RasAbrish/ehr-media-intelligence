"""HTTP hardening (docs/09 sections 5, 6, 8.1 and 11; FR-6.1 to FR-6.4)."""

from __future__ import annotations

import io
import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
import structlog
from fastapi.testclient import TestClient
from tests.support.api import client_for

from ehr_mip.config import PROJECT_ROOT
from ehr_mip.db.connection import connect
from ehr_mip.logging import configure_logging
from ehr_mip.observability.log_redaction import redact_phi

pytestmark = pytest.mark.integration
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}


@pytest.fixture(scope="module")
def client(api_store: Path) -> Iterator[TestClient]:
    with client_for(api_store) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def patient(api_store: Path) -> sqlite3.Row:
    with closing(connect(api_store / "ehr.db")) as conn:
        row: sqlite3.Row = conn.execute(
            "SELECT * FROM patients WHERE family_name IS NOT NULL LIMIT 1"
        ).fetchone()
        return row


def test_security_headers_present(client: TestClient, patient: sqlite3.Row) -> None:
    key = patient["patient_key"]
    responses = [
        client.get("/health"),
        client.get("/ready"),
        client.post("/search", json={"query": "chest pain"}),
        client.post("/search", json={"query": "x"}),  # 422
        client.get(f"/patients/{key}"),
        client.get(f"/patients/{key}/resources"),
        client.get(f"/patients/{key}/summary"),
        client.get(f"/patients/{uuid.uuid4()}"),  # 404
        client.get("/nope"),
        client.get("/metrics"),
    ]
    for response in responses:
        for name, value in SECURITY_HEADERS.items():
            assert response.headers.get(name) == value, (response.request.url, name)
        assert response.headers["x-request-id"]
        assert response.headers["server-timing"].startswith("total;dur=")
        assert "strict-transport-security" not in response.headers  # plain HTTP here
    assert responses[4].headers["cache-control"] == "no-store"


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    assert (
        client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"]
        == "abc-123"
    )
    generated = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert uuid.UUID(generated.headers["x-request-id"])


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    allowed = client.options(
        "/search",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-credentials" not in allowed.headers
    evil = client.options(
        "/search",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers
    simple = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


def test_rate_limit_search_429_with_retry_after(api_store: Path) -> None:
    with client_for(api_store, rate_limit_enabled=True) as limited:
        statuses = []
        for _ in range(61):
            response = limited.post("/search", json={"query": "x"})  # 422s still count
            statuses.append(response.status_code)
        assert statuses[:60] == [422] * 60
        assert statuses[60] == 429
        assert response.json()["code"] == "rate_limited"
        assert int(response.headers["retry-after"]) >= 1
        assert response.headers["ratelimit-limit"] == "60"
        assert response.headers["ratelimit-remaining"] == "0"
        assert response.headers["content-type"].startswith("application/problem+json")
        for name in SECURITY_HEADERS:
            assert name in response.headers
        # Other routes have their own budget.
        ok = limited.get("/health")
        assert ok.status_code == 200
        assert ok.headers["ratelimit-limit"] == "300"


def _exhaust(client: TestClient, forwarded: str) -> int:
    status = 0
    for _ in range(61):
        status = client.post("/search", json={"query": "x"},
                             headers={"X-Forwarded-For": forwarded}).status_code  # fmt: skip
    return status


def test_rate_limit_uses_forwarded_ip_only_from_trusted_proxy(api_store: Path) -> None:
    # The test client's peer is "testclient": trusted here, like the nginx container.
    with client_for(api_store, rate_limit_enabled=True, forwarded_allow_ips="testclient") as proxy:
        assert _exhaust(proxy, "10.0.0.1") == 429
        other = proxy.post("/search", json={"query": "x"}, headers={"X-Forwarded-For": "10.0.0.2"})
        assert other.status_code == 422  # a different client has its own budget
    # Untrusted peer: X-Forwarded-For is ignored, so changing it cannot reset the budget.
    with client_for(api_store, rate_limit_enabled=True) as direct:
        assert _exhaust(direct, "10.0.0.1") == 429
        spoofed = direct.post(
            "/search", json={"query": "x"}, headers={"X-Forwarded-For": "10.9.9.9"}
        )
        assert spoofed.status_code == 429


def test_body_too_large_413(client: TestClient) -> None:
    big = json.dumps({"query": "x" * 20_000})
    declared = client.post("/search", content=big, headers={"Content-Type": "application/json"})
    assert declared.status_code == 413
    assert declared.json()["code"] == "payload_too_large"

    def chunks() -> Iterator[bytes]:  # no Content-Length: chunked transfer
        yield b'{"query": "'
        for _ in range(20):
            yield b"x" * 1024
        yield b'"}'

    streamed = client.post(
        "/search", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert streamed.status_code == 413
    small = client.post(
        "/search", content=b'{"query": "chest"}', headers={"Content-Type": "application/json"}
    )
    assert small.status_code == 200


def test_500_has_no_stacktrace(api_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_: object) -> None:
        raise RuntimeError("secret detail Jane Doe 00012345")

    monkeypatch.setattr("ehr_mip.db.read_models.PatientReader.get", explode)
    with client_for(api_store, raise_server_exceptions=False) as test_client:
        response = test_client.get(f"/patients/{uuid.uuid4()}")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert body["detail"] == "An unexpected error occurred."
    text = response.text
    for leak in ("Traceback", "RuntimeError", "secret", "Jane", "00012345", ".py"):
        assert leak not in text


def test_logs_contain_no_phi(
    api_store: Path, patient: sqlite3.Row, monkeypatch: pytest.MonkeyPatch
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", stream)
    configure_logging("DEBUG", extra_processors=[redact_phi])
    log = structlog.get_logger("test")
    with client_for(api_store) as test_client:
        key = patient["patient_key"]
        test_client.get(f"/patients/{key}")
        test_client.post("/search", json={"query": f"{patient['family_name']} chest pain"})
        test_client.post("/search", json={"query": f"MRN {patient['mrn']}"})
    log.info(
        "probe",
        name=patient["family_name"],
        mrn=patient["mrn"],
        detail=f"record {patient['mrn']} for {patient['patient_key']}",
    )
    output = stream.getvalue()
    assert '"event": "request"' in output
    assert key in output  # ids are fine
    for identifier in (patient["family_name"], patient["mrn"], patient["birth_date"]):
        assert identifier not in output
    assert re.search(r"\[mrn\]", output)


def test_chroma_uses_persistent_client_only() -> None:
    """docs/09 section 8.1: the Chroma server advisories do not apply because no server or
    HTTP client exists. Guard that in the source."""
    source = PROJECT_ROOT / "backend" / "src" / "ehr_mip"
    forbidden = re.compile(
        r"HttpClient|AsyncHttpClient|chromadb\.Client\(|chroma run|fastapi_chroma"
    )
    found = {p.name: forbidden.findall(p.read_text(encoding="utf-8")) for p in source.rglob("*.py")}
    assert {name: hits for name, hits in found.items() if hits} == {}
    users = {p.name for p in source.rglob("*.py") if "PersistentClient" in p.read_text("utf-8")}
    assert users == {"vector_store.py"}
