"""CleanLabResult → FHIR Observation (laboratory)."""

from __future__ import annotations

from typing import Any

from ehr_mip.fhir import codes
from ehr_mip.fhir.mappers.common import concept, fhir_datetime, ref
from ehr_mip.ingestion.models import CleanLabResult

_COMPARATORS = ("<=", ">=", "<", ">")


def quantity(value: float, unit: str | None) -> dict[str, Any]:
    item: dict[str, Any] = {"value": value}
    if unit:
        item["unit"] = unit
        ucum = codes.UCUM_CODES.get(unit)
        if ucum:
            item["system"] = codes.UCUM
            item["code"] = ucum
    return item


def lab_code(lab: CleanLabResult) -> dict[str, Any]:
    if lab.loinc:
        return concept(codes.LOINC, lab.loinc, text=lab.test_name)
    return {"text": lab.test_name}


def map_observation(lab: CleanLabResult) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": lab.result_key,
        "status": "final",
        "category": [concept(codes.OBSERVATION_CATEGORY, "laboratory", "Laboratory")],
        "code": lab_code(lab),
        "subject": ref(lab.patient_key),
    }
    if lab.encounter_key:
        resource["encounter"] = ref(lab.encounter_key)
    effective = fhir_datetime(lab.collected_at)
    if effective:
        resource["effectiveDateTime"] = effective
    if lab.value is not None:
        value = quantity(lab.value, lab.unit)
        comparator = next((c for c in _COMPARATORS if lab.value_raw.startswith(c)), None)
        if comparator:
            value["comparator"] = comparator
        resource["valueQuantity"] = value
    elif lab.value_raw:
        resource["valueString"] = lab.value_raw
    reference_range = {
        key: quantity(limit, lab.unit)
        for key, limit in (("low", lab.ref_low), ("high", lab.ref_high))
        if limit is not None
    }
    if reference_range:
        resource["referenceRange"] = [reference_range]
    if lab.flag:
        display = codes.INTERPRETATION_DISPLAY[lab.flag]
        resource["interpretation"] = [concept(codes.V3_INTERPRETATION, lab.flag, display)]
    return resource
