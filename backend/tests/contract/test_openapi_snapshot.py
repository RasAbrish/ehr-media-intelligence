"""The generated OpenAPI must equal docs/openapi.json (docs/04 section 12).

An intentional API change: update docs/04-API-CONTRACT.md first, then run
``make openapi`` to refresh the snapshot.
"""

from __future__ import annotations

import importlib.util
import json
from types import ModuleType

from ehr_mip.config import PROJECT_ROOT


def _exporter() -> ModuleType:
    path = PROJECT_ROOT / "scripts" / "export_openapi.py"
    spec = importlib.util.spec_from_file_location("export_openapi", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_matches_snapshot() -> None:
    exporter = _exporter()
    live = exporter.render(exporter.openapi_document())
    snapshot = (PROJECT_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8")
    assert json.loads(live) == json.loads(snapshot), (
        "The API schema changed. Update docs/04-API-CONTRACT.md, then run `make openapi`."
    )


def test_snapshot_documents_every_built_endpoint() -> None:
    paths = json.loads((PROJECT_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))[
        "paths"
    ]
    expected = {
        "/health": {"get"},
        "/stats": {"get"},
        "/patients": {"get"},
        "/patients/{patient_key}/audit": {"get"},
        "/patients/{patient_key}/summary/feedback": {"post"},
        "/quality/overview": {"get"},
        "/quality/validation": {"get"},
        "/quality/audit": {"get"},
        "/quality/quarantine": {"get"},
        "/ready": {"get"},
        "/search": {"post"},
        "/patients/{patient_key}": {"get"},
        "/patients/{patient_key}/resources": {"get"},
        "/patients/{patient_key}/summary": {"get"},
        "/resources/{resource_type}/{resource_id}": {"get"},
    }
    assert {path: set(methods) for path, methods in paths.items()} == expected
