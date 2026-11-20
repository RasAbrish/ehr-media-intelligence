"""Identity, dedupe, quarantine and audit behavior (docs/05 sections 1.4 and 1.5)."""

from __future__ import annotations

from tests.support.raw_folder import (
    RawFolder,
    document,
    encounter,
    lab_row,
    note_text,
    patient,
)

from ehr_mip.ids import patient_key
from ehr_mip.ingestion.models import AuditEntry, IngestionResult


def entries(result: IngestionResult, rule: str) -> list[AuditEntry]:
    return [a for a in result.audit if a.rule == rule]


# ---------------------------------------------------------------- dedupe


def test_exact_duplicate_removed_keeps_richest(raw: RawFolder) -> None:
    body = "FINDINGS: Clear lungs.\nIMPRESSION: Normal chest."
    raw.patients = [patient(encounters=[encounter(documents=[document(text=body)])])]
    # The scanned copy has the same text but no author: the JSON document must win.
    raw.notes = {"copy.txt": note_text(body)}
    result = raw.run()
    assert len(result.documents) == 1
    kept = result.documents[0]
    assert kept.author == "Dr. A. Rivera"
    assert kept.source_record_id.startswith("ehr_export.json")
    dropped = entries(result, "dedupe.exact")
    assert [d.record_id for d in dropped] == ["notes/copy.txt"]
    assert result.stats.duplicates_exact == 1


def test_near_duplicate_whitespace_case_removed(raw: RawFolder) -> None:
    body = "FINDINGS: Clear lungs. No effusion.\nIMPRESSION: Normal chest."
    raw.patients = [patient(encounters=[encounter(documents=[document(text=body)])])]
    # Upper-cased scan with doubled spacing and a different (title-only) document type.
    raw.notes = {"near.txt": note_text(body.upper().replace(". ", ".  "), title="SCANNED PAGE 7")}
    result = raw.run()
    assert len(result.documents) == 1
    assert [d.record_id for d in entries(result, "dedupe.near")] == ["notes/near.txt"]
    assert result.stats.duplicates_near == 1


def test_distinct_documents_same_day_kept(raw: RawFolder) -> None:
    docs = [
        document("DOC-1", "FINDINGS: Clear lungs.\nIMPRESSION: Normal chest."),
        document(
            "DOC-2",
            "HPI: Cough for 4 days.\nPLAN: Start antibiotics.",
            doc_type="Progress Note",
            title="Progress Note",
        ),
    ]
    raw.patients = [patient(encounters=[encounter(documents=docs)])]
    result = raw.run()
    assert len(result.documents) == 2
    assert result.stats.duplicates_exact == result.stats.duplicates_near == 0


def test_near_duplicate_needs_close_dates(raw: RawFolder) -> None:
    body = "FINDINGS: Clear lungs.\nIMPRESSION: Normal chest."
    raw.patients = [patient(encounters=[encounter(documents=[document(text=body)])])]
    raw.notes = {"later.txt": note_text(body.lower(), when="2025-03-20")}
    assert len(raw.run().documents) == 2


def test_duplicates_never_cross_patients(raw: RawFolder) -> None:
    body = "FINDINGS: Clear lungs.\nIMPRESSION: Normal chest."
    raw.patients = [
        patient(encounters=[encounter(documents=[document(text=body)])]),
        patient(
            mrn="00055555",
            name="John Roe",
            dob="1970-01-15",
            sex="male",
            encounters=[encounter("ENC-2", [document("DOC-2", body)])],
        ),
    ]
    assert len(raw.run().documents) == 2


def test_duplicate_lab_row_removed(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter()])]
    raw.lab_rows = [lab_row(), lab_row()]
    result = raw.run()
    assert len(result.lab_results) == 1
    assert result.stats.duplicates_lab == 1
    assert [a.record_id for a in entries(result, "dedupe.lab")] == ["lab_results.csv:row 2"]


# ---------------------------------------------------------------- identity


def test_same_person_two_mrns_merged_with_secondary_identifier(raw: RawFolder) -> None:
    raw.patients = [
        patient(mrn="MRN-00012345", name="DOE, JANE A", encounters=[encounter("ENC-1")]),
        patient(mrn="98765", name="jane  doe", encounters=[encounter("ENC-2")]),
    ]
    raw.lab_rows = [lab_row(patient_mrn="12345"), lab_row(patient_mrn="12345", loinc="2951-2",
                    test_name="Sodium", value="140", ref_low="136", ref_high="145")]  # fmt: skip
    result = raw.run()
    assert len(result.patients) == 1
    merged = result.patients[0]
    assert merged.mrn == "00012345"  # most frequent MRN wins
    assert merged.secondary_mrns == ["00098765"]
    assert merged.patient_key == patient_key("00012345")
    assert merged.identity_conflict is False
    assert {e.patient_key for e in result.encounters} == {merged.patient_key}
    merges = entries(result, "identity.merge_mrn")
    assert len(merges) == 1
    assert merges[0].severity == "warning"
    assert (merges[0].before, merges[0].after) == ("00098765", "00012345")
    assert result.stats.identities_merged == 1


