"""Dependencies: app state and one SQLite connection per request (docs/02 section 9)."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date

from fastapi import Request

from ehr_mip.cache.backend import CacheBackend, MemoryBackend
from ehr_mip.config import Settings
from ehr_mip.db.connection import connect
from ehr_mip.errors import NotReadyError
from ehr_mip.ingestion.cleaners.dates import today_local
from ehr_mip.search.service import SearchService


@dataclass
class AppState:
    settings: Settings
    cache: CacheBackend  # search results: ids, scores and scrubbed snippets only
    # Patient responses hold identifiers, so they are cached in this process only,
    # never in a shared backend such as Redis (docs/02 section 8).
    patient_cache: MemoryBackend = field(default_factory=MemoryBackend)
    search: SearchService | None = None
    embedder_model: str = ""
    embedder_error: str | None = None

    def today(self) -> date:
        return today_local()


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.ehr
    return state


def get_search(request: Request) -> SearchService:
    search = get_state(request).search
    if search is None:
        msg = "The embedder or vector store is not loaded yet."
        raise NotReadyError(msg)
    return search


async def get_conn(request: Request) -> AsyncIterator[sqlite3.Connection]:
    """A connection opened and closed on the event loop thread that uses it."""
    conn = connect(get_state(request).settings.sqlite_path, apply_schema=False)
    try:
        yield conn
    finally:
        conn.close()
