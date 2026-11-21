"""A typed, read-only view of one patient's FHIR bundle for summarization."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from ehr_mip.ingestion.cleaners.dates import NY
from ehr_mip.summarization.schemas import EvidenceRef

RecordKind = Literal["note", "imaging", "pathology", "lab"]
_REPORT_KINDS: dict[str, RecordKind] = {"RAD": "imaging", "PAT": "pathology"}


@dataclass(frozen=True)
class PatientInfo:
    patient_key: str
    family: str | None
    given: tuple[str, ...]
    birth_date: date | None
    gender: str
    mrns: tuple[str, ...]
    merged: bool
    conflict: bool


@dataclass(frozen=True)
class LabValue:
    ref: EvidenceRef
    report_key: str | None
    test_name: str
    loinc: str | None
    value: float | None
    value_text: str
    unit: str | None
    low: float | None
    high: float | None
    flag: str | None
    when: date | None


@dataclass(frozen=True)
class SourceRecord:
    """A note, imaging or pathology report, or lab report the summary may cite."""

    ref: EvidenceRef
    kind: RecordKind
    subtype: str
    when: date | None
    title: str
    text: str
    conclusion: str | None = None
    results: tuple[LabValue, ...] = ()


@dataclass(frozen=True)
class EncounterInfo:
    ref: EvidenceRef
    start: date | None
    encounter_class: str


@dataclass
class BundleView:
    patient: PatientInfo
    records: list[SourceRecord] = field(default_factory=list)
    labs: list[LabValue] = field(default_factory=list)
    encounters: list[EncounterInfo] = field(default_factory=list)

    @property
    def ref_keys(self) -> set[str]:
        """Every resource that may be cited: records, lab results and encounters."""
        keys = {r.ref.key for r in self.records}
        keys |= {lab.ref.key for lab in self.labs}
        keys |= {e.ref.key for e in self.encounters}
        return keys

    def text_for(self, key: str) -> str:
        """Searchable text of a citable resource (for the diagnosis support check)."""
        for record in self.records:
            if record.ref.key == key:
                return "\n".join(
                    p for p in (record.title, record.conclusion or "", record.text) if p
                )
        for lab in self.labs:
            if lab.ref.key == key:
                return f"{lab.test_name} {lab.value_text} {lab.unit or ''} {lab.flag or ''}"
        return ""

    def latest_date(self) -> date | None:
        dates = [r.when for r in self.records if r.when]
        dates += [lab.when for lab in self.labs if lab.when]
        dates += [e.start for e in self.encounters if e.start]
        return max(dates) if dates else None


def _to_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:  # noqa: PLR2004
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value).astimezone(NY).date()
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _decode(attachment: dict[str, Any] | None) -> str:
    if not attachment or not isinstance(attachment.get("data"), str):
        return ""
    try:
        return base64.b64decode(attachment["data"]).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return ""


def _code(concept: dict[str, Any] | None) -> str | None:
    codings = (concept or {}).get("coding") or []
    return codings[0].get("code") if codings else None


def _patient(resource: dict[str, Any]) -> PatientInfo:
    name = (resource.get("name") or [{}])[0]
    identifiers = resource.get("identifier") or []
    tags = (resource.get("meta") or {}).get("tag") or []
    return PatientInfo(
        patient_key=str(resource["id"]),
        family=name.get("family"),
        given=tuple(name.get("given") or ()),
        birth_date=_to_date(resource.get("birthDate")),
        gender=str(resource.get("gender", "unknown")),
        mrns=tuple(str(i.get("value")) for i in identifiers if i.get("value")),
        merged=any(i.get("use") == "old" for i in identifiers),
        conflict=any(t.get("code") == "identity-conflict" for t in tags),
    )


def _observation(resource: dict[str, Any], report_of: dict[str, str]) -> LabValue:
    quantity = resource.get("valueQuantity") or {}
    value = quantity.get("value")
    comparator = quantity.get("comparator", "")
    value_text = (
        f"{comparator}{value:g}"
        if isinstance(value, int | float)
        else str(resource.get("valueString", ""))
    )
    ranges = (resource.get("referenceRange") or [{}])[0]
    ref = EvidenceRef(resource_type="Observation", resource_id=str(resource["id"]))
    return LabValue(
        ref=ref,
        report_key=report_of.get(ref.key),
        test_name=str(
            (resource.get("code") or {}).get("text") or _code(resource.get("code")) or "Test"
        ),
        loinc=_code(resource.get("code")),
        value=float(value) if isinstance(value, int | float) else None,
        value_text=value_text,
        unit=quantity.get("unit") or (ranges.get("low") or ranges.get("high") or {}).get("unit"),
        low=(ranges.get("low") or {}).get("value"),
        high=(ranges.get("high") or {}).get("value"),
        flag=_code((resource.get("interpretation") or [{}])[0]),
        when=_to_date(resource.get("effectiveDateTime")),
    )


def read_bundle(bundle: dict[str, Any]) -> BundleView:
    """Build a view of a bundle produced by ``ehr_mip.fhir.bundle.build_bundle``."""
    resources = [
        e["resource"] for e in bundle.get("entry", []) if isinstance(e.get("resource"), dict)
    ]
    patient = next(r for r in resources if r.get("resourceType") == "Patient")
    view = BundleView(patient=_patient(patient))

    report_of: dict[str, str] = {}
    for resource in resources:
        if resource.get("resourceType") == "DiagnosticReport":
            for result in resource.get("result") or []:
                target = str(result.get("reference", "")).removeprefix("urn:uuid:")
                report_of[f"Observation/{target}"] = f"DiagnosticReport/{resource['id']}"

    for resource in resources:
        if resource.get("resourceType") == "Observation":
            view.labs.append(_observation(resource, report_of))
    labs_by_report: dict[str, list[LabValue]] = {}
    for lab in view.labs:
        if lab.report_key:
            labs_by_report.setdefault(lab.report_key, []).append(lab)

    for resource in resources:
        kind = resource.get("resourceType")
        rid = str(resource.get("id"))
        if kind == "Encounter":
            view.encounters.append(
                EncounterInfo(
                    ref=EvidenceRef(resource_type="Encounter", resource_id=rid),
                    start=_to_date((resource.get("period") or {}).get("start")),
                    encounter_class=str((resource.get("class") or {}).get("code", "UNK")),
                )
            )
        elif kind == "DocumentReference":
            attachment = ((resource.get("content") or [{}])[0] or {}).get("attachment") or {}
            view.records.append(
                SourceRecord(
                    ref=EvidenceRef(resource_type="DocumentReference", resource_id=rid),
                    kind="note",
                    subtype=_doc_subtype(resource),
                    when=_to_date(resource.get("date")) or _to_date(attachment.get("creation")),
                    title=str(resource.get("description") or "Document"),
                    text=_decode(attachment),
                )
            )
        elif kind == "DiagnosticReport":
            category = _code((resource.get("category") or [{}])[0]) or "LAB"
            ref = EvidenceRef(resource_type="DiagnosticReport", resource_id=rid)
            results = tuple(labs_by_report.get(ref.key, []))
            forms = resource.get("presentedForm") or []
            view.records.append(
                SourceRecord(
                    ref=ref,
                    kind=_REPORT_KINDS.get(category, "lab"),
                    subtype=category,
                    when=_to_date(resource.get("effectiveDateTime")),
                    title=str((resource.get("code") or {}).get("text") or "Report"),
                    text=_decode(forms[0]) if forms else "",
                    conclusion=resource.get("conclusion"),
                    results=results,
                )
            )
    return view


_LOINC_DOC_TYPES = {
    "18842-5": "discharge_summary",
    "11506-3": "progress_note",
    "11488-4": "consult_note",
    "18748-4": "imaging_report",
    "11502-2": "lab_report",
    "11526-1": "pathology_report",
    "34109-9": "scanned_document",
}


def _doc_subtype(resource: dict[str, Any]) -> str:
    return _LOINC_DOC_TYPES.get(_code(resource.get("type")) or "", "scanned_document")
