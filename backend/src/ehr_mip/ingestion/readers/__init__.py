"""Readers for the three raw formats. Reader problems never stop a run."""

from __future__ import annotations

from pathlib import Path

from ehr_mip.ingestion.readers.base import ReadOutput, safe_path
from ehr_mip.ingestion.readers.csv_reader import read_csv
from ehr_mip.ingestion.readers.json_reader import read_json
from ehr_mip.ingestion.readers.text_reader import parse_note, read_notes

__all__ = [
    "ReadOutput",
    "parse_note",
    "read_all",
    "read_csv",
    "read_json",
    "read_notes",
    "safe_path",
]


def read_all(raw_dir: Path) -> ReadOutput:
    """Read JSON, CSV and TXT sources, in that order (it decides "earliest source" ties)."""
    out = ReadOutput()
    for reader in (read_json, read_csv, read_notes):
        out.extend(reader(raw_dir))
    return out
