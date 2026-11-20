"""Gender codes to FHIR AdministrativeGender (docs/05 section 1.3, rule ``gender.map``)."""

from __future__ import annotations

from ehr_mip.ingestion.audit import Cleaned, Note
from ehr_mip.ingestion.models import AdministrativeGender

_MAP: dict[str, AdministrativeGender] = {
    "m": AdministrativeGender.MALE,
    "male": AdministrativeGender.MALE,
    "1": AdministrativeGender.MALE,
    "f": AdministrativeGender.FEMALE,
    "female": AdministrativeGender.FEMALE,
    "2": AdministrativeGender.FEMALE,
    "o": AdministrativeGender.OTHER,
    "other": AdministrativeGender.OTHER,
    "x": AdministrativeGender.OTHER,
    "nonbinary": AdministrativeGender.OTHER,
    "non-binary": AdministrativeGender.OTHER,
    "u": AdministrativeGender.UNKNOWN,
    "unk": AdministrativeGender.UNKNOWN,
    "unknown": AdministrativeGender.UNKNOWN,
    "": AdministrativeGender.UNKNOWN,
}


def normalize_gender(raw: str | None) -> Cleaned[AdministrativeGender]:
    if raw is None:
        note = Note("field.missing", "info", "Gender is missing; set to unknown.")
        return Cleaned(AdministrativeGender.UNKNOWN, (note,))
    value = _MAP.get(raw.strip().lower())
    if value is None:
        note = Note(
            "gender.unmapped",
            "warning",
            "Unrecognized gender code; set to unknown.",
            raw,
            "unknown",
        )
        return Cleaned(AdministrativeGender.UNKNOWN, (note,))
    if raw == value.value:
        return Cleaned(value)
    note = Note("gender.map", "info", "Mapped to FHIR AdministrativeGender.", raw, value.value)
    return Cleaned(value, (note,))
