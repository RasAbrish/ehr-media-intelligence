"""SQLite connections (stdlib ``sqlite3``, ADR-009)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path


def schema_sql() -> str:
    return resources.files("ehr_mip.db").joinpath("schema.sql").read_text(encoding="utf-8")


def connect(path: Path, *, apply_schema: bool = True) -> sqlite3.Connection:
    """Open the database with foreign keys on and the schema applied (idempotent).

    The API applies the schema once at startup and opens per-request connections
    with ``apply_schema=False``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if apply_schema:
        conn.executescript(schema_sql())
    return conn


@contextmanager
def open_db(path: Path) -> Iterator[sqlite3.Connection]:
    """Connection that is always closed, even on error."""
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()
