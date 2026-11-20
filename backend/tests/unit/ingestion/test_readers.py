"""Readers (docs/05 section 1.1) and path confinement (docs/09 section 11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ehr_mip.config import PROJECT_ROOT
from ehr_mip.errors import PathOutsideRawDirError
from ehr_mip.ingestion.readers import read_all, read_csv, read_json, read_notes, safe_path

CSV_HEADER = (
    "patient_mrn,patient_name,dob,collected_at,test_name,loinc,value,unit,"
    "ref_low,ref_high,flag,report_id,encounter_id\n"
)


def _write_export(raw: Path, patients: list[object]) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "ehr_export.json").write_text(json.dumps({"patients": patients}), encoding="utf-8")


def test_json_reader_emits_patient_encounter_and_document_records(tmp_path: Path) -> None:
    _write_export(
        tmp_path,
        [
            {
                "mrn": "MRN-00012345",
                "name": "DOE, JANE A",
                "dob": "03/14/1968",
                "sex": "F",
                "encounters": [
                    {
                        "encounter_id": "ENC-1",
                        "type": "inpatient",
                        "start": "2025-02-01 08:30",
                        "end": "2025-02-04",
                        "documents": [{"doc_id": "DOC-1", "doc_type": "Discharge Summary",
                                       "date": "Feb 4 2025", "title": "DS", "text": "x"}],
                    }
                ],
            }
        ],
    )  # fmt: skip
    out = read_json(tmp_path)
    kinds = [r.kind for r in out.records]
    assert kinds == ["patient", "encounter", "document"]
    patient, encounter, document = out.records
    assert patient.source_locator == "ehr_export.json:patients[0]"
    assert encounter.source_locator == "ehr_export.json:patients[0].encounters[0]"
    assert document.source_locator == "ehr_export.json:patients[0].encounters[0].documents[0]"
    # Documents carry the patient identity and the parent encounter id.
    assert document.payload["patient_mrn"] == "MRN-00012345"
    assert document.payload["patient_dob"] == "03/14/1968"
    assert document.payload["encounter_id"] == "ENC-1"
    assert encounter.payload["patient_name"] == "DOE, JANE A"


def test_json_reader_missing_keys_become_missing_fields(tmp_path: Path) -> None:
    _write_export(tmp_path, [{"mrn": "1", "name": "A B", "encounters": []}])
    patient = read_json(tmp_path).records[0]
    assert patient.payload.get("dob") is None
    assert patient.payload.get("sex") is None


def test_json_reader_bad_entry_is_quarantined(tmp_path: Path) -> None:
    _write_export(tmp_path, ["not a patient", {"mrn": "1", "name": "A B"}])
    out = read_json(tmp_path)
    assert [q.reason for q in out.quarantine] == ["read_error"]
    assert out.quarantine[0].source_locator == "ehr_export.json:patients[0]"
    assert len(out.records) == 1


def test_json_reader_malformed_file_is_quarantined(tmp_path: Path) -> None:
    (tmp_path / "ehr_export.json").write_text("{not json", encoding="utf-8")
    out = read_json(tmp_path)
    assert out.records == []
    assert [q.reason for q in out.quarantine] == ["read_error"]


def test_csv_reader_one_record_per_row(tmp_path: Path) -> None:
    (tmp_path / "lab_results.csv").write_text(
        CSV_HEADER
        + '12345,"Jane Doe",1968-03-14,2025-02-02T06:10,Potassium,2823-3,5.9,mmol/L,'
        + "3.5,5.1,H,L1,E1\n"
        + '12345,"Jane Doe",1968-03-14,2025-02-02T06:10,Sodium,2951-2,140,mmol/L,'
        + "136,145,,L1,E1\n",
        encoding="utf-8",
    )
    out = read_csv(tmp_path)
    assert [r.source_locator for r in out.records] == [
        "lab_results.csv:row 1",
        "lab_results.csv:row 2",
    ]
    assert out.records[0].kind == "lab_result"
    assert out.records[0].payload["value"] == "5.9"
    assert out.notes == []


def test_csv_reader_latin1_fallback_audited(tmp_path: Path) -> None:
    row = (
        '12345,"Jos\xe9 P\xe9rez",1968-03-14,2025-02-02T06:10,Potassium,2823-3,4.1,'
        "mmol/L,3.5,5.1,,L1,E1\n"
    )
    (tmp_path / "lab_results.csv").write_bytes((CSV_HEADER + row).encode("latin-1"))
    out = read_csv(tmp_path)
    assert out.records[0].payload["patient_name"] == "José Pérez"
    assert [(rid, n.rule, n.severity) for rid, n in out.notes] == [
        ("lab_results.csv", "read.encoding_fallback", "warning")
    ]


def test_text_reader_parses_header_and_body(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "a.txt").write_text(
        "PATIENT: Jane Doe        MRN: 0012345        DOB: 14-Mar-1968\n"
        "DATE OF SERVICE: 2025/02/02     DOCUMENT: CT CHEST WITH CONTRAST\n"
        "ENCOUNTER: ENC-88231\n---\nFINDINGS: clear.\nIMPRESSION: normal.\n",
        encoding="utf-8",
    )
    record = read_notes(tmp_path).records[0]
    assert record.source_locator == "notes/a.txt"
    assert record.kind == "document"
    assert record.payload == {
        "patient_name": "Jane Doe",
        "patient_mrn": "0012345",
        "patient_dob": "14-Mar-1968",
        "date": "2025/02/02",
        "title": "CT CHEST WITH CONTRAST",
        "encounter_id": "ENC-88231",
        "text": "FINDINGS: clear.\nIMPRESSION: normal.\n",
    }


def test_text_reader_tolerates_missing_header_fields(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "b.txt").write_text(
        "PATIENT: Jane Doe     MRN: 12345     DOB: \nENCOUNTER: \n---\nBody text.\n",
        encoding="utf-8",
    )
    payload = read_notes(tmp_path).records[0].payload
    assert payload["patient_dob"] is None
    assert payload["date"] is None
    assert payload["title"] is None
    assert payload["encounter_id"] is None
    assert payload["text"] == "Body text.\n"


def test_text_reader_without_header_keeps_body(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "c.txt").write_text("Just a scanned page.\n", encoding="utf-8")
    payload = read_notes(tmp_path).records[0].payload
    assert payload["patient_mrn"] is None
    assert payload["text"] == "Just a scanned page.\n"


def test_text_reader_quarantines_empty_document(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "d.txt").write_text("\n\n", encoding="utf-8")
    out = read_notes(tmp_path)
    assert out.records == []
    assert [(q.source_locator, q.reason) for q in out.quarantine] == [
        ("notes/d.txt", "empty_document")
    ]


def test_text_reader_handles_crlf(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "e.txt").write_bytes(b"PATIENT: A B   MRN: 1   DOB: \r\n---\r\nLine one.\r\n")
    payload = read_notes(tmp_path).records[0].payload
    assert payload["patient_mrn"] == "1"
    assert payload["text"] == "Line one.\r\n"  # body kept raw; text.normalize fixes it later


def test_reader_rejects_path_outside_raw_dir(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    (raw / "notes").mkdir(parents=True)
    outside = tmp_path / "secret.txt"
    outside.write_text("PATIENT: A B   MRN: 1\n---\nsecret\n", encoding="utf-8")

    with pytest.raises(PathOutsideRawDirError):
        safe_path(raw, "../secret.txt")
    with pytest.raises(PathOutsideRawDirError):
        safe_path(raw, outside)

    (raw / "notes" / "link.txt").symlink_to(outside)
    out = read_notes(raw)
    assert out.records == []
    assert [(q.source_locator, q.reason) for q in out.quarantine] == [
        ("notes/link.txt", "path_outside_raw_dir")
    ]
    assert "secret" not in json.dumps(out.quarantine[0].payload)


def test_missing_files_are_reported_not_fatal(tmp_path: Path) -> None:
    out = read_all(tmp_path)
    assert out.records == []
    assert {n.rule for _, n in out.notes} == {"read.file_missing"}


def test_read_all_on_generated_data_counts_match_ground_truth() -> None:
    raw = PROJECT_ROOT / "data" / "raw"
    truth = json.loads((raw / "_ground_truth.json").read_text(encoding="utf-8"))
    out = read_all(raw)
    counts = truth["counts"]
    by_kind: dict[str, int] = {}
    for record in out.records:
        by_kind[record.kind] = by_kind.get(record.kind, 0) + 1
    assert by_kind["patient"] == counts["json_patient_entries"]
    assert by_kind["encounter"] == counts["encounters"]
    assert by_kind["lab_result"] == counts["csv_rows"]
    # TXT notes minus the empty scan become document records next to the JSON documents.
    assert by_kind["document"] == counts["json_documents"] + counts["txt_notes"] - 1
    assert [q.reason for q in out.quarantine] == ["empty_document"]
