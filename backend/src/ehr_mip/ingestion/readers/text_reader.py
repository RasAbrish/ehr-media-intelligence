"""Scanned note reader: a labelled header, a ``---`` line, then the body.

Missing header labels become missing fields. A note with no body is quarantined
as ``empty_document``; a file that resolves outside the raw folder is quarantined
as ``path_outside_raw_dir`` without being read.
"""

from __future__ import annotations

import re
from pathlib import Path

from ehr_mip.errors import PathOutsideRawDirError
from ehr_mip.ingestion.models import QuarantinedRecord, RawRecord
from ehr_mip.ingestion.readers.base import (
    ReadOutput,
    decode,
    encoding_note,
    missing_file,
    safe_path,
)

FOLDER = "notes"
_LABELS = re.compile(r"\b(PATIENT|MRN|DOB|DATE OF SERVICE|DOCUMENT|ENCOUNTER):")
_SEPARATOR = re.compile(r"^---[ \t]*\r?$", re.MULTILINE)
_FIELD_NAMES = {
    "PATIENT": "patient_name",
    "MRN": "patient_mrn",
    "DOB": "patient_dob",
    "DATE OF SERVICE": "date",
    "DOCUMENT": "title",
    "ENCOUNTER": "encounter_id",
}


def parse_note(text: str) -> dict[str, str | None]:
    """Split a note into header fields and body. Empty header values become None."""
    payload: dict[str, str | None] = dict.fromkeys(_FIELD_NAMES.values())
    separator = _SEPARATOR.search(text)
    if separator is None:
        payload["text"] = text
        return payload
    header, body = text[: separator.start()], text[separator.end() :]
    for line in header.splitlines():
        parts = _LABELS.split(line)
        for label, value in zip(parts[1::2], parts[2::2], strict=True):
            payload[_FIELD_NAMES[label]] = value.strip() or None
    payload["text"] = body.removeprefix("\n")
    return payload


def read_notes(raw_dir: Path, folder: str = FOLDER) -> ReadOutput:
    notes_dir = safe_path(raw_dir, folder)
    if not notes_dir.is_dir():
        return missing_file(folder)
    out = ReadOutput()
    for entry in sorted(notes_dir.glob("*.txt")):
        locator = f"{folder}/{entry.name}"
        try:
            path = safe_path(raw_dir, entry)
        except PathOutsideRawDirError:
            out.quarantine.append(
                QuarantinedRecord(source_locator=locator, reason="path_outside_raw_dir", payload={})
            )
            continue
        text, fell_back = decode(path.read_bytes())
        if fell_back:
            out.notes.append((locator, encoding_note()))
        payload = parse_note(text)
        body = payload["text"] or ""
        if not body.strip():
            out.quarantine.append(
                QuarantinedRecord(source_locator=locator, reason="empty_document", payload={})
            )
            continue
        out.records.append(
            RawRecord(
                source_file=locator,
                source_format="txt",
                source_locator=locator,
                kind="document",
                payload=dict(payload),
            )
        )
    return out