def test_merge_requires_exact_dob(raw: RawFolder) -> None:
    raw.patients = [
        patient(mrn="00012345"),
        patient(mrn="00098765", dob="1968-03-15"),
    ]
    result = raw.run()
    assert len(result.patients) == 2
    assert result.stats.identities_merged == 0


def test_same_mrn_conflicting_dob_not_merged_and_flagged(raw: RawFolder) -> None:
    raw.patients = [
        patient(mrn="00055501", name="Ann Lee", dob="1980-01-02", encounters=[encounter("ENC-1")]),
        patient(mrn="00055501", name="Ann Lee", dob="1980-01-02", encounters=[encounter("ENC-9")]),
        patient(mrn="00055501", name="Omar Haddad", dob="1975-07-19", sex="male"),
    ]
    result = raw.run()
    assert len(result.patients) == 2
    by_name = {p.family_name: p for p in result.patients}
    majority, minority = by_name["Lee"], by_name["Haddad"]
    assert majority.patient_key == patient_key("00055501")
    assert minority.patient_key != majority.patient_key
    assert majority.identity_conflict
    assert minority.identity_conflict
    assert majority.mrn == minority.mrn == "00055501"
    conflict = entries(result, "identity.conflict")
    assert conflict
    assert all(c.severity == "error" for c in conflict)
    assert result.stats.identity_conflicts == 1


def test_same_mrn_name_variants_are_one_person(raw: RawFolder) -> None:
    raw.patients = [
        patient(name="DOE, JANE A"),
        patient(mrn="12345", name="Dr. Jane Doe", dob=None),
        patient(mrn=" mrn 12345 ", name="jane  doe"),
    ]
    result = raw.run()
    assert len(result.patients) == 1
    assert result.patients[0].given_names == ["Jane", "A"]
    assert result.patients[0].birth_date is not None
    assert result.stats.identity_conflicts == 0


def test_missing_mrn_and_name_quarantined(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter()])]
    raw.lab_rows = [lab_row(patient_mrn="", patient_name="")]
    raw.notes = {"anon.txt": note_text("SUBJECTIVE: No complaints.", name="", mrn="", dob="")}
    result = raw.run()
    reasons = sorted((q.source_locator, q.reason) for q in result.quarantine)
    assert reasons == [
        ("lab_results.csv:row 1", "identity_unresolvable"),
        ("notes/anon.txt", "identity_unresolvable"),
    ]
    assert result.lab_results == []
    assert result.stats.quarantined == 2


def test_name_and_dob_without_mrn_attaches_to_patient(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter()])]
    raw.lab_rows = [lab_row(patient_mrn="")]
    result = raw.run()
    assert len(result.lab_results) == 1
    assert result.lab_results[0].patient_key == result.patients[0].patient_key


def test_missing_dob_allowed_with_info_audit(raw: RawFolder) -> None:
    raw.patients = [patient(dob=None, encounters=[encounter()])]
    result = raw.run()
    assert len(result.patients) == 1
    assert result.patients[0].birth_date is None
    missing = [a for a in result.audit if a.field == "dob"]
    assert [(a.rule, a.severity) for a in missing] == [("date.missing", "info")]
    assert missing[0].record_id == "ehr_export.json:patients[0]"
    assert missing[0].patient_key == result.patients[0].patient_key


# ---------------------------------------------------------------- audit


def test_untouched_record_has_no_audit(raw: RawFolder) -> None:
    raw.patients = [
        patient(encounters=[encounter(documents=[document()])]),
        patient(mrn="00055555", name="John Roe", dob="1970-01-15", sex="M"),
    ]
    result = raw.run()
    clean_records = {
        "ehr_export.json:patients[0]",
        "ehr_export.json:patients[0].encounters[0]",
        "ehr_export.json:patients[0].encounters[0].documents[0]",
    }
    assert not [a for a in result.audit if a.record_id in clean_records]
    # The second patient's gender code did change, so it is audited.
    assert [a.rule for a in result.audit if a.record_id == "ehr_export.json:patients[1]"] == [
        "gender.map"
    ]


