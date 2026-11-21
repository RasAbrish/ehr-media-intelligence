"""Task 1 pipeline: read, clean, resolve identities, dedupe, audit (docs/05 section 1).

The pipeline never aborts on a bad record: unreadable or unresolvable records go
to quarantine with a reason, everything else is cleaned and audited.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import structlog

from ehr_mip import ids
from ehr_mip.ingestion.audit import Note, to_entry, with_field
from ehr_mip.ingestion.cleaners.dates import parse_date, parse_datetime, today_local
from ehr_mip.ingestion.cleaners.doctype import classify_doc_type
from ehr_mip.ingestion.cleaners.gender import normalize_gender
from ehr_mip.ingestion.cleaners.labs import parse_lab_value, parse_number, recompute_flag
from ehr_mip.ingestion.cleaners.mrn import normalize_mrn
from ehr_mip.ingestion.cleaners.names import PersonName, normalize_name
from ehr_mip.ingestion.cleaners.text import content_hash, normalize_text
from ehr_mip.ingestion.dedupe import Ordered, dedupe_documents, dedupe_labs
from ehr_mip.ingestion.identity import Cluster, IdentityInput, resolve_identities
from ehr_mip.ingestion.models import (
    Address,
    AdministrativeGender,
    AuditEntry,
    CleanDocument,
    CleanEncounter,
    CleanLabResult,
    CleanPatient,
    EncounterClass,
    IngestionResult,
    IngestionStats,
    QuarantinedRecord,
    RawRecord,
    Stage,
)
from ehr_mip.ingestion.readers import read_all

log = structlog.get_logger(__name__)

_ENCOUNTER_CLASSES = {c.value: c for c in EncounterClass if c is not EncounterClass.UNKNOWN}
# (mrn, name, dob) payload keys per record shape.
_IDENTITY_KEYS = {
    "patient": ("mrn", "name", "dob"),
    "lab_result": ("patient_mrn", "patient_name", "dob"),
    "default": ("patient_mrn", "patient_name", "patient_dob"),
}


def _text(value: Any) -> str | None:
    """Strip a raw value; blank becomes None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass
class _Prepared:
    record: RawRecord
    order: int
    mrn: str | None
    name: PersonName | None
    dob: date | None
    values: dict[str, Any]
    notes: list[Note] = field(default_factory=list)

    @property
    def record_id(self) -> str:
        return self.record.source_locator


def _missing(field_name: str, label: str) -> Note:
    return Note("field.missing", "info", f"{label} is missing.", None, None, field_name)


# ---------------------------------------------------------------- cleaning per record


def _prepare(record: RawRecord, order: int, today: date) -> _Prepared:
    payload = record.payload
    mrn_key, name_key, dob_key = _IDENTITY_KEYS.get(record.kind, _IDENTITY_KEYS["default"])
    # JSON child records copy the patient's identity; it is audited once, on the patient.
    audit_identity = record.kind == "patient" or record.source_format != "json"
    mrn = normalize_mrn(payload.get(mrn_key))
    name = normalize_name(payload.get(name_key))
    dob = parse_date(payload.get(dob_key), kind="dob", today=today)
    prepared = _Prepared(record, order, mrn.value, name.value, dob.value, {})
    if audit_identity:
        for cleaned, field_name in ((mrn, "mrn"), (name, "name"), (dob, "dob")):
            prepared.notes.extend(with_field(cleaned.notes, field_name))

    builders = {
        "patient": _prepare_patient,
        "encounter": _prepare_encounter,
        "document": _prepare_document,
        "lab_result": _prepare_lab,
    }
    builders[record.kind](prepared, payload, today)
    return prepared


def _prepare_patient(p: _Prepared, payload: dict[str, Any], _today: date) -> None:
    gender = normalize_gender(payload.get("sex"))
    p.notes.extend(with_field(gender.notes, "gender"))
    address = payload.get("address")
    p.values = {
        "gender": gender.value,
        "phone": _text(payload.get("phone")),
        "address": Address(**{k: _text(address.get(k)) for k in ("line", "city", "state", "zip")})
        if isinstance(address, dict)
        else None,
    }


