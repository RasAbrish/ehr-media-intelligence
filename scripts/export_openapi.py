"""Write the API's OpenAPI document to docs/openapi.json (``make openapi``).

The contract snapshot test compares the live schema with this file, so any API
change must be exported (and docs/04-API-CONTRACT.md updated) on purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ehr_mip.api.main import create_app
from ehr_mip.config import PROJECT_ROOT, Settings

TARGET = PROJECT_ROOT / "docs" / "openapi.json"


def openapi_document() -> dict[str, Any]:
    app = create_app(Settings(_env_file=None, env="dev"), configure_logs=False)
    document: dict[str, Any] = app.openapi()
    return document


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(target: Path = TARGET) -> None:
    target.write_text(render(openapi_document()), encoding="utf-8")
    sys.stdout.write(f"Wrote {target}\n")


if __name__ == "__main__":
    main()
