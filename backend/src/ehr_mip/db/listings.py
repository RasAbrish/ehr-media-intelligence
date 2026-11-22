"""Paged, filtered listings for the directory and data quality pages (docs/04 sections 6, 8).

Sort columns and filters come from fixed whitelists; every value is a `?` parameter.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ehr_mip.db.read_models import PatientRow, _patient

DirectorySort = Literal["name", "mrn", "birth_date", "last_activity", "resource_count"]
_DIRECTORY_SORT: dict[str, str] = {
    "name": (
        "lower(coalesce(p.family_name, '')) {order}, lower(coalesce(p.given_names, '')) {order}"
    ),
    "mrn": "p.mrn {order}",
    "birth_date": "p.birth_date IS NULL, p.birth_date {order}",
    "last_activity": "last_activity IS NULL, last_activity {order}",
    "resource_count": "resource_count {order}",
}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like(value: str) -> str:
    return f"%{_escape(value)}%"


def _marks(count: int) -> str:
    return ", ".join("?" * count)


@dataclass(frozen=True)
class Page:
    rows: list[Any]
    total: int


@dataclass(frozen=True)
class DirectoryRow:
    patient: PatientRow
    last_activity: str | None
    resource_count: int


class Listings:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------ directory

    def directory(
        self,
        *,
        q: str | None,
        sort: DirectorySort,
        descending: bool,
        conflict_only: bool,
        limit: int,
        offset: int,
    ) -> Page:
        where = ["1 = 1"]
        params: list[Any] = []
        if q:
            # Match the name as displayed ("Jane A. Doe"): periods and spacing do not count.
            lowered = q.strip().lower()
            text = " ".join(lowered.replace(".", "").split()) or lowered
            digits = text.removeprefix("mrn").strip(" :#-")
            clause = (
                "lower(replace(trim(coalesce(p.given_names, '') || ' ' || "
                "coalesce(p.family_name, '') || ' ' || "
                "coalesce(json_extract(p.data_json, '$.name_suffix'), '')), '.', '')) "
                "LIKE ? ESCAPE '\\'"
            )
            params.append(_like(text))
            if digits.isdigit():
                # MRN prefix, ignoring the zero padding: "12345" finds 00012345.
                clause += (
                    " OR ltrim(p.mrn, '0') LIKE ? OR EXISTS (SELECT 1 FROM json_each(p.data_json, "
                    "'$.secondary_mrns') WHERE ltrim(value, '0') LIKE ?)"
                )
                prefix = digits.lstrip("0") or "0"
                params += [f"{prefix}%", f"{prefix}%"]
            where.append(f"({clause})")
        if conflict_only:
            where.append("p.identity_conflict = 1")
        condition = " AND ".join(where)
        total = int(
            self._conn.execute(
                f"SELECT COUNT(*) FROM patients p WHERE {condition}",  # noqa: S608 (fixed fragments)
                params,
            ).fetchone()[0]
        )
        order = _DIRECTORY_SORT[sort].format(order="DESC" if descending else "ASC")
        rows = self._conn.execute(
            f"""SELECT p.*,
                   (SELECT MAX(r.resource_date) FROM fhir_resources r
                     WHERE r.patient_key = p.patient_key AND r.resource_type != 'Patient')
                     AS last_activity,
                   (SELECT COUNT(*) FROM fhir_resources r
                     WHERE r.patient_key = p.patient_key AND r.resource_type != 'Patient')
                     AS resource_count
                FROM patients p WHERE {condition}
                ORDER BY {order}, p.patient_key LIMIT ? OFFSET ?""",  # noqa: S608
            [*params, limit, offset],
        )
        return Page(
            rows=[
                DirectoryRow(
                    patient=_patient(r),
                    last_activity=(r["last_activity"] or None) and str(r["last_activity"])[:10],
                    resource_count=int(r["resource_count"]),
                )
                for r in rows
            ],
            total=total,
        )

    def current_summaries(self, patient_keys: Sequence[str]) -> dict[str, dict[str, Any]]:
        """Newest summary JSON per patient for the current bundle."""
        keys = sorted(set(patient_keys))
        if not keys:
            return {}
        rows = self._conn.execute(
            "SELECT s.patient_key, s.summary_json FROM summary_cache s JOIN fhir_bundles b "  # noqa: S608
            "  ON b.patient_key = s.patient_key AND b.bundle_hash = s.bundle_hash "
            # Last row wins: model summaries after offline ones, then by date (ADR-014).
            f"WHERE s.patient_key IN ({_marks(len(keys))}) "
            "ORDER BY (s.provider != 'extractive'), s.created_at",
            keys,
        )
        return {key: json.loads(payload)["summary"] for key, payload in rows}

    # ------------------------------------------------------------------ data quality

    def audit(
        self,
        *,
        patient_key: str | None = None,
        severities: Sequence[str] = (),
        stages: Sequence[str] = (),
        rule_prefix: str | None = None,
        limit: int,
        offset: int,
    ) -> Page:
        where: list[str] = ["1 = 1"]
        params: list[Any] = []
        if patient_key:
            where.append("patient_key = ?")
            params.append(patient_key)
        if severities:
            where.append(f"severity IN ({_marks(len(severities))})")
            params += list(severities)
        if stages:
            where.append(f"stage IN ({_marks(len(stages))})")
            params += list(stages)
        if rule_prefix:
            where.append("rule LIKE ? ESCAPE '\\'")
            params.append(f"{_escape(rule_prefix)}%")
        condition = " AND ".join(where)
        total = int(
            self._conn.execute(
                f"SELECT COUNT(*) FROM audit_log WHERE {condition}",  # noqa: S608
                params,
            ).fetchone()[0]
        )
        rows = list(
            self._conn.execute(
                f"SELECT * FROM audit_log WHERE {condition} ORDER BY id LIMIT ? OFFSET ?",  # noqa: S608
                [*params, limit, offset],
            )
        )
        return Page(rows=rows, total=total)

    def validation(
        self,
        *,
        severities: Sequence[str] = (),
        resource_types: Sequence[str] = (),
        code: str | None = None,
        limit: int,
        offset: int,
    ) -> Page:
        where: list[str] = ["1 = 1"]
        params: list[Any] = []
        if severities:
            where.append(f"severity IN ({_marks(len(severities))})")
            params += list(severities)
        if resource_types:
            where.append(f"resource_type IN ({_marks(len(resource_types))})")
            params += list(resource_types)
        if code:
            where.append("code = ?")
            params.append(code)
        condition = " AND ".join(where)
        total = int(
            self._conn.execute(
                f"SELECT COUNT(*) FROM validation_issues WHERE {condition}",  # noqa: S608
                params,
            ).fetchone()[0]
        )
        rows = list(
            self._conn.execute(
                f"SELECT * FROM validation_issues WHERE {condition} "  # noqa: S608
                "ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, id "
                "LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        )
        return Page(rows=rows, total=total)

    def quarantine(self, *, limit: int, offset: int) -> Page:
        total = int(self._conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0])
        rows = list(
            self._conn.execute(
                "SELECT * FROM quarantine ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            )
        )
        return Page(rows=rows, total=total)

    # ------------------------------------------------------------------ overview

    def latest_run_stats(self, stage: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT stats_json FROM pipeline_runs WHERE stage = ? AND finished_at IS NOT NULL "
            "ORDER BY finished_at DESC, rowid DESC LIMIT 1",
            (stage,),
        ).fetchone()
        return dict(json.loads(row[0])) if row and row[0] else {}

    def top_rules(self, limit: int = 8) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT rule, COUNT(*) FROM audit_log GROUP BY rule ORDER BY 2 DESC, 1 LIMIT ?",
            (limit,),
        )
        return [(str(r), int(n)) for r, n in rows]

    def counts_by(self, table: str, column: str) -> dict[str, int]:
        allowed = {("audit_log", "severity"), ("validation_issues", "severity")}
        if (table, column) not in allowed:
            msg = f"Unsupported count: {table}.{column}"
            raise ValueError(msg)
        rows = self._conn.execute(f"SELECT {column}, COUNT(*) FROM {table} GROUP BY 1")  # noqa: S608
        return {str(k): int(v) for k, v in rows}

    def top_codes(self, limit: int = 8) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT code, COUNT(*) FROM validation_issues GROUP BY code ORDER BY 2 DESC, 1 LIMIT ?",
            (limit,),
        )
        return [(str(c), int(n)) for c, n in rows]

    def bundle_counts(self) -> tuple[int, int]:
        row = self._conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(is_valid), 0) FROM fhir_bundles"
        ).fetchone()
        return int(row[0]), int(row[1])

    def llm_rows(self) -> list[sqlite3.Row]:
        """Model calls only (the extractive provider makes no model calls)."""
        return list(
            self._conn.execute(
                "SELECT status, input_tokens, output_tokens, cost_usd_estimate, latency_ms "
                "FROM llm_calls WHERE provider != 'extractive'"
            )
        )

    def last_finished_at(self) -> str | None:
        row = self._conn.execute("SELECT MAX(finished_at) FROM pipeline_runs").fetchone()
        return str(row[0]) if row and row[0] else None
