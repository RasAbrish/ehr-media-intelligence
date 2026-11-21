"""CleanEncounter → FHIR Encounter."""

from __future__ import annotations

from typing import Any

from ehr_mip.fhir import codes
from ehr_mip.fhir.mappers.common import coding, period, ref
from ehr_mip.ingestion.models import CleanEncounter


def map_encounter(encounter: CleanEncounter) -> dict[str, Any]:
    system, code, display = codes.ENCOUNTER_CLASS[encounter.encounter_class]
    resource: dict[str, Any] = {
        "resourceType": "Encounter",
        "id": encounter.encounter_key,
        "status": "finished",
        "class": coding(system, code, display),
        "subject": ref(encounter.patient_key),
    }
    span = period(encounter.period_start, encounter.period_end)
    if span:
        resource["period"] = span
    return resource
