"""Read-only queries for the API and search hydration. All SQL uses ``?`` parameters."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import orjson

NON_PATIENT_TYPES = ("Encounter", "DocumentReference", "DiagnosticReport", "Observation")


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _marks(count: int) -> str:
    return ", ".join("?" * count)


@dataclass(frozen=True)
class PatientRow:
    patient_key: str
    mrn: str
    secondary_mrns: tuple[str, ...]
    family_name: str | None
    given_names: tuple[str, ...]
    name_suffix: str | None
    birth_date: date | None
    gender: str
    identity_conflict: bool
    phone: str | None
    address: dict[str, Any] | None

    @property
    def display_name(self) -> str:
        """``Jane A. Doe``; middle initials get a period; ``Unknown patient`` without a name."""
        given = [
            g if i == 0 or len(g) > 1 else f"{g}." for i, g in enumerate(self.given_names) if g
        ]
        parts = [*given, self.family_name or "", self.name_suffix or ""]
        name = " ".join(p for p in parts if p)
        return name or "Unknown patient"

    def age(self, today: date) -> int | None:
        if self.birth_date is None:
            return None
        born = self.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _patient(row: sqlite3.Row) -> PatientRow:
    data: dict[str, Any] = orjson.loads(row["data_json"])
    return PatientRow(
        patient_key=row["patient_key"],
        mrn=row["mrn"],
        secondary_mrns=tuple(data.get("secondary_mrns") or ()),
        family_name=row["family_name"],
        given_names=tuple(data.get("given_names") or ()),
        name_suffix=data.get("name_suffix"),
        birth_date=_date(row["birth_date"]),
        gender=row["gender"],
        identity_conflict=bool(row["identity_conflict"]),
        phone=data.get("phone"),
        address=data.get("address"),
    )


class PatientReader:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, patient_key: str) -> PatientRow | None:
        row = self._conn.execute(
            "SELECT * FROM patients WHERE patient_key = ?", (patient_key,)
        ).fetchone()
        return _patient(row) if row else None

    def many(self, patient_keys: Iterable[str]) -> dict[str, PatientRow]:
        keys = sorted(set(patient_keys))
        if not keys:
            return {}
        rows = self._conn.execute(
            f"SELECT * FROM patients WHERE patient_key IN ({_marks(len(keys))})",  # noqa: S608
            keys,
        )
        return {r["patient_key"]: _patient(r) for r in rows}

    def by_mrn(self, digits: str) -> list[PatientRow]:
        """Patients whose current or merged MRN equals the digits (zero padded to 8)."""
        mrn = digits.zfill(8)
        rows = self._conn.execute(
            "SELECT * FROM patients WHERE mrn = ? OR EXISTS ("
            "  SELECT 1 FROM json_each(data_json, '$.secondary_mrns') WHERE value = ?) "
            "ORDER BY patient_key",
            (mrn, mrn),
        )
        return [_patient(r) for r in rows]

    def name_index(self) -> dict[str, str]:
        """patient_key → name text, for the in-memory lexical index only."""
        return {
            r["patient_key"]: f"{r['given_names'] or ''} {r['family_name'] or ''}".strip()
            for r in self._conn.execute(
                "SELECT patient_key, given_names, family_name FROM patients"
            )
        }


@dataclass(frozen=True)
class ResourceRow:
    resource_id: str
    patient_key: str
    resource_type: str
    date: date | None
    title: str | None
    subtype: str | None
    text: str | None
    resource: dict[str, Any]


def _resource(row: sqlite3.Row) -> ResourceRow:
    return ResourceRow(
        resource_id=row["resource_id"],
        patient_key=row["patient_key"],
        resource_type=row["resource_type"],
        date=_date(row["resource_date"]),
        title=row["title"],
        subtype=row["subtype"],
        text=row["text_content"],
        resource=orjson.loads(row["resource_json"]),
    )


@dataclass(frozen=True)
class IssueRow:
    resource_id: str | None
    severity: str
    code: str
    message: str
    path: str


class ResourceReader:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, resource_type: str, resource_id: str) -> ResourceRow | None:
        row = self._conn.execute(
            "SELECT * FROM fhir_resources WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        ).fetchone()
        return _resource(row) if row else None

    def many(self, resource_ids: Iterable[str]) -> dict[str, ResourceRow]:
        ids = sorted(set(resource_ids))
        if not ids:
            return {}
        rows = self._conn.execute(
            f"SELECT * FROM fhir_resources WHERE resource_id IN ({_marks(len(ids))})",  # noqa: S608
            ids,
        )
        return {r["resource_id"]: _resource(r) for r in rows}

    def for_patient(self, patient_key: str, types: Sequence[str]) -> list[ResourceRow]:
        if not types:
            return []
        rows = self._conn.execute(
            f"SELECT * FROM fhir_resources WHERE patient_key = ? "  # noqa: S608
            f"AND resource_type IN ({_marks(len(types))})",
            (patient_key, *types),
        )
        return [_resource(r) for r in rows]

    def searchable(self, types: Sequence[str]) -> list[ResourceRow]:
        """Every resource of the given types, for the indexer."""
        rows = self._conn.execute(
            f"SELECT * FROM fhir_resources WHERE resource_type IN ({_marks(len(types))}) "  # noqa: S608
            "ORDER BY patient_key, resource_id",
            tuple(types),
        )
        return [_resource(r) for r in rows]

    def issues(self, resource_ids: Iterable[str]) -> dict[str, list[IssueRow]]:
        ids = sorted(set(resource_ids))
        found: dict[str, list[IssueRow]] = {}
        if not ids:
            return found
        rows = self._conn.execute(
            "SELECT resource_id, severity, code, message, path FROM validation_issues "  # noqa: S608
            f"WHERE resource_id IN ({_marks(len(ids))}) ORDER BY id",
            ids,
        )
        for r in rows:
            found.setdefault(r["resource_id"], []).append(
                IssueRow(r["resource_id"], r["severity"], r["code"], r["message"], r["path"] or "")
            )
        return found

    def counts_by_type(self, patient_key: str | None = None) -> dict[str, int]:
        query = "SELECT resource_type, COUNT(*) FROM fhir_resources"
        params: tuple[str, ...] = ()
        if patient_key is not None:
            query += " WHERE patient_key = ?"
            params = (patient_key,)
        counts = dict.fromkeys(NON_PATIENT_TYPES, 0)
        for resource_type, count in self._conn.execute(query + " GROUP BY 1", params):
            if resource_type in counts:
                counts[resource_type] = int(count)
        return counts

    def activity_range(self, patient_key: str) -> tuple[date | None, date | None]:
        row = self._conn.execute(
            "SELECT MIN(resource_date), MAX(resource_date) FROM fhir_resources "
            "WHERE patient_key = ? AND resource_type != 'Patient'",
            (patient_key,),
        ).fetchone()
        return _date(row[0]), _date(row[1])


@dataclass(frozen=True)
class BundleInfo:
    bundle_hash: str
    is_valid: bool
    error_count: int
    warning_count: int


class StatusReader:
    """Bundles, summaries, audit counts and pipeline runs."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def bundle(self, patient_key: str) -> BundleInfo | None:
        row = self._conn.execute(
            "SELECT bundle_hash, is_valid, error_count, warning_count FROM fhir_bundles "
            "WHERE patient_key = ?",
            (patient_key,),
        ).fetchone()
        if row is None:
            return None
        return BundleInfo(row[0], bool(row[1]), int(row[2]), int(row[3]))

    def chief_concerns(self, patient_keys: Iterable[str]) -> dict[str, str]:
        """Chief concern of each patient's newest summary for the current bundle (one query)."""
        keys = sorted(set(patient_keys))
        if not keys:
            return {}
        rows = self._conn.execute(
            "SELECT s.patient_key, json_extract(s.summary_json, '$.summary.chief_concern') "  # noqa: S608
            "FROM summary_cache s JOIN fhir_bundles b "
            "  ON b.patient_key = s.patient_key AND b.bundle_hash = s.bundle_hash "
            # Last row wins: model summaries after offline ones, then by date (ADR-014).
            f"WHERE s.patient_key IN ({_marks(len(keys))}) "
            "ORDER BY (s.provider != 'extractive'), s.created_at",
            keys,
        )
        return {key: concern for key, concern in rows if concern}  # newest wins

    def audit_counts(self, patient_key: str) -> dict[str, int]:
        counts = {"info": 0, "warning": 0, "error": 0}
        for severity, count in self._conn.execute(
            "SELECT severity, COUNT(*) FROM audit_log WHERE patient_key = ? GROUP BY 1",
            (patient_key,),
        ):
            counts[severity] = int(count)
        return counts

    def counts(self) -> dict[str, int]:
        def scalar(sql: str) -> int:
            return int(self._conn.execute(sql).fetchone()[0])

        return {
            "patients": scalar("SELECT COUNT(*) FROM patients"),
            "resources": scalar(
                "SELECT COUNT(*) FROM fhir_resources WHERE resource_type != 'Patient'"
            ),
            "summaries": scalar(
                "SELECT COUNT(DISTINCT s.patient_key) FROM summary_cache s JOIN fhir_bundles b "
                "ON b.patient_key = s.patient_key AND b.bundle_hash = s.bundle_hash"
            ),
        }

    def index_version(self) -> int:
        """Number of finished ``index`` runs: bumps on every reindex, seen by every process."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE stage = 'index' AND finished_at IS NOT NULL"
        ).fetchone()
        return int(row[0])

    def last_run(self) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self._conn.execute(
            "SELECT run_id, finished_at FROM pipeline_runs ORDER BY started_at DESC, rowid DESC "
            "LIMIT 1"
        ).fetchone()
        return row
