"""Pure functions from clean ingestion models to FHIR R4B resource dictionaries."""

from ehr_mip.fhir.mappers.diagnostic_report import (
    extract_conclusion,
    lab_conclusion,
    lab_report_code,
    map_imaging_report,
    map_lab_report,
)
from ehr_mip.fhir.mappers.document_reference import map_document_reference
from ehr_mip.fhir.mappers.encounter import map_encounter
from ehr_mip.fhir.mappers.observation import map_observation
from ehr_mip.fhir.mappers.patient import map_patient

__all__ = [
    "extract_conclusion",
    "lab_conclusion",
    "lab_report_code",
    "map_document_reference",
    "map_encounter",
    "map_imaging_report",
    "map_lab_report",
    "map_observation",
    "map_patient",
]
