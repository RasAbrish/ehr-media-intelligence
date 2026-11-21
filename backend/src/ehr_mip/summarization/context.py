"""De-identified model context (docs/05-ALGORITHMS.md section 3.2, ADR-005).

The model sees age, sex and clinical text only. Identifiers are removed from the
structured fields *and* from free text, instruction-like spans are removed, and
all record text is XML-escaped inside ``<record>`` tags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape

from ehr_mip.summarization.records import BundleView, PatientInfo, SourceRecord
from ehr_mip.summarization.schemas import Anomaly

NOTE_CHAR_LIMIT = 1200
DEFAULT_BUDGET_TOKENS = 6000
INSTRUCTION_REMOVED = "[instruction-like text removed]"

_SECTION = re.compile(r"^(?P<name>[A-Z][A-Z /&-]*):", re.MULTILINE)
_INSTRUCTION_PATTERNS = [
    r"\bignore\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions?|prompts?|rules?)[^\n.]*\.?",
    r"\bdisregard\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)[^\n.]*\.?",
    # Role reassignment aimed at the model, not "you are now cleared to drive".
    r"\byou\s+are\s+now\s+(?:acting\s+as\s+|in\s+)?(?:an?\s+|the\s+)?(?:\w+\s+){0,3}?"
    r"(?:assistant|AI|model|chatbot|bot|system|LLM|language\s+model|persona|mode|DAN)\b[^\n.]*\.?",
    r"\b(?:new|system)\s+instructions?\s*:[^\n]*",
]
INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE)


@dataclass(frozen=True)
class Context:
    text: str
    included: list[str]
    age: int | None
    sex: str
    truncated: bool


def _dob_variants(dob: date) -> set[str]:
    month_name = dob.strftime("%B")
    month_abbr = dob.strftime("%b")
    return {
        dob.isoformat(),
        dob.strftime("%m/%d/%Y"),
        dob.strftime("%d/%m/%Y"),
        dob.strftime("%m/%d/%y"),
        dob.strftime("%Y%m%d"),
        dob.strftime("%Y/%m/%d"),
        f"{dob.day:02d}-{month_abbr}-{dob.year}",
        f"{dob.day}-{month_abbr}-{dob.year}",
        f"{month_name} {dob.day}, {dob.year}",
        f"{month_abbr} {dob.day} {dob.year}",
        f"{dob.month}/{dob.day}/{dob.year}",
    }


def identifier_scrubber(patient: PatientInfo) -> list[tuple[re.Pattern[str], str]]:
    """Patterns that remove this patient's identifiers from free text."""
    rules: list[tuple[re.Pattern[str], str]] = []
    names = {part for part in (patient.family, *patient.given) if part and len(part) >= 2}  # noqa: PLR2004
    for part in sorted(names, key=len, reverse=True):
        rules.append((re.compile(rf"\b{re.escape(part)}\b", re.IGNORECASE), "[patient]"))
    mrn_forms = set()
    for mrn in patient.mrns:
        mrn_forms.add(mrn)
        stripped = mrn.lstrip("0")
        if len(stripped) >= 4:  # noqa: PLR2004
            mrn_forms.add(stripped)
    for form in sorted(mrn_forms, key=len, reverse=True):
        rules.append((re.compile(rf"(?<!\d)0*{re.escape(form.lstrip('0'))}(?!\d)"), "[mrn]"))
    if patient.birth_date is not None:
        for form in sorted(_dob_variants(patient.birth_date), key=len, reverse=True):
            rules.append(
                (re.compile(rf"(?<![\w/]){re.escape(form)}(?![\w/])", re.IGNORECASE), "[dob]")
            )
    return rules


# Identifiers that can appear in free text for anyone (patient, family, staff).
_CONTACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[email]"),
    (re.compile(r"(?<![\d-])\d{3}-\d{2}-\d{4}(?![\d-])"), "[ssn]"),
    (
        re.compile(
            r"(?<![\d-])(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?![\d-])"
        ),
        "[phone]",
    ),
    (
        re.compile(
            r"\b\d{1,5}\s+(?:[NSEW]\.?\s+)?(?:[A-Z][a-z]+\s+|\d+(?:st|nd|rd|th)\s+){1,3}"
            r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|"
            r"Place|Pl|Terrace|Ter|Parkway|Pkwy|Circle|Cir)\b\.?"
            r"(?:,?\s+(?:Apt|Unit|Suite|#)\.?\s*\w+)?"
        ),
        "[address]",
    ),
]


