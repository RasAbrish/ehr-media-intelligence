"""Audit primitives.

Cleaners do not know which record or patient they work on, so they return
``Note`` objects. The pipeline turns notes into ``AuditEntry`` rows once the
record id and the resolved patient key are known.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from ehr_mip.ingestion.models import AuditEntry, Severity, Stage

T_co = TypeVar("T_co", covariant=True)


@dataclass(frozen=True, slots=True)
class Note:
    """One change or finding produced by a rule."""

    rule: str
    severity: Severity
    message: str
    before: str | None = None
    after: str | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class Cleaned(Generic[T_co]):
    """A rule result: the new value plus the notes explaining any change."""

    value: T_co
    notes: tuple[Note, ...] = ()


def with_field(notes: tuple[Note, ...] | list[Note], field: str) -> list[Note]:
    """Attach a field name to notes that do not carry one yet."""
    return [
        n if n.field is not None else Note(n.rule, n.severity, n.message, n.before, n.after, field)
        for n in notes
    ]


def to_entry(note: Note, record_id: str, patient_key: str | None, stage: Stage) -> AuditEntry:
    return AuditEntry(
        record_id=record_id,
        patient_key=patient_key,
        stage=stage,
        field=note.field,
        rule=note.rule,
        before=note.before,
        after=note.after,
        severity=note.severity,
        message=note.message,
    )
