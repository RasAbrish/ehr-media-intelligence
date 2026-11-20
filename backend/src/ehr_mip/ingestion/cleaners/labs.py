"""Lab value parsing and flag recomputation (docs/05 section 1.3)."""

from __future__ import annotations

import re
from typing import get_args

from ehr_mip.ingestion.audit import Cleaned, Note
from ehr_mip.ingestion.models import LabFlag

_FLAGS: frozenset[str] = frozenset(get_args(LabFlag))
_VALUE = re.compile(
    r"(?P<op><=|>=|<|>)?\s*(?P<sign>-)?(?P<num>[0-9lIO][0-9lIO.,]*)\s*(?P<flag>LL|HH|L|H|N)?"
)

# Critical limits by LOINC: (critical low, critical high), inclusive.
CRITICAL: dict[str, tuple[float | None, float | None]] = {
    "2823-3": (2.5, 6.0),  # potassium
    "2951-2": (120.0, 160.0),  # sodium
    "2345-7": (40.0, 500.0),  # glucose
    "2524-7": (None, 4.0),  # lactate
    "718-7": (7.0, None),  # hemoglobin
    "777-3": (20.0, None),  # platelets
    "6690-2": (1.0, 30.0),  # WBC
}


def parse_number(raw: str | None) -> float | None:
    """Parse a plain number such as a reference limit; blank or bad input gives None."""
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def parse_lab_value(raw: str | None) -> Cleaned[float | None]:
    """Parse ``5.9``, ``<0.01``, ``>200``, ``5.9 H`` and OCR ``5.l`` into a number."""
    if raw is None or not raw.strip():
        return Cleaned(None, (Note("lab.value_parse", "warning", "Lab value is missing.", raw),))
    match = _VALUE.fullmatch(raw.strip())
    if match is None:
        note = Note("lab.value_parse", "warning", "Lab value is not numeric.", raw)
        return Cleaned(None, (note,))
    number_text = match["num"]
    repaired = number_text.replace("l", "1").replace("I", "1").replace("O", "0").replace(",", "")
    try:
        value = -float(repaired) if match["sign"] else float(repaired)
    except ValueError:
        note = Note("lab.value_parse", "warning", "Lab value is not numeric.", raw)
        return Cleaned(None, (note,))
    reasons = []
    if match["op"]:
        reasons.append(f"operator {match['op']}")
    if match["flag"]:
        reasons.append("trailing flag")
    if repaired != number_text:
        reasons.append("OCR characters")
    if raw != raw.strip():
        reasons.append("whitespace")
    if not reasons:
        return Cleaned(value)
    note = Note(
        "lab.value_parse",
        "info",
        "Parsed lab value: " + ", ".join(reasons) + ".",
        raw,
        f"{value:g}",
    )
    return Cleaned(value, (note,))


def _direction(flag: str | None) -> str | None:
    if flag in {"H", "HH"}:
        return "H"
    if flag in {"L", "LL"}:
        return "L"
    if flag == "N":
        return "N"
    return None


def recompute_flag(
    value: float | None,
    low: float | None,
    high: float | None,
    loinc: str | None,
    source_flag: str | None,
) -> Cleaned[LabFlag | None]:
    """Recompute the flag from the reference range and the critical table."""
    source = (source_flag or "").strip().upper()
    source_value: LabFlag | None = source if source in _FLAGS else None  # type: ignore[assignment]
    if value is None or (low is None and high is None):
        return Cleaned(source_value)

    direction = "H" if high is not None and value > high else "L"
    if direction == "L" and (low is None or value >= low):
        direction = "N"
    computed: LabFlag = direction  # type: ignore[assignment]
    critical_low, critical_high = CRITICAL.get(loinc or "", (None, None))
    if direction == "H" and critical_high is not None and value >= critical_high:
        computed = "HH"
    elif direction == "L" and critical_low is not None and value <= critical_low:
        computed = "LL"

    source_direction = _direction(source_value)
    if source_direction is None:
        if direction == "N":
            return Cleaned("N")
        note = Note(
            "lab.flag_recomputed",
            "warning",
            "Abnormal value had no flag; flag computed from the reference range.",
            source,
            computed,
        )
        return Cleaned(computed, (note,))
    if source_direction != direction:
        note = Note(
            "lab.flag_recomputed",
            "warning",
            "Source flag disagrees with the reference range; flag recomputed.",
            source,
            computed,
        )
        return Cleaned(computed, (note,))
    if computed != source_value:
        note = Note(
            "lab.flag_critical",
            "info",
            "Flag adjusted by the critical value table.",
            source,
            computed,
        )
        return Cleaned(computed, (note,))
    return Cleaned(computed)
