"""Per-mapper validity and field mapping (docs/03 section 5.3). Written before the mappers."""

from __future__ import annotations

import base64
import hashlib
from datetime import date, datetime
from typing import Any

import pytest
from fhir.resources.R4B.diagnosticreport import DiagnosticReport
from fhir.resources.R4B.documentreference import DocumentReference
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient
from tests.support.clean_models import (
    NY,
    PATIENT_KEY,
    make_document,
    make_encounter,
    make_lab,
    make_patient,
)

from ehr_mip.fhir import codes
from ehr_mip.fhir.mappers import (
    extract_conclusion,
    lab_report_code,
    map_document_reference,
    map_encounter,
    map_imaging_report,
    map_lab_report,
    map_observation,
    map_patient,
)
from ehr_mip.ingestion.models import AdministrativeGender, DocType, EncounterClass

PATIENT_REF = {"reference": f"urn:uuid:{PATIENT_KEY}"}


def codings(concept: dict[str, Any]) -> list[tuple[str, str]]:
    return [(c["system"], c["code"]) for c in concept["coding"]]


# ---------------------------------------------------------------- Patient


def test_patient_mapper_output_is_valid() -> None:
    resource = map_patient(make_patient())
    Patient.model_validate(resource)
    assert resource["id"] == PATIENT_KEY
    assert resource["gender"] == "female"
    assert resource["birthDate"] == "1968-03-14"
    assert resource["name"] == [{"use": "official", "family": "Doe", "given": ["Jane", "A"]}]
    (mrn,) = resource["identifier"]
    assert mrn["use"] == "usual"
    assert mrn["system"] == codes.MRN_SYSTEM
    assert mrn["value"] == "00012345"
    assert codings(mrn["type"]) == [(codes.V2_0203, "MR")]
    assert "meta" not in resource


def test_patient_secondary_mrns_are_old_identifiers() -> None:
    resource = map_patient(make_patient(secondary_mrns=["00098765"]))
    assert [(i["use"], i["value"]) for i in resource["identifier"]] == [
        ("usual", "00012345"),
        ("old", "00098765"),
    ]


def test_patient_conflict_tag_and_missing_birthdate() -> None:
    resource = map_patient(
        make_patient(identity_conflict=True, birth_date=None, gender=AdministrativeGender.UNKNOWN)
    )
    Patient.model_validate(resource)
    assert resource["meta"]["tag"] == [
        {"system": codes.TAG_SYSTEM, "code": "identity-conflict", "display": "Identity conflict"}
    ]
    assert "birthDate" not in resource
    assert resource["gender"] == "unknown"


def test_patient_without_name_omits_name() -> None:
    resource = map_patient(make_patient(family_name=None, given_names=[]))
    assert "name" not in resource


# ---------------------------------------------------------------- Encounter


def test_encounter_mapper_output_is_valid() -> None:
    encounter = make_encounter()
    resource = map_encounter(encounter)
    Encounter.model_validate(resource)
    assert resource["status"] == "finished"
    assert resource["class"] == {
        "system": codes.V3_ACT_CODE,
        "code": "IMP",
        "display": "inpatient encounter",
    }
    assert resource["subject"] == PATIENT_REF
    # Start keeps its time and offset; the date-only end keeps date precision.
    assert resource["period"] == {"start": "2025-02-01T08:30:00-05:00", "end": "2025-02-04"}


def test_encounter_unknown_class_uses_null_flavor() -> None:
    resource = map_encounter(make_encounter(encounter_class=EncounterClass.UNKNOWN))
    Encounter.model_validate(resource)
    assert resource["class"]["code"] == "UNK"


# ---------------------------------------------------------------- DocumentReference


def test_document_reference_mapper_output_is_valid() -> None:
    encounter = make_encounter()
    doc = make_document(encounter=encounter)
    resource = map_document_reference(doc, encounter)
    DocumentReference.model_validate(resource)
    assert resource["id"] == doc.document_key
    assert (resource["status"], resource["docStatus"]) == ("current", "final")
    assert codings(resource["type"]) == [(codes.LOINC, "18842-5")]
    assert codings(resource["category"][0]) == [(codes.DOCREF_CATEGORY, "clinical-note")]
    assert resource["subject"] == PATIENT_REF
    assert resource["author"] == [{"display": "Dr. A. Rivera"}]
    assert resource["description"] == "Discharge Summary"
    attachment = resource["content"][0]["attachment"]
    assert attachment["contentType"] == codes.TEXT_PLAIN
    raw = doc.text.encode("utf-8")
    assert base64.b64decode(attachment["data"]) == raw
    assert attachment["size"] == len(raw)
    assert attachment["hash"] == base64.b64encode(hashlib.sha1(raw).digest()).decode()  # noqa: S324
    assert resource["context"]["encounter"] == [
        {"reference": f"urn:uuid:{encounter.encounter_key}"}
    ]
    assert resource["context"]["period"] == {
        "start": "2025-02-01T08:30:00-05:00",
        "end": "2025-02-04",
    }


