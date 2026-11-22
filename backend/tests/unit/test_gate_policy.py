"""The relaxed gates stay as narrow as decided (docs/06 section 15, docs/09 section 8.1)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
import yaml

from ehr_mip.config import PROJECT_ROOT

REVIEW_BY = date(2026, 12, 22)
DEBIAN = {
    "CVE-2025-69720",
    "CVE-2026-9538",
    "CVE-2026-16742",
    "CVE-2026-54369",
    "CVE-2026-76642",
    "CVE-2026-78408",
    "CVE-2026-78409",
    "CVE-2026-78410",
    "CVE-2026-119373",
    "CVE-2026-119374",
    "CVE-2026-119379",
    "CVE-2026-124709",
}
CHROMA = {"CVE-2026-45829", "CVE-2026-45830", "CVE-2026-45831", "CVE-2026-45833"}


@pytest.fixture
def exceptions() -> list[dict[str, Any]]:
    text = (PROJECT_ROOT / ".trivyignore.yaml").read_text()
    entries: list[dict[str, Any]] = yaml.safe_load(text)["vulnerabilities"]
    return entries


def test_only_the_decided_advisories_are_excepted(exceptions: list[dict[str, Any]]) -> None:
    assert sorted(e["id"] for e in exceptions) == sorted(DEBIAN | CHROMA)


def test_every_exception_names_package_version_and_reason(
    exceptions: list[dict[str, Any]],
) -> None:
    for entry in exceptions:
        assert entry["statement"].strip(), entry["id"]
        assert entry["purls"], entry["id"]
        for purl in entry["purls"]:
            assert purl.startswith(("pkg:deb/debian/", "pkg:pypi/chromadb@")), purl
            assert purl.rpartition("@")[2] != purl, f"no version: {purl}"


def test_debian_exceptions_expire(exceptions: list[dict[str, Any]]) -> None:
    for entry in exceptions:
        if entry["id"] in DEBIAN:
            assert entry.get("expired_at") == REVIEW_BY, entry["id"]


def test_every_exception_is_in_the_security_doc(exceptions: list[dict[str, Any]]) -> None:
    doc = (PROJECT_ROOT / "docs/09-SECURITY.md").read_text()
    section = doc.split("### 8.1")[1].split("\n## ")[0]
    for entry in exceptions:
        assert entry["id"] in section, entry["id"]
    assert REVIEW_BY.isoformat() in section


def test_ci_fails_on_any_new_high() -> None:
    ci = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text()
    assert "run: bash scripts/image_scan.sh scan\n" in ci
    assert "scan CRITICAL" not in ci


def test_lighthouse_gate_is_4x_cpu_without_network_throttling() -> None:
    ci = json.loads((PROJECT_ROOT / "frontend/lighthouserc.json").read_text())["ci"]
    settings = ci["collect"]["settings"]
    assert settings["throttlingMethod"] == "devtools"
    assert settings["throttling"] == {
        "cpuSlowdownMultiplier": 4,
        "requestLatencyMs": 0,
        "downloadThroughputKbps": 0,
        "uploadThroughputKbps": 0,
    }
    assert "formFactor" not in settings, "the mobile viewport stays"
    assert "preset" not in settings
    for category in ("performance", "accessibility", "best-practices"):
        level, rule = ci["assert"]["assertions"][f"categories:{category}"]
        assert (level, rule["minScore"]) == ("error", 0.9)


def test_mobile_profile_is_still_reported_and_never_asserts() -> None:
    ci = json.loads((PROJECT_ROOT / "frontend/lighthouserc.mobile.json").read_text())["ci"]
    assert "throttlingMethod" not in ci["collect"]["settings"], "Lighthouse's slow 4G default"
    assert "assert" not in ci


def test_ci_chrome_flags_do_not_replace_the_gate_settings() -> None:
    # An LHCI_COLLECT__SETTINGS__* variable replaces the whole settings block of the config,
    # which silently restores slow 4G. The --settings.chromeFlags option merges instead.
    ci = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text()
    script = (PROJECT_ROOT / "scripts/lighthouse.sh").read_text()
    assert "LHCI_COLLECT__" not in ci
    assert "LIGHTHOUSE_CHROME_FLAGS" in ci
    assert "--settings.chromeFlags=" in script
