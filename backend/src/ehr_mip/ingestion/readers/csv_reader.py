"""Lab results CSV reader: one record per row."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ehr_mip.ingestion.models import QuarantinedRecord, RawRecord
from ehr_mip.ingestion.readers.base import (
    ReadOutput,
    decode,
    encoding_note,
    missing_file,
    safe_path,
)

FILE_NAME = "lab_results.csv"


def read_csv(raw_dir: Path, name: str = FILE_NAME) -> ReadOutput:
    path = safe_path(raw_dir, name)
    if not path.is_file():
        return missing_file(name)
    out = ReadOutput()
    text, fell_back = decode(path.read_bytes())
    if fell_back:
        out.notes.append((name, encoding_note()))
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        for row_number, row in enumerate(reader, start=1):
            locator = f"{name}:row {row_number}"
            payload = {key: value for key, value in row.items() if isinstance(key, str)}
            out.records.append(
                RawRecord(
                    source_file=name,
                    source_format="csv",
                    source_locator=locator,
                    kind="lab_result",
                    payload=payload,
                )
            )
    except csv.Error:
        out.quarantine.append(
            QuarantinedRecord(source_locator=name, reason="read_error", payload={})
        )
    return out