def _prepare_encounter(p: _Prepared, payload: dict[str, Any], today: date) -> None:
    encounter_id = _text(payload.get("encounter_id"))
    if encounter_id is None:
        p.notes.append(_missing("encounter_id", "Encounter id"))
    raw_class = _text(payload.get("type"))
    encounter_class = _ENCOUNTER_CLASSES.get((raw_class or "").lower(), EncounterClass.UNKNOWN)
    if encounter_class is EncounterClass.UNKNOWN:
        p.notes.append(
            Note(
                "encounter.class_unmapped",
                "warning",
                "Unrecognized encounter type; set to unknown.",
                raw_class,
                "unknown",
                "encounter_class",
            )
        )
    elif raw_class != encounter_class.value:
        p.notes.append(
            Note(
                "encounter.class_map",
                "info",
                "Mapped encounter type.",
                raw_class,
                encounter_class.value,
                "encounter_class",
            )
        )
    start = parse_datetime(payload.get("start"), dob=p.dob, today=today)
    end = parse_datetime(payload.get("end"), dob=p.dob, today=today)
    p.notes.extend(with_field(start.notes, "start"))
    p.notes.extend(with_field(end.notes, "end"))
    p.values = {
        "encounter_id": encounter_id,
        "encounter_class": encounter_class,
        "start": start.value,
        "end": end.value,
    }


def _prepare_document(p: _Prepared, payload: dict[str, Any], today: date) -> None:
    when = parse_datetime(payload.get("date"), dob=p.dob, today=today)
    p.notes.extend(with_field(when.notes, "date"))
    raw_type, raw_title = _text(payload.get("doc_type")), _text(payload.get("title"))
    doc_type = classify_doc_type(raw_type, raw_title)
    p.notes.extend(with_field(doc_type.notes, "doc_type"))
    text = normalize_text(str(payload.get("text") or ""))
    p.notes.extend(with_field(text.notes, "text"))
    encounter_id = _text(payload.get("encounter_id"))
    if encounter_id is None:
        p.notes.append(_missing("encounter_id", "Encounter id"))
    p.values = {
        "date": when.value,
        "doc_type": doc_type.value,
        "title": raw_title or raw_type or "Untitled document",
        "author": _text(payload.get("author")),
        "text": text.value,
        "encounter_id": encounter_id,
    }


def _prepare_lab(p: _Prepared, payload: dict[str, Any], today: date) -> None:
    collected = parse_datetime(payload.get("collected_at"), dob=p.dob, today=today)
    p.notes.extend(with_field(collected.notes, "collected_at"))
    raw_value = payload.get("value")
    value = parse_lab_value(raw_value)
    p.notes.extend(with_field(value.notes, "value"))
    low, high = parse_number(payload.get("ref_low")), parse_number(payload.get("ref_high"))
    loinc = _text(payload.get("loinc"))
    flag = recompute_flag(value.value, low, high, loinc, payload.get("flag"))
    p.notes.extend(with_field(flag.notes, "flag"))
    raw_unit = payload.get("unit")
    unit = _text(raw_unit)
    if raw_unit is not None and unit is not None and raw_unit != unit:
        p.notes.append(
            Note(
                "text.normalize", "info", "Removed surrounding whitespace.", raw_unit, unit, "unit"
            )
        )
    encounter_id = _text(payload.get("encounter_id"))
    if encounter_id is None:
        p.notes.append(_missing("encounter_id", "Encounter id"))
    p.values = {
        "collected_at": collected.value,
        "value": value.value,
        "value_raw": str(raw_value or "").strip(),
        "unit": unit,
        "ref_low": low,
        "ref_high": high,
        "flag": flag.value,
        "test_name": _text(payload.get("test_name")) or "Unnamed test",
        "loinc": loinc,
        "report_id": _text(payload.get("report_id")),
        "encounter_id": encounter_id,
    }


# ---------------------------------------------------------------- assembly


def _identity_input(p: _Prepared) -> IdentityInput:
    return IdentityInput(
        record_id=p.record_id,
        order=p.order,
        mrn=p.mrn,
        family=p.name.family if p.name else None,
        first_given=p.name.first_given if p.name else None,
        dob=p.dob,
    )


