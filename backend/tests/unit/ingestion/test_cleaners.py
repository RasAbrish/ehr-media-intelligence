"""Cleaner rules (docs/05-ALGORITHMS.md sections 1.2 and 1.3). Written before the cleaners."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ehr_mip.ingestion.cleaners.dates import parse_date, parse_datetime
from ehr_mip.ingestion.cleaners.doctype import classify_doc_type
from ehr_mip.ingestion.cleaners.gender import normalize_gender
from ehr_mip.ingestion.cleaners.labs import parse_lab_value, parse_number, recompute_flag
from ehr_mip.ingestion.cleaners.mrn import normalize_mrn
from ehr_mip.ingestion.cleaners.names import normalize_name
from ehr_mip.ingestion.cleaners.text import comparison_text, content_hash, normalize_text
from ehr_mip.ingestion.models import AdministrativeGender, DocType

TODAY = date(2026, 11, 20)
NY = ZoneInfo("America/New_York")


def rules(result: object) -> list[str]:
    return [n.rule for n in result.notes]  # type: ignore[attr-defined]


# ---------------------------------------------------------------- dates


def test_parse_date_iso() -> None:
    result = parse_date("2025-02-02", today=TODAY)
    assert result.value == date(2025, 2, 2)
    assert result.notes == ()  # already canonical: no audit


def test_parse_date_us_slash() -> None:
    result = parse_date("03/14/1968", kind="dob", today=TODAY)
    assert result.value == date(1968, 3, 14)
    assert rules(result) == ["date.parse.format"]
    assert result.notes[0].before == "03/14/1968"
    assert result.notes[0].after == "1968-03-14"


def test_parse_date_ambiguous_defaults_us_and_warns() -> None:
    result = parse_date("04/05/2024", today=TODAY)
    assert result.value == date(2024, 4, 5)
    assert rules(result) == ["date.parse.us_ambiguous"]
    assert result.notes[0].severity == "warning"


def test_parse_date_ddmm_when_day_gt_12() -> None:
    result = parse_date("14/03/1968", kind="dob", today=TODAY)
    assert result.value == date(1968, 3, 14)
    assert rules(result) == ["date.parse.ddmm"]


@pytest.mark.parametrize(
    "raw",
    ["14-Mar-1968", "March 14, 1968", "Mar 14 1968", "19680314", "1968/03/14", "1968-03-14"],
)
def test_parse_date_textual_month_formats(raw: str) -> None:
    assert parse_date(raw, kind="dob", today=TODAY).value == date(1968, 3, 14)


@pytest.mark.parametrize(
    "raw", ["02/30/2024", "13/13/2020", "2025-02-31", "00/12/2024", "31/31/2023"]
)
def test_parse_date_invalid_returns_none_with_error_audit(raw: str) -> None:
    result = parse_date(raw, today=TODAY)
    assert result.value is None
    # Exactly one error, never an extra ambiguity warning for an impossible date.
    assert rules(result) == ["date.parse.invalid"]
    assert result.notes[0].severity == "error"
    assert result.notes[0].before == raw


def test_parse_date_missing_is_info() -> None:
    for raw in (None, "", "   "):
        result = parse_date(raw, today=TODAY)
        assert result.value is None
        assert rules(result) == ["date.missing"]
        assert result.notes[0].severity == "info"


def test_parse_date_fixes_ocr_letter_o_in_digits() -> None:
    result = parse_date("2O25-02-O2", today=TODAY)
    assert result.value == date(2025, 2, 2)
    assert "date.parse.format" in rules(result)


def test_parse_date_keeps_month_names_containing_o() -> None:
    assert parse_date("14-Oct-1968", kind="dob", today=TODAY).value == date(1968, 10, 14)
    assert parse_date("Nov 3 2024", today=TODAY).value == date(2024, 11, 3)


def test_parse_date_dateutil_fallback_is_audited() -> None:
    result = parse_date("3rd of March 2024", today=TODAY)
    assert result.value == date(2024, 3, 3)
    assert rules(result) == ["date.parse.fallback"]


def test_two_digit_year_dob_never_future() -> None:
    result = parse_date("03/14/68", kind="dob", today=TODAY)
    assert result.value == date(1968, 3, 14)
    assert parse_date("05/20/02", kind="dob", today=TODAY).value == date(2002, 5, 20)
    # 2030 would be in the future for a DOB, so it pivots back a century.
    assert parse_date("01/15/30", kind="dob", today=TODAY).value == date(1930, 1, 15)


def test_dob_older_than_120_rejected() -> None:
    result = parse_date("1890-01-01", kind="dob", today=TODAY)
    assert result.value is None
    assert rules(result) == ["date.dob_implausible"]


def test_dob_in_future_rejected() -> None:
    assert rules(parse_date("2027-01-01", kind="dob", today=TODAY)) == ["date.dob_implausible"]


def test_clinical_date_before_dob_rejected() -> None:
    result = parse_date("1950-01-01", dob=date(1968, 3, 14), today=TODAY)
    assert result.value is None
    assert rules(result) == ["date.clinical_implausible"]


def test_clinical_date_more_than_a_day_ahead_rejected() -> None:
    assert rules(parse_date("2026-11-22", today=TODAY)) == ["date.clinical_implausible"]
    assert parse_date("2026-11-21", today=TODAY).value == date(2026, 11, 21)


def test_parse_datetime_keeps_time_and_zone() -> None:
    result = parse_datetime("2025-02-02T06:10", today=TODAY)
    assert result.value == datetime(2025, 2, 2, 6, 10, tzinfo=NY)
    assert result.notes == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025-02-02 06:10", datetime(2025, 2, 2, 6, 10, tzinfo=NY)),
        ("2025-02-02T06:10:00", datetime(2025, 2, 2, 6, 10, tzinfo=NY)),
        ("02/15/2025 13:02", datetime(2025, 2, 15, 13, 2, tzinfo=NY)),
    ],
)
def test_parse_datetime_variants_are_audited(raw: str, expected: datetime) -> None:
    result = parse_datetime(raw, today=TODAY)
    assert result.value == expected
    assert rules(result) == ["date.parse.format"]


def test_parse_datetime_date_only_keeps_date_precision() -> None:
    result = parse_datetime("Feb 4 2025", today=TODAY)
    assert result.value == date(2025, 2, 4)
    assert rules(result) == ["date.parse.format"]


def test_parse_datetime_invalid_date_part() -> None:
    result = parse_datetime("02/30/2024 08:00", today=TODAY)
    assert result.value is None
    assert rules(result) == ["date.parse.invalid"]


_FORMATS = [
    lambda d: d.isoformat(),
    lambda d: f"{d.day:02d}-{d:%b}-{d.year}",
    lambda d: f"{d:%B} {d.day}, {d.year}",
    lambda d: f"{d:%b} {d.day} {d.year}",
    lambda d: f"{d:%Y%m%d}",
    lambda d: f"{d:%Y/%m/%d}",
    lambda d: f"{d:%m/%d/%Y}",
]


@given(
    st.dates(min_value=date(1907, 1, 1), max_value=date(2026, 11, 20)),
    st.sampled_from(_FORMATS),
)
def test_date_normalizer_idempotent(value: date, fmt: object) -> None:
    raw = fmt(value)  # type: ignore[operator]
    first = parse_date(raw, kind="dob", today=TODAY)
    assert first.value is not None
    second = parse_date(first.value.isoformat(), kind="dob", today=TODAY)
    assert second.value == first.value
    assert second.notes == ()  # a normalized value never changes again


# ---------------------------------------------------------------- gender


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("M", AdministrativeGender.MALE),
        ("male", AdministrativeGender.MALE),
        ("1", AdministrativeGender.MALE),
        ("F", AdministrativeGender.FEMALE),
        ("Female", AdministrativeGender.FEMALE),
        ("f", AdministrativeGender.FEMALE),
        ("2", AdministrativeGender.FEMALE),
        ("x", AdministrativeGender.OTHER),
        ("nonbinary", AdministrativeGender.OTHER),
        ("U", AdministrativeGender.UNKNOWN),
        ("unknown", AdministrativeGender.UNKNOWN),
        ("", AdministrativeGender.UNKNOWN),
    ],
)
def test_gender_mapping_variants(raw: str, expected: AdministrativeGender) -> None:
    result = normalize_gender(raw)
    assert result.value == expected
    if raw == expected.value:
        assert result.notes == ()
    else:
        assert rules(result) == ["gender.map"]


def test_gender_unmapped_becomes_unknown_with_warning() -> None:
    result = normalize_gender("Q")
    assert result.value == AdministrativeGender.UNKNOWN
    assert rules(result) == ["gender.unmapped"]
    assert result.notes[0].severity == "warning"


def test_gender_absent_is_missing_field() -> None:
    result = normalize_gender(None)
    assert result.value == AdministrativeGender.UNKNOWN
    assert rules(result) == ["field.missing"]


# ---------------------------------------------------------------- mrn


@pytest.mark.parametrize(
    "raw", ["MRN-00012345", "12345", "0012345", " mrn 12345 ", "MRN12345", "mrn: 12-345"]
)
def test_mrn_normalization_variants(raw: str) -> None:
    result = normalize_mrn(raw)
    assert result.value == "00012345"
    assert rules(result) == ["mrn.normalize"]


def test_canonical_mrn_has_no_audit() -> None:
    assert normalize_mrn("00012345").notes == ()


@pytest.mark.parametrize("raw", ["MRN-", "unknown", "123456789"])
def test_mrn_without_digits_rejected(raw: str) -> None:
    result = normalize_mrn(raw)
    assert result.value is None
    assert rules(result) == ["mrn.invalid"]
    assert result.notes[0].severity == "error"


def test_mrn_missing_has_no_error() -> None:
    result = normalize_mrn("")
    assert result.value is None
    assert rules(result) == ["field.missing"]


# ---------------------------------------------------------------- names


def test_name_family_comma_given() -> None:
    result = normalize_name("DOE, JANE A")
    assert result.value is not None
    assert result.value.family == "Doe"
    assert result.value.given == ("Jane", "A")
    assert rules(result) == ["name.normalize"]


@pytest.mark.parametrize("raw", ["Dr. Jane Doe", "jane  doe", "  Jane Doe ", "Ms. JANE DOE"])
def test_name_strips_titles_and_whitespace(raw: str) -> None:
    result = normalize_name(raw)
    assert result.value is not None
    assert result.value.family == "Doe"
    assert result.value.given == ("Jane",)


def test_name_middle_initial_with_period() -> None:
    result = normalize_name("Jane A. Doe")
    assert result.value is not None
    assert result.value.given == ("Jane", "A")


@pytest.mark.parametrize(
    ("raw", "family"),
    [
        ("o'brien, sean", "O'Brien"),
        ("MCDONALD, ANNE", "McDonald"),
        ("smith-jones, ann", "Smith-Jones"),
    ],
)
def test_name_smart_title_case(raw: str, family: str) -> None:
    result = normalize_name(raw)
    assert result.value is not None
    assert result.value.family == family


def test_name_already_display_form_has_no_audit() -> None:
    assert normalize_name("Jane Doe").notes == ()


def test_name_missing() -> None:
    result = normalize_name("   ")
    assert result.value is None
    assert rules(result) == ["field.missing"]


# ---------------------------------------------------------------- text


def test_text_normalize_quotes_line_endings_and_spaces() -> None:
    raw = "IMPRESSION: \u201cstable\u201d   \r\nPLAN: none\u2019s\r\n\n\n\n\nEnd  "
    result = normalize_text(raw)
    assert result.value == 'IMPRESSION: "stable"\nPLAN: none\'s\n\nEnd'
    assert rules(result) == ["text.normalize"]
    # Notes never copy clinical text into the audit log.
    assert result.notes[0].before is None
    assert result.notes[0].after is None


def test_text_normalize_clean_text_unchanged() -> None:
    assert normalize_text("FINDINGS: normal.\nIMPRESSION: none.").notes == ()


def test_content_hash_ignores_normalized_noise() -> None:
    a = normalize_text("Line one  \r\nLine two").value
    b = normalize_text("Line one\nLine two").value
    assert content_hash(a) == content_hash(b)


def test_comparison_text_ignores_case_and_spacing() -> None:
    assert comparison_text("A  B.\n\nC") == comparison_text("a b. c")


# ---------------------------------------------------------------- doc type


@pytest.mark.parametrize(
    ("doc_type", "title", "expected"),
    [
        ("Discharge Summary", "Discharge Summary", DocType.DISCHARGE_SUMMARY),
        ("Progress Note", "Primary Care Visit", DocType.PROGRESS_NOTE),
        ("History and Physical", "Admission History and Physical", DocType.PROGRESS_NOTE),
        ("Emergency Department Note", "ED Provider Note", DocType.PROGRESS_NOTE),
        ("Consultation Note", "Nephrology Consult", DocType.CONSULT_NOTE),
        (None, "CT ANGIOGRAPHY CHEST", DocType.IMAGING_REPORT),
        (None, "TRANSTHORACIC ECHOCARDIOGRAM", DocType.IMAGING_REPORT),
        (None, "CHEST X-RAY PA AND LATERAL", DocType.IMAGING_REPORT),
        (None, "DIAGNOSTIC MAMMOGRAM AND BREAST ULTRASOUND", DocType.IMAGING_REPORT),
        (None, "SURGICAL PATHOLOGY REPORT", DocType.PATHOLOGY_REPORT),
        (None, "ED PROVIDER NOTE", DocType.PROGRESS_NOTE),
        (None, "ENDOCRINOLOGY FOLLOW-UP", DocType.PROGRESS_NOTE),
    ],
)
def test_doctype_keyword_map(doc_type: str | None, title: str, expected: DocType) -> None:
    result = classify_doc_type(doc_type, title)
    assert result.value == expected
    assert result.notes == ()


def test_doctype_default_is_scanned_with_info() -> None:
    result = classify_doc_type(None, "MISC SCAN 4")
    assert result.value == DocType.SCANNED_DOCUMENT
    assert rules(result) == ["doctype.map"]


def test_doctype_does_not_match_ct_inside_words() -> None:
    # "CT" must be a word: "PRACTICE" or "DOCTOR" are not CT scans.
    assert classify_doc_type(None, "PRACTICE LETTER").value == DocType.SCANNED_DOCUMENT


# ---------------------------------------------------------------- labs


@pytest.mark.parametrize(
    ("raw", "value", "audited"),
    [
        ("5.9", 5.9, False),
        ("<0.01", 0.01, True),
        (">5000", 5000.0, True),
        ("5.9 H", 5.9, True),
        ("5.l", 5.1, True),
        ("100 ", 100.0, True),
    ],
)
def test_lab_value_with_operator_parsed(raw: str, value: float, audited: bool) -> None:
    result = parse_lab_value(raw)
    assert result.value == value
    assert (rules(result) == ["lab.value_parse"]) is audited


def test_lab_value_unparseable() -> None:
    result = parse_lab_value("see note")
    assert result.value is None
    assert rules(result) == ["lab.value_parse"]
    assert result.notes[0].severity == "warning"


def test_parse_number_for_ranges() -> None:
    assert parse_number("3.5") == 3.5
    assert parse_number("") is None
    assert parse_number(None) is None


@pytest.mark.parametrize(
    ("value", "source", "expected", "rule"),
    [
        (4.2, "", "N", None),  # blank flag on a normal value: N without audit
        (4.2, "N", "N", None),
        (5.9, "H", "H", None),
        (5.9, "", "H", "lab.flag_recomputed"),  # abnormal value with no flag
        (5.9, "N", "H", "lab.flag_recomputed"),  # wrong direction
        (4.2, "H", "N", "lab.flag_recomputed"),
        (3.1, "L", "L", None),
        (6.1, "H", "HH", "lab.flag_critical"),  # critical upgrade, direction agrees
        (6.1, "", "HH", "lab.flag_recomputed"),
        (2.4, "L", "LL", "lab.flag_critical"),
    ],
)
def test_lab_flag_recomputed_from_range(
    value: float, source: str, expected: str, rule: str | None
) -> None:
    result = recompute_flag(value, 3.5, 5.1, "2823-3", source)  # potassium
    assert result.value == expected
    assert rules(result) == ([rule] if rule else [])


def test_lab_flag_recomputed_is_warning_and_critical_is_info() -> None:
    assert recompute_flag(5.9, 3.5, 5.1, "2823-3", "N").notes[0].severity == "warning"
    assert recompute_flag(6.1, 3.5, 5.1, "2823-3", "H").notes[0].severity == "info"


def test_lab_flag_without_value_or_range_keeps_source() -> None:
    assert recompute_flag(None, 3.5, 5.1, "2823-3", "H").value == "H"
    assert recompute_flag(4.0, None, None, None, "").value is None


def test_lab_flag_one_sided_range() -> None:
    assert recompute_flag(850, None, 100, "30934-4", "").value == "H"  # BNP
    assert recompute_flag(35, 40, None, "2085-9", "").value == "L"  # HDL


# ---------------------------------------------------------------- review regressions


@pytest.mark.parametrize("raw", ["March 2024", "2024", "14 March"])
def test_partial_dates_are_rejected_not_invented(raw: str) -> None:
    result = parse_date(raw, today=TODAY)
    assert result.value is None
    assert rules(result) == ["date.parse.invalid"]


def test_datetime_single_digit_hour_with_seconds() -> None:
    result = parse_datetime("2025-02-02 6:10:05", today=TODAY)
    assert result.value == datetime(2025, 2, 2, 6, 10, 5, tzinfo=NY)


@pytest.mark.parametrize(
    "raw", ["John Smith Jr.", "SMITH JR, JOHN", "SMITH, JOHN JR", "Dr. John Smith Jr"]
)
def test_name_suffix_is_not_the_family_name(raw: str) -> None:
    result = normalize_name(raw)
    assert result.value is not None
    assert (result.value.family, result.value.given, result.value.suffix) == (
        "Smith",
        ("John",),
        "Jr.",
    )


def test_negative_lab_value() -> None:
    assert parse_lab_value("-3.2").value == -3.2
    assert parse_lab_value("-3.2").notes == ()
