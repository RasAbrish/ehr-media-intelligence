"""Content-addressed summary cache in SQLite (FR-3.4, docs/02 section 8).

The key covers patient, bundle hash, prompt version and model, so new data, a new
prompt or a new model each produce a new key: entries never need invalidating.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

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
        """Newest summary for the patient's current bundle, from any provider or model."""
        row = self._conn.execute(
            "SELECT cache_key FROM summary_cache WHERE patient_key = ? AND bundle_hash = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (patient_key, bundle_hash),
        ).fetchone()
        if row is None:
            return None
        found = self.get(row[0])
        return found[0] if found else None