def test_document_date_only_goes_to_creation_not_instant() -> None:
    resource = map_document_reference(make_document(), None)
    DocumentReference.model_validate(resource)
    assert "date" not in resource  # an instant needs a time; none is invented
    assert resource["content"][0]["attachment"]["creation"] == "2025-02-04"


def test_document_with_time_sets_instant() -> None:
    doc = make_document(document_date=datetime(2025, 2, 4, 14, 5, tzinfo=NY))
    resource = map_document_reference(doc, None)
    DocumentReference.model_validate(resource)
    assert resource["date"] == "2025-02-04T14:05:00-05:00"


def test_encounter_omitted_when_absent() -> None:
    resource = map_document_reference(make_document(), None)
    assert "context" not in resource
    report = map_lab_report([make_lab()])
    assert "encounter" not in report
    assert "encounter" not in map_observation(make_lab())


# ---------------------------------------------------------------- imaging and pathology


IMAGING_TEXT = (
    "FINDINGS: Filling defects in the right lower lobe pulmonary arteries.\n"
    "IMPRESSION: Acute pulmonary embolism with mild right heart strain."
)


def test_imaging_report_mapper_output_is_valid() -> None:
    encounter = make_encounter()
    doc = make_document(
        IMAGING_TEXT, DocType.IMAGING_REPORT, encounter, title="CT ANGIOGRAPHY CHEST"
    )
    resource = map_imaging_report(doc, encounter)
    DiagnosticReport.model_validate(resource)
    assert resource["id"] == doc.document_key
    assert resource["status"] == "final"
    assert codings(resource["category"][0]) == [(codes.V2_0074, "RAD")]
    assert codings(resource["code"]) == [(codes.LOINC, "18748-4")]
    assert resource["code"]["text"] == "CT ANGIOGRAPHY CHEST"
    assert resource["effectiveDateTime"] == "2025-02-04"
    assert "issued" not in resource
    assert resource["conclusion"] == "Acute pulmonary embolism with mild right heart strain."
    form = resource["presentedForm"][0]
    assert base64.b64decode(form["data"]).decode() == IMAGING_TEXT
    assert resource["encounter"] == {"reference": f"urn:uuid:{encounter.encounter_key}"}


def test_pathology_report_category() -> None:
    text = "SPECIMEN: Left breast core biopsy.\nDIAGNOSIS: Invasive ductal carcinoma, grade 2."
    resource = map_imaging_report(make_document(text, DocType.PATHOLOGY_REPORT), None)
    DiagnosticReport.model_validate(resource)
    assert codings(resource["category"][0]) == [(codes.V2_0074, "PAT")]
    assert codings(resource["code"]) == [(codes.LOINC, "11526-1")]
    assert resource["conclusion"] == "Invasive ductal carcinoma, grade 2."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (IMAGING_TEXT, "Acute pulmonary embolism with mild right heart strain."),
        ("IMPRESSION: Line one\ncontinues here.\nRECOMMENDATION: none", "Line one continues here."),
        ("impression: lower case header", "lower case header"),
        ("FINDINGS: no impression section", None),
    ],
)
def test_extract_conclusion(text: str, expected: str | None) -> None:
    assert extract_conclusion(text) == expected


# ---------------------------------------------------------------- labs


def test_observation_mapper_output_is_valid() -> None:
    encounter = make_encounter()
    lab = make_lab(encounter=encounter)
    resource = map_observation(lab)
    Observation.model_validate(resource)
    assert resource["id"] == lab.result_key
    assert resource["status"] == "final"
    assert codings(resource["category"][0]) == [(codes.OBSERVATION_CATEGORY, "laboratory")]
    assert codings(resource["code"]) == [(codes.LOINC, "2823-3")]
    assert resource["code"]["text"] == "Potassium"
    assert resource["valueQuantity"] == {
        "value": 5.9,
        "unit": "mmol/L",
        "system": codes.UCUM,
        "code": "mmol/L",
    }
    assert resource["referenceRange"] == [
        {
            "low": {"value": 3.5, "unit": "mmol/L", "system": codes.UCUM, "code": "mmol/L"},
            "high": {"value": 5.1, "unit": "mmol/L", "system": codes.UCUM, "code": "mmol/L"},
        }
    ]
    assert codings(resource["interpretation"][0]) == [(codes.V3_INTERPRETATION, "H")]
    assert resource["effectiveDateTime"] == "2025-02-02T06:10:00-05:00"
    assert resource["encounter"] == {"reference": f"urn:uuid:{encounter.encounter_key}"}


