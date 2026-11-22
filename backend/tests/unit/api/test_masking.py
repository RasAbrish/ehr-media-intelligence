"""Audit and quarantine masking (FR-6.4): unknown fields fail closed."""

from __future__ import annotations

import json

import pytest

from ehr_mip.api.masking import mask_value, quarantine_preview


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("name", "Jane Doe", "J*** D**"),
        ("dob", "1968-03-14", "19**-**-14"),
        ("phone", "(212) 555-0142", "(***) ***-**42"),
        ("text", "Ms. Doe seen", "[text withheld, 12 characters]"),
        ("gender", "F", "F"),
        (None, "notes/note_028.txt", "notes/note_028.txt"),
        ("name", None, None),
    ],
)
def test_known_fields(field: str | None, value: str | None, expected: str | None) -> None:
    assert mask_value(field, value) == expected


@pytest.mark.parametrize("field", ["guardian_name", "first_name", "ssn", "anything_new"])
def test_unknown_fields_fail_closed(field: str) -> None:
    assert mask_value(field, "Jane Doe 123-45-6789") == "[value withheld]"


def test_quarantine_masks_non_string_and_nested_values() -> None:
    payload = {"dob": 19680314, "patient": {"first_name": "Jane", "phone": 2125550142}}
    preview = quarantine_preview(json.dumps(payload))
    for identifier in ("19680314", "Jane", "2125550142"):
        assert identifier not in preview


# Every raw shape the sources use for a birth date (1962-09-04, 1987-07-12).
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sep 4 1962", "*** * ****"),
        ("September 4, 1962", "*** *, ****"),
        ("May 21, 1991", "*** **, ****"),
        ("04-Sep-1962", "**-***-****"),
        ("09/04/1962", "**/**/****"),
        ("12/07/1987", "**/**/****"),
        ("07/12/87", "**/**/**"),
        ("1962/09/04", "****/**/**"),
        ("19620904", "********"),
        ("1962-O9-04", "****-****-**"),
        ("1962-14-09", "****-**-**"),
        ("1962-09-04T00:00:00", "****-**-*******:**:**"),
        ("1962-09-04, 1962-09-14", "****-**-**, ****-**-**"),
    ],
)
@pytest.mark.parametrize("field", ["dob", "birth_date", "patient_dob"])
def test_only_iso_dates_keep_century_and_day(field: str, raw: str, expected: str) -> None:
    assert mask_value(field, raw) == expected


def test_short_house_number_is_masked() -> None:
    assert mask_value("address", "5 Main St") == "* M*** S*"


@pytest.mark.parametrize("value", ["Jane Doe", "1962-09-04", "Sep 4 1962", "2125550142"])
def test_value_without_a_field_is_served_only_as_a_locator(value: str) -> None:
    assert mask_value(None, value) == "[value withheld]"


def test_export_locator_without_a_field_is_served() -> None:
    locator = "ehr_export.json:patients[12].encounters[0].documents[1]"
    assert mask_value(None, locator) == locator