def test_every_changed_field_is_audited(raw: RawFolder) -> None:
    raw.patients = [
        patient(
            mrn="MRN-12345",
            name="DOE, JANE A",
            dob="03/14/1968",
            sex="F",
            encounters=[encounter(documents=[document(doc_date="Feb 4 2025")])],
        )
    ]
    raw.lab_rows = [lab_row(value="5.9", flag="N", collected_at="02/15/2025 06:10")]
    result = raw.run()
    by_field = {(a.record_id, a.field): a.rule for a in result.audit}
    assert by_field[("ehr_export.json:patients[0]", "mrn")] == "mrn.normalize"
    assert by_field[("ehr_export.json:patients[0]", "name")] == "name.normalize"
    assert by_field[("ehr_export.json:patients[0]", "dob")] == "date.parse.format"
    assert by_field[("ehr_export.json:patients[0]", "gender")] == "gender.map"
    doc_loc = "ehr_export.json:patients[0].encounters[0].documents[0]"
    assert by_field[(doc_loc, "date")] == "date.parse.format"
    assert by_field[("lab_results.csv:row 1", "flag")] == "lab.flag_recomputed"
    assert by_field[("lab_results.csv:row 1", "collected_at")] == "date.parse.format"
    # Identity fields copied into JSON child records are not audited twice.
    assert not [a for a in result.audit if a.record_id == doc_loc and a.field == "mrn"]


def test_audit_entries_carry_resolved_patient_key(raw: RawFolder) -> None:
    raw.patients = [patient(mrn="MRN-00012345", encounters=[encounter()])]
    result = raw.run()
    assert {a.patient_key for a in result.audit} == {result.patients[0].patient_key}


def test_document_links_to_encounter(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter(documents=[document()])])]
    raw.notes = {"scan.txt": note_text("FINDINGS: Normal heart size.", title="CHEST X-RAY")}
    result = raw.run()
    assert {d.encounter_key for d in result.documents} == {result.encounters[0].encounter_key}


def test_unknown_encounter_reference_is_warned(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter()])]
    raw.lab_rows = [lab_row(encounter_id="ENC-404")]
    result = raw.run()
    assert result.lab_results[0].encounter_key is None
    assert [a.rule for a in result.audit if a.field == "encounter_id"] == ["ref.encounter_unknown"]


def test_lab_result_fields(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter()])]
    raw.lab_rows = [lab_row(value="<0.01", test_name="Troponin I", loinc="10839-9",
                            ref_low="", ref_high="0.04", unit=" ng/mL")]  # fmt: skip
    lab = raw.run().lab_results[0]
    assert (lab.value, lab.value_raw, lab.unit, lab.flag) == (0.01, "<0.01", "ng/mL", "N")
    assert lab.ref_low is None
    assert lab.ref_high == 0.04


def test_rerun_is_deterministic(raw: RawFolder) -> None:
    raw.patients = [patient(mrn="MRN-1", encounters=[encounter(documents=[document()])])]
    raw.lab_rows = [lab_row(patient_mrn="1")]
    first, second = raw.run(), raw.run()
    assert first == second


# ---------------------------------------------------------------- review regressions


def test_split_patients_sharing_a_dob_get_distinct_keys(raw: RawFolder) -> None:
    raw.patients = [
        patient(mrn="00055501", name="Ann Lee", dob="1980-01-02"),
        patient(mrn="00055501", name="Ann Lee", dob="1980-01-02"),
        patient(mrn="00055501", name="Omar Haddad", dob="1975-07-19", sex="male"),
        patient(mrn="00055501", name="Yusuf Haddad", dob="1975-07-19", sex="male"),
    ]
    result = raw.run()
    assert len(result.patients) == 3
    assert len({p.patient_key for p in result.patients}) == 3
    assert {p.family_name for p in result.patients} == {"Lee", "Haddad"}


def test_labs_without_time_or_report_are_never_collapsed(raw: RawFolder) -> None:
    raw.patients = [patient(encounters=[encounter()])]
    raw.lab_rows = [
        lab_row(report_id="", collected_at="02/30/2024", value="4.2"),
        lab_row(report_id="", collected_at="02/30/2024", value="4.2"),
        lab_row(report_id="", collected_at="02/30/2024", value="6.4"),
    ]
    result = raw.run()
    assert len(result.lab_results) == 3
    assert len({lab.result_key for lab in result.lab_results}) == 3
    assert result.stats.duplicates_lab == 0