def scrub(text: str, rules: list[tuple[re.Pattern[str], str]]) -> str:
    """Remove this patient's identifiers, contact details and instruction-like spans."""
    for pattern, replacement in [*rules, *_CONTACT_PATTERNS]:
        text = pattern.sub(replacement, text)
    return INSTRUCTION_RE.sub(INSTRUCTION_REMOVED, text)


def _sections(text: str) -> list[tuple[str, str]]:
    """Split text into (section name, section text) pieces; text before any header is ''."""
    matches = list(_SECTION.finditer(text))
    if not matches:
        return [("", text)]
    pieces = []
    if matches[0].start() > 0:
        pieces.append(("", text[: matches[0].start()]))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pieces.append((match["name"], text[match.start() : end]))
    return pieces


def _reorder(text: str, first: tuple[str, ...]) -> str:
    pieces = _sections(text)
    lead = [body for name, body in pieces if name in first]
    lead.sort(key=lambda body: next(i for i, f in enumerate(first) if body.startswith(f)))
    rest = [body for name, body in pieces if name not in first]
    return "\n".join(p.strip() for p in [*lead, *rest] if p.strip())


def _record_body(record: SourceRecord) -> str:
    if record.kind in {"imaging", "pathology"}:
        return _reorder(record.text, ("IMPRESSION", "DIAGNOSIS"))
    return _reorder(record.text, ("ASSESSMENT", "PLAN"))


def _attr(value: str) -> str:
    return escape(value, quote=True)


def _age(patient: PatientInfo, on: date | None) -> int | None:
    if patient.birth_date is None or on is None:
        return None
    born = patient.birth_date
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _date_attr(value: date | None) -> str:
    return value.isoformat() if value else "unknown"


def build_context(
    view: BundleView, anomalies: list[Anomaly], *, budget_tokens: int = DEFAULT_BUDGET_TOKENS
) -> Context:
    patient = view.patient
    rules = identifier_scrubber(patient)
    age = _age(patient, view.latest_date())
    age_attr = f' age="{age}"' if age is not None else ""
    header = f'<patient ref="P1"{age_attr} sex="{_attr(patient.gender)}" />'

    hint_lines = []
    lab_dates = {lab.ref.key: lab.when for lab in view.labs}
    for anomaly in anomalies:
        when = next((lab_dates.get(e.key) for e in anomaly.evidence if e.key in lab_dates), None)
        evidence = ", ".join(e.key for e in anomaly.evidence)
        parts = [f"- [{anomaly.severity}] {anomaly.description}"]
        if when:
            parts.append(when.isoformat())
        if evidence:
            parts.append(f" evidence={evidence}")
        hint_lines.append(_attr(scrub(" ".join(parts), rules)))
    hints = "<anomaly_hints>\n" + "".join(f"{line}\n" for line in hint_lines) + "</anomaly_hints>"

    blocks: list[str] = []
    included: list[str] = []
    used = len(header) + len(hints) + 40
    truncated = False
    ordered = sorted(view.records, key=lambda r: (r.when or date.min, r.ref.key), reverse=True)
    for record in ordered:
        if record.kind == "lab":
            items = "; ".join(f"{lab.test_name} {lab.value_text} {lab.flag or ''}".strip()
                              for lab in record.results)  # fmt: skip
            block = (
                f'<labs report="{record.ref.key}" date="{_date_attr(record.when)}">'
                f"{_attr(scrub(items, rules))}</labs>"
            )
        else:
            body = scrub(_record_body(record), rules)[:NOTE_CHAR_LIMIT]
            kind = record.kind if record.kind != "note" else record.subtype
            block = (
                f'<record id="{record.ref.key}" type="{kind}" date="{_date_attr(record.when)}" '
                f'title="{_attr(scrub(record.title, rules))}">{_attr(body)}</record>'
            )
        if blocks and (used + len(block)) / 4 > budget_tokens:
            truncated = True
            break
        blocks.append(block)
        included.append(record.ref.key)
        used += len(block) + 1

    records = "<records>\n" + "".join(f"{b}\n" for b in blocks) + "</records>"
    return Context(
        text=f"{header}\n{hints}\n{records}",
        included=included,
        age=age,
        sex=patient.gender,
        truncated=truncated,
    )