def _build_patient(cluster: Cluster, members: list[_Prepared]) -> CleanPatient:
    order_of = {m.record_id: m.order for m in members}
    patient_records = [m for m in members if m.record.kind == "patient"]
    named = [m for m in (patient_records or members) if m.name is not None] or [
        m for m in members if m.name is not None
    ]
    counts = Counter((m.name.family, m.name.given) for m in named if m.name is not None)
    # Prefer the most complete form (with middle names), then the most common, then the earliest.
    first_seen: dict[tuple[str, tuple[str, ...]], int] = {}
    for m in named:
        if m.name is not None:
            first_seen.setdefault((m.name.family, m.name.given), m.order)
    family: str | None = None
    given: tuple[str, ...] = ()
    if counts:
        family, given = sorted(counts, key=lambda k: (-len(k[1]), -counts[k], first_seen[k]))[0]
    suffixes = Counter(
        m.name.suffix
        for m in named
        if m.name is not None and m.name.suffix and (m.name.family, m.name.given[:1]) ==
        (family, given[:1])
    )  # fmt: skip
    dobs = Counter(m.dob for m in members if m.dob is not None)
    genders = Counter(
        m.values["gender"]
        for m in patient_records
        if m.values.get("gender") not in (None, AdministrativeGender.UNKNOWN)
    )
    contact = patient_records[0].values if patient_records else {}
    return CleanPatient(
        patient_key=cluster.patient_key,
        mrn=cluster.mrn,
        secondary_mrns=cluster.secondary_mrns,
        family_name=family,
        given_names=list(given),
        name_suffix=suffixes.most_common(1)[0][0] if suffixes else None,
        birth_date=dobs.most_common(1)[0][0] if dobs else None,
        gender=genders.most_common(1)[0][0] if genders else AdministrativeGender.UNKNOWN,
        phone=contact.get("phone"),
        address=contact.get("address"),
        source_record_ids=sorted(cluster.record_ids, key=order_of.__getitem__),
        identity_conflict=cluster.identity_conflict,
    )


@dataclass
class _Collector:
    entries: list[AuditEntry] = field(default_factory=list)

    def add(self, record_id: str, patient_key: str | None, stage: Stage, note: Note) -> None:
        self.entries.append(to_entry(note, record_id, patient_key, stage))


@dataclass
class _EncounterLinker:
    """Resolves a record's source encounter id to an encounter key of the same patient."""

    index: dict[tuple[str, str], str]

    def link(self, p: _Prepared, patient: str) -> str | None:
        source_id = p.values.get("encounter_id")
        if source_id is None:
            return None
        key = self.index.get((patient, source_id))
        if key is None:
            p.notes.append(
                Note(
                    "ref.encounter_unknown",
                    "warning",
                    "Encounter id not found for this patient; record kept without encounter.",
                    source_id,
                    None,
                    "encounter_id",
                )
            )
        return key


def _build_encounters(
    resolved: list[_Prepared], key_of: dict[str, str]
) -> tuple[dict[str, CleanEncounter], _EncounterLinker]:
    encounters: dict[str, CleanEncounter] = {}
    index: dict[tuple[str, str], str] = {}
    for p in resolved:
        source_id = p.values.get("encounter_id")
        if p.record.kind != "encounter" or source_id is None:
            continue
        patient = key_of[p.record_id]
        key = ids.encounter_key(patient, source_id)
        index.setdefault((patient, source_id), key)
        encounters.setdefault(
            key,
            CleanEncounter(
                encounter_key=key,
                patient_key=patient,
                source_encounter_id=source_id,
                encounter_class=p.values["encounter_class"],
                period_start=p.values["start"],
                period_end=p.values["end"],
            ),
        )
    return encounters, _EncounterLinker(index)


def _build_document(
    p: _Prepared, patient: str, linker: _EncounterLinker
) -> tuple[CleanDocument, Ordered]:
    digest = content_hash(p.values["text"])
    document = CleanDocument(
        document_key=ids.document_key(patient, digest),
        patient_key=patient,
        encounter_key=linker.link(p, patient),
        doc_type=p.values["doc_type"],
        title=p.values["title"],
        author=p.values["author"],
        document_date=p.values["date"],
        text=p.values["text"],
        content_hash=digest,
        source_record_id=p.record_id,
    )
    return document, Ordered(p.order, p.record_id)


