"""Epic-style JSON export reader: patients, encounters and documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ehr_mip.ingestion.models import QuarantinedRecord, RawRecord
from ehr_mip.ingestion.readers.base import (
    ReadOutput,
    decode,
    encoding_note,
    missing_file,
    safe_path,
)

FILE_NAME = "ehr_export.json"
_PATIENT_FIELDS = ("mrn", "name", "dob", "sex", "phone", "address")
_ENCOUNTER_FIELDS = ("encounter_id", "type", "start", "end")
_DOCUMENT_FIELDS = ("doc_id", "doc_type", "date", "author", "title", "text")


def _pick(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source.get(key) for key in keys}


def _identity(patient: dict[str, Any]) -> dict[str, Any]:
    return {
        "patient_mrn": patient.get("mrn"),
        "patient_name": patient.get("name"),
        "patient_dob": patient.get("dob"),
    }


def _record(locator: str, kind: str, payload: dict[str, Any]) -> RawRecord:
    return RawRecord(
        source_file=FILE_NAME,
        source_format="json",
        source_locator=locator,
        kind=kind,  # type: ignore[arg-type]
        payload=payload,
    )


def read_json(raw_dir: Path, name: str = FILE_NAME) -> ReadOutput:
    path = safe_path(raw_dir, name)
    if not path.is_file():
        return missing_file(name)
    out = ReadOutput()
    text, fell_back = decode(path.read_bytes())
    if fell_back:
        out.notes.append((name, encoding_note()))
    try:
        export = json.loads(text)
        patients = export["patients"]
        if not isinstance(patients, list):
            raise TypeError
    except (json.JSONDecodeError, KeyError, TypeError):
        out.quarantine.append(
            QuarantinedRecord(source_locator=name, reason="read_error", payload={})
        )
        return out

    for i, patient in enumerate(patients):
        p_loc = f"{name}:patients[{i}]"
        if not isinstance(patient, dict):
            out.quarantine.append(
                QuarantinedRecord(source_locator=p_loc, reason="read_error", payload={})
            )
            continue
        out.records.append(_record(p_loc, "patient", _pick(patient, _PATIENT_FIELDS)))
        encounters = patient.get("encounters") or []
        for j, encounter in enumerate(encounters if isinstance(encounters, list) else []):
            e_loc = f"{p_loc}.encounters[{j}]"
            if not isinstance(encounter, dict):
                out.quarantine.append(
                    QuarantinedRecord(source_locator=e_loc, reason="read_error", payload={})
                )
                continue
            out.records.append(
                _record(
                    e_loc, "encounter", _pick(encounter, _ENCOUNTER_FIELDS) | _identity(patient)
                )
            )
            documents = encounter.get("documents") or []
            for k, document in enumerate(documents if isinstance(documents, list) else []):
                d_loc = f"{e_loc}.documents[{k}]"
                if not isinstance(document, dict):
                    out.quarantine.append(
                        QuarantinedRecord(source_locator=d_loc, reason="read_error", payload={})
                    )
                    continue
                payload = (
                    _pick(document, _DOCUMENT_FIELDS)
                    | {"encounter_id": encounter.get("encounter_id")}
                    | _identity(patient)
                )
                out.records.append(_record(d_loc, "document", payload))
    return out
