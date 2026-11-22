"""Summary feedback per summary version (FR-7.5, docs/04 section 9a.1).

One vote per anonymous client per summary version: the browser sends a random id in
`X-Client-Id`; only its SHA-256 is stored, together with the prompt version so the
feedback can be compared across prompt changes.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Rating = Literal["helpful", "not_helpful"]
Reason = Literal["inaccurate", "missing_information", "too_long", "unclear", "other"]


class DuplicateFeedbackError(Exception):
    """This client already rated this summary version."""


@dataclass(frozen=True)
class FeedbackTotals:
    helpful: int
    not_helpful: int


def hash_client(client_id: str | None) -> str | None:
    return hashlib.sha256(client_id.encode()).hexdigest() if client_id else None


class FeedbackRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def summary_version(self, patient_key: str, cache_key: str) -> str | None:
        """Prompt version of a summary that belongs to this patient, or None."""
        row = self._conn.execute(
            "SELECT prompt_version FROM summary_cache WHERE cache_key = ? AND patient_key = ?",
            (cache_key, patient_key),
        ).fetchone()
        return str(row[0]) if row else None

    def record(
        self,
        *,
        patient_key: str,
        cache_key: str,
        prompt_version: str,
        rating: Rating,
        reason: Reason | None,
        comment: str | None,
        client_id: str | None,
        at: datetime,
    ) -> int:
        try:
            with self._conn:
                cursor = self._conn.execute(
                    """INSERT INTO summary_feedback (patient_key, cache_key, prompt_version,
                           rating, reason, comment, client_id_hash, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        patient_key,
                        cache_key,
                        prompt_version,
                        rating,
                        reason,
                        comment,
                        hash_client(client_id),
                        at.isoformat(timespec="seconds"),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateFeedbackError from error
        return int(cursor.lastrowid or 0)

    def totals(self, cache_key: str) -> FeedbackTotals:
        counts = dict(
            self._conn.execute(
                "SELECT rating, COUNT(*) FROM summary_feedback WHERE cache_key = ? GROUP BY 1",
                (cache_key,),
            ).fetchall()
        )
        return FeedbackTotals(int(counts.get("helpful", 0)), int(counts.get("not_helpful", 0)))

    def by_prompt_version(self) -> list[tuple[str, int, int]]:
        """(prompt_version, helpful, not_helpful), oldest version first."""
        rows = self._conn.execute(
            "SELECT prompt_version, SUM(rating = 'helpful'), SUM(rating = 'not_helpful') "
            "FROM summary_feedback GROUP BY 1 ORDER BY 1"
        )
        return [(str(v), int(h or 0), int(n or 0)) for v, h, n in rows]
