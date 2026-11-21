"""Build the 60-patient synthetic store once and serve it through the real app.

Tests use the HashEmbedder and a temporary Chroma folder, so no model is downloaded.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ehr_mip.api.main import create_app
from ehr_mip.config import PROJECT_ROOT, Settings
from ehr_mip.db.connection import connect
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.fhir.pipeline import run_normalization
from ehr_mip.fhir.store import BundleStore
from ehr_mip.ingestion.pipeline import run_ingestion
from ehr_mip.ingestion.repository import IngestionRepository
from ehr_mip.search.embedder import Embedder, HashEmbedder
from ehr_mip.search.indexer import run_index
from ehr_mip.search.vector_store import VectorStore, open_client
from ehr_mip.summarization.providers.extractive import ExtractiveProvider
from ehr_mip.summarization.service import SummaryService

RAW = PROJECT_ROOT / "data" / "raw"
TODAY = date(2026, 11, 21)
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def build_store(root: Path, embedder: Embedder | None = None) -> Path:
    """ingest → normalize → summarize (extractive) → index, into ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    with closing(connect(root / "ehr.db")) as conn:
        runs = PipelineRunRepository(conn)
        run_id = runs.start("ingest")
        IngestionRepository(conn).save(run_id, run_ingestion(RAW, today=TODAY))
        runs.finish(run_id, {})
        BundleStore(conn).save(
            run_normalization(conn, today=TODAY, timestamp=NOW), created_at=NOW, full_refresh=True
        )
        service = SummaryService(
            conn, provider=ExtractiveProvider(), prompt_version="v1", today=TODAY, clock=lambda: NOW
        )
        asyncio.run(service.summarize_all())
        run_index(
            conn,
            VectorStore(open_client(root / "chroma")),
            embedder or HashEmbedder(),
            index_observations=False,
        )
    return root


def copy_store(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    return target


def settings_for(root: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "sqlite_path": root / "ehr.db",
        "chroma_dir": root / "chroma",
        "rate_limit_enabled": False,
        **overrides,
    }
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def client_for(
    root: Path,
    *,
    embedder_factory: Callable[[Settings], Embedder] = lambda _: HashEmbedder(),
    raise_server_exceptions: bool = True,
    **overrides: Any,
) -> TestClient:
    app = create_app(
        settings_for(root, **overrides), embedder_factory=embedder_factory, configure_logs=False
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)
