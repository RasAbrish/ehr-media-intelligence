"""CleanPatient → FHIR Patient."""

from __future__ import annotations

from typing import Any

from ehr_mip.fhir import codes
from ehr_mip.fhir.mappers.common import concept
from ehr_mip.ingestion.models import CleanPatient


def _identifier(mrn: str, use: str) -> dict[str, Any]:
    return {
        "use": use,
        "type": concept(codes.V2_0203, "MR", "Medical record number"),
        "system": codes.MRN_SYSTEM,
        "value": mrn,
    }


def map_patient(patient: CleanPatient) -> dict[str, Any]:
    resource: dict[str, Any] = {"resourceType": "Patient", "id": patient.patient_key}
    if patient.identity_conflict:
        resource["meta"] = {
            "tag": [
                {
                    "system": codes.TAG_SYSTEM,
                    "code": "identity-conflict",
                    "display": "Identity conflict",
                }
            ]
        }
    resource["identifier"] = [_identifier(patient.mrn, "usual")] + [
        _identifier(mrn, "old") for mrn in patient.secondary_mrns
    ]
    name: dict[str, Any] = {"use": "official"}
    if patient.family_name:
        name["family"] = patient.family_name
    if patient.given_names:
        name["given"] = list(patient.given_names)
    if patient.name_suffix:
        name["suffix"] = [patient.name_suffix]
    if len(name) > 1:
        resource["name"] = [name]
    resource["gender"] = patient.gender.value
    if patient.birth_date is not None:
        resource["birthDate"] = patient.birth_date.isoformat()
    return resource
