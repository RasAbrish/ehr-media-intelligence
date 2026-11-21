"""BundleStore: bundles, indexed resources and validation issues in SQLite (FR-2.6).

A save replaces the FHIR rows of the patients it is given, inside one transaction,
and never touches other patients. ``full_refresh=True`` (used by ``ehr-mip
normalize``, which processes every patient) also removes bundles of patients that
are no longer in the result.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import orjson

from ehr_mip.fhir.models import NormalizedBundle, ValidationIssue


def _json(value: Any) -> str:
    return orjson.dumps(value).decode("utf-8")


class BundleStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(
        self,
        results: Sequence[NormalizedBundle],
        *,
        created_at: datetime,
        full_refresh: bool = False,
    ) -> None:
        keys = [r.built.patient_key for r in results]
        if full_refresh and not keys:
            msg = "Refusing a full refresh with no bundles; it would erase the FHIR store."
            raise ValueError(msg)
        with self._conn:
            for table in ("fhir_resources", "validation_issues"):
                self._conn.executemany(
                    f"DELETE FROM {table} WHERE patient_key = ?",  # noqa: S608 (fixed names)
                    [(k,) for k in keys],
                )
            if full_refresh:
                existing = {
                    row[0] for row in self._conn.execute("SELECT patient_key FROM fhir_bundles")
                }
                gone = sorted(existing - set(keys))
                for table in ("fhir_bundles", "fhir_resources", "validation_issues"):
                    self._conn.executemany(
                        f"DELETE FROM {table} WHERE patient_key = ?",  # noqa: S608
                        [(k,) for k in gone],
                    )
            self._conn.executemany(
                """INSERT INTO fhir_bundles (patient_key, bundle_json, bundle_hash, is_valid,
                       error_count, warning_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(patient_key) DO UPDATE SET bundle_json = excluded.bundle_json,
                       bundle_hash = excluded.bundle_hash, is_valid = excluded.is_valid,
                       error_count = excluded.error_count, warning_count = excluded.warning_count,
                       created_at = excluded.created_at""",
                [
                    (
                        r.built.patient_key,
                        _json(r.built.bundle),
                        r.built.bundle_hash,
                        int(r.validation.is_valid),
                        r.validation.error_count,
                        r.validation.warning_count,
                        created_at.isoformat(timespec="seconds"),
                    )
                    for r in results
                ],
            )
            self._conn.executemany(
                """INSERT INTO fhir_resources (resource_id, patient_key, resource_type,
                       resource_date, title, subtype, text_content, resource_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        row.resource_id,
                        row.patient_key,
                        row.resource_type,
                        row.resource_date,
                        row.title,
                        row.subtype,
                        row.text_content,
                        _json(row.resource),
                    )
                    for r in results
                    for row in r.built.rows
                ],
            )
            self._conn.executemany(
                """INSERT INTO validation_issues (patient_key, resource_type, resource_id, path,
                       severity, code, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        i.patient_key,
                        i.resource_type,
                        i.resource_id,
                        i.path,
                        i.severity,
                        i.code,
                        i.message,
                    )
                    for r in results
                    for i in r.validation.issues
                ],
            )

    def load_bundle(self, patient_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT bundle_json FROM fhir_bundles WHERE patient_key = ?", (patient_key,)
        ).fetchone()
        if row is None:
            return None
        bundle: dict[str, Any] = orjson.loads(row[0])
        return bundle

    def load_with_meta(self, patient_key: str) -> tuple[dict[str, Any], str, bool] | None:
        """Bundle, its hash and whether it is valid, in one read."""
        row = self._conn.execute(
            "SELECT bundle_json, bundle_hash, is_valid FROM fhir_bundles WHERE patient_key = ?",
            (patient_key,),
        ).fetchone()
        if row is None:
            return None
        bundle: dict[str, Any] = orjson.loads(row[0])
        return bundle, str(row[1]), bool(row[2])

    def bundle_hash(self, patient_key: str) -> str | None:
        row = self._conn.execute(
            "SELECT bundle_hash FROM fhir_bundles WHERE patient_key = ?", (patient_key,)
        ).fetchone()
        return str(row[0]) if row else None

    def patient_keys(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT patient_key FROM fhir_bundles ORDER BY 1")]

    def load_resource(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT resource_json FROM fhir_resources WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        ).fetchone()
        if row is None:
            return None
        resource: dict[str, Any] = orjson.loads(row[0])
        return resource

    def load_issues(self, patient_key: str | None = None) -> list[ValidationIssue]:
        query = (
            "SELECT patient_key, resource_type, resource_id, path, severity, code, message "
            "FROM validation_issues"
        )
        params: tuple[str, ...] = ()
        if patient_key is not None:
            query += " WHERE patient_key = ?"
            params = (patient_key,)
        rows = self._conn.execute(query + " ORDER BY id", params)
        return [ValidationIssue(**dict(r)) for r in rows]
