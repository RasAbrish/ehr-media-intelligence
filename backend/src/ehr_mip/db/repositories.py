"""Domain-free repositories. Layer-specific repositories live in their own layer
(for example ``ehr_mip.ingestion.repository``) because ``db`` sits below them."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PipelineRunRepository:
    """Rows in ``pipeline_runs``: one per stage execution."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def start(self, stage: str) -> str:
        run_id = uuid.uuid4().hex
        with self._conn:
            self._conn.execute(
                "INSERT INTO pipeline_runs (run_id, stage, started_at) VALUES (?, ?, ?)",
                (run_id, stage, _now()),
            )
        return run_id

    def finish(self, run_id: str, stats: dict[str, Any]) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE pipeline_runs SET finished_at = ?, stats_json = ? WHERE run_id = ?",
                (_now(), json.dumps(stats, sort_keys=True), run_id),
            )

    def latest(self, stage: str) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self._conn.execute(
            "SELECT * FROM pipeline_runs WHERE stage = ? AND finished_at IS NOT NULL "
            "ORDER BY finished_at DESC, rowid DESC LIMIT 1",
            (stage,),
        ).fetchone()
        return row
