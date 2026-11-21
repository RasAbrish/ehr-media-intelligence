"""Rule-based anomalies (docs/05-ALGORITHMS.md section 3.1).

These never depend on the model: they are computed from the bundle and every
high-severity one is guaranteed to appear in the final summary.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from itertools import pairwise

from ehr_mip.summarization.records import BundleView, LabValue
from ehr_mip.summarization.schemas import Anomaly, AnomalySeverity, EvidenceRef

MIN_TREND_POINTS = 3

# Critical rules by LOINC: value → is it critical?
_CRITICAL: dict[str, Callable[[LabValue], bool]] = {
    "2823-3": lambda lab: lab.value is not None and (lab.value > 6.0 or lab.value < 3.0),  # noqa: PLR2004
    "2951-2": lambda lab: lab.value is not None and (lab.value < 125 or lab.value > 155),  # noqa: PLR2004
    "2345-7": lambda lab: lab.value is not None and lab.value > 400,  # noqa: PLR2004
    "2524-7": lambda lab: lab.value is not None and lab.value > 4.0,  # noqa: PLR2004
    "10839-9": lambda lab: lab.value is not None and lab.high is not None and lab.value > lab.high,
    "718-7": lambda lab: lab.value is not None and lab.value < 7.0,  # noqa: PLR2004
}
_RANK = {"high": 0, "moderate": 1, "low": 2}


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:g}"


def describe(lab: LabValue) -> str:
    """``Potassium 6.3 mmol/L (HH, ref 3.5 to 5.1)``."""
    parts = " ".join(p for p in (lab.test_name, lab.value_text, lab.unit or "") if p)
    details = [lab.flag] if lab.flag and lab.flag != "N" else []
    if lab.low is not None and lab.high is not None:
        details.append(f"ref {_number(lab.low)} to {_number(lab.high)}")
    elif lab.high is not None:
        details.append(f"ref up to {_number(lab.high)}")
    elif lab.low is not None:
        details.append(f"ref at least {_number(lab.low)}")
    return f"{parts} ({', '.join(details)})" if details else parts


def _lab_severity(lab: LabValue) -> AnomalySeverity | None:
    critical = _CRITICAL.get(lab.loinc or "")
    if lab.flag in {"HH", "LL"} or (critical is not None and critical(lab)):
        return "high"
    if lab.flag in {"H", "L"}:
        return "moderate"
    return None


def _trend(labs: list[LabValue]) -> list[Anomaly]:
    found: list[Anomaly] = []
    series: dict[str, list[LabValue]] = {}
    for lab in labs:
        if lab.loinc and lab.value is not None and lab.when is not None:
            series.setdefault(lab.loinc, []).append(lab)
    for points in series.values():
        points.sort(key=lambda lab: lab.when or date.min)
        if len(points) < MIN_TREND_POINTS:
            continue
        values = [p.value for p in points if p.value is not None]
        last = points[-1]
        rising = all(a < b for a, b in pairwise(values))
        falling = all(a > b for a, b in pairwise(values))
        abnormal_high = last.high is not None and values[-1] > last.high
        abnormal_low = last.low is not None and values[-1] < last.low
        if (rising and abnormal_high) or (falling and abnormal_low):
            word = "Rising" if rising else "Falling"
            found.append(
                Anomaly(
                    description=(
                        f"{word} {last.test_name} over {len(points)} results "
                        f"({_number(values[0])} to {_number(values[-1])} {last.unit or ''})"
                    ).replace(" )", ")"),
                    severity="moderate",
                    source="rule",
                    evidence=[p.ref for p in points],
                )
            )
    return found


def detect_anomalies(view: BundleView, *, today: date) -> list[Anomaly]:
    """Every rule anomaly, highest severity first, newest first within a severity."""
    dated: list[tuple[Anomaly, date | None]] = []
    for lab in view.labs:
        severity = _lab_severity(lab)
        if severity:
            anomaly = Anomaly(
                description=describe(lab), severity=severity, source="rule", evidence=[lab.ref]
            )
            dated.append((anomaly, lab.when))
    dated += [(a, None) for a in _trend(view.labs)]

    patient = view.patient
    if patient.merged:
        dated.append(
            (
                Anomaly(
                    description=f"Record merged from {len(patient.mrns)} MRNs",
                    severity="low",
                    source="rule",
                    evidence=[],
                ),
                None,
            )
        )
    if patient.conflict:
        dated.append(
            (
                Anomaly(
                    description="MRN shared with another person; identity flagged for review",
                    severity="low",
                    source="rule",
                    evidence=[],
                ),
                None,
            )
        )
    for record in view.records:
        if record.when is None:
            continue
        problem = None
        if patient.birth_date is not None and record.when < patient.birth_date:
            problem = "is dated before the date of birth"
        elif record.when > today + timedelta(days=1):
            problem = "is dated in the future"
        if problem:
            anomaly = Anomaly(
                description=f"{record.title} {problem}",
                severity="low",
                source="rule",
                evidence=[EvidenceRef(resource_type=record.ref.resource_type,
                                      resource_id=record.ref.resource_id)],
            )  # fmt: skip
            dated.append((anomaly, record.when))

    dated.sort(key=lambda item: (_RANK[item[0].severity], -(item[1] or date.min).toordinal()))
    return [anomaly for anomaly, _ in dated]
