"""The free demo deployment stays free, synthetic and as hardened as compose (docs/02 section 7)."""

from __future__ import annotations

import re
from typing import Any

import pytest
import yaml

from ehr_mip.config import PROJECT_ROOT


@pytest.fixture
def services() -> dict[str, dict[str, Any]]:
    blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text())
    return {service["runtime"]: service for service in blueprint["services"]}


def _env(service: dict[str, Any]) -> dict[str, str]:
    return {item["key"]: str(item["value"]) for item in service["envVars"] if "value" in item}


def _prompted(service: dict[str, Any]) -> set[str]:
    """Keys whose value is entered in the Render dashboard (``sync: false``), never in git."""
    return {item["key"] for item in service["envVars"] if item.get("sync") is False}


def test_only_free_services(services: dict[str, dict[str, Any]]) -> None:
    assert set(services) == {"docker", "static"}
    # An omitted plan creates a paid instance, so it must be spelled out.
    assert services["docker"]["plan"] == "free"
    assert "disk" not in services["docker"]
    assert "plan" not in services["static"]


def test_the_public_demo_cannot_spend_money_on_the_model(
    services: dict[str, dict[str, Any]],
) -> None:
    env = _env(services["docker"])
    assert env["LLM_PROVIDER"] == "extractive"
    assert "ANTHROPIC_API_KEY" not in env
    assert env.get("RATE_LIMIT_ENABLED", "true") == "true"
    assert "FORWARDED_ALLOW_IPS" not in env, "never trust a caller's X-Forwarded-For"


def test_the_login_is_entered_in_the_dashboard_and_never_shown(
    services: dict[str, dict[str, Any]],
) -> None:
    api, site = _env(services["docker"]), _env(services["static"])
    assert api.get("AUTH_ENABLED", "true") == "true"
    assert _prompted(services["docker"]) == {"SEED_ACCOUNT_EMAIL", "SEED_ACCOUNT_PASSWORD"}
    assert not {"VITE_DEMO_EMAIL", "VITE_DEMO_PASSWORD"} & set(site)
    secret_like = re.compile(r"(^|_)(KEY|TOKEN|SECRET|PASSWORD|EMAIL)(_|$)")
    for env in (api, site):
        assert not {key for key in env if secret_like.search(key)}


def test_the_api_docs_are_published(services: dict[str, dict[str, Any]]) -> None:
    assert _env(services["docker"])["API_DOCS_ENABLED"] == "true"


def test_the_image_ships_the_model_summaries() -> None:
    dockerfile = (PROJECT_ROOT / "backend/Dockerfile").read_text()
    assert "COPY data/summaries /app/data/summaries" in dockerfile
    assert "!data/summaries/" in (PROJECT_ROOT / ".dockerignore").read_text()


def test_the_api_serves_the_index_built_into_the_image(
    services: dict[str, dict[str, Any]],
) -> None:
    env = _env(services["docker"])
    dockerfile = (PROJECT_ROOT / "backend/Dockerfile").read_text()
    for key in ("SQLITE_PATH", "CHROMA_DIR"):
        assert f"{key}={env[key]}" in dockerfile
    assert "ehr-mip run-all" in dockerfile


def test_the_site_proxies_the_api_before_the_spa_fallback(
    services: dict[str, dict[str, Any]],
) -> None:
    api, spa = services["static"]["routes"]
    assert api["source"] == "/api/*"
    assert api["destination"] == f"https://{services['docker']['name']}.onrender.com/*"
    assert (spa["source"], spa["destination"]) == ("/*", "/index.html")
    assert _env(services["static"])["VITE_DEMO_MODE"] == "true"


def test_the_site_sends_the_same_security_headers_as_nginx(
    services: dict[str, dict[str, Any]],
) -> None:
    conf = (PROJECT_ROOT / "frontend/security-headers.conf").read_text()
    expected = set(re.findall(r'^add_header (\S+) "([^"]+)" always;$', conf, re.MULTILINE))
    sent = {(h["name"], h["value"]) for h in services["static"]["headers"] if h["path"] == "/*"}
    assert expected <= sent
