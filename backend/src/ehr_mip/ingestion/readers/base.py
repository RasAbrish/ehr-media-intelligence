"""Shared reader types and path confinement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ehr_mip.errors import PathOutsideRawDirError
from ehr_mip.ingestion.audit import Note
from ehr_mip.ingestion.models import QuarantinedRecord, RawRecord


@dataclass
class ReadOutput:
    """What a reader produced. ``notes`` are file-level findings keyed by record id."""

    records: list[RawRecord] = field(default_factory=list)
    quarantine: list[QuarantinedRecord] = field(default_factory=list)
    notes: list[tuple[str, Note]] = field(default_factory=list)

    def extend(self, other: ReadOutput) -> None:
        self.records.extend(other.records)
        self.quarantine.extend(other.quarantine)
        self.notes.extend(other.notes)


def safe_path(raw_dir: Path, path: str | Path) -> Path:
    """Resolve ``path`` (relative to ``raw_dir`` or absolute) and refuse anything outside it.

    Symlinks are resolved first, so a link pointing outside the raw folder is refused too.
    """
    root = raw_dir.resolve()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not resolved.is_relative_to(root):
        msg = "Refusing to read outside the raw data folder."
        raise PathOutsideRawDirError(msg)
    return resolved


def decode(data: bytes) -> tuple[str, bool]:
    """Decode UTF-8 (with or without BOM), falling back to Latin-1. Returns (text, fell_back)."""
    try:
        return data.decode("utf-8-sig"), False
    except UnicodeDecodeError:
        return data.decode("latin-1"), True


def missing_file(name: str) -> ReadOutput:
    note = Note("read.file_missing", "warning", "Source file not found; nothing read from it.")
    return ReadOutput(notes=[(name, note)])


def encoding_note() -> Note:
    return Note("read.encoding_fallback", "warning", "File is not UTF-8; decoded as Latin-1.")
