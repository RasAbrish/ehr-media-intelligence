"""Code systems and value sets used by the FHIR mappers (docs/03-DATA-MODEL.md section 5.2)."""

from __future__ import annotations

from typing import Final

from ehr_mip.ingestion.models import DocType, EncounterClass

# ---------------------------------------------------------------- systems

MRN_SYSTEM: Final = "urn:oid:2.999.1.1"  # ITU-T example arc: fictional by construction
V2_0203: Final = "http://terminology.hl7.org/CodeSystem/v2-0203"
V2_0074: Final = "http://terminology.hl7.org/CodeSystem/v2-0074"
V3_ACT_CODE: Final = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
V3_NULL_FLAVOR: Final = "http://terminology.hl7.org/CodeSystem/v3-NullFlavor"
V3_INTERPRETATION: Final = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
OBSERVATION_CATEGORY: Final = "http://terminology.hl7.org/CodeSystem/observation-category"
DOCREF_CATEGORY: Final = "http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category"
LOINC: Final = "http://loinc.org"
UCUM: Final = "http://unitsofmeasure.org"
TAG_SYSTEM: Final = "urn:ehr-mip:tags"
BUNDLE_IDENTIFIER_SYSTEM: Final = "urn:ehr-mip:bundle"
TEXT_PLAIN: Final = "text/plain; charset=utf-8"

# ---------------------------------------------------------------- documents

DOC_TYPE_LOINC: Final[dict[DocType, tuple[str, str]]] = {
    DocType.DISCHARGE_SUMMARY: ("18842-5", "Discharge summary"),
    DocType.PROGRESS_NOTE: ("11506-3", "Progress note"),
    DocType.CONSULT_NOTE: ("11488-4", "Consult note"),
    DocType.IMAGING_REPORT: ("18748-4", "Diagnostic imaging study"),
    DocType.LAB_REPORT: ("11502-2", "Laboratory report"),
    DocType.PATHOLOGY_REPORT: ("11526-1", "Pathology study"),
    DocType.SCANNED_DOCUMENT: ("34109-9", "Note"),
}

# Documents that become DiagnosticReports, with their v2-0074 category.
REPORT_CATEGORY: Final[dict[DocType, tuple[str, str]]] = {
    DocType.IMAGING_REPORT: ("RAD", "Radiology"),
    DocType.PATHOLOGY_REPORT: ("PAT", "Pathology (gross & histopath, not surgical)"),
}
LAB_CATEGORY: Final = ("LAB", "Laboratory")

# ---------------------------------------------------------------- encounters

ENCOUNTER_CLASS: Final[dict[EncounterClass, tuple[str, str, str]]] = {
    EncounterClass.INPATIENT: (V3_ACT_CODE, "IMP", "inpatient encounter"),
    EncounterClass.OUTPATIENT: (V3_ACT_CODE, "AMB", "ambulatory"),
    EncounterClass.EMERGENCY: (V3_ACT_CODE, "EMER", "emergency"),
    EncounterClass.VIRTUAL: (V3_ACT_CODE, "VR", "virtual"),
    EncounterClass.UNKNOWN: (V3_NULL_FLAVOR, "UNK", "unknown"),
}

# ---------------------------------------------------------------- labs

INTERPRETATION_DISPLAY: Final = {
    "LL": "Critical low",
    "L": "Low",
    "N": "Normal",
    "H": "High",
    "HH": "Critical high",
}

# Source unit → UCUM code. Units missing here are sent as text only.
UCUM_CODES: Final = {
    "mmol/L": "mmol/L",
    "mg/dL": "mg/dL",
    "g/dL": "g/dL",
    "ng/dL": "ng/dL",
    "pg/mL": "pg/mL",
    "ng/mL": "ng/mL",
    "%": "%",
    "10*3/uL": "10*3/uL",
    "mIU/L": "m[IU]/L",
}

# Known panels: exact member LOINC set → (panel LOINC or None, display, short title).
# A panel code is claimed only when the report holds exactly the panel's defined tests.
# The seven-test chemistry set lacks calcium, which LOINC 51990-0 (BMP) includes, so it
# keeps the generic laboratory report code and only gets a readable title.
PANELS: Final[list[tuple[frozenset[str], str | None, str | None, str]]] = [
    (
        frozenset(
            {"2951-2", "2823-3", "2075-0", "2028-9", "3094-0", "2160-0", "2345-7", "17861-6"}
        ),
        "51990-0",
        "Basic metabolic panel - Blood",
        "Basic metabolic panel",
    ),
    (
        frozenset({"2951-2", "2823-3", "2075-0", "2028-9", "3094-0", "2160-0", "2345-7"}),
        None,
        None,
        "Basic metabolic panel (without calcium)",
    ),
    (
        frozenset({"6690-2", "718-7", "777-3"}),
        "58410-2",
        "CBC panel - Blood by Automated count",
        "Complete blood count",
    ),
    (
        # 13457-7 is LDL by calculation, so this is the standard (calculated LDL) lipid panel.
        frozenset({"2093-3", "13457-7", "2085-9", "2571-8"}),
        "24331-1",
        "Lipid panel - Serum or Plasma",
        "Lipid panel",
    ),
]
LAB_REPORT_CODE: Final = ("11502-2", "Laboratory report")

# ---------------------------------------------------------------- required value sets
# fhir.resources 8 checks code format only, so the validator checks these bindings.

ADMINISTRATIVE_GENDER: Final = frozenset({"male", "female", "other", "unknown"})
STATUS_VALUES: Final[dict[str, frozenset[str]]] = {
    "Encounter": frozenset(
        {
            "planned",
            "arrived",
            "triaged",
            "in-progress",
            "onleave",
            "finished",
            "cancelled",
            "entered-in-error",
            "unknown",
        }
    ),
    "DocumentReference": frozenset({"current", "superseded", "entered-in-error"}),
    "DiagnosticReport": frozenset(
        {
            "registered",
            "partial",
            "preliminary",
            "final",
            "amended",
            "corrected",
            "appended",
            "cancelled",
            "entered-in-error",
            "unknown",
        }
    ),
    "Observation": frozenset(
        {
            "registered",
            "preliminary",
            "final",
            "amended",
            "corrected",
            "cancelled",
            "entered-in-error",
            "unknown",
        }
    ),
}
DOC_STATUS_VALUES: Final = frozenset({"preliminary", "final", "amended", "entered-in-error"})
BUNDLE_TYPES: Final = frozenset(
    {"document", "message", "transaction", "transaction-response", "batch", "batch-response",
     "history", "searchset", "collection"}
)  # fmt: skip