def _build_lab(
    p: _Prepared, patient: str, linker: _EncounterLinker
) -> tuple[CleanLabResult, Ordered]:
    collected = p.values["collected_at"]
    # Report identity: source report id, else the collection time, else this row alone
    # (so rows with neither never collapse into one shared "unknown" report).
    report_source = p.values["report_id"] or (
        collected.isoformat() if isinstance(collected, date | datetime) else f"row:{p.record_id}"
    )
    report = ids.report_key(patient, report_source)
    lab = CleanLabResult(
        result_key=ids.result_key(report, p.values["loinc"] or p.values["test_name"]),
        patient_key=patient,
        encounter_key=linker.link(p, patient),
        report_key=report,
        test_name=p.values["test_name"],
        loinc=p.values["loinc"],
        value=p.values["value"],
        value_raw=p.values["value_raw"],
        unit=p.values["unit"],
        ref_low=p.values["ref_low"],
        ref_high=p.values["ref_high"],
        flag=p.values["flag"],
        collected_at=collected,
        source_record_id=p.record_id,
    )
    return lab, Ordered(p.order, p.record_id)


def run_ingestion(raw_dir: Path, *, today: date | None = None) -> IngestionResult:
    """Run Task 1 end to end over ``raw_dir`` and return the clean IR, audit and stats."""
    today = today or today_local()
    read = read_all(raw_dir)
    audit = _Collector()
    for record_id, note in read.notes:
        audit.add(record_id, None, "read", note)
    quarantine = list(read.quarantine)

    prepared = [_prepare(record, order, today) for order, record in enumerate(read.records)]
    identity = resolve_identities([_identity_input(p) for p in prepared])
    unresolved = set(identity.unresolved)
    for p in prepared:
        if p.record_id in unresolved:
            quarantine.append(
                QuarantinedRecord(
                    source_locator=p.record_id,
                    reason="identity_unresolvable",
                    payload={k: v for k, v in p.record.payload.items() if k != "text"},
                )
            )
    resolved = [p for p in prepared if p.record_id not in unresolved]
    key_of = identity.assignment

    by_cluster: dict[str, list[_Prepared]] = {}
    for p in resolved:
        by_cluster.setdefault(key_of[p.record_id], []).append(p)
    patients = [_build_patient(c, by_cluster[c.patient_key]) for c in identity.clusters]

    encounters, linker = _build_encounters(resolved, key_of)
    documents = [
        _build_document(p, key_of[p.record_id], linker)
        for p in resolved
        if p.record.kind == "document"
    ]
    labs = [
        _build_lab(p, key_of[p.record_id], linker)
        for p in resolved
        if p.record.kind == "lab_result"
    ]

    kept_docs, doc_notes, exact, near = dedupe_documents(documents)
    kept_labs, lab_notes, lab_dupes = dedupe_labs(labs)

    # Audit: cleaning notes with the resolved patient, then identity and dedupe decisions.
    for p in prepared:
        patient = key_of.get(p.record_id)
        for note in p.notes:
            audit.add(p.record_id, patient, "clean", note)
    for record_id, note in identity.notes:
        audit.add(record_id, key_of.get(record_id), "identity", note)
    for record_id, patient, note in [*doc_notes, *lab_notes]:
        audit.add(record_id, patient, "dedupe", note)

    entries = audit.entries
    stats = IngestionStats(
        records_read=dict(sorted(Counter(r.source_format for r in read.records).items())),
        patients=len(patients),
        encounters=len(encounters),
        documents=len(kept_docs),
        lab_results=len(kept_labs),
        lab_reports=len({lab.report_key for lab, _ in kept_labs}),
        duplicates_exact=exact,
        duplicates_near=near,
        duplicates_lab=lab_dupes,
        identities_merged=identity.merged,
        identity_conflicts=identity.conflicts,
        quarantined=len(quarantine),
        audit_by_rule=dict(sorted(Counter(e.rule for e in entries).items())),
        audit_by_severity=dict(sorted(Counter(e.severity for e in entries).items())),
    )
    log.info(
        "ingest_completed",
        patients=stats.patients,
        documents=stats.documents,
        lab_results=stats.lab_results,
        quarantined=stats.quarantined,
        audit_entries=len(entries),
    )
    return IngestionResult(
        patients=patients,
        encounters=list(encounters.values()),
        documents=[d for d, _ in kept_docs],
        lab_results=[lab for lab, _ in kept_labs],
        audit=entries,
        quarantine=quarantine,
        stats=stats,
    )
