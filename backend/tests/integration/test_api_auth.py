"""Sign-in, sessions and the session gate on every data route (docs/04 section 3a)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.support.api import client_for, copy_store

pytestmark = pytest.mark.integration

EMAIL, PASSWORD = "demo@example.org", "synthetic-demo-2026"
PUBLIC = {"/health", "/ready", "/metrics", "/auth/login", "/auth/logout"}  # docs/04 section 1
UUID = "00000000-0000-5000-8000-000000000000"


@pytest.fixture(scope="module")
def store(api_store: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_store(api_store, tmp_path_factory.mktemp("auth") / "store")


def make_client(store: Path, **overrides: object) -> TestClient:
    return client_for(
        store,
        auth_enabled=True,
        seed_account_email=EMAIL,
        seed_account_password=PASSWORD,
        **overrides,
    )


@pytest.fixture
def client(store: Path) -> Iterator[TestClient]:
    with make_client(store) as test_client:
        yield test_client


def sign_in(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200, response.text


def test_sign_in_sets_a_strict_http_only_cookie(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "Demo@Example.org", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"email": EMAIL, "display_name": "Clinician"}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("ehr_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie  # ENV=dev
    assert "Max-Age" not in cookie
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


def test_cookie_is_secure_in_prod(store: Path) -> None:
    with make_client(store, env="prod") as client:
        response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert "Secure" in response.headers["set-cookie"]


def test_login_failures_are_identical(client: TestClient) -> None:
    wrong = client.post("/auth/login", json={"email": EMAIL, "password": "wrong password!!"})
    unknown = client.post("/auth/login", json={"email": "x@example.org", "password": PASSWORD})
    for response in (wrong, unknown):
        assert response.status_code == 401
        assert "set-cookie" not in response.headers
    body = {k: v for k, v in wrong.json().items() if k != "request_id"}
    assert body == {k: v for k, v in unknown.json().items() if k != "request_id"}
    assert body["code"] == "invalid_credentials"


def test_sign_out_ends_the_session(client: TestClient) -> None:
    sign_in(client)
    token = client.cookies.get("ehr_session")
    assert client.post("/auth/logout").status_code == 204
    client.cookies.set("ehr_session", token or "")
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/logout").status_code == 204  # nothing to end is fine


def test_post_without_csrf_header_is_refused(store: Path) -> None:
    with make_client(store) as client:
        client.headers.pop("X-Requested-With")
        response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert response.status_code == 403
        assert response.json()["code"] == "csrf_check_failed"


def _concrete(path: str) -> str:
    return re.sub(r"\{resource_type\}", "Observation", re.sub(r"\{[a-z_]+\}", UUID, path))


def test_every_data_route_needs_a_session(client: TestClient) -> None:
    # Included routers are resolved lazily, so the OpenAPI document is the full route list.
    paths: dict[str, dict[str, object]] = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    checked = 0
    for path, operations in paths.items():
        if path in PUBLIC:
            continue
        for method in operations:
            response = client.request(method.upper(), _concrete(path), json={})
            assert response.status_code == 401, (method, path, response.status_code)
            assert response.json()["code"] == "not_authenticated"
            checked += 1
    assert checked >= 12
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code in (200, 503)


def test_signed_in_requests_reach_the_data(client: TestClient) -> None:
    sign_in(client)
    assert client.get("/stats").json()["patients"] == 60
    assert client.post("/search", json={"query": "potassium"}).status_code == 200


def test_login_is_rate_limited(store: Path) -> None:
    with make_client(store, rate_limit_enabled=True) as client:
        codes = [
            client.post(
                "/auth/login", json={"email": EMAIL, "password": "wrong password!!"}
            ).status_code
            for _ in range(11)
        ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


@pytest.mark.parametrize(("enabled", "status"), [(None, 404), (True, 200)])
def test_swagger_docs_in_prod_follow_the_setting(
    store: Path, enabled: bool | None, status: int
) -> None:
    with make_client(store, env="prod", api_docs_enabled=enabled) as client:
        assert client.get("/docs").status_code == status
        assert client.get("/openapi.json").status_code == status
        assert client.get("/stats").status_code == 401  # data still needs a session
