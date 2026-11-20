"""Builders for tiny raw data folders used by pipeline-level tests."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ehr_mip.ingestion.models import IngestionResult
from ehr_mip.ingestion.pipeline import run_ingestion

TODAY = date(2026, 11, 20)
CSV_COLUMNS = [
    "patient_mrn", "patient_name", "dob", "collected_at", "test_name", "loinc", "value", "unit",
    "ref_low", "ref_high", "flag", "report_id", "encounter_id",
]  # fmt: skip


def patient(
    mrn: str = "00012345",
    name: str = "Jane Doe",
    dob: str | None = "1968-03-14",
    sex: str | None = "female",
    encounters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"mrn": mrn, "name": name, "sex": sex, "encounters": encounters or []}
    if dob is not None:
        entry["dob"] = dob
    if sex is None:
        del entry["sex"]
    return entry


def encounter(
    encounter_id: str = "ENC-1", documents: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "encounter_id": encounter_id,
        "type": "inpatient",
        "start": "2025-02-01T08:30",
        "end": "2025-02-04",
        "documents": documents or [],
    }


def document(
    doc_id: str = "DOC-1",
    text: str = "HOSPITAL COURSE: Treated for pneumonia.\nPLAN: Amoxicillin.",
    doc_date: str = "2025-02-04",
    doc_type: str = "Discharge Summary",
    title: str = "Discharge Summary",
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "date": doc_date,
        "author": "Dr. A. Rivera",
        "title": title,
        "text": text,
    }


def note_text(
    body: str,
    *,
    name: str = "Jane Doe",
    mrn: str = "00012345",
    dob: str = "1968-03-14",
    when: str = "2025-02-04",
    title: str = "DISCHARGE SUMMARY",
    encounter_id: str = "ENC-1",
) -> str:
    return (
        f"PATIENT: {name}   MRN: {mrn}   DOB: {dob}\n"
        f"DATE OF SERVICE: {when}   DOCUMENT: {title}\n"
        f"ENCOUNTER: {encounter_id}\n---\n{body}\n"
    )


@dataclass
class RawFolder:
    root: Path
    patients: list[dict[str, Any]] = field(default_factory=list)
    lab_rows: list[dict[str, str]] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)

    def write(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "ehr_export.json").write_text(
            json.dumps({"patients": self.patients}), encoding="utf-8"
        )
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in self.lab_rows:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})
        (self.root / "lab_results.csv").write_text(buf.getvalue(), encoding="utf-8")
        notes_dir = self.root / "notes"
        notes_dir.mkdir(exist_ok=True)
        for name, text in self.notes.items():
            (notes_dir / name).write_text(text, encoding="utf-8")
        return self.root

    def run(self) -> IngestionResult:
        return run_ingestion(self.write(), today=TODAY)


@pytest.fixture
def raw(tmp_path: Path) -> RawFolder:
    return RawFolder(tmp_path / "raw")


LabRow = Callable[..., dict[str, str]]


def lab_row(**overrides: str) -> dict[str, str]:
    row = {
        "patient_mrn": "00012345",
        "patient_name": "Jane Doe",
        "dob": "1968-03-14",
        "collected_at": "2025-02-02T06:10",
        "test_name": "Potassium",
        "loinc": "2823-3",
        "value": "4.2",
        "unit": "mmol/L",
        "ref_low": "3.5",
        "ref_high": "5.1",
        "flag": "",
        "report_id": "LAB-1",
        "encounter_id": "ENC-1",
    }
    row.update(overrides)
    return row
