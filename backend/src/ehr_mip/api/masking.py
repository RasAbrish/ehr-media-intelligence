"""PHI masking for audit and quarantine values served by the API (FR-6.4, docs/09 section 6).

The audit log keeps the raw values for traceability; the API never returns them for
identity fields. Names keep their first letters ("J*** D**"), ISO dates keep the
century and the day ("19**-**-14"), dates in any other shape keep only separators,
phones keep the last two digits, free text is withheld. Masking fails closed: a field
that is not listed below is withheld, and so is a value without a field unless it is a
source locator.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

NAME_FIELDS = frozenset({"name", "family_name", "given_names", "patient_name", "author"})
DATE_FIELDS = frozenset({"dob", "birth_date", "patient_dob"})
CONTACT_FIELDS = frozenset({"phone", "address", "email", "line", "city", "zip", "postal_code"})
TEXT_FIELDS = frozenset({"text", "content", "note"})
# Served as stored: clinical, administrative and locator fields without identity content.
SAFE_FIELDS = frozenset(
    {
        "collected_at",
        "date",
        "start",
        "end",
        "encounter_id",
        "flag",
        "gender",
        "mrn",
        "patient_mrn",
        "unit",
        "value",
        "loinc",
        "test_name",
        "ref_high",
        "ref_low",
        "report_id",
        "title",
    }
)
WITHHELD = "[value withheld]"
PREVIEW_CHARS = 200

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_DIGIT = re.compile(r"\d")
_ISO_DATE = re.compile(r"([12]\d)\d\d-(?:0[1-9]|1[0-2])-([0-3]\d)")
# "notes/note_028.txt", "ehr_export.json:patients[12].encounters[0]", "lab_results.csv:14"
_LOCATOR = re.compile(r"notes/[\w.-]+\.txt|[\w-]+\.(?:json|csv)(?::[\w.\[\]-]+)?")
_MIN_DIGITS_FOR_TAIL = 5


def mask_name(value: str) -> str:
    return _WORD.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), value)


def mask_date(value: str) -> str:
    """Century and day of an ISO date (1968-03-14 → 19**-**-14), otherwise only separators.

    Digit positions mean different parts in different formats ("Sep 4 1962", "09/04/62"),
    so no digit and no month word survives unless the shape is exactly ISO.
    """
    if iso := _ISO_DATE.fullmatch(value):
        return f"{iso[1]}**-**-{iso[2]}"
    return _DIGIT.sub("*", _WORD.sub("***", value))


def mask_contact(value: str) -> str:
    digits = [m.start() for m in _DIGIT.finditer(value)]
    keep = set(digits[-2:]) if len(digits) >= _MIN_DIGITS_FOR_TAIL else set()
    masked = "".join("*" if i in digits and i not in keep else ch for i, ch in enumerate(value))
    return _WORD.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), masked)


def mask_text(value: str) -> str:
    return f"[text withheld, {len(value)} characters]"


_MASKERS: tuple[tuple[frozenset[str], Callable[[str], str]], ...] = (
    (NAME_FIELDS, mask_name),
    (DATE_FIELDS, mask_date),
    (CONTACT_FIELDS, mask_contact),
    (TEXT_FIELDS, mask_text),
)


def mask_value(field: str | None, value: str | None) -> str | None:
    if not value:
        return value
    if field is None:
        return value if _LOCATOR.fullmatch(value) else WITHHELD
    key = field.lower()
    for fields, mask in _MASKERS:
        if key in fields:
            return mask(value)
    return value if key in SAFE_FIELDS else WITHHELD


def _mask_payload(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _mask_payload(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_payload(v, key) for v in value]
    if value is None or isinstance(value, bool):
        return value
    return mask_value(key, str(value)) if key else WITHHELD


def quarantine_preview(payload_json: str) -> str:
    """Masked, compact JSON of a quarantined record, at most 200 characters."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return "[unreadable payload]"
    text = json.dumps(_mask_payload(payload), ensure_ascii=False, separators=(", ", ": "))
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"
