"""Content-addressed summary cache in SQLite (FR-3.4, docs/02 section 8).

The key covers patient, bundle hash, prompt version and model, so new data, a new
prompt or a new model each produce a new key: entries never need invalidating.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from ehr_mip.summarization.schemas import ClinicalSummary, SummaryTrace

# Raise when the extractive rules change their output: the rules have no prompt version.
EXTRACTIVE_RULES_VERSION = 2


def cache_key(patient_key: str, bundle_hash: str, prompt_version: str, model: str | None) -> str:
    source = model or f"extractive-{EXTRACTIVE_RULES_VERSION}"
    raw = f"{patient_key}:{bundle_hash}:{prompt_version}:{source}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SummaryCache:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> tuple[ClinicalSummary, SummaryTrace | None] | None:
        row = self._conn.execute(
            "SELECT summary_json FROM summary_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        summary = ClinicalSummary.model_validate(payload["summary"]).model_copy(
            update={"cached": True}
        )
        trace = SummaryTrace.model_validate(payload["trace"]) if payload.get("trace") else None
        return summary, trace

    def put(self, summary: ClinicalSummary, trace: SummaryTrace | None) -> None:
        payload = {
            "summary": summary.model_copy(update={"cached": False}).model_dump(mode="json"),
            "trace": trace.model_dump(mode="json") if trace else None,
        }
        with self._conn:
            # Upsert, never REPLACE: feedback rows reference this key with ON DELETE CASCADE.
            self._conn.execute(
                """INSERT INTO summary_cache (cache_key, patient_key, bundle_hash, model,
                       prompt_version, provider, summary_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(cache_key) DO UPDATE SET summary_json = excluded.summary_json,
                       provider = excluded.provider, created_at = excluded.created_at""",
                (
                    summary.cache_key,
                    summary.patient_key,
                    summary.bundle_hash,
                    summary.model,
                    summary.prompt_version,
                    summary.provider,
                    json.dumps(payload),
                    summary.generated_at.isoformat(timespec="seconds"),
                ),
            )

    def latest(self, patient_key: str, bundle_hash: str) -> ClinicalSummary | None:
        """The summary to serve: a model summary before an offline one, then the newest."""
        row = self._conn.execute(
            "SELECT cache_key FROM summary_cache WHERE patient_key = ? AND bundle_hash = ? "
            "ORDER BY (provider != 'extractive') DESC, created_at DESC LIMIT 1",
            (patient_key, bundle_hash),
        ).fetchone()
        if row is None:
            return None
        found = self.get(row[0])
        return found[0] if found else None


def export_summaries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Model summaries of every current bundle, as stored payloads (ADR-014)."""
    rows = conn.execute(
        "SELECT s.summary_json FROM summary_cache s JOIN fhir_bundles b "
        "  ON b.patient_key = s.patient_key AND b.bundle_hash = s.bundle_hash "
        "WHERE s.provider != 'extractive' ORDER BY s.patient_key, s.created_at"
    )
    latest: dict[str, dict[str, Any]] = {}
    for (payload,) in rows:
        item = json.loads(payload)
        latest[item["summary"]["patient_key"]] = item  # newest per patient wins
    return list(latest.values())


def import_summaries(conn: sqlite3.Connection, items: list[dict[str, Any]]) -> tuple[int, int]:
    """Store summaries whose bundle hash matches the current data. Returns (imported, skipped)."""
    current = dict(conn.execute("SELECT patient_key, bundle_hash FROM fhir_bundles").fetchall())
    cache = SummaryCache(conn)
    imported = skipped = 0
    for item in items:
        summary = ClinicalSummary.model_validate(item["summary"])
        if current.get(summary.patient_key) != summary.bundle_hash:
            skipped += 1
            continue
        trace = SummaryTrace.model_validate(item["trace"]) if item.get("trace") else None
        cache.put(summary, trace)
        imported += 1
    return imported, skipped
