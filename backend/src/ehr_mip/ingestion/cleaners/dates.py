"""Date normalization (docs/05-ALGORITHMS.md section 1.2).

US-origin data: ambiguous ``NN/NN/YYYY`` values are read as month/day and flagged
with a warning so every guess is visible (ADR-008). Naive times are local
``America/New_York`` wall-clock times.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from dateutil import parser as dateutil_parser

from ehr_mip.ingestion.audit import Cleaned, Note

NY = ZoneInfo("America/New_York")
DateKind = Literal["dob", "clinical"]
MAX_AGE_YEARS = 120
MAX_MONTH = 12

_SHAPES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "%Y/%m/%d"),
    (re.compile(r"^\d{8}$"), "%Y%m%d"),
    (re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$"), "%d-%b-%Y"),
    (re.compile(r"^[A-Za-z]{3} \d{1,2} \d{4}$"), "%b %d %Y"),
    (re.compile(r"^[A-Za-z]+ \d{1,2}, \d{4}$"), "%B %d, %Y"),
]
_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})$")
_NUMERIC_WITH_OCR = re.compile(r"[\dOo/\-.]+")
_DATETIME = re.compile(r"^(?P<date>.+?)[ T](?P<time>\d{1,2}:\d{2}(?::\d{2})?)$")


def today_local() -> date:
    """Today's date in the data's time zone."""
    return datetime.now(NY).date()


def _missing() -> Cleaned[None]:
    return Cleaned(None, (Note("date.missing", "info", "Date is missing."),))


def _invalid(raw: str) -> Cleaned[None]:
    return Cleaned(None, (Note("date.parse.invalid", "error", "Date could not be parsed.", raw),))


def _age_years(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _pivot_two_digit(yy: int, today: date) -> int:
    year = 2000 + yy
    return year - 100 if year > today.year else year


def _parse_shape(text: str, kind: DateKind, today: date) -> tuple[date | None, Note | None, bool]:
    """Return (date, note-for-reading-choice, matched-a-known-shape)."""
    slash = _SLASH.match(text)
    if slash:
        first, second, year_text = int(slash[1]), int(slash[2]), slash[3]
        year = int(year_text)
        if len(year_text) == 2:  # noqa: PLR2004
            year = _pivot_two_digit(year, today)
        if first > MAX_MONTH:
            day, month = first, second
            note = Note("date.parse.ddmm", "info", "Read as day/month because the first part > 12.")
        elif second > MAX_MONTH:
            month, day = first, second
            note = Note("date.parse.format", "info", "Normalized to ISO 8601.")
        else:
            month, day = first, second
            note = Note(
                "date.parse.us_ambiguous",
                "warning",
                "Ambiguous date read as US month/day.",
            )
        try:
            value = date(year, month, day)
        except ValueError:
            return None, None, True
        if kind == "dob" and len(year_text) == 2 and value > today:  # noqa: PLR2004
            value = value.replace(year=value.year - 100)
        return value, note, True

    for pattern, fmt in _SHAPES:
        if pattern.match(text):
            try:
                return datetime.strptime(text, fmt).date(), None, True  # noqa: DTZ007
            except ValueError:
                return None, None, True
    return None, None, False


_SENTINELS = (datetime(2001, 1, 1), datetime(2002, 2, 2))  # noqa: DTZ001 (date-only use)


def _fallback_parse(text: str) -> date | None:
    """dateutil for unusual formats, refusing partial dates.

    dateutil fills missing parts from its default, so parse twice with different
    defaults: if the results differ, the input lacked a day, month or year.
    """
    try:
        first, second = (dateutil_parser.parse(text, default=d) for d in _SENTINELS)
    except (ValueError, OverflowError):
        return None
    return first.date() if first == second else None


def _implausible(
    value: date, raw: str, kind: DateKind, dob: date | None, today: date
) -> Note | None:
    """A DOB in the future or over 120 years ago, or a clinical date before birth or ahead."""
    if kind == "dob":
        if value > today or _age_years(value, today) > MAX_AGE_YEARS:
            return Note("date.dob_implausible", "error", "Date of birth is not plausible.", raw)
        return None
    if (dob is not None and value < dob) or value > today + timedelta(days=1):
        return Note("date.clinical_implausible", "error", "Clinical date is not plausible.", raw)
    return None


def parse_date(
    raw: str | None,
    *,
    kind: DateKind = "clinical",
    dob: date | None = None,
    today: date | None = None,
) -> Cleaned[date | None]:
    """Parse a date in any supported format into a ``date`` with audit notes."""
    if raw is None or not raw.strip():
        return _missing()
    today = today or today_local()
    text = raw.strip()
    if _NUMERIC_WITH_OCR.fullmatch(text) and re.search(r"\d", text):
        text = text.replace("O", "0").replace("o", "0")

    value, choice, matched = _parse_shape(text, kind, today)
    if matched and value is None:
        return _invalid(raw)
    if not matched:
        value = _fallback_parse(text)
        if value is None:
            return _invalid(raw)
        choice = Note("date.parse.fallback", "info", "Parsed with the fallback date parser.")
    assert value is not None  # noqa: S101 (narrowing for mypy)

    implausible = _implausible(value, raw, kind, dob, today)
    if implausible is not None:
        return Cleaned(None, (implausible,))

    iso = value.isoformat()
    if choice is None:
        if raw == iso:
            return Cleaned(value)
        choice = Note("date.parse.format", "info", "Normalized to ISO 8601.")
    return Cleaned(value, (Note(choice.rule, choice.severity, choice.message, raw, iso),))


def parse_datetime(
    raw: str | None,
    *,
    dob: date | None = None,
    today: date | None = None,
) -> Cleaned[datetime | date | None]:
    """Parse a date with optional time. Date-only input keeps date precision."""
    if raw is None or not raw.strip():
        return _missing()
    match = _DATETIME.match(raw.strip())
    if match is None:
        only_date = parse_date(raw, kind="clinical", dob=dob, today=today)
        return Cleaned(only_date.value, only_date.notes)

    date_part = parse_date(match["date"], kind="clinical", dob=dob, today=today)
    if date_part.value is None:
        relabeled = tuple(
            Note(n.rule, n.severity, n.message, raw, n.after) for n in date_part.notes
        )
        return Cleaned(None, relabeled)
    hour, minute, second = (int(part) for part in (*match["time"].split(":"), "0")[:3])
    try:
        clock = time(hour, minute, second)
    except ValueError:
        return _invalid(raw)

    value = datetime.combine(date_part.value, clock, tzinfo=NY)
    canonical = value.strftime("%Y-%m-%dT%H:%M") + (f":{clock.second:02d}" if clock.second else "")
    if raw == canonical:
        return Cleaned(value)
    reading = date_part.notes[0] if date_part.notes else None
    rule, severity, message = (
        (reading.rule, reading.severity, reading.message)
        if reading is not None and reading.rule != "date.parse.format"
        else ("date.parse.format", "info", "Normalized to ISO 8601.")
    )
    return Cleaned(value, (Note(rule, severity, message, raw, canonical),))
