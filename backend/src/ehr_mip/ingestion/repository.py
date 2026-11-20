"""Persist and load Task 1 output in SQLite.

Clean tables are kept in sync with the latest run: rows from the new result are
upserted (``ON CONFLICT ... DO UPDATE``, never ``REPLACE``, so foreign-key children
are not deleted) and rows the new result no longer contains are removed. Audit
and quarantine rows are appended per run and read back for the latest run.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime

from ehr_mip.errors import EmptyIngestionError
from ehr_mip.ingestion.models import (
    AuditEntry,
    CleanDocument,
    CleanEncounter,
    CleanLabResult,
    CleanPatient,
    IngestionResult,
    QuarantinedRecord,
)


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


class IngestionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ---------------------------------------------------------------- writes

    def save(self, run_id: str, result: IngestionResult) -> None:
        """Write one ingestion result atomically.

        Order matters for foreign keys: children that disappeared are removed first,
        parents are upserted before children, and stale encounters and patients are
        removed last, once no kept row references them. Audit and quarantine rows
        from older runs are pruned so only the current run's decisions remain.
        """
        if not result.patients:
            msg = "Ingestion produced no patients; refusing to overwrite the existing data."
            raise EmptyIngestionError(msg)
        with self._conn:
            self._delete_stale(
                "documents", "document_key", {d.document_key for d in result.documents}
            )
            self._delete_stale(
                "lab_results", "result_key", {r.result_key for r in result.lab_results}
            )
            self._upsert_patients(result.patients)
            self._upsert_encounters(result.encounters)
            self._upsert_documents(result.documents)
            self._upsert_labs(result.lab_results)
            self._delete_stale(
                "encounters", "encounter_key", {e.encounter_key for e in result.encounters}
            )
            self._delete_stale("patients", "patient_key", {p.patient_key for p in result.patients})
            self._conn.execute("DELETE FROM audit_log WHERE run_id IS NOT ?", (run_id,))
            self._conn.execute("DELETE FROM quarantine WHERE run_id IS NOT ?", (run_id,))
            self._insert_audit(run_id, result.audit)
            self._insert_quarantine(run_id, result.quarantine)

    def _delete_stale(self, table: str, key: str, keep: set[str]) -> None:
        existing = {row[0] for row in self._conn.execute(f"SELECT {key} FROM {table}")}  # noqa: S608
        stale = sorted(existing - keep)
        if stale:
            self._conn.executemany(
                f"DELETE FROM {table} WHERE {key} = ?",  # noqa: S608 (fixed identifiers)
                [(k,) for k in stale],
            )

    def _upsert_patients(self, patients: Iterable[CleanPatient]) -> None:
        self._conn.executemany(
            """INSERT INTO patients (patient_key, mrn, family_name, given_names, birth_date,
                   gender, identity_conflict, data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(patient_key) DO UPDATE SET mrn = excluded.mrn,
                   family_name = excluded.family_name, given_names = excluded.given_names,
                   birth_date = excluded.birth_date, gender = excluded.gender,
                   identity_conflict = excluded.identity_conflict,
                   data_json = excluded.data_json""",
            [
                (
                    p.patient_key,
                    p.mrn,
                    p.family_name,
                    " ".join(p.given_names),
                    _iso(p.birth_date),
                    p.gender.value,
                    int(p.identity_conflict),
                    p.model_dump_json(),
                )
                for p in patients
            ],
        )

    def _upsert_encounters(self, encounters: Iterable[CleanEncounter]) -> None:
        self._conn.executemany(
            """INSERT INTO encounters (encounter_key, patient_key, encounter_class, period_start,
                   data_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(encounter_key) DO UPDATE SET patient_key = excluded.patient_key,
                   encounter_class = excluded.encounter_class,
                   period_start = excluded.period_start, data_json = excluded.data_json""",
            [
                (
                    e.encounter_key,
                    e.patient_key,
                    e.encounter_class.value,
                    _iso(e.period_start),
                    e.model_dump_json(),
                )
                for e in encounters
            ],
        )

    def _upsert_documents(self, documents: Iterable[CleanDocument]) -> None:
        self._conn.executemany(
            """INSERT INTO documents (document_key, patient_key, encounter_key, doc_type,
                   document_date, content_hash, data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(document_key) DO UPDATE SET patient_key = excluded.patient_key,
                   encounter_key = excluded.encounter_key, doc_type = excluded.doc_type,
                   document_date = excluded.document_date,
                   content_hash = excluded.content_hash, data_json = excluded.data_json""",
            [
                (
                    d.document_key,
                    d.patient_key,
                    d.encounter_key,
                    d.doc_type.value,
                    _iso(d.document_date),
                    d.content_hash,
                    d.model_dump_json(),
                )
                for d in documents
            ],
        )

    def _upsert_labs(self, labs: Iterable[CleanLabResult]) -> None:
        self._conn.executemany(
            """INSERT INTO lab_results (result_key, patient_key, report_key, loinc, collected_at,
                   data_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(result_key) DO UPDATE SET patient_key = excluded.patient_key,
                   report_key = excluded.report_key, loinc = excluded.loinc,
                   collected_at = excluded.collected_at, data_json = excluded.data_json""",
            [
                (
                    r.result_key,
                    r.patient_key,
                    r.report_key,
                    r.loinc,
                    _iso(r.collected_at),
                    r.model_dump_json(),
                )
                for r in labs
            ],
        )

    def _insert_audit(self, run_id: str, entries: Sequence[AuditEntry]) -> None:
        self._conn.executemany(
            """INSERT INTO audit_log (run_id, record_id, patient_key, stage, field, rule, before,
                   after, severity, message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    run_id,
                    a.record_id,
                    a.patient_key,
                    a.stage,
                    a.field,
                    a.rule,
                    a.before,
                    a.after,
                    a.severity,
                    a.message,
                )
                for a in entries
            ],
        )

    def _insert_quarantine(self, run_id: str, records: Sequence[QuarantinedRecord]) -> None:
        self._conn.executemany(
            "INSERT INTO quarantine (run_id, source_locator, reason, payload_json) "
            "VALUES (?, ?, ?, ?)",
            [
                (run_id, q.source_locator, q.reason, json.dumps(q.payload, sort_keys=True))
                for q in records
            ],
        )

    # ---------------------------------------------------------------- reads

    def load_patients(self) -> list[CleanPatient]:
        rows = self._conn.execute("SELECT data_json FROM patients ORDER BY mrn, patient_key")
        return [CleanPatient.model_validate_json(r[0]) for r in rows]

    def load_encounters(self) -> list[CleanEncounter]:
        rows = self._conn.execute("SELECT data_json FROM encounters ORDER BY encounter_key")
        return [CleanEncounter.model_validate_json(r[0]) for r in rows]

    def load_documents(self) -> list[CleanDocument]:
        rows = self._conn.execute("SELECT data_json FROM documents ORDER BY document_key")
        return [CleanDocument.model_validate_json(r[0]) for r in rows]

    def load_lab_results(self) -> list[CleanLabResult]:
        rows = self._conn.execute("SELECT data_json FROM lab_results ORDER BY result_key")
        return [CleanLabResult.model_validate_json(r[0]) for r in rows]

    def load_audit(self, run_id: str) -> list[AuditEntry]:
        rows = self._conn.execute(
            "SELECT record_id, patient_key, stage, field, rule, before, after, severity, message "
            "FROM audit_log WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [AuditEntry(**dict(r)) for r in rows]

    def load_quarantine(self, run_id: str) -> list[QuarantinedRecord]:
        rows = self._conn.execute(
            "SELECT source_locator, reason, payload_json FROM quarantine WHERE run_id = ? "
            "ORDER BY id",
            (run_id,),
        )
        return [
            QuarantinedRecord(source_locator=r[0], reason=r[1], payload=json.loads(r[2]))
            for r in rows
        ]