def test_observation_comparator_and_ucum_mapping() -> None:
    lab = make_lab("Troponin I", "10839-9", 0.01, value_raw="<0.01", unit="ng/mL",
                   ref_low=None, ref_high=0.04, flag="N")  # fmt: skip
    resource = map_observation(lab)
    Observation.model_validate(resource)
    assert resource["valueQuantity"]["comparator"] == "<"
    assert resource["referenceRange"] == [
        {"high": {"value": 0.04, "unit": "ng/mL", "system": codes.UCUM, "code": "ng/mL"}}
    ]
    tsh = map_observation(make_lab("TSH", "3016-3", 9.8, unit="mIU/L"))
    assert tsh["valueQuantity"]["code"] == "m[IU]/L"


def test_observation_non_numeric_value_and_unknown_unit() -> None:
    lab = make_lab(value=None, value_raw="see note", unit="widgets", flag=None, loinc=None)
    resource = map_observation(lab)
    Observation.model_validate(resource)
    assert resource["valueString"] == "see note"
    assert "valueQuantity" not in resource
    assert "interpretation" not in resource
    assert resource["code"] == {"text": "Potassium"}
    assert resource["referenceRange"][0]["low"] == {"value": 3.5, "unit": "widgets"}


def test_lab_report_mapper_output_is_valid() -> None:
    encounter = make_encounter()
    labs = [
        make_lab(encounter=encounter),
        make_lab("Creatinine", "2160-0", 2.1, unit="mg/dL", ref_low=0.6, ref_high=1.2,
                 encounter=encounter),
        make_lab("Sodium", "2951-2", 140, ref_low=136, ref_high=145, flag="N",
                 encounter=encounter),
    ]  # fmt: skip
    resource = map_lab_report(labs)
    DiagnosticReport.model_validate(resource)
    assert resource["id"] == labs[0].report_key
    assert codings(resource["category"][0]) == [(codes.V2_0074, "LAB")]
    assert resource["result"] == [{"reference": f"urn:uuid:{lab.result_key}"} for lab in labs]
    assert resource["effectiveDateTime"] == "2025-02-02T06:10:00-05:00"
    assert resource["conclusion"] == "2 abnormal: Potassium H, Creatinine H."
    assert resource["encounter"] == {"reference": f"urn:uuid:{encounter.encounter_key}"}


def test_lab_report_all_normal_conclusion() -> None:
    resource = map_lab_report([make_lab(value=4.2, flag="N")])
    assert resource["conclusion"] == "All results within the reference range."


@pytest.mark.parametrize(
    ("loincs", "code", "title"),
    [
        (["2951-2", "2823-3", "2075-0", "2028-9", "3094-0", "2160-0", "2345-7", "17861-6"],
         "51990-0", "Basic metabolic panel"),
        # Without calcium the set is not a LOINC BMP: generic code, honest title.
        (["2951-2", "2823-3", "2075-0", "2028-9", "3094-0", "2160-0", "2345-7"], "11502-2",
         "Basic metabolic panel (without calcium)"),
        (["6690-2", "718-7", "777-3"], "58410-2", "Complete blood count"),
        # 13457-7 is calculated LDL, so the standard lipid panel, not the direct-LDL one.
        (["2093-3", "13457-7", "2085-9", "2571-8"], "24331-1", "Lipid panel"),
        (["4548-4"], "4548-4", "Hemoglobin A1c"),
        (["3016-3", "3024-7"], "11502-2", "TSH and Free T4"),
    ],
)  # fmt: skip
def test_lab_report_code(loincs: list[str], code: str, title: str) -> None:
    names = {"4548-4": "Hemoglobin A1c", "3016-3": "TSH", "3024-7": "Free T4"}
    labs = [make_lab(names.get(c, c), c) for c in loincs]
    coding, text = lab_report_code(labs)
    assert coding[1] == code
    assert text == title


def test_lab_report_date_only_collection() -> None:
    resource = map_lab_report([make_lab(collected_at=date(2025, 2, 2))])
    DiagnosticReport.model_validate(resource)
    assert resource["effectiveDateTime"] == "2025-02-02"


# ---------------------------------------------------------------- review regressions


def test_conclusion_keeps_lower_case_lines_with_colons() -> None:
    text = "IMPRESSION: Stable nodule.\nComparison with prior: unchanged.\nRECOMMENDATION: none"
    assert extract_conclusion(text) == "Stable nodule. Comparison with prior: unchanged."


def test_patient_name_suffix_is_kept() -> None:
    resource = map_patient(
        make_patient(given_names=["John"], family_name="Smith", name_suffix="Jr.")
    )
    Patient.model_validate(resource)
    assert resource["name"] == [
        {"use": "official", "family": "Smith", "given": ["John"], "suffix": ["Jr."]}
    ]
